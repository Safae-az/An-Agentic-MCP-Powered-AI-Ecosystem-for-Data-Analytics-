from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.tools.generate_chart import generate_chart
from app.tools.publish_dashboard import publish_dashboard


class BIAgent:
    """
    Deterministic BI agent that consumes insights.json, prepares a dashboard-ready
    payload, generates charts, and publishes an executive dashboard similar to the
    provided mockup. It also produces a handoff artifact so downstream agents can
    continue the workflow.
    """

    agent_name = "bi_agent"
    system_prompt = "Dashboard generation agent"

    def __init__(self, run_id: str = ""):
        self.run_id = run_id

    def run(self, step: str, context: dict) -> dict:
        run_id = context.get("run_id") or self.run_id or "run_bi_preview"
        insights_payload = self._resolve_insights_payload(context)
        if insights_payload.get("error"):
            return {
                "success": False,
                "error": insights_payload["error"],
                "dashboard_path": f"runs/{run_id}/artifacts/dashboard.html",
                "charts": [],
                "summary": "BI Agent could not find a valid insights payload.",
            }

        result = self.generate_dashboard_from_insights(
            insights_payload=insights_payload,
            run_id=run_id,
            context=context,
        )
        result["step"] = step
        return result

    def generate_dashboard_from_insights(self, insights_payload: dict, run_id: str, context: dict | None = None) -> dict:
        context = context or {}
        kpis = insights_payload.get("kpis", {})
        alertes = insights_payload.get("alertes", [])
        insights = insights_payload.get("insights", [])

        charts = self._build_charts(kpis, run_id)
        agent_context = self._build_agent_context(context, insights_payload)
        dashboard_result = publish_dashboard(
            charts=charts,
            run_id=run_id,
            kpis=kpis,
            alertes=alertes,
            insights=insights,
            agent_context=agent_context,
        )

        handoff = self._write_handoff(run_id, charts, dashboard_result, kpis, insights, agent_context)
        return {
            "success": dashboard_result.get("published", False),
            "dashboard_path": dashboard_result.get("dashboard_path"),
            "charts": [chart.get("chart_path") for chart in charts if chart.get("chart_path")],
            "summary": self._build_summary(kpis, alertes),
            "handoff_path": handoff,
            "agent_messages": agent_context,
        }

    def _resolve_insights_payload(self, context: dict) -> dict:
        artifacts = context.get("artifacts", {}) or {}

        candidates: list[dict[str, Any]] = []
        for key in ("data_scientist", "kpi_calculator", "insights"):
            item = artifacts.get(key)
            if isinstance(item, dict):
                candidates.append(item)

        explicit_paths = [
            context.get("insights_json_path"),
            artifacts.get("insights_path"),
            artifacts.get("output_path"),
        ]

        for candidate in candidates:
            if candidate.get("kpis"):
                return candidate
            if isinstance(candidate.get("output_path"), str) and candidate["output_path"].endswith("insights.json"):
                explicit_paths.append(candidate["output_path"])

        for path in explicit_paths:
            if isinstance(path, str) and path.endswith("insights.json") and os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)

        return {
            "error": "No insights.json payload found in context. Provide artifacts['data_scientist'], artifacts['kpi_calculator'], or insights_json_path.",
        }

    def _build_charts(self, kpis: dict, run_id: str) -> list[dict]:
        charts: list[dict] = []

        ca_par_mois = kpis.get("CA_par_mois") or {}
        if ca_par_mois:
            trend = generate_chart(
                chart_type="line",
                title="Sales Over Time",
                data={"labels": list(ca_par_mois.keys()), "values": list(ca_par_mois.values()), "slot": "trend", "height": 320},
                run_id=run_id,
            )
            charts.append(trend)

        country_sales = kpis.get("CA_par_pays_top10") or {}
        if country_sales:
            top_countries = list(country_sales.items())[:5]
            mix = generate_chart(
                chart_type="pie",
                title="Sales by Country",
                data={
                    "labels": [name for name, _ in top_countries],
                    "values": [value for _, value in top_countries],
                    "slot": "mix",
                    "hole": 0.62,
                    "height": 320,
                },
                run_id=run_id,
            )
            charts.append(mix)

            country_bar = generate_chart(
                chart_type="bar",
                title="Country Revenue Ranking",
                data={
                    "labels": [name for name, _ in top_countries],
                    "values": [value for _, value in top_countries],
                    "slot": "breakdown",
                    "orientation": "h",
                    "height": 320,
                },
                run_id=run_id,
            )
            charts.append(country_bar)

        top_products = kpis.get("top_10_produits") or {}
        if top_products:
            product_items = list(top_products.items())[:5]
            products_chart = generate_chart(
                chart_type="bar",
                title="Top Product Revenue",
                data={
                    "labels": [name[:22] + ("…" if len(name) > 22 else "") for name, _ in product_items],
                    "values": [value for _, value in product_items],
                    "slot": "products",
                    "orientation": "h",
                    "height": 320,
                },
                run_id=run_id,
            )
            charts.append(products_chart)

        return [chart for chart in charts if not chart.get("error")]

    def _build_agent_context(self, context: dict, insights_payload: dict) -> dict:
        artifacts = context.get("artifacts", {}) or {}
        upstream = []
        for agent_name in ("data_engineer", "data_scientist", "reporter"):
            artifact = artifacts.get(agent_name)
            if artifact:
                upstream.append({"agent": agent_name, "artifact": artifact})

        return {
            "flow": ["Data Engineer", "Data Scientist", "BI Agent", "Reporter"],
            "received_from": [item["agent"] for item in upstream] or ["data_scientist"],
            "source_output": insights_payload.get("output_path"),
            "upstream_artifacts": upstream,
        }

    def _write_handoff(self, run_id: str, charts: list[dict], dashboard_result: dict, kpis: dict, insights: list[str], agent_context: dict) -> str:
        path = Path(f"runs/{run_id}/artifacts/bi_agent_handoff.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "producer": "bi_agent",
            "consumers": ["reporter", "orchestrator"],
            "dashboard_path": dashboard_result.get("dashboard_path"),
            "charts": [chart.get("chart_path") for chart in charts if chart.get("chart_path")],
            "headline_metrics": {
                "CA_total": kpis.get("CA_total"),
                "nb_commandes": kpis.get("nb_commandes"),
                "nb_clients_uniques": kpis.get("nb_clients_uniques"),
            },
            "insights": insights[:4],
            "message": "Dashboard published successfully. Reporter can now compile the final report using the HTML dashboard and chart artifacts.",
            "agent_context": agent_context,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def _build_summary(self, kpis: dict, alertes: list[dict]) -> str:
        return (
            f"Executive dashboard generated with {len(kpis.get('CA_par_mois', {})) or 0} monthly points, "
            f"{len(kpis.get('CA_par_pays_top10', {})) or 0} country entries, and {len(alertes)} active alerts."
        )
