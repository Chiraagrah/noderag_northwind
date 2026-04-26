# Shallow Personalized PageRank: biases graph walks toward query-relevant seed nodes
from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class ShallowPPR:
    def __init__(self, alpha: float | None = None, max_iter: int | None = None):
        self.alpha    = alpha    if alpha    is not None else config.PPR_ALPHA
        self.max_iter = max_iter if max_iter is not None else config.PPR_MAX_ITER

    def run(
        self,
        G: nx.MultiDiGraph,
        seed_node_ids: list[str],
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        # keep only seeds that are actually in the graph
        seeds = [s for s in seed_node_ids if s in G]
        if not seeds:
            return []

        G_un = G.to_undirected()

        # personalization: uniform weight over seed set
        weight = 1.0 / len(seeds)
        personalization = {n: (weight if n in seeds else 0.0) for n in G_un.nodes()}

        ppr_scores: dict[str, float] = nx.pagerank(
            G_un,
            alpha=self.alpha,
            personalization=personalization,
            max_iter=self.max_iter,
            weight="weight",
        )

        # collect 2-hop neighbourhood of every seed
        two_hop: set[str] = set()
        for seed in seeds:
            lengths = nx.single_source_shortest_path_length(G_un, seed, cutoff=2)
            two_hop.update(lengths.keys())

        # filter to 2-hop, sort descending, return top_k
        filtered = [
            (nid, ppr_scores[nid])
            for nid in two_hop
            if nid in ppr_scores
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)
        return filtered[:top_k]

    def explain(
        self,
        G: nx.MultiDiGraph,
        node_id: str,
        seed_ids: list[str],
    ) -> str:
        G_un = G.to_undirected()
        best_path: list[str] | None = None

        for seed in seed_ids:
            if seed not in G_un or node_id not in G_un:
                continue
            try:
                path = nx.shortest_path(G_un, seed, node_id)
                if len(path) <= 3 and (best_path is None or len(path) < len(best_path)):
                    best_path = path
            except nx.NetworkXNoPath:
                continue

        if best_path is None or len(best_path) < 2:
            return f"Retrieved via direct match: {node_id}"

        # build hop-by-hop label string
        parts: list[str] = [best_path[0]]
        for i in range(len(best_path) - 1):
            src, dst = best_path[i], best_path[i + 1]
            # pick the first edge relation label available
            edge_data = G_un.get_edge_data(src, dst) or {}
            # undirected MultiGraph: edge_data is {0: {...}, 1: {...}, ...}
            relation = "?"
            if isinstance(edge_data, dict):
                first = next(iter(edge_data.values()), {})
                relation = first.get("relation", "RELATED_TO")
            parts.append(f"--[{relation}]-->")
            parts.append(dst)

        return "Retrieved via: " + " ".join(parts)
