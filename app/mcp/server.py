# =============================================================================
# app/mcp/server.py — MCP Server corrigé (V2 complète)
# Corrections appliquées :
#   1. run_id obligatoire (plus de valeur par défaut "")
#   2. Vérification getattr avant exécution
#   3. Sérialisation JSON sécurisée (types pandas/numpy)
#   4. Gestion erreurs fine par type d'exception
# =============================================================================

from fastapi        import FastAPI, HTTPException
from pydantic       import BaseModel, field_validator
from app.mcp.auth   import is_authorized, get_permissions
from app.mcp.registry        import get_tool_module, list_tools
from app.mcp.schemas         import TOOL_SCHEMAS
from app.storage.artifact_store import ArtifactStore
from app.orchestrator.models    import ToolCall
import importlib
import json
import numpy  as np
import pandas as pd


app   = FastAPI(title="MCP Server — KPI Monitoring")
store = ArtifactStore()


# =============================================================================
# Sérialiseur JSON sécurisé — gère types pandas / numpy
# =============================================================================
def safe_serialize(obj):
    """
    Convertit récursivement les types non-sérialisables en types Python natifs.
    Gère : numpy int/float, pandas Timestamp, NaN, Infinity, bytes.
    """
    if isinstance(obj, dict):
        return {k: safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [safe_serialize(i) for i in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) or np.isinf(obj) else float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


def serialize_result(result: dict) -> dict:
    """Passe le résultat dans safe_serialize puis round-trip JSON pour garantir."""
    try:
        cleaned = safe_serialize(result)
        return json.loads(json.dumps(cleaned))
    except Exception as e:
        raise ValueError(f"Résultat non sérialisable : {e}")


# =============================================================================
# Modèle de requête — run_id obligatoire
# =============================================================================
class ToolRequest(BaseModel):
    agent:  str
    tool:   str
    params: dict
    run_id: str          # ← OBLIGATOIRE, plus de valeur par défaut ""

    @field_validator("run_id")
    @classmethod
    def run_id_non_vide(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("run_id ne peut pas être vide")
        return v.strip()

    @field_validator("agent")
    @classmethod
    def agent_non_vide(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("agent ne peut pas être vide")
        return v.strip()

    @field_validator("tool")
    @classmethod
    def tool_non_vide(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("tool ne peut pas être vide")
        return v.strip()


# =============================================================================
# Endpoint principal — POST /call
# =============================================================================
@app.post("/call")
def call_tool(req: ToolRequest):
    print(f"[MCP] {req.agent} → {req.tool} (run: {req.run_id})")

    # ── 1. Vérifier la permission ─────────────────────────────────────────
    if not is_authorized(req.agent, req.tool):
        print(f"[MCP] PERMISSION REFUSÉE : {req.agent} → {req.tool}")
        raise HTTPException(
            status_code=403,
            detail=f"Agent '{req.agent}' non autorisé pour l'outil '{req.tool}'"
        )

    # ── 2. Vérifier que l'outil existe dans le registre ──────────────────
    module_path = get_tool_module(req.tool)
    if not module_path:
        raise HTTPException(
            status_code=404,
            detail=f"Outil '{req.tool}' introuvable dans le registre"
        )

    # ── 3. Importer le module ─────────────────────────────────────────────
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Module '{module_path}' introuvable : {e}"
        )

    # ── 4. Vérifier que la fonction existe dans le module ─────────────────
    if not hasattr(module, req.tool):
        raise HTTPException(
            status_code=500,
            detail=f"Fonction '{req.tool}' introuvable dans le module '{module_path}'"
        )

    # ── 5. Exécuter l'outil ───────────────────────────────────────────────
    result  = {}
    success = True
    error   = ""

    try:
        func   = getattr(module, req.tool)
        raw    = func(**req.params)
        result = serialize_result(raw)          # ← sérialisation sécurisée

    except TypeError as e:
        # Mauvais paramètres passés à la fonction
        success = False
        error   = f"Paramètres invalides pour '{req.tool}' : {e}"

    except ValueError as e:
        # Erreur de sérialisation ou de valeur
        success = False
        error   = str(e)

    except Exception as e:
        # Toute autre erreur d'exécution
        success = False
        error   = str(e)

    # ── 6. Logger l'appel (toujours, succès ou échec) ────────────────────
    store.log_tool_call(req.run_id, ToolCall(
        agent_name = req.agent,
        tool_name  = req.tool,
        input      = req.params,
        output     = result,
        success    = success,
        error      = error
    ))

    # ── 7. Retourner l'erreur si échec ───────────────────────────────────
    if not success:
        print(f"[MCP] ERREUR dans {req.tool} : {error}")
        raise HTTPException(status_code=500, detail=error)

    print(f"[MCP] {req.tool} terminé avec succès")
    return {"result": result}


# =============================================================================
# Endpoints utilitaires
# =============================================================================

@app.get("/tools")
def get_tools():
    """Liste tous les outils disponibles dans le registre."""
    return {"tools": list_tools()}


@app.get("/tools/schemas")
def get_schemas():
    """Retourne les schémas JSON de tous les outils (pour Claude/LLM)."""
    return {"schemas": TOOL_SCHEMAS}


@app.get("/permissions/{agent}")
def agent_permissions(agent: str):
    """Retourne la liste des outils autorisés pour un agent donné."""
    perms = get_permissions(agent)
    if perms is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent}' inconnu"
        )
    return {"agent": agent, "tools": perms}


@app.get("/logs/{run_id}")
def get_logs(run_id: str):
    """Retourne tous les appels loggés pour un run donné."""
    logs = store.get_logs(run_id)
    if logs is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' introuvable"
        )
    return {"run_id": run_id, "logs": logs}


@app.get("/status/{run_id}")
def get_status(run_id: str):
    """Retourne les métadonnées et le statut global d'un run."""
    status = store.get_metadata(run_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' introuvable"
        )
    return status


@app.get("/health")
def health():
    """Health check — vérifie que le serveur et le registre sont opérationnels."""
    return {
        "status"  : "ok",
        "service" : "MCP Server",
        "tools"   : list_tools()
    }
