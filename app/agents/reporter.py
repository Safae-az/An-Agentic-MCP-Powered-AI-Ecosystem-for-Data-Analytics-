from app.agents.base_agent import BaseAgent


class ReporterAgent(BaseAgent):
    """
    Final pipeline agent.

    It consumes the artifacts produced by the previous agents and asks the MCP
    server to compile a final HTML report. The agent is deterministic on purpose:
    the report must be generated every time, even if the LLM/API is unavailable.
    """

    agent_name = "reporter"

    system_prompt = """
Tu es le Reporter du pipeline analytics.

Ton role:
1. Collecter les resultats du run: qualite, KPIs, alertes, insights, dashboard.
2. Appeler compile_report pour generer le rapport final HTML.
3. Appeler log_artifact pour tracer le rapport produit.

Retourne toujours un JSON avec report_path et summary.
"""

    def run(self, step: str, context: dict) -> dict:
        run_id = context.get("run_id", self.run_id)
        artifacts = context.get("artifacts", {}) or {}

        print(f"\n{'='*55}")
        print(f"  REPORTER AGENT - {run_id}")
        print(f"  Compilation du rapport final via MCP Server")
        print(f"{'='*55}")

        if not run_id:
            return {
                "status": "error",
                "agent": self.agent_name,
                "step": step,
                "error": "run_id manquant pour generer le rapport.",
            }

        report_result = self._call_mcp(
            "compile_report",
            {"run_id": run_id},
            run_id,
        )

        if report_result.get("error"):
            return {
                "status": "error",
                "agent": self.agent_name,
                "step": "compile_report",
                "error": report_result.get("error"),
            }

        report_path = report_result.get("report_path", "")
        pdf_path = report_result.get("pdf_path", "")
        excel_path = report_result.get("excel_path", "")
        summary = self._build_summary(report_result, artifacts)

        log_result = self._call_mcp(
            "log_artifact",
            {
                "run_id": run_id,
                "tool_name": "compile_report",
                "data": {
                    "type": "report",
                    "path": report_path,
                    "producer": self.agent_name,
                    "metadata": {
                        "pdf_path": pdf_path,
                        "excel_path": excel_path,
                        "nb_kpis": report_result.get("nb_kpis", 0),
                        "nb_alertes": report_result.get("nb_alertes", 0),
                        "nb_charts": report_result.get("nb_charts", 0),
                    },
                },
            },
            run_id,
        )

        if isinstance(log_result, dict) and log_result.get("error"):
            print(f"[Reporter] Warning log_artifact: {log_result.get('error')}")

        final = {
            "status": "success",
            "agent": self.agent_name,
            "run_id": run_id,
            "report_path": report_path,
            "pdf_path": pdf_path,
            "excel_path": excel_path,
            "summary": summary,
            "generated": bool(report_result.get("generated")),
            "nb_kpis": report_result.get("nb_kpis", 0),
            "nb_alertes": report_result.get("nb_alertes", 0),
            "nb_charts": report_result.get("nb_charts", 0),
        }

        print(f"[Reporter] Rapport genere : {report_path}")
        print(f"{'='*55}\n")
        return final

    def _build_summary(self, report_result: dict, artifacts: dict) -> str:
        nb_kpis = report_result.get("nb_kpis", 0)
        nb_alertes = report_result.get("nb_alertes", 0)
        nb_charts = report_result.get("nb_charts", 0)
        pdf_status = report_result.get("pdf_status", "unknown")
        dashboard = (
            artifacts.get("bi_agent", {}).get("dashboard_path")
            or report_result.get("dashboard_path")
            or "dashboard non disponible"
        )
        return (
            f"Rapport final genere avec {nb_kpis} KPI(s), "
            f"{nb_alertes} alerte(s) et {nb_charts} chart(s). "
            f"Dashboard associe: {dashboard}. PDF: {pdf_status}."
        )
