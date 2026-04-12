from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.mcp.auth     import is_authorized, get_permissions
from app.mcp.registry import get_tool_module, list_tools
from app.mcp.schemas  import TOOL_SCHEMAS
from app.storage.artifact_store import ArtifactStore
from app.orchestrator.models    import ToolCall
import importlib

app   = FastAPI(title="MCP Server — KPI Monitoring")
store = ArtifactStore()

# Seul load_dataset retourne (df, result) — les autres retournent dict
TUPLE_TOOLS = set() 


class ToolRequest(BaseModel):
    agent:  str
    tool:   str
    params: dict
    run_id: str = ""


@app.post("/call")
def call_tool(req: ToolRequest):

    # 1. Permission
    if not is_authorized(req.agent, req.tool):
        raise HTTPException(403, f"'{req.agent}' ne peut pas appeler '{req.tool}'")

    # 2. Outil existe ?
    module_path = get_tool_module(req.tool)
    if not module_path:
        raise HTTPException(404, f"Outil '{req.tool}' introuvable")

    # 3. Exécuter
    try:
        module  = importlib.import_module(module_path)
        func    = getattr(module, req.tool)
        raw     = func(**req.params)
        result  = raw[1] if req.tool in TUPLE_TOOLS else raw
        success = True
        error   = ""
        print(f"OUTIL OK : {req.tool}")
    except Exception as e:
        result  = {}
        success = False
        error   = str(e)
        print(f"ERREUR OUTIL : {e}")
    # 4. Logger
    if req.run_id:
        # CORRECTION
        store.log_tool_call(req.run_id, ToolCall(
            agent_name = req.agent,
            tool_name  = req.tool,
            input      = req.params,
            output     = result if isinstance(result, dict) else {},
            success    = success,
            error      = error,
            timestamp  = ""
         ))

    if not success:
        raise HTTPException(500, error)

    return {"result": result}


@app.get("/tools")
def get_tools():
    return {"tools": list_tools()}

@app.get("/tools/schemas")
def get_schemas():
    return {"schemas": TOOL_SCHEMAS}

@app.get("/permissions/{agent}")
def agent_permissions(agent: str):
    return {"agent": agent, "tools": get_permissions(agent)}

@app.get("/logs/{run_id}")
def get_logs(run_id: str):
    return {"logs": store.get_logs(run_id)}

@app.get("/status/{run_id}")
def get_status(run_id: str):
    return store.get_metadata(run_id)

@app.get("/health")
def health():
    return {"status": "ok", "service": "MCP Server"}
