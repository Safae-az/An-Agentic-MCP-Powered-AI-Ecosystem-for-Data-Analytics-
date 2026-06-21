import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ── MCP Server ────────────────────────────────────────────────────────
MCP_URL            = os.getenv("MCP_URL", "http://localhost:8000/call")
MCP_TIMEOUT_HEAVY  = int(os.getenv("MCP_TIMEOUT_HEAVY", 600))   # clean_data, profile_data, run_analysis
MCP_TIMEOUT_LIGHT  = int(os.getenv("MCP_TIMEOUT_LIGHT", 60))

# ── Chemins ───────────────────────────────────────────────────────────
RUNS_DIR    = os.getenv("RUNS_DIR", "runs")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")

# ── Pipeline ──────────────────────────────────────────────────────────
DEVOPS_MAX_RETRIES = int(os.getenv("DEVOPS_MAX_RETRIES", 2))
