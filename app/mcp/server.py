
from fastapi  import FastAPI, HTTPException
from pydantic import BaseModel
import importlib
from app.tools.log_artifact import log_artifact

app = FastAPI(title="MCP Server")

# Outils qui retournent (df, result) au lieu d'un dict
# A garder pour compatibilite si load_dataset est appele directement
TUPLE_TOOLS = {"load_dataset"}

# ── Permissions ──
PERMISSIONS = {
    "data_engineer"  : ["load_dataset", "profile_data",
                        "clean_data", "log_artifact"],
    "data_scientist" : ["run_analysis", "log_artifact"],
    "bi_agent"       : ["generate_chart", "publish_dashboard",
                        "log_artifact"],
    "reporter"       : ["compile_report", "log_artifact"],
    "orchestrator"   : ["*"],
}

# ── Registre des outils ──
TOOL_MODULES = {
    "load_dataset"      : "app.tools.load_dataset",
    "profile_data"      : "app.tools.profile_data",
    "clean_data"        : "app.tools.clean_data",
    "run_analysis"      : "app.tools.run_analysis",
    "generate_chart"    : "app.tools.generate_chart",
    "publish_dashboard" : "app.tools.publish_dashboard",
    "log_artifact"      : "app.tools.log_artifact",
    "compile_report"    : "app.tools.compile_report",
}

class ToolRequest(BaseModel):
    agent  : str
    tool   : str
    params : dict
    run_id : str

def is_authorized(agent: str, tool: str) -> bool:
    """Verifie si l'agent a le droit d'appeler cet outil."""
    perms = PERMISSIONS.get(agent, [])
    return "*" in perms or tool in perms

@app.post("/call")
def call_tool(req: ToolRequest):
    """
    Endpoint principal du MCP Server.
    Recoit tous les appels d'outils des agents.
    Etapes : 1.Permission 2.Registry 3.Execution 4.Log
    """
    print(f"[MCP] {req.agent} → {req.tool} (run: {req.run_id})")

    # 1. Verifier permission
    if not is_authorized(req.agent, req.tool):
        print(f"[MCP] PERMISSION REFUSEE : {req.agent} / {req.tool}")
        raise HTTPException(
            status_code = 403,
            detail      = f"Agent '{req.agent}' non autorise "
                          f"pour l'outil '{req.tool}'"
        )

    # 2. Trouver le module dans le registre
    module_path = TOOL_MODULES.get(req.tool)
    if not module_path:
        raise HTTPException(
            status_code = 404,
            detail      = f"Outil '{req.tool}' non trouve"
        )

    # 3. Executer l'outil
    try:
        module = importlib.import_module(module_path)
        func   = getattr(module, req.tool)
        raw    = func(**req.params)

        # Gerer les outils qui retournent encore un tuple (df, result)
        if req.tool in TUPLE_TOOLS and isinstance(raw, tuple):
            _, result = raw
        else:
            result = raw

        # 4. Logger l'appel dans tool_calls.jsonl
        log_artifact(req.run_id, f"mcp_{req.tool}", {
            "agent"  : req.agent,
            "tool"   : req.tool,
            "status" : "success"
        })

        print(f"[MCP] {req.tool} termine avec succes")
        return {"result": result}

    except Exception as e:
        print(f"[MCP] ERREUR dans {req.tool} : {e}")
        log_artifact(req.run_id, f"mcp_error_{req.tool}", {
            "agent" : req.agent,
            "tool"  : req.tool,
            "error" : str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    """Verifie que le serveur MCP tourne."""
    return {
        "status" : "ok",
        "tools"  : list(TOOL_MODULES.keys()),
        "agents" : list(PERMISSIONS.keys())

    }

