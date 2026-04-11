# app/tools/log_artifact.py
# Version simplifiee — autonome, sans imports complexes
import json, os
from datetime import datetime

def log_artifact(run_id: str, tool_name: str, data: dict) -> None:
    """Enregistre chaque appel outil dans tool_calls.jsonl"""

    run_dir = f"runs/{run_id}"
    os.makedirs(f"{run_dir}/artifacts", exist_ok=True)
    os.makedirs(f"{run_dir}/charts",    exist_ok=True)

    entry = {
        "timestamp" : datetime.now().isoformat(),
        "run_id"    : run_id,
        "tool"      : tool_name,
        "data"      : data
    }

    with open(f"{run_dir}/tool_calls.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")