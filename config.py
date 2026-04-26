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
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "10"))
PPR_ALPHA = float(os.getenv("PPR_ALPHA", "0.85"))
PPR_MAX_ITER = int(os.getenv("PPR_MAX_ITER", "100"))
KCORE_MIN_K = int(os.getenv("KCORE_MIN_K", "2"))
