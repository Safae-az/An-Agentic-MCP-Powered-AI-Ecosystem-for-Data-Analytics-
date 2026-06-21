from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.tools.generate_chart import generate_chart
from app.tools.publish_dashboard import publish_dashboard


class BIAgent:
    """
    BI Agent adaptatif.

    Il lit n'importe quel insights.json généré par le Data Scientist et génère :
    - des KPI cards depuis les valeurs numériques simples
    - des graphiques depuis les dictionnaires numériques
    - un fallback chart si le JSON contient seulement des KPIs simples

    FIXES v2:
    - Lit chart_hints.chart_id (au lieu de chart_hints.key)
    - Normalise les types "bar_chart" → "bar", "line_chart" → "line", etc.
    """

    agent_name = "bi_agent"
    system_prompt = "Adaptive BI dashboard generation agent"

    SUMMARY_KEYS = {
        "total",
        "sum",
        "mean",
        "avg",
        "average",
        "median",
        "min",
        "max",
        "count",
        "nb",
        "value",
        "formula",
        "unit",
        "description",
    }
    FIXED_SLOTS = [
    "trend", "products", "breakdown", "mix",
    "chart_1", "chart_2", "chart_3", "chart_4",
    "chart_5", "chart_6", "chart_7", "chart_8",
]



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
                "summary": "BI Agent could not find insights.json.",
            }

        result = self.generate_dashboard_from_insights(
            insights_payload=insights_payload,
            run_id=run_id,
            context=context,
        )

        result["step"] = step
        return result

    def generate_dashboard_from_insights(
        self,
        insights_payload: dict,
        run_id: str,
        context: dict | None = None,
    ) -> dict:
        context = context or {}

        dashboard_model = self._build_dashboard_model(insights_payload)
        charts = self._build_charts(dashboard_model, run_id, insights_payload=insights_payload)

        agent_context = self._build_agent_context(
            context=context,
            insights_payload=insights_payload,
            dashboard_model=dashboard_model,
            charts=charts,
        )

        dashboard_result = publish_dashboard(
            charts=charts,
            run_id=run_id,
            kpis=dashboard_model,
            alertes=insights_payload.get("alertes", []) or [],
            insights=insights_payload.get("insights", []) or [],
            agent_context=agent_context,
        )

        handoff_path = self._write_handoff(
            run_id=run_id,
            charts=charts,
            dashboard_result=dashboard_result,
            dashboard_model=dashboard_model,
            insights=insights_payload.get("insights", []) or [],
            agent_context=agent_context,
        )

        return {
            "success": dashboard_result.get("published", False),
            "dashboard_path": dashboard_result.get("dashboard_path"),
            "payload_path": dashboard_result.get("payload_path"),
            "manifest_path": dashboard_result.get("manifest_path"),
            "charts": [chart.get("chart_path") for chart in charts if chart.get("chart_path")],
            "summary": (
                f"Adaptive dashboard generated with "
                f"{len(dashboard_model.get('_dashboard_metrics', []))} KPI cards and "
                f"{len(charts)} charts."
            ),
            "handoff_path": handoff_path,
            "agent_messages": agent_context,
        }

    # ------------------------------------------------------------------
    # 1. Read insights.json
    # ------------------------------------------------------------------
    def _resolve_insights_payload(self, context: dict) -> dict:
        artifacts = context.get("artifacts", {}) or {}

        explicit_paths = [
            context.get("insights_json_path"),
            artifacts.get("insights_path"),
            artifacts.get("output_path"),
        ]

        for key in ("insights", "data_scientist", "kpi_calculator"):
            item = artifacts.get(key)

            if isinstance(item, dict):
                output_path = item.get("output_path")

                if isinstance(output_path, str) and output_path.endswith("insights.json"):
                    explicit_paths.append(output_path)

        for path in explicit_paths:
            if isinstance(path, str) and path.endswith("insights.json") and os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                if isinstance(payload, dict):
                    return payload

        for key in ("insights", "data_scientist", "kpi_calculator"):
            item = artifacts.get(key)

            if isinstance(item, dict) and (
                isinstance(item.get("kpis"), dict)
                or isinstance(item.get("data_quality"), dict)
                or isinstance(item.get("insights"), list)
            ):
                return item

        return {
            "error": (
                "No valid insights.json found. "
                "Expected context['insights_json_path'] or artifacts['data_scientist']['output_path']."
            )
        }

    # ------------------------------------------------------------------
    # 2. Build adaptive dashboard model
    # ------------------------------------------------------------------
    def _build_dashboard_model(self, insights_payload: dict) -> dict:
        kpis = insights_payload.get("kpis")
        if not isinstance(kpis, dict):
            kpis = {}

        data_quality = insights_payload.get("data_quality")
        if not isinstance(data_quality, dict):
            data_quality = {}

        domain = (
            insights_payload.get("domain")
            or kpis.get("domain_detected")
            or kpis.get("domain")
            or "Business"
        )

        metrics = self._extract_metrics(kpis, data_quality)
        series = self._extract_series(kpis)

        dashboard_model = dict(kpis)

        dashboard_model["_dashboard_domain"] = self._human_title(str(domain))
        dashboard_model["_dashboard_metrics"] = metrics[:8]
        dashboard_model["_chart_series"] = series[:12]
        dashboard_model["_original_kpi_keys"] = list(kpis.keys())
        dashboard_model["_data_quality"] = data_quality

        quality = (
            kpis.get("data_quality_score")
            or data_quality.get("score_global")
            or data_quality.get("score")
            or data_quality.get("quality_score")
        )

        if self._is_number(quality):
            dashboard_model["data_quality_score"] = float(quality)

        self._add_legacy_keys(dashboard_model, metrics, series)

        return dashboard_model

    def _add_legacy_keys(
        self,
        model: dict[str, Any],
        metrics: list[dict[str, Any]],
        series: list[dict[str, Any]],
    ) -> None:
        model.setdefault(
            "CA_total",
            self._find_metric(metrics, ["revenue", "sales", "salary", "total", "amount"]),
        )

        model.setdefault(
            "nb_commandes",
            self._find_metric(metrics, ["order", "invoice", "transaction", "count", "employee"]),
        )

        model.setdefault(
            "nb_clients_uniques",
            self._find_metric(metrics, ["customer", "client", "employee", "user"]),
        )

        model.setdefault(
            "panier_moyen",
            self._find_metric(metrics, ["average", "avg", "mean", "salary", "price"]),
        )

        model.setdefault("revenue_moyen", model.get("panier_moyen"))

        temporal = self._first_series(series, ["month", "year", "date", "time"])
        if temporal:
            model.setdefault("CA_par_mois", temporal["values"])

        breakdown = self._first_series(series, ["country", "department", "region", "market", "category"])
        if breakdown:
            model.setdefault("CA_par_pays_top10", breakdown["values"])

        products = self._first_series(series, ["product", "item", "sku"])
        if products:
            model.setdefault("top_10_produits", products["values"])
        else:
            model.setdefault(
                "top_10_produits",
                {
                    metric["label"]: metric["value"]
                    for metric in metrics[:5]
                    if self._is_number(metric.get("value"))
                },
            )

    # ------------------------------------------------------------------
    # 3. Extract KPI cards
    # ------------------------------------------------------------------
    def _extract_metrics(
        self,
        kpis: dict[str, Any],
        data_quality: dict[str, Any],
    ) -> list[dict[str, Any]]:
        metrics: list[dict[str, Any]] = []
        used: set[str] = set()

        for key, value in kpis.items():
            key = str(key)

            if key.startswith("_"):
                continue

            if self._is_number(value):
                self._add_metric(
                    metrics=metrics,
                    used=used,
                    key=key,
                    label=self._human_title(key),
                    value=float(value),
                )
                continue

            if isinstance(value, dict):
                if self._looks_like_summary(value):
                    total = self._first_number(value, ["total", "sum", "value", "count", "nb"])
                    mean = self._first_number(value, ["mean", "avg", "average"])

                    if total is not None:
                        self._add_metric(
                            metrics=metrics,
                            used=used,
                            key=key,
                            label=self._human_title(key),
                            value=total,
                        )

                    if mean is not None:
                        self._add_metric(
                            metrics=metrics,
                            used=used,
                            key=f"{key}_average",
                            label=f"Average {self._human_title(key)}",
                            value=mean,
                        )

        quality = (
            kpis.get("data_quality_score")
            or data_quality.get("score_global")
            or data_quality.get("score")
            or data_quality.get("quality_score")
        )

        if self._is_number(quality):
            self._add_metric(
                metrics=metrics,
                used=used,
                key="data_quality_score",
                label="Data Quality",
                value=float(quality),
                kind="percent",
            )

        if len(metrics) < 4:
            for path, value in self._walk_numbers(kpis):
                if len(metrics) >= 8:
                    break

                if path not in used:
                    self._add_metric(
                        metrics=metrics,
                        used=used,
                        key=path,
                        label=self._human_title(path.split(".")[-1]),
                        value=float(value),
                    )

        return self._rank_metrics(metrics)

    def _add_metric(
        self,
        metrics: list[dict[str, Any]],
        used: set[str],
        key: str,
        label: str,
        value: float,
        kind: str | None = None,
    ) -> None:
        if key in used:
            return

        used.add(key)

        metrics.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "kind": kind or self._guess_kind(key),
            }
        )

    def _rank_metrics(self, metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority = [
            "total",
            "revenue",
            "sales",
            "salary",
            "profit",
            "amount",
            "count",
            "employee",
            "customer",
            "client",
            "order",
            "invoice",
            "average",
            "avg",
            "mean",
            "age",
            "score",
            "quality",
            "rate",
            "churn",
            "attrition",
        ]

        def score(metric: dict[str, Any]) -> int:
            text = f"{metric.get('key', '')} {metric.get('label', '')}".lower()

            for index, word in enumerate(priority):
                if word in text:
                    return index

            return 999

        return sorted(metrics, key=score)

    # ------------------------------------------------------------------
    # 4. Extract chart series
    # ------------------------------------------------------------------
    def _extract_series(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []

        for key, value in kpis.items():
            key = str(key)

            if key.startswith("_"):
                continue

            found.extend(self._series_from_value(value, key))

        unique: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in found:
            values = item.get("values") or {}

            if item["key"] in seen:
                continue

            if isinstance(values, dict) and len(values) >= 2:
                seen.add(item["key"])
                unique.append(item)

        return unique

    def _series_from_value(self, value: Any, path: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        if isinstance(value, dict):
            numeric_dict = self._numeric_dict(value)

            if len(numeric_dict) >= 2 and not self._looks_like_summary(value):
                values = (
                    self._sort_time(numeric_dict)
                    if self._looks_temporal(path, numeric_dict)
                    else self._sort_desc(numeric_dict)
                )

                result.append(
                    {
                        "key": path,
                        "title": self._human_title(path),
                        "values": values,
                        "chart_type": self._guess_chart_type(path, values),
                        "slot": self._slot_from_key(path),
                        "description": f"Generated from KPI key: {path}",
                    }
                )

                return result

            for child_key, child_value in value.items():
                if str(child_key).lower() in self.SUMMARY_KEYS:
                    continue

                result.extend(
                    self._series_from_value(
                        child_value,
                        f"{path}.{child_key}",
                    )
                )

        elif isinstance(value, list):
            values = self._series_from_list(value)

            if values:
                result.append(
                    {
                        "key": path,
                        "title": self._human_title(path),
                        "values": values,
                        "chart_type": self._guess_chart_type(path, values),
                        "slot": self._slot_from_key(path),
                        "description": f"Generated from list KPI key: {path}",
                    }
                )

        return result

    def _numeric_dict(self, value: dict[str, Any]) -> dict[str, float]:
        result: dict[str, float] = {}

        for key, item in value.items():
            key_str = str(key)

            if key_str.lower() in self.SUMMARY_KEYS:
                continue

            if self._is_number(item):
                result[key_str] = float(item)
                continue

            if isinstance(item, dict):
                number = self._first_number(
                    item,
                    ["count", "nb", "total", "sum", "value", "mean", "avg", "average"],
                )

                if number is not None:
                    result[key_str] = number

        return result

    def _series_from_list(self, items: list[Any]) -> dict[str, float] | None:
        if len(items) < 2:
            return None

        if all(self._is_number(item) for item in items):
            return {
                str(index + 1): float(value)
                for index, value in enumerate(items)
            }

        if all(isinstance(item, dict) for item in items):
            label_keys = [
                "label",
                "name",
                "category",
                "type",
                "group",
                "country",
                "department",
                "segment",
                "date",
                "month",
                "year",
            ]

            value_keys = [
                "value",
                "count",
                "total",
                "sum",
                "amount",
                "revenue",
                "sales",
                "salary",
                "score",
                "rate",
            ]

            result: dict[str, float] = {}

            for item in items:
                label = None
                value = None

                for label_key in label_keys:
                    if label_key in item:
                        label = item[label_key]
                        break

                for value_key in value_keys:
                    if value_key in item and self._is_number(item[value_key]):
                        value = float(item[value_key])
                        break

                if label is not None and value is not None:
                    result[str(label)] = value

            if len(result) >= 2:
                return result

        return None

    MAX_CHARTS = 12

    # ------------------------------------------------------------------
    # 5. Generate charts
    # ------------------------------------------------------------------
    def _build_charts(
        self,
        model: dict[str, Any],
        run_id: str,
        insights_payload: dict | None = None,
    ) -> list[dict[str, Any]]:
        chart_specs = list(model.get("_chart_series") or [])
        metrics = list(model.get("_dashboard_metrics") or [])

        # ----------------------------------------------------------------
        # FIX: Merge chart_hints from Data Scientist
        # Avant : hint.get("key") or hint.get("kpi")  → toujours vide
        # Après  : hint.get("chart_id") en priorité, puis "key", "kpi"
        # FIX: Normalise "bar_chart" → "bar", "line_chart" → "line", etc.
        # ----------------------------------------------------------------
        chart_hints = (insights_payload or {}).get("chart_hints") or []

        for hint in chart_hints:
            if not isinstance(hint, dict):
                continue

            # FIX 1 — lire chart_id en priorité
            key = str(
                hint.get("chart_id")
                or hint.get("key")
                or hint.get("kpi")
                or ""
            )

            if not key:
                continue

            if any(s.get("key") == key for s in chart_specs):
                continue

            kpis = (insights_payload or {}).get("kpis") or {}
            raw = kpis.get(key)

            if isinstance(raw, dict):
                numeric = self._numeric_dict(raw)

                if len(numeric) >= 2 and not self._looks_like_summary(raw):
                    # FIX 2 — normaliser le type de chart
                    raw_type = hint.get("type") or hint.get("chart_type") or ""
                    chart_type = self._normalize_chart_type(raw_type) or self._guess_chart_type(key, numeric)

                    chart_specs.append({
                        "key": key,
                        "title": hint.get("title") or self._human_title(key),
                        "values": numeric,
                        "chart_type": chart_type,
                        "slot": hint.get("slot") or self._slot_from_key(key),
                        "description": hint.get("description") or f"From chart_hints: {key}",
                    })
            else:
                # Pas de données dict → fallback sur les métriques scalaires
                # pour quand même honorer le hint avec ce qu'on a
                scalar = {
                    m["label"]: m["value"]
                    for m in metrics[:8]
                    if self._is_number(m.get("value"))
                }
                if len(scalar) >= 2:
                    raw_type = hint.get("type") or hint.get("chart_type") or ""
                    chart_type = self._normalize_chart_type(raw_type) or self._guess_chart_type(key, scalar)

                    chart_specs.append({
                        "key": key,
                        "title": hint.get("title") or self._human_title(key),
                        "values": scalar,
                        "chart_type": chart_type,
                        "slot": hint.get("slot") or self._slot_from_key(key),
                        "description": f"From chart_hints (scalar fallback): {key}",
                    })

        if not chart_specs and metrics:
            scalar_values = {
                metric["label"]: metric["value"]
                for metric in metrics[:8]
                if self._is_number(metric.get("value"))
            }

            chart_specs = [
                {
                    "key": "scalar_kpi_overview",
                    "title": "KPI Overview",
                    "values": scalar_values,
                    "chart_type": "bar",
                    "slot": "trend",
                    "description": "Generated from scalar KPI values.",
                },
                {
                    "key": "scalar_kpi_mix",
                    "title": "KPI Mix",
                    "values": scalar_values,
                    "chart_type": "pie",
                    "slot": "mix",
                    "description": "Generated from scalar KPI values.",
                },
            ]

        chart_specs = self._assign_slots(chart_specs)

        charts: list[dict[str, Any]] = []

        for spec in chart_specs[: self.MAX_CHARTS]:
            values = spec.get("values") or {}

            if not isinstance(values, dict) or len(values) < 2:
                continue

            values = dict(list(values.items())[:14])

            chart_type = spec.get("chart_type") or "bar"
            slot = spec.get("slot") or "trend"
            title = spec.get("title") or self._human_title(spec.get("key", "Chart"))

            data = {
                "labels": [self._short_label(label) for label in values.keys()],
                "values": list(values.values()),
                "slot": slot,
                "height": 340,
            }

            if chart_type == "bar":
                data["orientation"] = "h" if len(values) > 5 else "v"

            if chart_type == "pie":
                data["hole"] = 0.55

            chart = self._safe_generate_chart(
                chart_type=chart_type,
                title=title,
                data=data,
                run_id=run_id,
            )

            if chart and not chart.get("error"):
                chart["slot"] = slot
                chart["source_key"] = spec.get("key")
                chart["description"] = spec.get("description")
                charts.append(chart)

        return charts

    def _assign_slots(self, specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Assign fixed slots to the first N specs, then dynamic slots to the rest."""
        result: list[dict[str, Any]] = []
        used: set[str] = set()

        for spec in specs:
            spec = dict(spec)
            slot = spec.get("slot") or self._slot_from_key(spec.get("key", ""))

            if slot == "dynamic" or slot in used:
                slot = None

            if not slot:
                for candidate in self.FIXED_SLOTS:
                    if candidate not in used:
                        slot = candidate
                        break

            if not slot:
                slot = f"dynamic_{len(used) + 1}"

            spec["slot"] = slot
            used.add(slot)
            result.append(spec)

        return result

    def _safe_generate_chart(
        self,
        chart_type: str,
        title: str,
        data: dict,
        run_id: str,
    ) -> dict:
        try:
            return generate_chart(
                chart_type=chart_type,
                title=title,
                data=data,
                run_id=run_id,
            )

        except Exception as exc:
            return {
                "error": str(exc),
                "title": title,
                "chart_type": chart_type,
            }

    # ------------------------------------------------------------------
    # 6. Context / handoff
    # ------------------------------------------------------------------
    def _build_agent_context(
        self,
        context: dict,
        insights_payload: dict,
        dashboard_model: dict,
        charts: list[dict[str, Any]],
    ) -> dict:
        artifacts = context.get("artifacts", {}) or {}
        upstream = []

        for agent_name in ("data_engineer", "data_scientist", "reporter"):
            artifact = artifacts.get(agent_name)

            if artifact:
                upstream.append(
                    {
                        "agent": agent_name,
                        "artifact": artifact,
                    }
                )

        return {
            "flow": ["Data Engineer", "Data Scientist", "BI Agent", "Reporter"],
            "received_from": [item["agent"] for item in upstream] or ["data_scientist"],
            "source_output": insights_payload.get("output_path"),
            "domain": dashboard_model.get("_dashboard_domain"),
            "original_kpi_keys": dashboard_model.get("_original_kpi_keys", []),
            "metric_keys": [
                metric.get("key")
                for metric in dashboard_model.get("_dashboard_metrics", [])
            ],
            "chart_series_keys": [
                series.get("key")
                for series in dashboard_model.get("_chart_series", [])
            ],
            "generated_charts": [
                {
                    "title": chart.get("title"),
                    "slot": chart.get("slot"),
                    "source_key": chart.get("source_key"),
                    "chart_path": chart.get("chart_path"),
                }
                for chart in charts
            ],
            "upstream_artifacts": upstream,
        }

    def _write_handoff(
        self,
        run_id: str,
        charts: list[dict[str, Any]],
        dashboard_result: dict,
        dashboard_model: dict,
        insights: list[Any],
        agent_context: dict,
    ) -> str:
        path = Path(f"runs/{run_id}/artifacts/bi_agent_handoff.json")
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "producer": "bi_agent",
            "consumers": ["reporter", "orchestrator"],
            "dashboard_path": dashboard_result.get("dashboard_path"),
            "payload_path": dashboard_result.get("payload_path"),
            "manifest_path": dashboard_result.get("manifest_path"),
            "charts": [
                chart.get("chart_path")
                for chart in charts
                if chart.get("chart_path")
            ],
            "headline_metrics": dashboard_model.get("_dashboard_metrics", []),
            "chart_series": dashboard_model.get("_chart_series", []),
            "insights": insights[:8],
            "message": "Adaptive dashboard generated from insights.json.",
            "agent_context": agent_context,
        }

        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return str(path)

    # ------------------------------------------------------------------
    # 7. Helpers
    # ------------------------------------------------------------------

    # FIX: Nouveau helper — normalise les types de charts
    def _normalize_chart_type(self, raw: str) -> str:
        """
        Convertit les types verbeux du Data Scientist en types courts
        attendus par generate_chart().

        Exemples :
            "bar_chart"  → "bar"
            "line_chart" → "line"
            "pie_chart"  → "pie"
            "bar"        → "bar"   (déjà correct)
            ""           → ""      (fallback à l'appelant)
        """
        if not raw:
            return ""

        mapping = {
            "bar_chart": "bar",
            "barchart": "bar",
            "bar graph": "bar",
            "bargraph": "bar",
            "line_chart": "line",
            "linechart": "line",
            "line graph": "line",
            "linegraph": "line",
            "area_chart": "line",
            "areachart": "line",
            "pie_chart": "pie",
            "piechart": "pie",
            "donut": "pie",
            "donut_chart": "pie",
            "scatter_chart": "scatter",
            "scatterchart": "scatter",
            "scatter plot": "scatter",
            "scatterplot": "scatter",
        }

        normalized = raw.strip().lower().replace("-", "_")
        return mapping.get(normalized, normalized)

    def _find_metric(
        self,
        metrics: list[dict[str, Any]],
        keywords: list[str],
    ) -> float | None:
        for metric in metrics:
            text = f"{metric.get('key', '')} {metric.get('label', '')}".lower()

            if any(keyword in text for keyword in keywords) and self._is_number(metric.get("value")):
                return float(metric["value"])

        return None

    def _first_series(
        self,
        series: list[dict[str, Any]],
        keywords: list[str],
    ) -> dict[str, Any] | None:
        for item in series:
            text = f"{item.get('key', '')} {item.get('title', '')}".lower()

            if any(keyword in text for keyword in keywords):
                return item

        return series[0] if series else None

    def _looks_like_summary(self, value: dict[str, Any]) -> bool:
        keys = {str(key).lower() for key in value.keys()}

        if not keys:
            return False

        return bool(keys.intersection(self.SUMMARY_KEYS))

    def _first_number(
        self,
        data: dict[str, Any],
        keys: list[str],
    ) -> float | None:
        for key in keys:
            if key in data and self._is_number(data[key]):
                return float(data[key])

        return None

    def _walk_numbers(
        self,
        value: Any,
        path: str = "",
    ) -> list[tuple[str, float]]:
        output: list[tuple[str, float]] = []

        if self._is_number(value):
            output.append((path or "value", float(value)))
            return output

        if isinstance(value, dict):
            for key, item in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                output.extend(self._walk_numbers(item, child_path))

        elif isinstance(value, list):
            for index, item in enumerate(value):
                child_path = f"{path}.{index}" if path else str(index)
                output.extend(self._walk_numbers(item, child_path))

        return output

    def _guess_kind(self, key: str) -> str:
        key = str(key).lower()

        if any(word in key for word in ["rate", "ratio", "percent", "score", "quality", "churn", "attrition"]):
            return "percent"

        if any(word in key for word in ["sales", "revenue", "salary", "price", "amount", "profit", "cost", "balance", "ca"]):
            return "currency"

        return "number"

    def _guess_chart_type(
        self,
        key: str,
        values: dict[str, float],
    ) -> str:
        key = str(key).lower()

        if self._looks_temporal(key, values):
            return "line"

        if any(word in key for word in ["gender", "status", "mix", "share", "distribution", "country", "department", "category"]):
            if len(values) <= 8:
                return "pie"

        return "bar"

    def _looks_temporal(
        self,
        key: str,
        values: dict[str, Any],
    ) -> bool:
        key = str(key).lower()

        if any(word in key for word in ["date", "month", "monthly", "year", "time", "day", "week", "mois", "annee"]):
            return True

        labels = list(values.keys())

        if not labels:
            return False

        hits = 0

        for label in labels:
            text = str(label)

            if re.fullmatch(r"\d{4}-\d{1,2}", text):
                hits += 1
            elif re.fullmatch(r"\d{4}", text):
                hits += 1
            elif re.fullmatch(r"\d{1,2}", text) and 1 <= int(text) <= 12:
                hits += 1

        return hits / len(labels) >= 0.7

    def _slot_from_key(self, key: str) -> str:
        key = str(key).lower()

        if any(word in key for word in ["date", "month", "year", "time", "week"]):
            return "trend"

        if any(word in key for word in ["product", "item", "sku"]):
            return "products"

        if any(word in key for word in ["country", "region", "market", "department", "category"]):
            return "breakdown"

        if any(word in key for word in ["gender", "status", "mix", "share", "distribution"]):
            return "mix"

        return "dynamic"

    def _sort_desc(self, data: dict[str, float]) -> dict[str, float]:
        return dict(
            sorted(
                data.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        )

    def _sort_time(self, data: dict[str, float]) -> dict[str, float]:
        def key_fn(item: tuple[str, float]) -> tuple[int, int, int]:
            numbers = re.findall(r"\d+", str(item[0]))

            if not numbers:
                return (9999, 9999, 9999)

            numbers = [int(number) for number in numbers[:3]]

            while len(numbers) < 3:
                numbers.append(0)

            return tuple(numbers)

        return dict(sorted(data.items(), key=key_fn))

    def _human_title(self, key: str) -> str:
        text = str(key).replace("_", " ").replace("-", " ").replace(".", " / ")
        text = re.sub(r"\s+", " ", text).strip()

        return text.title() if text else "KPI"

    def _short_label(
        self,
        label: Any,
        max_len: int = 34,
    ) -> str:
        text = str(label)

        if len(text) <= max_len:
            return text

        return text[: max_len - 3] + "..."

    def _is_number(self, value: Any) -> bool:
        try:
            if value is None or value == "":
                return False

            float(value)
            return True

        except Exception:
            return False