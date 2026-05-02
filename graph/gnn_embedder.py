"""GraphSAGE-based node embedder — improved v2.

Improvements over v1
--------------------
* 3-layer GraphSAGE with residual/skip connection
  → 3-hop receptive field; same-domain nodes that are 3 edges apart
    (e.g. supplier_5 → product → category → supplier_8) get pulled together
* Node-type one-hot features (7-dim) appended to base embeddings
  → GNN explicitly knows the type of every node it aggregates
* Hard negative sampling: negatives drawn from the SAME node_type as the
  positive target (not random)
  → Forces within-type discrimination (UK supplier vs Spanish supplier),
    instead of trivial between-type discrimination
* Dropout (0.2) for regularisation
* 500 epochs with cosine-annealing LR schedule

Output
------
L2-normalised topology-aware node embeddings, saved to a separate .npz
file at index-build time and used at query time by GNNExpander for
node-to-node neighbourhood expansion. They are NOT placed in FAISS — the
FAISS index keeps the sentence-transformer embeddings so query vectors
remain in a compatible space.
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Optional

import networkx as nx
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


# ── Node-type registry (one-hot dim) ──────────────────────────────────────────
_NODE_TYPES = [
    "text_chunk", "entity", "semantic_unit",
    "relationship", "attribute", "high_level_insight", "community",
]
_TYPE2IDX  = {t: i for i, t in enumerate(_NODE_TYPES)}
_TYPE_DIM  = len(_NODE_TYPES)   # 7


# ── SAGEConv layer ────────────────────────────────────────────────────────────

class _SAGEConv(nn.Module):
    """Single GraphSAGE mean-aggregation layer with dropout."""

    def __init__(self, in_dim: int, out_dim: int, dropout: float = 0.0):
        super().__init__()
        self.linear  = nn.Linear(in_dim * 2, out_dim, bias=True)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: "torch.Tensor", adj: list[list[int]]) -> "torch.Tensor":
        N = x.size(0)
        agg = torch.zeros(N, x.size(1), device=x.device)
        for i, neighbours in enumerate(adj):
            if neighbours:
                agg[i] = x[neighbours].mean(dim=0)
            else:
                agg[i] = x[i]   # isolated node: self-loop
        h = torch.cat([x, agg], dim=-1)
        return self.linear(self.dropout(h))


# ── 3-layer GraphSAGE with residual ───────────────────────────────────────────

class GraphSAGE(nn.Module):
    """
    Architecture:
        in_dim → SAGEConv → hidden  (ReLU + dropout)
               → SAGEConv → hidden  (ReLU + dropout)
               → SAGEConv → out_dim
        + skip(in_dim → out_dim)              residual
        → L2-normalise
    """

    def __init__(
        self,
        in_dim:     int   = 384 + _TYPE_DIM,   # 391
        hidden_dim: int   = 256,
        out_dim:    int   = 384,
        dropout:    float = 0.2,
    ):
        super().__init__()
        self.conv1 = _SAGEConv(in_dim,     hidden_dim, dropout)
        self.conv2 = _SAGEConv(hidden_dim, hidden_dim, dropout)
        self.conv3 = _SAGEConv(hidden_dim, out_dim,    dropout)
        self.skip  = nn.Linear(in_dim, out_dim, bias=False)
        self.drop  = nn.Dropout(dropout)

    def forward(self, x: "torch.Tensor", adj: list[list[int]]) -> "torch.Tensor":
        skip_h = self.skip(x)
        h = F.relu(self.conv1(x, adj));  h = self.drop(h)
        h = F.relu(self.conv2(h, adj));  h = self.drop(h)
        h = self.conv3(h, adj) + skip_h          # residual
        return F.normalize(h, p=2, dim=-1)


# ── GNNEmbedder ───────────────────────────────────────────────────────────────

class GNNEmbedder:
    """
    Trains GraphSAGE on the heterograph and returns L2-normalised node
    embeddings. Stored separately (not in FAISS) and consumed at query time
    by GNNExpander.
    """

    def __init__(
        self,
        hidden_dim: int   = 256,
        out_dim:    int   = 384,
        epochs:     int   = 500,
        lr:         float = 1e-3,
        neg_ratio:  int   = 5,
        dropout:    float = 0.2,
        device:     Optional[str] = None,
    ):
        if not _TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is required for GNNEmbedder. "
                "Install it with: pip install torch"
            )
        self.hidden_dim = hidden_dim
        self.out_dim    = out_dim
        self.epochs     = epochs
        self.lr         = lr
        self.neg_ratio  = neg_ratio
        self.dropout    = dropout
        self.device     = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )

    # ── public ────────────────────────────────────────────────────────────────

    def fit_transform(
        self,
        G: nx.Graph,
        base_embeddings: dict[str, np.ndarray],
        verbose: bool = True,
    ) -> dict[str, np.ndarray]:
        node_ids   = list(base_embeddings.keys())
        node_index = {nid: i for i, nid in enumerate(node_ids)}
        N          = len(node_ids)
        base_dim   = next(iter(base_embeddings.values())).shape[0]   # 384

        # ── feature matrix: base embedding ⊕ node-type one-hot ────────────────
        feat = np.zeros((N, base_dim + _TYPE_DIM), dtype=np.float32)
        node_type_list: list[str] = []
        for i, nid in enumerate(node_ids):
            feat[i, :base_dim] = base_embeddings[nid]
            nd = G.nodes[nid].get("data") if nid in G else None
            nt = nd.node_type if nd else "entity"
            feat[i, base_dim + _TYPE2IDX.get(nt, 0)] = 1.0
            node_type_list.append(nt)
        x = torch.from_numpy(feat).to(self.device)

        # ── undirected adjacency ──────────────────────────────────────────────
        G_un = G.to_undirected()
        adj: list[list[int]] = [[] for _ in range(N)]
        for i, nid in enumerate(node_ids):
            if nid in G_un:
                for nbr in G_un.neighbors(nid):
                    j = node_index.get(nbr)
                    if j is not None:
                        adj[i].append(j)

        # ── positive edges ────────────────────────────────────────────────────
        pos_edges: list[tuple[int, int]] = []
        for i in range(N):
            for j in adj[i]:
                if i < j:
                    pos_edges.append((i, j))

        if not pos_edges:
            if verbose:
                print("  [GNNEmbedder] No edges — returning base embeddings unchanged.")
            return base_embeddings

        # ── bucket node indices by type for hard-negative sampling ────────────
        type_buckets: dict[str, list[int]] = defaultdict(list)
        for i, nt in enumerate(node_type_list):
            type_buckets[nt].append(i)
        type_buckets = dict(type_buckets)

        if verbose:
            print(
                f"  [GNNEmbedder] Training GraphSAGE (3-layer + skip)  "
                f"nodes={N}  edges={len(pos_edges)}  "
                f"in_dim={base_dim + _TYPE_DIM}  hidden={self.hidden_dim}  "
                f"out={self.out_dim}  epochs={self.epochs}  device={self.device}"
            )

        # ── model + optimiser + cosine LR scheduler ───────────────────────────
        model = GraphSAGE(
            in_dim     = base_dim + _TYPE_DIM,
            hidden_dim = self.hidden_dim,
            out_dim    = self.out_dim,
            dropout    = self.dropout,
        ).to(self.device)
        optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=self.epochs)

        # ── training loop ─────────────────────────────────────────────────────
        for epoch in range(1, self.epochs + 1):
            model.train()
            optimizer.zero_grad()

            h = model(x, adj)   # (N, out_dim)

            # positive scores
            src_pos = torch.tensor([e[0] for e in pos_edges], device=self.device)
            dst_pos = torch.tensor([e[1] for e in pos_edges], device=self.device)
            pos_scores = (h[src_pos] * h[dst_pos]).sum(dim=-1)

            # hard negative sampling — same-type as target
            neg_src, neg_dst = self._sample_hard_negatives(
                pos_edges, node_type_list, type_buckets, self.neg_ratio
            )
            src_neg = torch.tensor(neg_src, device=self.device)
            dst_neg = torch.tensor(neg_dst, device=self.device)
            neg_scores = (h[src_neg] * h[dst_neg]).sum(dim=-1)

            scores = torch.cat([pos_scores, neg_scores])
            labels = torch.cat([
                torch.ones(len(pos_edges),   device=self.device),
                torch.zeros(len(neg_src),    device=self.device),
            ])

            loss = F.binary_cross_entropy_with_logits(scores, labels)
            loss.backward()
            optimizer.step()
            scheduler.step()

            if verbose and (epoch == 1 or epoch % 50 == 0 or epoch == self.epochs):
                print(
                    f"    epoch {epoch:>4d}/{self.epochs}  "
                    f"loss={loss.item():.4f}  "
                    f"lr={scheduler.get_last_lr()[0]:.5f}"
                )

        # ── inference ─────────────────────────────────────────────────────────
        model.eval()
        with torch.no_grad():
            h_final = model(x, adj).cpu().numpy()

        result = dict(base_embeddings)
        for i, nid in enumerate(node_ids):
            result[nid] = h_final[i]

        if verbose:
            print(f"  [GNNEmbedder] Done. Output dim={h_final.shape[1]}")

        return result

    # ── hard negative sampling ────────────────────────────────────────────────

    @staticmethod
    def _sample_hard_negatives(
        pos_edges:      list[tuple[int, int]],
        node_type_list: list[str],
        type_buckets:   dict[str, list[int]],
        neg_ratio:      int,
    ) -> tuple[list[int], list[int]]:
        """
        For every positive edge (src, tgt), sample neg_ratio nodes that:
        - share node_type with tgt   (hard: within-type discrimination)
        - are not tgt itself
        - do not form an existing edge with src

        Returns parallel lists (src_list, dst_list).
        """
        edge_set = set(pos_edges) | {(b, a) for a, b in pos_edges}
        src_list: list[int] = []
        dst_list: list[int] = []

        for src, tgt in pos_edges:
            tgt_type  = node_type_list[tgt]
            same_type = type_buckets.get(tgt_type, [])
            if len(same_type) <= 1:
                continue
            count, attempts = 0, 0
            while count < neg_ratio and attempts < neg_ratio * 10:
                neg = random.choice(same_type)
                if neg != tgt and neg != src and (src, neg) not in edge_set:
                    src_list.append(src)
                    dst_list.append(neg)
                    count += 1
                attempts += 1

        return src_list, dst_list


# ── standalone training script ────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))

    import config

    parser = argparse.ArgumentParser(description="Train improved GraphSAGE embeddings on the Northwind graph")
    parser.add_argument("--epochs",      type=int,   default=config.GNN_EPOCHS)
    parser.add_argument("--hidden-dim",  type=int,   default=config.GNN_HIDDEN_DIM)
    parser.add_argument("--out-dim",     type=int,   default=config.GNN_OUT_DIM)
    parser.add_argument("--lr",          type=float, default=config.GNN_LR)
    parser.add_argument("--neg-ratio",   type=int,   default=config.GNN_NEG_RATIO)
    parser.add_argument("--dropout",     type=float, default=config.GNN_DROPOUT)
    parser.add_argument("--graph",       type=str,   default="data/northwind_graph.json")
    parser.add_argument("--gnn-out",     type=str,   default="data/northwind_gnn_embeddings.npz")
    args = parser.parse_args()

    root = Path(__file__).parent.parent

    # ── load graph ────────────────────────────────────────────────────────────
    from graph.node_types import node_from_dict

    graph_path = root / args.graph
    print(f"Loading graph from {graph_path} ...")
    with open(graph_path, encoding="utf-8") as f:
        raw = json.load(f)
    for n in raw["nodes"]:
        if "data" in n and isinstance(n["data"], dict):
            n["data"] = node_from_dict(n["data"])
    G = nx.node_link_graph(raw, directed=True, multigraph=True)
    print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # ── base embeddings (sentence transformer) ────────────────────────────────
    from graph.embedder import NodeEmbedder

    print("Computing base sentence-transformer embeddings ...")
    embedder = NodeEmbedder()
    base_emb = embedder.embed_graph(G)
    dim      = next(iter(base_emb.values())).shape[0]
    print(f"  {len(base_emb)} embeddings, dim={dim}")

    # ── GNN training ──────────────────────────────────────────────────────────
    print(
        f"\nTraining GraphSAGE  layers=3  hidden={args.hidden_dim}  out={args.out_dim}  "
        f"epochs={args.epochs}  lr={args.lr}  neg_ratio={args.neg_ratio}  "
        f"dropout={args.dropout}"
    )

    gnn = GNNEmbedder(
        hidden_dim = args.hidden_dim,
        out_dim    = args.out_dim,
        epochs     = args.epochs,
        lr         = args.lr,
        neg_ratio  = args.neg_ratio,
        dropout    = args.dropout,
    )
    gnn_emb = gnn.fit_transform(G, base_emb, verbose=True)

    # ── save GNN embeddings to a .npz file (NOT FAISS) ────────────────────────
    out_path = str(root / args.gnn_out)
    np.savez_compressed(
        out_path,
        node_ids   = np.array(list(gnn_emb.keys())),
        embeddings = np.stack(list(gnn_emb.values())).astype(np.float32),
    )
    print(f"\nGNN embeddings saved to {out_path}")
    print(f"  {len(gnn_emb)} vectors  dim={args.out_dim}")
    print("\nDone. FAISS index is unchanged (still sentence-transformer space).")
