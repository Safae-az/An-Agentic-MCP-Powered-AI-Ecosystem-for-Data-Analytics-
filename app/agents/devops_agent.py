from app.agents.base_agent import BaseAgent
from app.storage.artifact_store import ArtifactStore

store = ArtifactStore()


class DevOpsAgent(BaseAgent):
    """
    Agent responsable de la surveillance et gestion des erreurs.
    Intervient quand un agent échoue.
    Codé par P1 (toi).
    """

    agent_name    = "devops"
    system_prompt = """
Tu es le DevOps du pipeline analytics.
Tu interviens uniquement quand une erreur est détectée.

Tes actions :
- Analyser l'erreur reçue
- Décider : retry / skip / escalate
- Logger l'incident

Retourne toujours un JSON :
{
  "action"     : "retry" | "skip" | "escalate",
  "reason"     : "explication",
  "suggestion" : "comment corriger"
}
"""

    def handle_failure(self, step: str, error: str, run_id: str, retries: int) -> dict:
        """
        Décide quoi faire en cas d'échec d'une étape.
        retries : nombre de tentatives déjà effectuées
        """
        store.log_decision(run_id, "devops", f"failure_{step}", error)

        # Logique de décision simple
        if retries < 2:
            decision = "retry"
            reason   = f"Première/deuxième tentative sur {step}"
        else:
            decision = "skip"
            reason   = f"Trop d'échecs sur {step}, on continue sans"

        store.log_decision(run_id, "devops", decision, reason)

        print(f"  🛠️  DevOps : {decision} sur {step} — {reason}")

        return {
            "action":     decision,
            "reason":     reason,
            "step":       step,
            "suggestion": "Vérifier le fichier d'entrée et les permissions"
        }

    def run(self, step: str, context: dict) -> dict:
        # Le DevOps n'est pas appelé directement dans le pipeline normal
        # Il est appelé par l'engine en cas d'erreur
        return {"status": "devops_ready"}
