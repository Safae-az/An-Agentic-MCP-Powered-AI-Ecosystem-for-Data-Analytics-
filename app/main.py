from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from app.orchestrator.engine import run_pipeline
from app.storage.artifact_store import ArtifactStore
from app.storage.run_store import RunStore
from app.tools.load_dataset import load_from_url, load_from_api
import shutil, os, uuid
from pathlib import Path

load_dotenv()

app = FastAPI(title="KPI Monitoring System")
store = ArtifactStore()
runs = RunStore()
BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "app" / "ui"
DATA_DIR = BASE_DIR / "data"
RUNS_DIR = BASE_DIR / "runs"

if RUNS_DIR.exists():
    app.mount("/runs-files", StaticFiles(directory=str(RUNS_DIR)), name="runs-files")

try:
    import multipart  # noqa: F401
    MULTIPART_AVAILABLE = True
except ImportError:
    MULTIPART_AVAILABLE = False


class LocalFileRunRequest(BaseModel):
    file_path: str
    objective: str


class UrlRunRequest(BaseModel):
    url: str
    objective: str


class ApiRunRequest(BaseModel):
    api_url: str
    api_key: str
    objective: str
    key_param: str = ""


# Autoriser les appels depuis l'UI (P4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return FileResponse(UI_DIR / "index.html")


@app.get("/api")
def api_info():
    return {"message": "KPI Monitoring System - En ligne"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run/start")
async def start_run(payload: LocalFileRunRequest):
    """
    Lance le pipeline depuis un fichier deja present sur la machine.
    Exemple: {"file_path": "data/demo.csv", "objective": "analyser"}
    """
    return run_pipeline(payload.file_path, payload.objective)


if MULTIPART_AVAILABLE:
    @app.post("/run/start-upload")
    async def start_run_upload(
        file: UploadFile = File(...),
        objective: str = Form(...),
    ):
        """
        Upload fichier classique. Necessite python-multipart.
        """
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        return run_pipeline(file_path, objective)
else:
    @app.post("/run/start-upload")
    async def start_run_upload_unavailable():
        return {
            "status": "error",
            "message": "Upload indisponible : installez python-multipart avec pip install python-multipart.",
        }


@app.post("/run/start-url")
async def start_run_url(payload: UrlRunRequest):
    """
    Methode via lien direct : URL publique vers CSV, JSON, Excel, Parquet, TSV ou TXT.
    """
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    result = load_from_url(url=payload.url, run_id=run_id)

    if result.get("status") == "error":
        return result

    return run_pipeline(result["file_path"], payload.objective, run_id=run_id)


@app.post("/run/start-api")
async def start_run_api(payload: ApiRunRequest):
    """
    Methode via cle API : endpoint API + cle personnelle.
    """
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    result = load_from_api(
        api_url=payload.api_url,
        api_key=payload.api_key,
        run_id=run_id,
        key_param=payload.key_param,
    )

    if result.get("status") == "error":
        return result

    return run_pipeline(result["file_path"], payload.objective, run_id=run_id)


@app.get("/run/{run_id}/logs")
def get_logs(run_id: str):
    """Retourne les logs en temps reel."""
    return {"logs": store.get_logs(run_id)}


@app.get("/run/{run_id}/status")
def get_status(run_id: str):
    """Retourne le statut et la metadata du run."""
    return store.get_metadata(run_id)


@app.get("/runs")
def list_runs():
    """Liste tous les runs passes."""
    return {"runs": runs.get_all_runs()}


@app.get("/datasets")
def list_datasets():
    """Liste les datasets locaux disponibles pour l'interface."""
    if not DATA_DIR.exists():
        return {"datasets": []}

    datasets = []
    for path in sorted(DATA_DIR.iterdir()):
        if not path.is_file():
            continue
        datasets.append({
            "name": path.name,
            "path": str(Path("data") / path.name).replace("\\", "/"),
            "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
        })
    return {"datasets": datasets}


@app.get("/run/{run_id}/artifacts")
def get_run_artifacts(run_id: str):
    """Retourne les chemins principaux des artifacts produits par un run."""
    artifacts_dir = RUNS_DIR / run_id / "artifacts"
    if not artifacts_dir.exists():
        return {"run_id": run_id, "artifacts": []}

    items = []
    for path in sorted(artifacts_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(RUNS_DIR / run_id).as_posix()
        items.append({
            "name": path.name,
            "type": path.suffix.lower().lstrip(".") or "file",
            "path": str(path.relative_to(BASE_DIR)).replace("\\", "/"),
            "url": f"/runs-files/{run_id}/{rel}",
            "size_kb": round(path.stat().st_size / 1024, 1),
        })
    return {"run_id": run_id, "artifacts": items}


@app.get("/run/{run_id}/tool-calls")
def get_tool_calls(run_id: str):
    """Retourne les appels MCP traces pour l'audit UI."""
    path = RUNS_DIR / run_id / "tool_calls.jsonl"
    if not path.exists():
        return {"tool_calls": []}

    import json

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"raw": line})
    return {"tool_calls": rows[-80:]}
