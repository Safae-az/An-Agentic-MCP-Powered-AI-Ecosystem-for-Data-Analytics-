# app/orchestrator/router.py
from app.agents.data_engineer  import DataEngineerAgent
from app.agents.data_scientist import DataScientistAgent
from app.agents.bi_agent       import BIAgent
from app.agents.reporter       import ReporterAgent


class Router:
    """
    Décide QUI fait la tâche.
    Reçoit un nom de tâche et retourne le bon agent instancié.
    """

    def get_agent(self, task_name: str, run_id: str):
        print(f"[Router] Tache '{task_name}' → agent correspondant")

        if task_name == "data_engineer":
            return DataEngineerAgent(run_id=run_id)

        elif task_name == "data_scientist":
            return DataScientistAgent(run_id=run_id)

        elif task_name == "bi_agent":
            return BIAgent(run_id=run_id)

        elif task_name == "reporter":
            return ReporterAgent(run_id=run_id)

        else:
            print(f"[Router] Agent '{task_name}' pas encore disponible — skip")
            return None
