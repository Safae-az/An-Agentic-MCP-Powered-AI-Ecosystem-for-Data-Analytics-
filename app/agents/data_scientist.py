 import json
import re
from app.agents.base_agent import BaseAgent

DATA_SCIENTIST_TOOLS = [
    {
        "name": "run_analysis",
        "description": (
            "Analyse complète du dataset e-commerce nettoyé. Calcule les KPIs business : "
            "CA total, CA par mois, CA par pays, panier moyen, taux annulation, "
            "top 10 produits. Génère alertes warning/critical et insights textuels. "
            "Sauvegarde tout dans runs/{run_id}/artifacts/insights.json."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Chemin vers le fichier CSV nettoyé à analyser."
                },
                "run_id": {
                    "type": "string",
                    "description": "Identifiant du run en cours (ex: 'run_002')."
                }
            },
            "required": ["file_path", "run_id"]
        }
    }
]


class DataScientistAgent(BaseAgent):

    agent_name = "data_scientist"

    def __init__(self, run_id: str = ""):
        self.agent_name   = "data_scientist"
        self.system_prompt = """Tu es un Data Scientist expert en KPI Business Analytics.

Ton rôle :
1. Appeler run_analysis avec file_path et run_id.
2. Retourner UNIQUEMENT un JSON valide avec ces champs :
{
  "success"      : true,
  "output_path"  : "runs/{run_id}/artifacts/insights.json",
  "kpis"         : { "CA_total": ..., "panier_moyen": ..., ... },
  "alertes"      : [ { "kpi": ..., "niveau": ..., "message": ... } ],
  "insights"     : [ "phrase 1", "phrase 2" ],
  "chart_hints"  : [ { "chart_id": "chart1", "type": "line", "title": "CA mensuel" } ]
}

Règles :
- Appelle TOUJOURS run_analysis — ne calcule jamais toi-même.
- Réponds UNIQUEMENT avec le JSON, sans texte autour."""

        super().__init__(run_id=run_id)

    def run(self, step: str, context: dict) -> dict:

        run_id = context.get("run_id", "run_unknown")

        file_path = (
            context.get("artifacts", {}).get("last_file")
            or context.get("artifacts", {}).get("data_engineer", {}).get("clean_path")
            or context.get("dataset_path", "")
        )

        if not file_path:
            return {
                "success": False,
                "error"  : "Aucun fichier nettoyé trouvé dans le contexte.",
                "kpis"   : {}, "alertes": [], "insights": [], "chart_hints": []
            }

        print(f"\n[data_scientist] run={run_id} | fichier={file_path}")

        messages = [{
            "role": "user",
            "content": (
                f"Analyse le dataset e-commerce nettoyé.\n"
                f"file_path : {file_path}\n"
                f"run_id    : {run_id}\n\n"
                f"Appelle run_analysis puis retourne le JSON complet."
            )
        }]

        raw_output = self._run_loop(messages, DATA_SCIENTIST_TOOLS, run_id)
        print(f"[data_scientist] Terminé.")

        result = self._parse_output(raw_output, run_id)
        return result

    def _parse_output(self, raw: str, run_id: str) -> dict:
        # Essai 1 : JSON dans bloc ```json
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Essai 2 : JSON brut
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback : lire insights.json directement sur disque
        import os
        insights_path = f"runs/{run_id}/artifacts/insights.json"
        if os.path.exists(insights_path):
            print(f"[data_scientist] Fallback — lecture de {insights_path}")
            with open(insights_path) as f:
                data = json.load(f)
            return {
                "success"    : True,
                "output_path": insights_path,
                "kpis"       : data.get("kpis", {}),
                "alertes"    : data.get("alertes", []),
                "insights"   : data.get("insights", []),
                "chart_hints": data.get("chart_hints", []),
            }

        return {
            "success"    : False,
            "error"      : "Parsing échoué et insights.json introuvable.",
            "raw_output" : raw,
            "kpis"       : {}, "alertes": [], "insights": [], "chart_hints": []
        }
