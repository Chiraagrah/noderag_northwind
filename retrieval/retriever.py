# Retrieval pipeline: sentence-transformer FAISS seed → GNN neighbourhood expansion → K-core boost
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import networkx as nx
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from graph.node_types import AnyNode


# ── result model ─────────────────────────────────────────────────────────────

class RetrievalResult(BaseModel):
    query:           str
    seed_nodes:      list[dict[str, Any]]
    retrieved_nodes: list[dict[str, Any]]
    context_text:    str
    retrieval_path:  list[str]


# ── node types eligible as vector-search seeds (skip community nodes) ─────────
_SEED_TYPES = [
    "text_chunk", "entity", "semantic_unit",
    "relationship", "attribute", "high_level_insight",
]

# section headings for context assembly
_SECTION_ORDER = [
    ("text_chunk",        "## Schema Context"),
    ("attribute",         "## Column Metadata"),
    ("entity",            "## Entities"),
    ("semantic_unit",     "## Semantic Groups"),
    ("relationship",      "## Relationships"),
    ("high_level_insight","## Business Insights"),
    ("community",         "## Structural Communities"),
]


class NodeRAGRetriever:
    """
    NodeRAG retrieval pipeline:
      1. Embed query (sentence transformer)
      2. FAISS seed search (sentence-transformer embeddings — same space as query)
      3. GNN neighbourhood expansion (topology-aware, replaces ShallowPPR)
         Falls back to PPR if GNN embeddings file is not present.
      4. K-core boost  ->  re-rank by structural importance
      5. Assemble context window
    """

    def __init__(self, G, index, embedder, kcore):
        self.G        = G
        self.index    = index
        self.embedder = embedder
        self.kcore    = kcore

        # Load GNN expander if available and non-degenerate, otherwise fall back to PPR
        from retrieval.gnn_expand import GNNExpander
        self._gnn = GNNExpander()
        if self._gnn.is_useful():
            self._gnn.load()
            self._use_gnn = True
        else:
            self._use_gnn = False

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        k = top_k or config.TOP_K_RETRIEVAL

        # 1. embed query with sentence transformer
        qvec = self.embedder.embed_text(query)

        # 2. FAISS seed search — sentence-transformer space, compatible with query
        seed_hits = self.index.search(qvec, top_k=k, filter_types=_SEED_TYPES)
        seed_ids  = [h["node_id"] for h in seed_hits]
        seed_nodes_out = [
            {"node_id": h["node_id"], "score": h["score"],
             "node_type": h["node"].node_type if h["node"] else "?",
             "text": h["node"].text[:120] if h["node"] else ""}
            for h in seed_hits
        ]

        # 3. Neighbourhood expansion
        from retrieval.ppr import ShallowPPR
        ppr = ShallowPPR()
        # Always run PPR for discriminative ranking; GNN is used for candidate discovery only
        ppr_scores_map = dict(ppr.run(self.G, seed_ids, top_k=k * 5))
        if self._use_gnn:
            # GNN discovers topology-adjacent candidates
            gnn_candidates = self._gnn.expand(
                seed_ids,
                top_k             = k * 3,
                neighbors_per_seed= config.GNN_NEIGHBORS_PER_SEED,
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
            expanded = ppr.run(self.G, seed_ids, top_k=k * 3)
            if not expanded:
                expanded = [(h["node_id"], h["score"]) for h in seed_hits]
        # Ensure FAISS seeds appear in the expanded set with their semantic scores.
        # Semantic summary nodes have high FAISS relevance but low PPR (few edges);
        # this guarantees they act as high-weight endpoints in augment_with_paths.
        seed_faiss = {h["node_id"]: h["score"] for h in seed_hits}
        exp_map = dict(expanded)
        for nid, faiss_score in seed_faiss.items():
            if nid not in exp_map or exp_map[nid] < faiss_score:
                exp_map[nid] = faiss_score
        expanded = sorted(exp_map.items(), key=lambda x: -x[1])
        # Bridge-node augmentation with FAISS+PPR scores driving pair scoring
        expanded = self._gnn.augment_with_paths(self.G, expanded, seed_ids, max_pair_probes=20, max_path_len=8)

        # 4. K-core boost
        core_numbers = self.kcore.get_core_numbers(self.G)
        boosted      = self.kcore.boost_scores(expanded, core_numbers)[:k]

        # 5. Build retrieved_nodes list
        retrieved_nodes_out: list[dict] = []
        for nid, score in boosted:
            nd = self.G.nodes[nid].get("data") if nid in self.G else None
            retrieved_nodes_out.append({
                "node_id":   nid,
                "score":     round(score, 6),
                "node_type": nd.node_type if nd else "?",
                "text":      nd.text[:120] if nd else "",
            })

        # 6. Assemble context
        node_objs = [
            self.G.nodes[nid].get("data")
            for nid, _ in boosted
            if nid in self.G and self.G.nodes[nid].get("data")
        ]
        context_text = self._assemble_context(node_objs)

        # 7. Retrieval path (top 5)
        retrieval_path = []
        method = "GNN" if self._use_gnn else "PPR"
        for rank, (nid, score) in enumerate(boosted[:5], 1):
            nd    = self.G.nodes[nid].get("data") if nid in self.G else None
            ntype = nd.node_type if nd else "?"
            kval  = core_numbers.get(nid, 0)
            if self._use_gnn:
                detail = self._gnn.explain(nid, seed_ids)
            else:
                detail = f"[PPR] {nid}"
            retrieval_path.append(
                f"#{rank} [{ntype}] score={score:.4f} k-core={kval}  {detail}"
            )

        return RetrievalResult(
            query=query,
            seed_nodes=seed_nodes_out,
            retrieved_nodes=retrieved_nodes_out,
            context_text=context_text,
            retrieval_path=retrieval_path,
        )

    def _assemble_context(self, nodes: list[AnyNode]) -> str:
        # group by node_type
        buckets: dict[str, list[AnyNode]] = {nt: [] for nt, _ in _SECTION_ORDER}
        for nd in nodes:
            if nd.node_type in buckets:
                buckets[nd.node_type].append(nd)

        MAX_WORDS   = 3000
        word_budget = MAX_WORDS
        sections: list[str] = []

        for node_type, heading in _SECTION_ORDER:
            group = buckets[node_type]
            if not group:
                continue
            lines: list[str] = [heading]
            for nd in group:
                text = nd.text
                words = text.split()
                if len(words) > 120:
                    text = " ".join(words[:120]) + " ...[truncated]"
                    words = words[:120]
                if word_budget <= 0:
                    lines.append("...[context limit reached]")
                    break
                lines.append(f"- [{nd.node_id}] {text}")
                word_budget -= len(words)
            sections.append("\n".join(lines))

        return "\n\n".join(sections)


# ── __main__ ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import networkx as nx
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from graph.embedder import NodeEmbedder
    from graph.indexer import NodeIndex
    from graph.node_types import node_from_dict
    from retrieval.kcore import KCoreRanker

    console = Console()
    root = Path(__file__).parent.parent

    # ── load graph ────────────────────────────────────────────────────────────
    console.print("[cyan]Loading graph...[/cyan]")
    with open(root / "data" / "northwind_graph.json", encoding="utf-8") as f:
        raw = json.load(f)
    for n in raw["nodes"]:
        if "data" in n and isinstance(n["data"], dict):
            n["data"] = node_from_dict(n["data"])
    G = nx.node_link_graph(raw, directed=True, multigraph=True)
    console.print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # ── load index ────────────────────────────────────────────────────────────
    console.print("[cyan]Loading FAISS index...[/cyan]")
    index = NodeIndex()
    index.load(str(root / "data" / "northwind_index"))
    console.print(f"  {len(index.node_ids)} vectors indexed")

    # ── build pipeline ────────────────────────────────────────────────────────
    embedder  = NodeEmbedder()
    kcore     = KCoreRanker()
    retriever = NodeRAGRetriever(G, index, embedder, kcore)

    # ── three sample queries ──────────────────────────────────────────────────
    queries = [
        "Which suppliers provide beverages and what products do they offer?",
        "Who are the top customers and what did they order?",
        "Which employees handle the most freight-heavy shipments to Germany?",
    ]

    for query in queries:
        console.print(f"\n[bold yellow]Query:[/bold yellow] {query}")
        result = retriever.retrieve(query, top_k=config.TOP_K_RETRIEVAL)

        # seed nodes table
        seed_tbl = Table(title="Seed Nodes (vector search)", show_lines=True)
        seed_tbl.add_column("node_id",    style="dim",  no_wrap=True)
        seed_tbl.add_column("node_type",  style="cyan", no_wrap=True)
        seed_tbl.add_column("score",      justify="right", style="green")
        seed_tbl.add_column("text",       style="white")
        for s in result.seed_nodes[:5]:
            seed_tbl.add_row(
                s["node_id"][:40],
                s["node_type"],
                f"{s['score']:.4f}",
                s["text"][:70],
            )
        console.print(seed_tbl)

        # retrieved nodes table
        ret_tbl = Table(title="Retrieved Nodes (GNN + K-core boosted)", show_lines=True)
        ret_tbl.add_column("rank",       justify="right", style="dim")
        ret_tbl.add_column("node_type",  style="cyan",    no_wrap=True)
        ret_tbl.add_column("score",      justify="right", style="green")
        ret_tbl.add_column("text",       style="white")
        for i, r in enumerate(result.retrieved_nodes, 1):
            ret_tbl.add_row(
                str(i),
                r["node_type"],
                f"{r['score']:.4f}",
                r["text"][:70],
            )
        console.print(ret_tbl)

        # retrieval path
        console.print(Panel(
            "\n".join(result.retrieval_path),
            title="Retrieval Path (top 5 nodes)",
            border_style="dim",
        ))
