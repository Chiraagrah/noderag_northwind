"""GNN-based neighbourhood expansion with iterative multi-hop + path augmentation.

How it works
------------
FAISS seeds are found in sentence-transformer space (query-compatible).
We expand the seed set in TWO ways and combine:

1. Iterative GNN expansion (multi-round, default 2 rounds)
   For each seed, find K nearest neighbours in GNN embedding space — these
   are nodes that share local topology because the GNN was trained with
   link prediction. Round 2 uses round-1's expansion as new seeds, giving
   an effective 6-hop reach for a 3-layer GNN. Scores from later rounds
   are decayed so closer-hop nodes still rank higher.

2. Shortest-path augmentation
   For each pair of high-scoring expanded nodes, find the shortest path
   in the underlying graph and inject the intermediate nodes. This
   guarantees that connecting relationship/order/orderdetail nodes are
   pulled into context whenever the query spans two distant clusters
   (e.g. UK suppliers ↔ German customers).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import networkx as nx


class GNNExpander:
    """Loads pre-computed GNN embeddings and expands a seed set using them."""

    def __init__(self, gnn_path: str | None = None):
        root = Path(__file__).parent.parent
        self.gnn_path = gnn_path or str(root / "data" / "northwind_gnn_embeddings.npz")
        self._emb: dict[str, np.ndarray] | None = None
        self._mat: np.ndarray | None = None
        self._all_ids: list[str] | None = None

    # ── loading ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        data = np.load(self.gnn_path, allow_pickle=True)
        node_ids   = data["node_ids"].tolist()
        embeddings = data["embeddings"]          # (N, dim) float32
        self._emb     = {nid: embeddings[i] for i, nid in enumerate(node_ids)}
        self._all_ids = list(self._emb.keys())
        self._mat     = np.stack([self._emb[nid] for nid in self._all_ids], axis=0)

    @property
    def embeddings(self) -> dict[str, np.ndarray]:
        if self._emb is None:
            self.load()
        return self._emb

    def available(self) -> bool:
        return Path(self.gnn_path).exists()

    def is_useful(self) -> bool:
        """Returns False if embeddings are degenerate (all vectors nearly the same).
        Degenerate GNN embeddings produce cosine similarities ~1.0 for all pairs,
        making neighbour expansion meaningless — in that case PPR is a better fallback.
        """
        if not self.available():
            return False
        emb = self.embeddings
        if len(emb) < 10:
            return False
        mat = self._mat          # (N, dim), assumed unit-normalised by training
        # sample up to 200 nodes and compute pairwise dot products
        n_sample = min(200, len(self._all_ids))
        idx = np.random.choice(len(self._all_ids), n_sample, replace=False)
        sample = mat[idx]        # (n_sample, dim)
        sims = sample @ sample.T # (n_sample, n_sample) — cosine sims if unit-normalised
        # off-diagonal std; meaningful embeddings have std > 0.05
        mask = ~np.eye(n_sample, dtype=bool)
        return float(np.std(sims[mask])) > 0.05

    # ── single-round expansion (used as a building block) ─────────────────────

    def _expand_once(
        self,
        seed_ids:           list[str],
        top_k:              int,
        neighbors_per_seed: int,
    ) -> dict[str, float]:
        """One round of GNN expansion. Returns {node_id: max_cosine_score}."""
        emb = self.embeddings
        if not emb:
            return {}

        scores: dict[str, float] = {}
        for seed_id in seed_ids:
            if seed_id not in emb:
                continue
            seed_vec = emb[seed_id]
            sims     = self._mat @ seed_vec                  # (N,)
            top_idx  = np.argpartition(sims, -neighbors_per_seed)[-neighbors_per_seed:]
            for idx in top_idx:
                nid   = self._all_ids[idx]
                score = float(sims[idx])
                if nid not in scores or scores[nid] < score:
                    scores[nid] = score
        return scores

    # ── public: iterative multi-round expansion ───────────────────────────────

    def expand(
        self,
        seed_ids:           list[str],
        top_k:              int  = 30,
        neighbors_per_seed: int  = 15,
        rounds:             int  = 2,
        round_decay:        float= 0.7,
    ) -> list[tuple[str, float]]:
        """
        Iterative GNN expansion.

        Round 1: expand from FAISS seeds.
        Round 2..R: re-expand from the previous round's top-k, with each
                    round's scores multiplied by `round_decay` so closer
                    hops dominate the final ranking.

        Returns deduplicated, score-sorted (node_id, score) pairs (top_k).
        """
        emb = self.embeddings
        if not emb:
            return []

        merged: dict[str, float] = {}
        current_seeds = list(seed_ids)

        for r in range(rounds):
            round_scores = self._expand_once(
                current_seeds,
                top_k             = top_k,
                neighbors_per_seed= neighbors_per_seed,
            )
            decay = round_decay ** r
            for nid, s in round_scores.items():
                decayed = s * decay
                if nid not in merged or merged[nid] < decayed:
                    merged[nid] = decayed

            # next round's seeds = top of this round
            current_seeds = [
                nid for nid, _ in
                sorted(round_scores.items(), key=lambda x: -x[1])[:top_k]
            ]
            if not current_seeds:
                break

        sorted_nodes = sorted(merged.items(), key=lambda x: -x[1])
        return sorted_nodes[:top_k]

    # ── shortest-path augmentation ────────────────────────────────────────────

    def augment_with_paths(
        self,
        G:                nx.Graph,
        ranked_nodes:     list[tuple[str, float]],
        seed_ids:         list[str],
        max_pair_probes:  int   = 8,
        max_path_len:     int   = 6,
        path_score_floor: float | None = None,
    ) -> list[tuple[str, float]]:
        """
        Find shortest paths between top-ranked retrieved nodes and inject
        intermediate connecting nodes. This is what gives multi-hop relational
        queries (e.g. "which UK suppliers have German customers") their
        connecting evidence — the relationship/order/orderdetail nodes that
        were never going to be semantically similar to the query but ARE
        on the proof path.

        Bridge nodes are scored as the geometric mean of their two endpoint
        scores, so nodes on paths between the most relevant endpoints rank
        highest — rather than all bridge nodes tying at a flat floor.
        """
        if G is None or not ranked_nodes:
            return ranked_nodes

        G_un = G.to_undirected() if G.is_directed() else G

        # Build a subgraph without community nodes so shortest_path uses real FK chains
        non_comm = [n for n in G_un.nodes() if not n.startswith("community_")]
        G_no_comm = G_un.subgraph(non_comm)

        score_map = dict(ranked_nodes)
        existing  = set(score_map.keys())

        # candidate endpoints: top-ranked, non-community nodes that exist in graph
        endpoints = [
            nid for nid, _ in ranked_nodes[:max_pair_probes]
            if nid in G_no_comm and not nid.startswith("community_")
        ]

        # also use the original FAISS seeds as endpoints
        for sid in seed_ids[:5]:
            if sid in G_no_comm and sid not in endpoints and not sid.startswith("community_"):
                endpoints.append(sid)

        # find shortest paths between every pair of endpoints (no community shortcuts)
        for i, src in enumerate(endpoints):
            for dst in endpoints[i + 1:]:
                try:
                    path = nx.shortest_path(G_no_comm, src, dst)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                if not (2 < len(path) <= max_path_len):
                    continue   # 2 = direct edge (no intermediates), >max = too far

                # Score bridge nodes as geometric mean of endpoint scores.
                # This gives higher ranks to bridges on important paths while
                # naturally differentiating bridges from different pairs.
                src_score = score_map.get(src, 0.0)
                dst_score = score_map.get(dst, 0.0)
                pair_score = (src_score * dst_score) ** 0.5

                # Optionally respect a caller-supplied absolute floor
                if path_score_floor is not None:
                    pair_score = max(pair_score, path_score_floor)

                for nid in path[1:-1]:
                    if nid.startswith("community_"):
                        continue
                    if nid not in existing:
                        score_map[nid] = pair_score
                        existing.add(nid)
                    elif score_map[nid] < pair_score:
                        score_map[nid] = pair_score

        # remove community nodes from final results — they're structural shortcuts,
        # not informative for the LLM
        score_map = {k: v for k, v in score_map.items() if not k.startswith("community_")}
        return sorted(score_map.items(), key=lambda x: -x[1])

    # ── explanation helper ────────────────────────────────────────────────────

    def explain(self, node_id: str, seed_ids: list[str]) -> str:
        emb = self.embeddings
        if node_id not in emb:
            return f"[GNN] {node_id} — not in GNN embedding space"
        best_seed, best_sim = None, -1.0
        for seed_id in seed_ids:
            if seed_id in emb:
                sim = float(np.dot(emb[node_id], emb[seed_id]))
                if sim > best_sim:
                    best_sim, best_seed = sim, seed_id
        return (
            f"[GNN] {node_id}  ←  GNN-cos={best_sim:.4f}  "
            f"closest seed: {best_seed}"
        )
