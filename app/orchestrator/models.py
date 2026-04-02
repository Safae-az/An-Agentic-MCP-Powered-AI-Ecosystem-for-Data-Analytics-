# from pydantic import BaseModel
# from datetime import datetime
# import uuid


# class RunState(BaseModel):
#     run_id:          str  = ""
#     objective:       str  = ""
#     dataset_path:    str  = ""
#     status:          str  = "pending"
#     current_step:    str  = ""
#     completed_tasks: list = []
#     failed_tasks:    list = []
#     artifacts:       list = []
#     started_at:      str  = ""
#     finished_at:     str  = ""

#     @staticmethod
#     def create(objective: str, dataset_path: str) -> "RunState":
#         return RunState(
#             run_id       = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
#             objective    = objective,
#             dataset_path = dataset_path,
#             status       = "running",
#             started_at   = datetime.now().isoformat()
#         )


# class Task(BaseModel):
#     task_id:         str  = ""
#     agent_name:      str  = ""
#     goal:            str  = ""
#     input_refs:      list = []
#     expected_output: str  = ""
#     status:          str  = "pending"
#     retries:         int  = 0
#     result:          dict = {}

#     @staticmethod
#     def create(agent: str, goal: str, inputs: list, expected: str) -> "Task":
#         return Task(
#             task_id         = str(uuid.uuid4())[:8],
#             agent_name      = agent,
#             goal            = goal,
#             input_refs      = inputs,
#             expected_output = expected,
#             status          = "pending"
#         )


# class Artifact(BaseModel):
#     artifact_id: str  = ""
#     type:        str  = ""
#     path:        str  = ""
#     producer:    str  = ""
#     metadata:    dict = {}


# class ToolCall(BaseModel):
#     agent_name: str
#     tool_name:  str
#     input:      dict
#     output:     dict
#     success:    bool
#     timestamp:  str = ""
#     error:      str = ""
# app/orchestrator/models.py
from typing import Optional, List, Dict, Any

class RunState:
    """La mémoire du run — partagée entre tous les agents."""

    def __init__(self, run_id: str, file_path: str):
        self.run_id    = run_id
        self.file_path = file_path
        self.completed : List[str]       = []
        self.current   : Optional[str]   = None
        self.pending   : List[str]       = [
            "data_engineer",
            "data_scientist",
            "bi_agent",
            "reporter"
        ]
        self.artifacts : Dict[str, str]  = {}
        self.errors    : List[str]       = []
        self.status    : str             = "running"

    def mark_done(self, task: str, artifacts: dict = {}):
        """Marque une tâche comme terminée."""
        self.completed.append(task)
        self.artifacts.update(artifacts)
        if task in self.pending:
            self.pending.remove(task)
        self.current = None

    def next_task(self) -> Optional[str]:
        """Retourne la prochaine tâche à faire."""
        if self.pending:
            return self.pending[0]
        return None

    def is_finished(self) -> bool:
        """Vérifie si tout est terminé."""
        return len(self.pending) == 0

    def summary(self) -> dict:
        """Résumé de l'état actuel."""
        return {
            "run_id"    : self.run_id,
            "status"    : self.status,
            "completed" : self.completed,
            "pending"   : self.pending,
            "artifacts" : self.artifacts
        }