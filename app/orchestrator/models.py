
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
    
    # Ajouter à la fin de models.py

class Artifact:
    """Represente un fichier produit par un agent."""
    def __init__(self, name: str, path: str,
                 produced_by: str, artifact_type: str):
        self.name          = name
        self.path          = path
        self.produced_by   = produced_by
        self.artifact_type = artifact_type

class ToolCall:
    """Represente un appel d'outil MCP."""
    def __init__(self, agent: str, tool: str,
                 params: dict, run_id: str):
        self.agent  = agent
        self.tool   = tool
        self.params = params
        self.run_id = run_id
        self.result = None
        self.success = False

        self.success = False
