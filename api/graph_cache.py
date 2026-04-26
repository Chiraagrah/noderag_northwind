"""Module-level singleton cache — graph, index, embedder, and stats loaded once at startup."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import networkx as nx

_graph    = None
_index    = None
_embedder = None
_stats    = None

_GRAPH_PATH = ROOT / "data" / "northwind_graph.json"
_INDEX_PATH = str(ROOT / "data" / "northwind_index")


def get_graph() -> nx.MultiDiGraph:
    global _graph
    if _graph is None:
        from graph.node_types import node_from_dict
        with open(_GRAPH_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        for n in raw["nodes"]:
            if "data" in n and isinstance(n["data"], dict):
                n["data"] = node_from_dict(n["data"])
        _graph = nx.node_link_graph(raw, directed=True, multigraph=True)
    return _graph


def get_index():
    global _index
    if _index is None:
        from graph.indexer import NodeIndex
        _index = NodeIndex()
        _index.load(_INDEX_PATH)
    return _index


def get_embedder():
    global _embedder
    if _embedder is None:
        from graph.embedder import NodeEmbedder
        _embedder = NodeEmbedder()
    return _embedder


def get_stats() -> dict:
    global _stats
    if _stats is None:
        from collections import defaultdict
        G = get_graph()
        node_counts: dict[str, int] = defaultdict(int)
        for _, d in G.nodes(data=True):
            nd = d.get("data")
            if nd:
                node_counts[nd.node_type] += 1
        edge_counts: dict[str, int] = defaultdict(int)
        for _, _, d in G.edges(data=True):
            edge_counts[d.get("relation", "unknown")] += 1
        _stats = {
            "node_count":       G.number_of_nodes(),
            "edge_count":       G.number_of_edges(),
            "node_counts":      dict(node_counts),
            "edge_counts":      dict(edge_counts),
            "node_type_count":  len(node_counts),
        }
    return _stats


def reload() -> None:
    global _graph, _index, _embedder, _stats
    _graph    = None
    _index    = None
    _embedder = None
    _stats    = None
