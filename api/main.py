"""FastAPI application entry point."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api.graph_cache import get_embedder, get_graph, get_index
from api.routers.graph import router as graph_router
from api.routers.query import router as query_router

app = FastAPI(title="NodeRAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router)
app.include_router(query_router)


@app.on_event("startup")
async def startup():
    G       = get_graph()
    _index  = get_index()
    emb     = get_embedder()
    print("NodeRAG API ready")
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print("Index: loaded")
    print(f"Model: {config.EMBED_MODEL}")


@app.get("/api/")
def root():
    return {"status": "ok"}


# ── static frontend (production build) ────────────────────────────────────────
# Mount AFTER API routers so /api/* routes take priority.
import os
from fastapi.staticfiles import StaticFiles

_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
