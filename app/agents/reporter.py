from app.agents.base_agent import BaseAgent
from app.mcp.schemas import get_schemas_for_agent


class ReporterAgent(BaseAgent):
    """
    Agent responsable de la compilation du rapport final PDF.
    Gère l'étape : reporter.
    Codé par P4.
    """

    agent_name = "reporter"

    system_prompt = """
Tu es le Reporter du pipeline analytics.

Ton rôle :
1. Collecter tous les résultats du run (qualité, KPIs, dashboard)
2. Appeler compile_report pour générer le rapport PDF
3. Appeler log_artifact pour sauvegarder le rapport

Le rapport PDF doit contenir :
- Résumé exécutif (objectif du run)
- Data Quality Score et problèmes détectés
- KPIs business calculés
- Alertes déclenchées
- Référence au dashboard interactif
- Décisions prises par chaque agent

Toujours retourner un JSON avec :
- report_path  : chemin vers le PDF généré
- summary      : résumé en 2-3 phrases
"""

    def run(self, step: str, context: dict) -> dict:
        run_id    = context.get("run_id", "")
        objective = context.get("objective", "")
        artifacts = context.get("artifacts", {})

        tools = get_schemas_for_agent(self.agent_name)

        messages = [{
            "role": "user",
            "content": f"""
Étape demandée : {step}
Run ID : {run_id}
Objectif original : {objective}
Artifacts produits : {list(artifacts.keys())}

Génère le rapport PDF final pour ce run.
Retourne un JSON avec report_path et summary.
"""
        }]

        result_text = self._run_loop(messages, tools, run_id)

        return self._parse_result(result_text, run_id)

    def _parse_result(self, text: str, run_id: str) -> dict:
        import json, re
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        return {
            "report_path": f"runs/{run_id}/artifacts/report.pdf",
            "summary":     text[:300],
        }
