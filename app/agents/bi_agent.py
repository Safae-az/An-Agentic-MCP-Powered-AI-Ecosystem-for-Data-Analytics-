from app.agents.base_agent import BaseAgent
from app.mcp.schemas import get_schemas_for_agent


class BIAgent(BaseAgent):
    """
    Agent responsable de la génération du dashboard.
    Gère l'étape : bi_agent.
    Codé par P3.
    """

    agent_name = "bi_agent"

    system_prompt = """
Tu es un expert en Business Intelligence et visualisation de données.

Ton rôle :
1. Lire les KPIs et insights produits par le Data Scientist
2. Décider quels graphiques créer (minimum 3)
3. Appeler generate_chart pour chaque graphique
4. Appeler publish_dashboard pour assembler le dashboard
5. Appeler log_artifact pour sauvegarder

Règles de sélection des graphiques :
- CA mensuel           → line chart  (tendance temporelle)
- CA par pays top 10   → bar chart   (comparaison)
- Répartition statuts  → pie chart   (composition)
- Top produits         → bar chart   (classement)

Le dashboard doit toujours contenir :
- Les KPIs principaux en haut (CA, clients, panier moyen)
- Les alertes en rouge/orange si présentes
- Minimum 3 graphiques interactifs

Toujours retourner un JSON avec :
- dashboard_path : chemin vers le dashboard HTML
- charts         : liste des chemins des charts générés
- summary        : description du dashboard
"""

    def run(self, step: str, context: dict) -> dict:
        run_id    = context.get("run_id", "")
        artifacts = context.get("artifacts", {})

        # Récupérer les KPIs du Data Scientist
        kpi_data  = artifacts.get("kpi_calculator", {})
        kpis      = kpi_data.get("kpis", {})
        alertes   = kpi_data.get("alertes", [])

        tools = get_schemas_for_agent(self.agent_name)

        messages = [{
            "role": "user",
            "content": f"""
Étape demandée : {step}
Run ID : {run_id}
KPIs disponibles : {kpis}
Alertes détectées : {alertes}

Génère minimum 3 graphiques pertinents et publie le dashboard.
Retourne un JSON avec dashboard_path, charts, summary.
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
            "dashboard_path": f"runs/{run_id}/artifacts/dashboard.html",
            "charts":         [],
            "summary":        text[:300],
        }
