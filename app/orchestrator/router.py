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
from app.agents.data_scientist import DataScientistAgent


class Router:
    def get_agent(self, task_name: str, run_id: str):

        if task_name == 'data_engineer':
            return DataEngineerAgent(run_id=run_id)

        if task_name == 'data_scientist':
            return DataScientistAgent(run_id=run_id)  # ← AJOUTER

        print(f"[Router] '{task_name}' pas encore disponible")
        return None

