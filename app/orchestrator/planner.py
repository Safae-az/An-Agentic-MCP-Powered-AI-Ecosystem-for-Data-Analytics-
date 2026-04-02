# from app.orchestrator.state import StateManager


# # Ordre fixe du pipeline
# PIPELINE_STEPS = [
#     "data_quality",
#     "data_engineer",
#     "kpi_calculator",
#     "bi_agent",
#     "reporter",
# ]


# class Planner:
#     """
#     Décide quelle est la prochaine étape à exécuter
#     en regardant ce qui est déjà fait dans le StateManager.
#     """

#     def decide_next_step(self, state_manager: StateManager) -> str | None:
#         completed = state_manager.get_completed_steps()
#         failed    = [t["step"] for t in state_manager.state.failed_tasks]

#         for step in PIPELINE_STEPS:
#             if step not in completed and step not in failed:
#                 return step

#         return None  # tout est fait

#     def is_pipeline_complete(self, state_manager: StateManager) -> bool:
#         completed = state_manager.get_completed_steps()
#         return all(step in completed for step in PIPELINE_STEPS)

#     def get_remaining_steps(self, state_manager: StateManager) -> list:
#         completed = state_manager.get_completed_steps()
#         return [s for s in PIPELINE_STEPS if s not in completed]
  

# app/orchestrator/planner.py
from app.orchestrator.models import RunState
from typing import Optional

class Planner:
    """
    Décide QUOI faire ensuite.
    Regarde l'état du run et retourne la prochaine tâche.
    """

    def next_task(self, state: RunState) -> Optional[str]:
        """
        Regarde ce qui est déjà fait et décide la suite.
        Exemple :
            completed = []                → "data_engineer"
            completed = ["data_engineer"] → "data_scientist"
        """
        tache = state.next_task()

        if tache:
            print(f"[Planner] Prochaine tache : {tache}")
        else:
            print(f"[Planner] Tout est termine !")

        return tache