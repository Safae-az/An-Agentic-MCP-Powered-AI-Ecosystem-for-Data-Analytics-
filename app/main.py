from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.orchestrator.engine import run_pipeline
from app.storage.artifact_store import ArtifactStore
from app.storage.run_store import RunStore
import shutil, os

load_dotenv()

app   = FastAPI(title="KPI Monitoring System")
store = ArtifactStore()
runs  = RunStore()

# Autoriser les appels depuis l'UI (P4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "KPI Monitoring System — En ligne ✅"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run/start")
async def start_run(
    file:      UploadFile = File(...),
    objective: str        = Form(...)
):
    """
    Point d'entrée principal.
    P4 appelle cet endpoint depuis l'UI pour lancer le pipeline.
    """
    # Sauvegarder le fichier uploadé
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Lancer le pipeline complet
    result = run_pipeline(file_path, objective)
    return result


@app.get("/run/{run_id}/logs")
def get_logs(run_id: str):
    """Retourne les logs en temps réel — utilisé par l'UI pour le monitoring."""
    return {"logs": store.get_logs(run_id)}


@app.get("/run/{run_id}/status")
def get_status(run_id: str):
    """Retourne le statut et la metadata du run."""
    return store.get_metadata(run_id)


@app.get("/runs")
def list_runs():
    """Liste tous les runs passés — pour l'historique dans l'UI."""
    return {"runs": runs.get_all_runs()}
