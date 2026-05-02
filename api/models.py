"""Pydantic DTOs for the NodeRAG API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GraphNodeDTO(BaseModel):
    node_id:     str
    node_type:   str
    label:       str = Field(max_length=60)
    text:        str = Field(max_length=200)
    table_name:  Optional[str] = None
    attributes:  dict          = Field(default_factory=dict)
    core_number: Optional[int] = None


class GraphEdgeDTO(BaseModel):
    source:   str
    target:   str
    relation: str
    weight:   float = 1.0


class GraphResponseDTO(BaseModel):
    nodes:       list[GraphNodeDTO]
    edges:       list[GraphEdgeDTO]
    node_counts: dict[str, int]
    edge_counts: dict[str, int]


class SubgraphRequest(BaseModel):
    center_node_id: str
    depth:          int = 2
    max_nodes:      int = 80


class QueryRequest(BaseModel):
    question: str
    top_k:    int  = 25
    verbose:  bool = False


class RetrievalStepEvent(BaseModel):
    event_type: str  # "seed" | "ppr" | "kcore" | "context" | "answer" | "error"
    data:       dict
