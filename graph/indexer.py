# FAISS / in-memory vector index: stores and searches node embeddings by cosine similarity
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))


class NodeIndex:
    """In-memory FAISS index over node embeddings, with metadata lookup."""

    def __init__(self):
        self.index = None
        self.node_ids: list[str] = []
        self.node_data: dict = {}

    # ── build / search ────────────────────────────────────────────────────────

    def build(self, embeddings: dict[str, np.ndarray], node_data: dict) -> None:
        import faiss

        self.node_ids = list(embeddings.keys())
        self.node_data = node_data

        dim = next(iter(embeddings.values())).shape[0]
        matrix = np.stack([embeddings[nid] for nid in self.node_ids]).astype(np.float32)

        self.index = faiss.IndexFlatIP(dim)   # inner product == cosine on unit vecs
        self.index.add(matrix)

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
        filter_types: list[str] | None = None,
    ) -> list[dict]:
        if self.index is None:
            raise RuntimeError("Index not built — call build() or load() first.")

        # over-fetch so we have room to filter by type
        fetch_k = top_k * 5 if filter_types else top_k
        fetch_k = min(fetch_k, len(self.node_ids))

        q = query_vec.reshape(1, -1).astype(np.float32)
        scores, indices = self.index.search(q, fetch_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            nid  = self.node_ids[idx]
            node = self.node_data.get(nid)
            if filter_types and (node is None or node.node_type not in filter_types):
                continue
            results.append({"node_id": nid, "score": float(score), "node": node})
            if len(results) >= top_k:
                break

        return results

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        import faiss

        base = Path(path)
        faiss.write_index(self.index, str(base) + ".faiss")

        meta = {
            "node_ids":  self.node_ids,
            "node_data": {
                nid: nd.model_dump() if hasattr(nd, "model_dump") else nd
                for nid, nd in self.node_data.items()
            },
        }
        with open(str(base) + ".json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

    def load(self, path: str) -> None:
        import faiss
        from graph.node_types import node_from_dict

        base = Path(path)
        self.index = faiss.read_index(str(base) + ".faiss")

        with open(str(base) + ".json", encoding="utf-8") as f:
            meta = json.load(f)

        self.node_ids = meta["node_ids"]
        self.node_data = {
            nid: node_from_dict(d) if isinstance(d, dict) else d
            for nid, d in meta["node_data"].items()
        }


# ── __main__ ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import time

    import networkx as nx
    from rich.console import Console
    from rich.table import Table

    from graph.embedder import NodeEmbedder
    from graph.node_types import node_from_dict

    console = Console()
    root = Path(__file__).parent.parent

    # 1. Load graph
    console.print("[cyan]Loading graph from disk...[/cyan]")
    with open(root / "data" / "northwind_graph.json", encoding="utf-8") as f:
        raw = json.load(f)
    for n in raw["nodes"]:
        if "data" in n and isinstance(n["data"], dict):
            n["data"] = node_from_dict(n["data"])
    G = nx.node_link_graph(raw, directed=True, multigraph=True)
    console.print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges loaded.")

    # 2. Embed
    console.print("[cyan]Embedding all nodes...[/cyan]")
    t0 = time.time()
    embedder = NodeEmbedder()
    embeddings = embedder.embed_graph(G)
    elapsed = time.time() - t0
    dim = next(iter(embeddings.values())).shape[0]
    console.print(
        f"  Embedded {len(embeddings)} nodes  |  dim={dim}  |  "
        f"time={elapsed:.1f}s"
    )

    # 3. Build index and node_data dict
    node_data = {
        nid: G.nodes[nid]["data"]
        for nid in embeddings
        if G.nodes[nid].get("data") is not None
    }

    console.print("[cyan]Building FAISS index...[/cyan]")
    idx = NodeIndex()
    idx.build(embeddings, node_data)

    index_base = str(root / "data" / "northwind_index")
    idx.save(index_base)
    console.print(f"  Saved to {index_base}.faiss + .json")

    # 4. Sample query
    query = "Which products are discontinued?"
    console.print(f"\n[bold]Sample query:[/bold] {query}")
    qvec = embedder.embed_text(query)
    hits = idx.search(qvec, top_k=5)

    # 5. Rich table
    tbl = Table(title=f'Top 5 results for: "{query}"', show_lines=True)
    tbl.add_column("Rank",      justify="right", style="dim")
    tbl.add_column("node_type", style="cyan",    no_wrap=True)
    tbl.add_column("score",     justify="right", style="green")
    tbl.add_column("text (truncated to 80 chars)", style="white")

    for i, hit in enumerate(hits, 1):
        node = hit["node"]
        tbl.add_row(
            str(i),
            node.node_type if node else "?",
            f"{hit['score']:.4f}",
            (node.text[:80] + "...") if node and len(node.text) > 80 else (node.text if node else ""),
        )
    console.print(tbl)
