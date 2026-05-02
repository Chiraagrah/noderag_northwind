# Central configuration: loads all env vars and exposes typed constants for the project
import os
from pathlib import Path
from dotenv import load_dotenv

# always load from the project root, regardless of cwd
load_dotenv(Path(__file__).parent / ".env", override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
DB_PATH = os.getenv("DB_PATH", "data/northwind.db")
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "20"))
KCORE_MIN_K     = int(os.getenv("KCORE_MIN_K", "2"))

# GNN embedding hyperparameters (GraphSAGE, trained during ingestion)
GNN_HIDDEN_DIM        = int(os.getenv("GNN_HIDDEN_DIM",        "256"))
GNN_OUT_DIM           = int(os.getenv("GNN_OUT_DIM",           "384"))
GNN_EPOCHS            = int(os.getenv("GNN_EPOCHS",            "500"))
GNN_LR                = float(os.getenv("GNN_LR",              "0.001"))
GNN_NEG_RATIO         = int(os.getenv("GNN_NEG_RATIO",         "5"))
GNN_DROPOUT           = float(os.getenv("GNN_DROPOUT",         "0.2"))
GNN_NEIGHBORS_PER_SEED = int(os.getenv("GNN_NEIGHBORS_PER_SEED", "15"))
