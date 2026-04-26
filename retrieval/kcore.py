# K-core decomposition: identifies structurally important nodes and boosts their PPR scores
from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class KCoreRanker:
    def __init__(self, min_k: int | None = None):
        self.min_k = min_k if min_k is not None else config.KCORE_MIN_K

    def get_core_numbers(self, G: nx.MultiDiGraph) -> dict[str, int]:
        # core_number requires a simple (non-multi) undirected graph
        G_simple = nx.Graph(G.to_undirected())
        raw = nx.core_number(G_simple)
        return {nid: k if k >= self.min_k else 0 for nid, k in raw.items()}

    def boost_scores(
        self,
        ppr_results: list[tuple[str, float]],
        core_numbers: dict[str, int],
    ) -> list[tuple[str, float]]:
        max_k = max(core_numbers.values(), default=1)
        if max_k == 0:
            max_k = 1

        boosted = [
            (nid, score * (1.0 + (core_numbers.get(nid, 0) / max_k) * 0.5))
            for nid, score in ppr_results
        ]
        boosted.sort(key=lambda x: x[1], reverse=True)
        return boosted

    def get_structurally_important(
        self,
        G: nx.MultiDiGraph,
        top_n: int = 10,
    ) -> list[str]:
        core_numbers = self.get_core_numbers(G)
        G_simple     = nx.Graph(G.to_undirected())
        deg_cent     = nx.degree_centrality(G_simple)

        # sort by (core_number DESC, degree_centrality DESC)
        ranked = sorted(
            G.nodes(),
            key=lambda n: (core_numbers.get(n, 0), deg_cent.get(n, 0)),
            reverse=True,
        )
        return ranked[:top_n]
