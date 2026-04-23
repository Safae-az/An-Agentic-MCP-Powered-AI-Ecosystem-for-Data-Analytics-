
# app/orchestrator/router.py
from app.agents.data_engineer  import DataEngineerAgent
from app.agents.data_scientist import DataScientistAgent


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

        # bi_agent et reporter seront ajoutés par P3 et P4
        else:
            print(f"[Router] Agent '{task_name}' pas encore disponible — skip")
            return None
