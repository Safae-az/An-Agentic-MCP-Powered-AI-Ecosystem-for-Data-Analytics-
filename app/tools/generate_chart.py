import plotly.express as px
import plotly.graph_objects as go
import json
import os


def generate_chart(chart_type: str, title: str, data: dict, run_id: str) -> dict:
    """
    Génère un graphique interactif Plotly et le sauvegarde en HTML.
    Types supportés : bar, line, pie, scatter.
    Codé par P3.
    """
    try:
        charts_dir = f"runs/{run_id}/artifacts/charts"
        os.makedirs(charts_dir, exist_ok=True)

        safe_title = title.replace(" ", "_").replace("/", "_").lower()[:40]
        output_path = f"{charts_dir}/{safe_title}.html"

        fig = None

        # ── Bar chart ─────────────────────────────────────
        if chart_type == "bar":
            labels = list(data.get("labels", data.keys() if isinstance(data, dict) else []))
            values = list(data.get("values", data.values() if isinstance(data, dict) else []))
            if not labels and isinstance(data, dict):
                labels = list(data.keys())
                values = list(data.values())
            fig = px.bar(
                x=labels, y=values,
                title=title,
                labels={"x": "", "y": ""},
                color_discrete_sequence=["#2E75B6"]
            )

        # ── Line chart ────────────────────────────────────
        elif chart_type == "line":
            labels = list(data.get("labels", []))
            values = list(data.get("values", []))
            if not labels and isinstance(data, dict):
                labels = list(data.keys())
                values = list(data.values())
            fig = px.line(
                x=labels, y=values,
                title=title,
                labels={"x": "", "y": ""},
                markers=True,
                color_discrete_sequence=["#2E75B6"]
            )

        # ── Pie chart ─────────────────────────────────────
        elif chart_type == "pie":
            labels = list(data.get("labels", []))
            values = list(data.get("values", []))
            if not labels and isinstance(data, dict):
                labels = list(data.keys())
                values = list(data.values())
            fig = px.pie(
                names=labels, values=values,
                title=title,
                color_discrete_sequence=px.colors.qualitative.Set2
            )

        # ── Scatter chart ─────────────────────────────────
        elif chart_type == "scatter":
            x_vals = data.get("x", [])
            y_vals = data.get("y", [])
            fig = px.scatter(
                x=x_vals, y=y_vals,
                title=title,
                labels={"x": data.get("x_label", "X"), "y": data.get("y_label", "Y")},
                color_discrete_sequence=["#2E75B6"]
            )

        else:
            return {"error": f"Type de chart inconnu : {chart_type}"}

        # Mise en forme commune
        fig.update_layout(
            plot_bgcolor  = "white",
            paper_bgcolor = "white",
            font          = dict(family="Arial", size=13),
            title_font    = dict(size=16, color="#1F4E79"),
            margin        = dict(l=40, r=40, t=60, b=40),
        )

        fig.write_html(output_path, include_plotlyjs="cdn")

        return {
            "chart_path": output_path,
            "chart_type": chart_type,
            "title":      title,
        }

    except Exception as e:
        return {"error": str(e)}
