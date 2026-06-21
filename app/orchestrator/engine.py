# app/orchestrator/engine.py
from app.orchestrator.models  import RunState
from app.orchestrator.planner import Planner
from app.orchestrator.router  import Router
from app.agents.devops_agent  import DevOpsAgent
import json
import os
import uuid


class Engine:
    """
    La boucle principale du pipeline.
    Ordre : data_engineer → data_scientist → bi_agent → reporter
    Le DevOpsAgent supervise chaque étape : retry / skip / escalate.
    """

    def __init__(self):
        self.planner = Planner()
        self.router  = Router()
        self.devops  = DevOpsAgent()

    def run(self, file_path: str, run_id: str) -> dict:

        print(f"\n{'='*55}")
        print(f"  ENGINE DEMARRE — run_id : {run_id}")
        print(f"  Fichier : {file_path}")
        print(f"{'='*55}\n")

        state = RunState(run_id=run_id, file_path=file_path)
        print(f"[Engine] Taches a faire : {state.pending}\n")

        context = {
            "run_id"      : run_id,
            "dataset_path": file_path,
            "artifacts"   : {},
        }

        while not state.is_finished():
            task = self.planner.next_task(state)
            if not task:
                break

            state.current = task
            print(f"\n[Engine] Lancement : {task}")

            should_stop = self._run_task(task, run_id, state, context, file_path)
            if should_stop:
                break

        state.status = "completed" if not state.errors else "failed"

        print(f"\n{'='*55}")
        print(f"  PIPELINE TERMINE — statut : {state.status}")
        print(f"  Taches terminees : {state.completed}")
        print(f"{'='*55}\n")

        self._save_summary(state)
        return state.summary()

    # ──────────────────────────────────────────────────────────────
    # DevOps supervision layer
    # ──────────────────────────────────────────────────────────────

    def _run_task(self, task: str, run_id: str, state: RunState,
                  context: dict, file_path: str) -> bool:
        """
        Execute a task with DevOps retry / skip / escalate supervision.
        Returns True if the pipeline must stop (escalate).
        """
        retries = 0

        while True:
            agent = self.router.get_agent(task, run_id)
            if agent is None:
                print(f"[Engine] Skip '{task}' — agent non disponible")
                state.mark_done(task + "_skipped", {})
                if task in state.pending:
                    state.pending.remove(task)
                return False

            error = None
            try:
                error = self._execute_agent(task, agent, run_id, state, context, file_path)
            except Exception as e:
                error = str(e)
                print(f"[Engine] Exception dans '{task}' : {e}")

            if error is None:
                return False  # success — move on

            # ── Failure → ask DevOps ──────────────────────────────
            decision = self.devops.handle_failure(task, error, run_id, retries)
            action   = decision.get("action", "escalate")

            if action == "retry" and retries < self.devops.MAX_RETRIES:
                retries += 1
                print(f"[Engine] Retry {retries}/{self.devops.MAX_RETRIES} pour '{task}'...")
                continue

            elif action == "skip":
                print(f"[Engine] '{task}' skipped sur decision DevOps — pipeline continue")
                if task in state.pending:
                    state.pending.remove(task)
                state.completed.append(task + "_skipped")
                return False

            else:  # escalate
                state.errors.append(f"{task}: {error}")
                print(f"[Engine] Escalade sur '{task}' — pipeline arrete")
                print(f"[Engine] Suggestion : {decision.get('suggestion', '')}")
                return True

    # ──────────────────────────────────────────────────────────────
    # Per-agent execution (returns None on success, error str on failure)
    # ──────────────────────────────────────────────────────────────

    def _execute_agent(self, task: str, agent, run_id: str, state: RunState,
                       context: dict, file_path: str):

        # ── data_engineer ─────────────────────────────────────────
        if task == "data_engineer":
            result = agent.run(file_path)

            if result.get("status") == "success":
                clean_path = result["clean_path"]
                state.mark_done(task, {
                    "clean_csv"    : clean_path,
                    "quality_score": str(result.get("quality_score", "")),
                    "final_rows"   : str(result.get("final_rows", "")),
                })
                context["artifacts"]["last_file"]     = clean_path
                context["artifacts"]["data_engineer"] = result
                print(f"[Engine] '{task}' termine ✓")
                print(f"[Engine] Artifact : {clean_path}")
                return None

            return result.get("error", "Erreur inconnue")

        # ── data_scientist ────────────────────────────────────────
        elif task == "data_scientist":
            ds_context = {
                "run_id"      : run_id,
                "dataset_path": file_path,
                "artifacts"   : context["artifacts"],
            }
            result = agent.run(step=task, context=ds_context)

            if result.get("status") == "success":
                kpis   = result.get("kpis", {})
                ca_val = None
                for key in ["CA_total", "total_sales", "total_revenue", "revenu_total"]:
                    val = kpis.get(key)
                    if val is not None:
                        ca_val = val.get("total") if isinstance(val, dict) else val
                        break

                domain = (
                    result.get("domain") or
                    kpis.get("domain_detected") or
                    "unknown"
                )

                state.mark_done(task, {
                    "insights_json": result.get("output_path", ""),
                    "nb_kpis"      : str(len(kpis)),
                    "domain"       : str(domain),
                    "CA_total"     : str(ca_val) if ca_val is not None else "N/A",
                })
                context["artifacts"]["last_file"]      = result.get("output_path", "")
                context["artifacts"]["data_scientist"] = result

                print(f"[Engine] '{task}' termine ✓")
                print(f"[Engine] Domaine  : {domain}")
                print(f"[Engine] Nb KPIs  : {len(kpis)}")
                print(f"[Engine] CA total : {ca_val if ca_val is not None else 'N/A'}")
                return None

            return result.get("message", result.get("error", "Erreur inconnue"))

        # ── bi_agent ──────────────────────────────────────────────
        elif task == "bi_agent":
            bi_context = {
                "run_id"      : run_id,
                "dataset_path": file_path,
                "artifacts"   : context["artifacts"],
            }
            result = agent.run(step=task, context=bi_context)

            if result.get("success"):
                state.mark_done(task, {
                    "dashboard_path": result.get("dashboard_path", ""),
                    "nb_charts"     : str(len(result.get("charts", []))),
                    "handoff_path"  : result.get("handoff_path", ""),
                })
                context["artifacts"]["last_file"] = result.get("dashboard_path", "")
                context["artifacts"]["bi_agent"]  = result
                print(f"[Engine] '{task}' termine ✓ — {len(result.get('charts', []))} charts")
                print(f"[Engine] Dashboard : {result.get('dashboard_path', 'N/A')}")
                return None

            return result.get("error", result.get("summary", "Erreur inconnue"))

        # ── reporter ──────────────────────────────────────────────
        elif task == "reporter":
            reporter_context = {
                "run_id"      : run_id,
                "dataset_path": file_path,
                "artifacts"   : context["artifacts"],
            }
            result = agent.run(step=task, context=reporter_context)

            if result.get("status") == "success" or result.get("generated"):
                report_path = result.get("report_path", "")
                state.mark_done(task, {
                    "report_path": report_path,
                    "summary"    : result.get("summary", ""),
                })
                context["artifacts"]["last_file"] = report_path
                context["artifacts"]["reporter"]  = result
                print(f"[Engine] '{task}' termine ✓")
                print(f"[Engine] Rapport : {report_path}")
                return None

            return result.get("error", result.get("summary", "Erreur inconnue"))

        return f"Tache '{task}' non reconnue"

    # ──────────────────────────────────────────────────────────────

    def _save_summary(self, state: RunState):
        run_dir = f"runs/{state.run_id}"
        os.makedirs(run_dir, exist_ok=True)
        path = f"{run_dir}/metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.summary(), f, indent=2, ensure_ascii=False)
        print(f"[Engine] Metadata sauvegarde : {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Module-level entry point imported by main.py
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline(file_path: str, objective: str, run_id: str | None = None) -> dict:
    run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
    print(f"\n[run_pipeline] Nouveau run : {run_id}")
    print(f"[run_pipeline] Objectif    : {objective}")
    engine = Engine()
    result = engine.run(file_path=file_path, run_id=run_id)
    result["objective"] = objective
    return result
