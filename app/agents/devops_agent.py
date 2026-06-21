# app/agents/devops_agent.py
import json
import os
import time
from app.agents.base_agent import BaseAgent
from app.storage.artifact_store import ArtifactStore

store = ArtifactStore()

# Erreurs critiques → escalate immédiat sans retry
CRITICAL_ERRORS = [
    "fichier introuvable",
    "no such file",
    "permission denied",
    "api key",
    "authentication",
    "quota exceeded",
]

# Erreurs récupérables → retry
RETRYABLE_ERRORS = [
    "connection refused",
    "timeout",
    "max retries",
    "temporarily unavailable",
    "rate limit",
    "500",
    "502",
    "503",
]

DEVOPS_TOOLS = [
    {
        "name": "log_incident",
        "description": "Logger un incident DevOps dans l'Artifact Store.",
        "input_schema": {
            "type": "object",
            "properties": {
                "step":       {"type": "string", "description": "Étape qui a échoué"},
                "error":      {"type": "string", "description": "Message d'erreur"},
                "action":     {"type": "string", "description": "Action décidée : retry / skip / escalate"},
                "reason":     {"type": "string", "description": "Raison de la décision"},
                "suggestion": {"type": "string", "description": "Suggestion pour corriger"}
            },
            "required": ["step", "error", "action", "reason"]
        }
    }
]


class DevOpsAgent(BaseAgent):
    """
    Agent DevOps — surveillance, retry automatique, fallback et escalade.
    Intervient quand un agent échoue dans le pipeline.
    """

    agent_name    = "devops"
    system_prompt = """Tu es le DevOps Engineer du pipeline analytics.
Tu interviens uniquement quand une erreur est détectée.

Ton rôle :
1. Analyser l'erreur reçue
2. Décider l'action la plus appropriée :
   - "retry"   : erreur temporaire, réessayer (réseau, timeout, surcharge)
   - "skip"    : erreur persistante, continuer sans cette étape
   - "escalate": erreur critique bloquante (fichier manquant, clé API invalide)
3. Logger l'incident avec log_incident
4. Retourner un JSON clair avec ta décision

Retourne TOUJOURS un JSON valide :
{
  "action"     : "retry" | "skip" | "escalate",
  "reason"     : "explication courte",
  "suggestion" : "comment corriger le problème"
}"""

    MAX_RETRIES = int(os.getenv("DEVOPS_MAX_RETRIES", 2))

    def __init__(self, run_id: str = ""):
        super().__init__(run_id=run_id)

    def handle_failure(self, step: str, error: str, run_id: str, retries: int) -> dict:
        """
        Décide quoi faire en cas d'échec d'une étape.
        retries : nombre de tentatives déjà effectuées
        """
        print(f"\n  🛠️  [DevOps] Analyse échec — étape: {step} | tentative: {retries}")
        print(f"  🛠️  [DevOps] Erreur : {error[:100]}")

        # Logger l'incident
        store.log_decision(run_id, "devops", f"failure_{step}", error)

        # Étape 1 — Détection rapide des erreurs critiques
        error_lower = error.lower()

        if any(kw in error_lower for kw in CRITICAL_ERRORS):
            decision = self._decide_escalate(step, error, run_id)
            print(f"  🛠️  [DevOps] → ESCALATE (erreur critique)")
            return decision

        # Étape 2 — Trop de retries → skip
        if retries >= self.MAX_RETRIES:
            decision = self._decide_skip(step, error, run_id, retries)
            print(f"  🛠️  [DevOps] → SKIP (max retries atteint)")
            return decision

        # Étape 3 — Erreur récupérable → retry
        if any(kw in error_lower for kw in RETRYABLE_ERRORS):
            decision = self._decide_retry(step, error, run_id, retries)
            print(f"  🛠️  [DevOps] → RETRY (erreur temporaire)")
            return decision

        # Étape 4 — Erreur inconnue → LLM décide
        decision = self._llm_decide(step, error, run_id, retries)
        print(f"  🛠️  [DevOps] → {decision['action'].upper()} (décision LLM)")
        return decision

    def _decide_retry(self, step: str, error: str, run_id: str, retries: int) -> dict:
        decision = {
            "action"    : "retry",
            "reason"    : f"Erreur temporaire sur '{step}' (tentative {retries + 1}/{self.MAX_RETRIES})",
            "step"      : step,
            "suggestion": f"Vérifier la connexion réseau et le MCP Server. Erreur : {error[:120]}"
        }
        store.log_decision(run_id, "devops", "retry", decision["reason"])
        time.sleep(1)
        return decision

    def _decide_skip(self, step: str, error: str, run_id: str, retries: int) -> dict:
        decision = {
            "action"    : "skip",
            "reason"    : f"Trop d'échecs sur '{step}' ({retries} tentatives) — pipeline continue",
            "step"      : step,
            "suggestion": f"Erreur : {error[:120]} — vérifier les logs dans runs/{run_id}/"
        }
        store.log_decision(run_id, "devops", "skip", decision["reason"])
        return decision

    def _decide_escalate(self, step: str, error: str, run_id: str) -> dict:
        decision = {
            "action"    : "escalate",
            "reason"    : f"Erreur critique sur '{step}' — intervention manuelle requise",
            "step"      : step,
            "suggestion": f"Erreur : {error[:120]} — vérifier le fichier d'entrée, les permissions et la clé API"
        }
        store.log_decision(run_id, "devops", "escalate", decision["reason"])
        return decision

    def _llm_decide(self, step: str, error: str, run_id: str, retries: int) -> dict:
        """Utilise le LLM pour analyser une erreur inconnue."""
        try:
            messages = [{
                "role": "user",
                "content": (
                    f"Étape en échec : {step}\n"
                    f"Erreur : {error}\n"
                    f"Tentatives déjà effectuées : {retries}/{self.MAX_RETRIES}\n\n"
                    f"Analyse l'erreur et décide : retry, skip ou escalate.\n"
                    f"Retourne UNIQUEMENT le JSON de décision."
                )
            }]

            raw = self._run_loop(messages, DEVOPS_TOOLS, run_id)

            # Parser la réponse LLM
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
                result["step"] = step
                store.log_decision(run_id, "devops", result.get("action", "skip"), result.get("reason", ""))
                return result

        except Exception as e:
            print(f"  🛠️  [DevOps] LLM indisponible ({e}) — fallback skip")

        # Fallback si LLM échoue
        return self._decide_skip(step, error, run_id, retries)

    def run(self, step: str = "", context: dict = {}) -> dict:  # noqa: ARG002
        return {"status": "devops_ready", "agent": self.agent_name}
