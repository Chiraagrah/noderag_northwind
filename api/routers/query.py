"""Query endpoint — SSE stream of retrieval pipeline events (GNN-based)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.graph_cache import get_embedder, get_graph, get_index
from api.models import GraphNodeDTO, QueryRequest

router = APIRouter(prefix="/api/query")

_SEED_TYPES = [
    "text_chunk", "entity", "semantic_unit",
    "relationship", "attribute", "high_level_insight",
]


def _node_to_dto_dict(node_id: str, G) -> dict:
    nd = G.nodes.get(node_id, {}).get("data") if node_id in G else None
    if nd is None:
        return {"node_id": node_id, "node_type": "?", "label": node_id[:60],
                "text": "", "table_name": None, "attributes": {}, "core_number": None}
    raw_label = (nd.text or "").replace("\n", " ")[:60]
    return GraphNodeDTO(
        node_id     = node_id,
        node_type   = nd.node_type,
        label       = raw_label,
        text        = (nd.text or "")[:200],
        table_name  = getattr(nd, "table_name", None),
        attributes  = nd.attributes if nd.node_type == "entity" else {},
        core_number = nd.core_number if nd.node_type == "community" else None,
    ).model_dump()


def _sse(event_type: str, data: dict) -> str:
    payload = json.dumps({"event_type": event_type, "data": data})
    return f"data: {payload}\n\n"


@router.post("/")
async def run_query(req: QueryRequest):

    async def generate():
        G        = get_graph()
        index    = get_index()
        embedder = get_embedder()
        k        = req.top_k

        try:
            # 1. Announce embedding
            yield _sse("seed", {"status": "embedding", "question": req.question})
            await asyncio.sleep(0.3)

            # 2. Embed + FAISS seed search (sentence-transformer space, query-compatible)
            qvec      = embedder.embed_text(req.question)
            seed_hits = index.search(qvec, top_k=k, filter_types=_SEED_TYPES)
            seed_ids  = [h["node_id"] for h in seed_hits]
            seed_dtos = [_node_to_dto_dict(h["node_id"], G) for h in seed_hits[:5]]
            yield _sse("seed", {"nodes": seed_dtos})
            await asyncio.sleep(0.3)

            # 3. GNN neighbourhood expansion (topology-aware; falls back to PPR)
            from retrieval.gnn_expand import GNNExpander
            from retrieval.ppr import ShallowPPR
            import config as _cfg
            gnn_exp = GNNExpander()
            ppr     = ShallowPPR()
            # Always run PPR for discriminative ranking scores
            ppr_scores_map = dict(ppr.run(G, seed_ids, top_k=k * 5))
            if gnn_exp.is_useful():
                # GNN discovers topology-adjacent candidate nodes
                gnn_exp.load()
                gnn_candidates = gnn_exp.expand(
                    seed_ids,
                    top_k             = k * 3,
                    neighbors_per_seed= _cfg.GNN_NEIGHBORS_PER_SEED,
                    rounds            = 2,
                )
                # Score by PPR (discriminative) rather than flat GNN cosine sims
                expanded = [
                    (nid, ppr_scores_map.get(nid, score * 0.001))
                    for nid, score in gnn_candidates
                ]
                if not expanded:
                    expanded = [(h["node_id"], h["score"]) for h in seed_hits]
            else:
                expanded = ppr.run(G, seed_ids, top_k=k * 3)
                if not expanded:
                    expanded = [(h["node_id"], h["score"]) for h in seed_hits]
            # Ensure FAISS seeds are in the expanded set with their semantic scores.
            # Semantic summary nodes (su_*) have high FAISS relevance but low PPR due
            # to few edges; preserving their FAISS scores makes augment_with_paths use
            # them as high-weight endpoints for bridge-node pair scoring.
            seed_faiss = {h["node_id"]: h["score"] for h in seed_hits}
            exp_map = dict(expanded)
            for nid, faiss_score in seed_faiss.items():
                if nid not in exp_map or exp_map[nid] < faiss_score:
                    exp_map[nid] = faiss_score
            expanded = sorted(exp_map.items(), key=lambda x: -x[1])
            # Bridge-node augmentation with FAISS+PPR scores driving pair scoring
            expanded   = gnn_exp.augment_with_paths(G, expanded, seed_ids, max_pair_probes=20, max_path_len=8)
            exp_scores = {nid: score for nid, score in expanded}
            exp_dtos   = [_node_to_dto_dict(nid, G) for nid, _ in expanded[:10]]
            yield _sse("ppr", {"nodes": exp_dtos, "scores": exp_scores})
            await asyncio.sleep(0.3)

            # 4. K-core boost
            from retrieval.kcore import KCoreRanker
            kcore        = KCoreRanker()
            core_numbers = kcore.get_core_numbers(G)
            boosted      = kcore.boost_scores(expanded, core_numbers)[:k]
            boosts       = {
                nid: round(bs - exp_scores.get(nid, bs), 6)
                for nid, bs in boosted
            }
            kcore_dtos = [_node_to_dto_dict(nid, G) for nid, _ in boosted]
            yield _sse("kcore", {"nodes": kcore_dtos, "boosts": boosts})
            await asyncio.sleep(0.3)

            # 5. Assemble context
            from retrieval.retriever import NodeRAGRetriever
            node_objs = [
                G.nodes[nid].get("data")
                for nid, _ in boosted
                if nid in G and G.nodes[nid].get("data")
            ]
            retriever    = NodeRAGRetriever(G, index, embedder, kcore)
            context_text = retriever._assemble_context(node_objs)
            node_ids     = [nid for nid, _ in boosted]
            yield _sse("context", {
                "node_count": len(node_ids),
                "node_ids":   node_ids,
                "char_count": len(context_text),
            })
            await asyncio.sleep(0.3)

            # 6. LLM answer (synchronous — run in thread pool)
            from llm.answerer import NodeRAGAnswerer
            answerer       = NodeRAGAnswerer()
            retrieval_path = [
                f"#{i+1} [{G.nodes[nid].get('data').node_type if nid in G and G.nodes[nid].get('data') else '?'}] "
                f"{nid}  score={score:.4f}  k-core={core_numbers.get(nid, 0)}"
                for i, (nid, score) in enumerate(boosted[:5])
            ]

            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: answerer.answer(req.question, context_text, retrieval_path),
            )
            yield _sse("answer", {
                "answer":               result.answer,
                "reasoning_steps":      result.reasoning_steps,
                "cited_nodes":          result.cited_nodes,
                "confidence":           result.confidence,
                "suggested_follow_ups": result.suggested_follow_ups,
            })

        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream")
