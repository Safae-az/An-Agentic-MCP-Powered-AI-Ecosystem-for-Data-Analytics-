import os, json
from datetime import datetime
from app.orchestrator.models import RunState, Artifact, ToolCall


class ArtifactStore:

    def __init__(self, base_dir: str = "runs"):
        self.base_dir = base_dir

    def init_run(self, state: RunState) -> str:
        run_path = f"{self.base_dir}/{state.run_id}"
        os.makedirs(f"{run_path}/artifacts/charts", exist_ok=True)
        with open(f"{run_path}/metadata.json", "w") as f:
            json.dump(state.dict(), f, indent=2)
        print(f"📁 Artifact Store créé : {run_path}")
        return run_path

    def save_artifact(self, run_id: str, artifact: Artifact):
        path = f"{self.base_dir}/{run_id}/artifacts.json"
        artifacts = []
        if os.path.exists(path):
            with open(path) as f:
                artifacts = json.load(f)
        artifacts.append(artifact.dict())
        with open(path, "w") as f:
            json.dump(artifacts, f, indent=2)

    def log_tool_call(self, run_id: str, call: ToolCall):
        path = f"{self.base_dir}/{run_id}/tool_calls.jsonl"
        with open(path, "a") as f:
            entry = call.dict()
            entry["timestamp"] = datetime.now().isoformat()
            f.write(json.dumps(entry) + "\n")

    def log_decision(self, run_id: str, agent: str, decision: str, reason: str):
        path = f"{self.base_dir}/{run_id}/decisions.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "agent":     agent,
                "decision":  decision,
                "reason":    reason
            }) + "\n")

    def update_status(self, run_id: str, status: str, step: str = ""):
        path = f"{self.base_dir}/{run_id}/metadata.json"
        if not os.path.exists(path):
            return
        with open(path) as f:
            meta = json.load(f)
        meta["status"]       = status
        meta["current_step"] = step
        if status in ["completed", "failed"]:
            meta["finished_at"] = datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)

    def get_logs(self, run_id: str) -> list:
        path = f"{self.base_dir}/{run_id}/decisions.jsonl"
        if not os.path.exists(path):
            return []
        logs = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    logs.append(json.loads(line))
        return logs

    def get_metadata(self, run_id: str) -> dict:
        path = f"{self.base_dir}/{run_id}/metadata.json"
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            return json.load(f)

    def list_runs(self) -> list:
        if not os.path.exists(self.base_dir):
            return []
        runs = []
        for name in sorted(os.listdir(self.base_dir), reverse=True):
            meta_path = f"{self.base_dir}/{name}/metadata.json"
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    runs.append(json.load(f))
        return runs
