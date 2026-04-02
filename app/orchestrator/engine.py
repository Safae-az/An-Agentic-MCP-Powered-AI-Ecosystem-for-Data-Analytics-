# import json
# from app.orchestrator.models import RunState
# from app.orchestrator.state   import StateManager
# from app.orchestrator.planner import Planner
# from app.orchestrator.router  import Router
# from app.storage.artifact_store import ArtifactStore

# store   = ArtifactStore()
# planner = Planner()
# router  = Router()


# def run_pipeline(dataset_path: str, objective: str) -> dict:
#     """
#     Point d'entrée principal du pipeline.
#     Lance tous les agents dans l'ordre et retourne le résultat final.
#     """

#     # ── 1. Initialiser le run ─────────────────────────────────────
#     sm = StateManager()
#     state = sm.init(objective, dataset_path)
#     store.init_run(state)

#     print(f"\n{'='*55}")
#     print(f"  🚀 RUN DÉMARRÉ : {state.run_id}")
#     print(f"  Objectif : {objective}")
#     print(f"{'='*55}\n")

#     context = {
#         "dataset_path": dataset_path,
#         "objective":    objective,
#         "run_id":       state.run_id,
#         "artifacts":    {},
#     }

#     max_steps = 10
#     step_count = 0

#     # ── 2. Boucle principale ──────────────────────────────────────
#     while not planner.is_pipeline_complete(sm) and step_count < max_steps:
#         step_count += 1

#         next_step = planner.decide_next_step(sm)
#         if not next_step:
#             break

#         agent_name = router.pick_agent(next_step)

#         print(f"📋 Étape {step_count} : {next_step}  →  agent : {agent_name}")
#         store.log_decision(state.run_id, "orchestrator", next_step, f"Délégation à {agent_name}")

#         store.update_status(state.run_id, "running", next_step)

#         # ── 3. Lancer l'agent ─────────────────────────────────────
#         result = _run_agent(agent_name, next_step, context)

#         if result.get("error"):
#             error_msg = result["error"]
#             print(f"  ❌ Échec : {error_msg}")
#             store.log_decision(state.run_id, agent_name, "failed", error_msg)

#             # DevOps : retry une fois
#             if sm.state.failed_tasks.count({"step": next_step}) < 1:
#                 print(f"  🔄 DevOps retry sur {next_step}...")
#                 result = _run_agent(agent_name, next_step, context)

#             if result.get("error"):
#                 sm.mark_failed(next_step, error_msg)
#                 print(f"  ⚠️  Étape {next_step} skippée après 2 échecs")
#                 continue
        
#         # ── 4. Succès : sauvegarder le résultat ───────────────────
#         context["artifacts"][next_step] = result
#         sm.mark_completed(next_step, result)

#         # Propager les chemins de fichiers importants
#         if "output_path" in result:
#             context["artifacts"]["last_file"] = result["output_path"]
#         if "dashboard_path" in result:
#             context["artifacts"]["dashboard"] = result["dashboard_path"]
#         if "report_path" in result:
#             context["artifacts"]["report"] = result["report_path"]

#         print(f"  ✅ {next_step} terminé\n")

#     # ── 5. Fin du pipeline ────────────────────────────────────────
#     if planner.is_pipeline_complete(sm):
#         store.update_status(state.run_id, "completed", "done")
#         print(f"\n{'='*55}")
#         print(f"  ✅ PIPELINE TERMINÉ : {state.run_id}")
#         print(f"{'='*55}\n")
#         status = "completed"
#     else:
#         store.update_status(state.run_id, "failed", "incomplete")
#         status = "failed"

#     return {
#         "status":    status,
#         "run_id":    state.run_id,
#         "artifacts": context["artifacts"],
#         "steps_done": sm.get_completed_steps(),
#     }


