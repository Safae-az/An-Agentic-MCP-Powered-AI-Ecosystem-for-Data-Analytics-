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


class ToolRequest(BaseModel):
    agent:  str
    tool:   str
    params: dict
    run_id: str = ""


@app.post("/call")
def call_tool(req: ToolRequest):

    # 1. Vérifier la permission
    if not is_authorized(req.agent, req.tool):
        raise HTTPException(
            status_code=403,
            detail=f"'{req.agent}' n'est pas autorisé à appeler '{req.tool}'"
        )

    # 2. Vérifier que l'outil existe
    module_path = get_tool_module(req.tool)
    if not module_path:
        raise HTTPException(status_code=404, detail=f"Outil '{req.tool}' introuvable")

    # 3. Importer et exécuter l'outil
    try:
        module  = importlib.import_module(module_path)
        func    = getattr(module, req.tool)
        result  = func(**req.params)
        success = True
        error   = ""
    except Exception as e:
        result  = {}
        success = False
        error   = str(e)

    # 4. Logger l'appel
    if req.run_id:
        store.log_tool_call(req.run_id, ToolCall(
            agent_name = req.agent,
            tool_name  = req.tool,
            input      = req.params,
            output     = result,
            success    = success,
            error      = error
        ))

    if not success:
        raise HTTPException(status_code=500, detail=error)

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
