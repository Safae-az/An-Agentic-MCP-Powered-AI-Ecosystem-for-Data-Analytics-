from app.orchestrator.models import RunState


class StateManager:
    """
    Garde en mémoire l'état du run en cours.
    Permet à l'engine de savoir ce qui est fait, en cours, en attente.
    """

    def __init__(self):
        self.state: RunState = None

    def init(self, objective: str, dataset_path: str) -> RunState:
        self.state = RunState.create(objective, dataset_path)
        return self.state

    def mark_completed(self, step: str, result: dict = {}):
        if step not in self.state.completed_tasks:
            self.state.completed_tasks.append({"step": step, "result": result})
        self.state.current_step = step

    def mark_failed(self, step: str, error: str = ""):
        self.state.failed_tasks.append({"step": step, "error": error})

    def add_artifact(self, key: str, path: str):
        self.state.artifacts.append({"key": key, "path": path})

    def get_artifact(self, key: str) -> str:
        for a in self.state.artifacts:
            if a["key"] == key:
                return a["path"]
        return ""

    def is_step_done(self, step: str) -> bool:
        return any(t["step"] == step for t in self.state.completed_tasks)

    def get_completed_steps(self) -> list:
        return [t["step"] for t in self.state.completed_tasks]

    def to_dict(self) -> dict:
        return self.state.dict() if self.state else {}