# def _run_agent(agent_name: str, step: str, context: dict) -> dict:
#     """Importe et lance dynamiquement le bon agent."""
#     try:
#         if agent_name == "data_engineer":
#             from app.agents.data_engineer import DataEngineerAgent
#             agent = DataEngineerAgent()
#         elif agent_name == "data_scientist":
#             from app.agents.data_scientist import DataScientistAgent
#             agent = DataScientistAgent()
#         elif agent_name == "bi_agent":
#             from app.agents.bi_agent import BIAgent
#             agent = BIAgent()
#         elif agent_name == "reporter":
#             from app.agents.reporter import ReporterAgent
#             agent = ReporterAgent()
#         else:
#             return {"error": f"Agent '{agent_name}' inconnu"}

#         return agent.run(step=step, context=context)

#     except Exception as e:
#         return {"error": str(e)}



# app/orchestrator/engine.py
from app.orchestrator.models  import RunState
from app.orchestrator.planner import Planner
from app.orchestrator.router  import Router
import json, os

class Engine:
    """
    La boucle principale du pipeline.
    Tourne jusqu'à ce que tout soit terminé.
    """

    def __init__(self):
        self.planner = Planner()
        self.router  = Router()

    def run(self, file_path: str, run_id: str) -> dict:
        """
        Lance le pipeline complet.
        Entrée : fichier CSV + run_id
        Sortie : résumé du run
        """
        print(f"\n{'='*55}")
        print(f"  ENGINE DEMARRE — run_id : {run_id}")
        print(f"  Fichier : {file_path}")
        print(f"{'='*55}\n")

        # 1. Créer l'état initial du run
        state = RunState(run_id=run_id, file_path=file_path)
        print(f"[Engine] State cree")
        print(f"[Engine] Taches a faire : {state.pending}\n")

        # 2. Boucle principale — tourne jusqu'à la fin
        while not state.is_finished():

            # Planner décide quoi faire
            task = self.planner.next_task(state)
            if not task:
                break

            # Marquer comme en cours
            state.current = task
            print(f"\n[Engine] Lancement de la tache : {task}")
            print(f"[Engine] Progression : {state.completed} → [{task}] → {state.pending[1:]}")

            # Router choisit le bon agent
            agent = self.router.get_agent(task, run_id)

            if agent is None:
                # Agent pas encore codé — on skip pour l'instant
                print(f"[Engine] Skip '{task}' — agent non disponible\n")
                state.pending.remove(task)
                state.completed.append(task + "_skipped")
                continue

            # Lancer l'agent avec les bonnes données
            try:
                if task == "data_engineer":
                    result = agent.run(file_path)

                    if result["status"] == "success":
                        # Mettre à jour le state avec ce que l'agent a produit
                        state.mark_done(task, {
                            "clean_csv"     : result["clean_path"],
                            "quality_score" : str(result["quality_score"]),
                            "final_rows"    : str(result["final_rows"])
                        })
                        print(f"[Engine] '{task}' termine ✓")
                        print(f"[Engine] Artifact produit : {result['clean_path']}")
                    else:
                        print(f"[Engine] ERREUR dans '{task}'")
                        state.errors.append(task)
                        break

            except Exception as e:
                print(f"[Engine] Exception dans '{task}' : {e}")
                state.errors.append(str(e))
                break

        # 3. Fin du pipeline
        state.status = "completed" if not state.errors else "failed"

        print(f"\n{'='*55}")
        print(f"  PIPELINE TERMINE — statut : {state.status}")
        print(f"  Taches terminees : {state.completed}")
        print(f"  Artifacts produits :")
        for key, val in state.artifacts.items():
            print(f"    {key} : {val}")
        print(f"{'='*55}\n")

        # Sauvegarder le résumé du run
        self._save_summary(state)

        return state.summary()

    def _save_summary(self, state: RunState):
        """Sauvegarde le résumé du run dans metadata.json"""
        run_dir = f"runs/{state.run_id}"
        os.makedirs(run_dir, exist_ok=True)
        path = f"{run_dir}/metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.summary(), f, indent=2, ensure_ascii=False)
        print(f"[Engine] Metadata sauvegarde : {path}")