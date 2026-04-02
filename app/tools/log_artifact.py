# from app.storage.artifact_store import ArtifactStore
# from app.orchestrator.models import Artifact
# import uuid

# store = ArtifactStore()


# def log_artifact(run_id: str, type: str, path: str, producer: str, metadata: dict = {}) -> dict:
#     """
#     Sauvegarde un artifact produit pendant le run.
#     Appelable par tous les agents.
#     """
#     artifact = Artifact(
#         artifact_id = str(uuid.uuid4())[:8],
#         type        = type,
#         path        = path,
#         producer    = producer,
#         metadata    = metadata
#     )
#     store.save_artifact(run_id, artifact)
#     return {
#         "artifact_id": artifact.artifact_id,
#         "saved":       True,
#         "path":        path
#     }

# app/tools/log_artifact.py
import json, os
from datetime import datetime

def log_artifact(run_id: str, tool_name: str, data: dict) -> None:
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