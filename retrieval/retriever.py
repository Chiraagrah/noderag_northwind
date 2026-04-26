# Unified retrieval pipeline: vector search -> seed nodes -> Shallow PPR -> K-core boost
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
    Full NodeRAG retrieval pipeline:
      1. Embed query
      2. Vector search  -> seed nodes (N1-N6 only)
      3. Shallow PPR    -> expanded neighbourhood
      4. K-core boost   -> re-rank by structural importance
      5. Assemble context window
    """

    def __init__(self, G, index, embedder, ppr, kcore):
        self.G       = G
        self.index   = index
        self.embedder = embedder
        self.ppr     = ppr
        self.kcore   = kcore

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        k = top_k or config.TOP_K_RETRIEVAL

        # 1. embed query
        qvec = self.embedder.embed_text(query)

        # 2. vector search — seed from N1-N6 only
        seed_hits = self.index.search(qvec, top_k=k, filter_types=_SEED_TYPES)
        seed_ids  = [h["node_id"] for h in seed_hits]
        seed_nodes_out = [
            {"node_id": h["node_id"], "score": h["score"],
             "node_type": h["node"].node_type if h["node"] else "?",
             "text": h["node"].text[:120] if h["node"] else ""}
            for h in seed_hits
        ]

        # 3. Shallow PPR from seed set
        ppr_results = self.ppr.run(self.G, seed_ids, top_k=k * 3)

        if not ppr_results:
            # fallback: use seed nodes directly
            ppr_results = [(h["node_id"], h["score"]) for h in seed_hits]

        # 4. K-core boost
        core_numbers  = self.kcore.get_core_numbers(self.G)
        boosted       = self.kcore.boost_scores(ppr_results, core_numbers)[:k]

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
        retrieval_path = [
            self.ppr.explain(self.G, nid, seed_ids)
            for nid, _ in boosted[:5]
        ]

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
    from retrieval.ppr import ShallowPPR
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
    ppr       = ShallowPPR()
    kcore     = KCoreRanker()
    retriever = NodeRAGRetriever(G, index, embedder, ppr, kcore)

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
        ret_tbl = Table(title="Retrieved Nodes (PPR + K-core boosted)", show_lines=True)
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
