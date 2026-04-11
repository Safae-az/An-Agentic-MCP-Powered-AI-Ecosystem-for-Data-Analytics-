# app/tools/load_dataset.py
import pandas as pd
import os
from app.tools.log_artifact import log_artifact

def load_dataset(file_path: str, run_id: str) -> dict:
    """
    Charge le CSV et retourne schema + preview.
    Retourne un dict JSON (compatible MCP).
    """
    print(f"[load_dataset] Chargement de {file_path}...")

    if not os.path.exists(file_path):
        result = {
            "status"  : "error",
            "message" : f"Fichier introuvable : {file_path}"
        }
        log_artifact(run_id, "load_dataset", result)
        return result

    df = pd.read_csv(file_path)

    result = {
        "status"  : "success",
        "run_id"  : run_id,
        "rows"    : len(df),
        "columns" : list(df.columns),
        "dtypes"  : {col: str(df[col].dtype) for col in df.columns},
        "preview" : df.head(3).to_dict(orient="records")
    }

    print(f"[load_dataset] OK — {len(df):,} lignes chargees")
    log_artifact(run_id, "load_dataset", {
        "status" : "success",
        "rows"   : len(df)
    })

    return result   # dict seulement — plus de tuple

