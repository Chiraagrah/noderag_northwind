# Sentence-transformer embedding utility: embeds node text fields into unit-normalized vectors
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))


class NodeEmbedder:
    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer
        import config
        name = model_name or config.EMBED_MODEL
        self._model = SentenceTransformer(name)

    def embed_text(self, text: str) -> np.ndarray:
        vec = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return vec.astype(np.float32)

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 64,
        show_progress: bool = True,
    ) -> np.ndarray:
        vecs = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vecs.astype(np.float32)

    def embed_graph(self, G) -> dict[str, np.ndarray]:
        import networkx as nx

        node_ids, texts = [], []
        for nid, data in G.nodes(data=True):
            nd = data.get("data")
            if nd and nd.text:
                node_ids.append(nid)
                texts.append(nd.text)

        if not texts:
            return {}

        vecs = self.embed_batch(texts, show_progress=True)
        return dict(zip(node_ids, vecs))


if __name__ == "__main__":
    import json
    import networkx as nx
    from rich.console import Console
    from graph.node_types import node_from_dict

    console = Console()
    root = Path(__file__).parent.parent

    console.print("[cyan]Loading graph...[/cyan]")
    with open(root / "data" / "northwind_graph.json", encoding="utf-8") as f:
        data = json.load(f)
    for n in data["nodes"]:
        if "data" in n and isinstance(n["data"], dict):
            n["data"] = node_from_dict(n["data"])
    G = nx.node_link_graph(data, directed=True, multigraph=True)
    console.print(f"  Loaded {G.number_of_nodes()} nodes.")

    console.print("[cyan]Embedding nodes...[/cyan]")
    embedder = NodeEmbedder()
    embeddings = embedder.embed_graph(G)
    console.print(
        f"  Embedded {len(embeddings)} nodes, "
        f"dim={next(iter(embeddings.values())).shape[0]}."
    )
