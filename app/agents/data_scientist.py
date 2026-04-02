from app.agents.base_agent import BaseAgent
from app.mcp.schemas import get_schemas_for_agent
import os


class DataScientistAgent(BaseAgent):
    """
    Agent responsable du calcul des KPIs business.
    Gère l'étape : kpi_calculator.
    Codé par P2.
    """

    agent_name = "kpi_calculator"

    system_prompt = """
Tu es un Data Scientist expert en KPIs e-commerce.

Ton rôle :
1. Appelle run_analysis sur le fichier nettoyé
2. Identifie les alertes (KPIs hors seuils)
3. Prépare les insights pour le BI Agent
4. Appelle log_artifact pour sauvegarder les insights

KPIs à calculer obligatoirement :
- CA total et par mois
- CA par pays (top 10)
- Taux d'annulation
- Nombre de clients uniques
- Panier moyen par commande
- Top 10 produits par revenue
- Data Quality Score

Seuils d'alerte :
- Taux annulation > 5%  → warning
- Taux annulation > 10% → critical

Toujours retourner un JSON avec :
- kpis        : dictionnaire de tous les KPIs calculés
- alertes     : liste des alertes déclenchées
- insights    : liste de 3 insights textuels
- output_path : chemin du fichier insights.json sauvegardé
"""

    def run(self, step: str, context: dict) -> dict:
        run_id    = context.get("run_id", "")
        artifacts = context.get("artifacts", {})

        # Récupérer le fichier nettoyé produit par le Data Engineer
        cleaned_file = artifacts.get("data_engineer", {}).get("output_path", "")
        if not cleaned_file:
            cleaned_file = f"runs/{run_id}/artifacts/cleaned_data.csv"

        output_path = f"runs/{run_id}/artifacts/insights.json"

        tools = get_schemas_for_agent(self.agent_name)

        messages = [{
            "role": "user",
            "content": f"""
Étape demandée : {step}
Fichier nettoyé à analyser : {cleaned_file}
Fichier de sortie insights : {output_path}
Run ID : {run_id}

Calcule tous les KPIs, détecte les alertes, et sauvegarde les insights.
Retourne un JSON avec kpis, alertes, insights, output_path.
"""
        }]

        result_text = self._run_loop(messages, tools, run_id)

        return self._parse_result(result_text, output_path)

    def _parse_result(self, text: str, output_path: str) -> dict:
        import json, re
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        return {
            "output_path": output_path,
            "summary":     text[:300],
            "kpis":        {},
            "alertes":     [],
        }
