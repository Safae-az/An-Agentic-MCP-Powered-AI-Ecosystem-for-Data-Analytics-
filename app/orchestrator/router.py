# # Associe chaque étape du pipeline à son agent
# STEP_TO_AGENT = {
#     "data_quality":   "data_engineer",
#     "data_engineer":  "data_engineer",
#     "kpi_calculator": "data_scientist",
#     "bi_agent":       "bi_agent",
#     "reporter":       "reporter",
# }


# class Router:
#     """
#     Reçoit le nom d'une étape et retourne
#     le nom de l'agent qui doit l'exécuter.
#     """

#     def pick_agent(self, step: str) -> str:
#         agent = STEP_TO_AGENT.get(step)
#         if not agent:
#             raise ValueError(f"Aucun agent trouvé pour l'étape '{step}'")
#         return agent


# app/orchestrator/router.py
from app.agents.data_engineer import DataEngineerAgent

class Router:
    """
    Décide QUI fait la tâche.
    Reçoit un nom de tâche et retourne le bon agent.
    """

    def get_agent(self, task_name: str, run_id: str):
        """
        Table de correspondance tâche → agent.
        Exemple :
            "data_engineer" → DataEngineerAgent
        """
        print(f"[Router] Tache '{task_name}' → agent correspondant")

        if task_name == "data_engineer":
            return DataEngineerAgent(run_id=run_id)

        # Les autres agents seront ajoutés par P2/P3/P4
        # quand ils auront codé leurs agents
        else:
            print(f"[Router] Agent '{task_name}' pas encore disponible — skip")
            return None