"""Graph REST endpoints: full graph, subgraph, stats, node detail, reload."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import networkx as nx
from fastapi import APIRouter, HTTPException

from api.graph_cache import get_graph, get_stats, reload
from api.models import GraphEdgeDTO, GraphNodeDTO, GraphResponseDTO

router = APIRouter(prefix="/api/graph")


# ── helpers ───────────────────────────────────────────────────────────────────

def _node_to_dto(node_id: str, node_data) -> GraphNodeDTO:
    nd = node_data
    raw_label = (nd.text or "").replace("\n", " ")[:60]
    table_name  = getattr(nd, "table_name",  None)
    attributes  = nd.attributes if nd.node_type == "entity" else {}
    core_number = nd.core_number if nd.node_type == "community" else None
    return GraphNodeDTO(
        node_id     = node_id,
        node_type   = nd.node_type,
        label       = raw_label,
        text        = (nd.text or "")[:200],
        table_name  = table_name,
        attributes  = attributes,
        core_number = core_number,
    )


def _build_response(G: nx.MultiDiGraph) -> GraphResponseDTO:
    from collections import defaultdict

    nodes: list[GraphNodeDTO] = []
    for nid, d in G.nodes(data=True):
        nd = d.get("data")
        if nd:
            nodes.append(_node_to_dto(nid, nd))

    edges: list[GraphEdgeDTO] = []
    for src, tgt, d in G.edges(data=True):
        edges.append(GraphEdgeDTO(
            source   = src,
            target   = tgt,
            relation = d.get("relation", "unknown"),
            weight   = float(d.get("weight", 1.0)),
        ))

    node_counts: dict[str, int] = defaultdict(int)
    for n in nodes:
        node_counts[n.node_type] += 1

    edge_counts: dict[str, int] = defaultdict(int)
    for e in edges:
        edge_counts[e.relation] += 1

    return GraphResponseDTO(
        nodes       = nodes,
        edges       = edges,
        node_counts = dict(node_counts),
        edge_counts = dict(edge_counts),
    )


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=GraphResponseDTO)
def get_full_graph():
    return _build_response(get_graph())


@router.get("/stats")
def graph_stats():
    return get_stats()


@router.get("/subgraph", response_model=GraphResponseDTO)
def get_subgraph(
    center_node_id: str,
    depth:          int = 2,
    max_nodes:      int = 80,
):
    G = get_graph()
    if center_node_id not in G:
        raise HTTPException(status_code=404, detail=f"Node '{center_node_id}' not found")

    sub = nx.ego_graph(G, center_node_id, radius=depth, undirected=True)

    if sub.number_of_nodes() > max_nodes:
        # drop lowest-degree nodes until within budget
        degrees   = dict(sub.degree())
        to_remove = sorted(
            [n for n in sub.nodes() if n != center_node_id],
            key=lambda n: degrees[n],
        )
        while sub.number_of_nodes() > max_nodes and to_remove:
            sub.remove_node(to_remove.pop(0))

    return _build_response(sub)


@router.get("/node/{node_id}")
def get_node(node_id: str):
    G = get_graph()
    if node_id not in G:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    nd = G.nodes[node_id].get("data")
    if nd is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' has no data")
    return nd.model_dump()


@router.post("/reload")
def reload_graph():
    reload()
    return {"status": "reloaded", "stats": get_stats()}
