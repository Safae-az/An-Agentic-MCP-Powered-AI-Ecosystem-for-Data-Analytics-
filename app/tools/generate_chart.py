import os

import plotly.graph_objects as go

# Dashboard-matched color palette (mirrors publish_dashboard.py CSS variables)
CHART_COLORS = [
    "#5af8e8",  # KPI Ops cyan
    "#4cff9a",  # KPI Ops green
    "#a887ff",  # soft violet
    "#ffd166",  # warning amber
    "#ff647c",  # danger coral
    "#06b6d4",  # cyan
    "#ec4899",  # pink
]

# Shared dark-transparent layout — charts blend into dark dashboard panels
_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Arial, sans-serif", size=12, color="#8ea4c0"),
    title_font=dict(size=15, color="#ecf3ff", family="Inter, Arial, sans-serif"),
    title_x=0,
    margin=dict(l=10, r=10, t=48, b=10),
    hoverlabel=dict(
        bgcolor="#0b192f",
        bordercolor="#5af8e8",
        font=dict(color="#ecf3ff", size=12),
    ),
    legend=dict(
        font=dict(color="#8ea4c0", size=11),
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(0,0,0,0)",
    ),
)

_X_CLEAN = dict(
    showgrid=False, zeroline=False,
    tickfont=dict(color="#8ea4c0"),
    linecolor="rgba(148,163,184,0.12)",
)
_Y_GRID = dict(
    showgrid=True, gridcolor="rgba(148,163,184,0.08)",
    zeroline=False,
    tickfont=dict(color="#8ea4c0"),
    linecolor="rgba(0,0,0,0)",
)


def generate_chart(chart_type: str, title: str, data: dict, run_id: str) -> dict:
    """
    Génère un graphique interactif Plotly et le sauvegarde en HTML.
    Types supportés : bar, line, pie, scatter.
    Charts use transparent backgrounds and the dashboard color palette so they
    blend into dark panels without white rectangle artifacts.
    """
    try:
        charts_dir = f"runs/{run_id}/artifacts/charts"
        os.makedirs(charts_dir, exist_ok=True)

        safe_title = title.replace(" ", "_").replace("/", "_").lower()[:40]
        output_path = f"{charts_dir}/{safe_title}.html"

        # Extract labels / values (used by bar, line, pie)
        labels = list(data.get("labels", []))
        values = list(data.get("values", []))
        if not labels and isinstance(data, dict):
            for k, v in data.items():
                if k not in ("labels", "values", "x", "y", "x_label", "y_label"):
                    labels.append(k)
                    values.append(v)

        fig = None

        # ── Bar chart ────────────────────────────────────────────────────
        if chart_type == "bar":
            fig = go.Figure(go.Bar(
                x=labels,
                y=values,
                marker=dict(
                    color=CHART_COLORS[0],
                    opacity=0.88,
                    line=dict(color="rgba(0,0,0,0)", width=0),
                ),
                hovertemplate="<b>%{x}</b><br>Value: %{y:,.0f}<extra></extra>",
            ))
            fig.update_xaxes(**_X_CLEAN)
            fig.update_yaxes(**_Y_GRID)

        # ── Line chart (with area fill) ───────────────────────────────────
        elif chart_type == "line":
            fig = go.Figure(go.Scatter(
                x=labels,
                y=values,
                mode="lines+markers",
                line=dict(color=CHART_COLORS[0], width=3, shape="spline"),
                marker=dict(
                    size=7,
                    color=CHART_COLORS[0],
                    line=dict(color="#050713", width=2),
                ),
                fill="tozeroy",
                fillcolor="rgba(90,248,232,0.10)",
                hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>",
            ))
            fig.update_xaxes(**_X_CLEAN)
            fig.update_yaxes(**_Y_GRID)

        # ── Pie chart → modern donut ──────────────────────────────────────
        elif chart_type == "pie":
            fig = go.Figure(go.Pie(
                labels=labels,
                values=values,
                hole=0.42,
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} (%{percent})<extra></extra>",
                marker=dict(
                    colors=CHART_COLORS,
                    line=dict(color="#050713", width=2),
                ),
                sort=True,
            ))
            fig.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="v",
                    x=1.02,
                    y=0.5,
                    font=dict(color="#8ea4c0", size=11),
                    bgcolor="rgba(0,0,0,0)",
                ),
            )

        # ── Scatter chart ─────────────────────────────────────────────────
        elif chart_type == "scatter":
            x_vals = data.get("x", [])
            y_vals = data.get("y", [])
            x_label = data.get("x_label", "X")
            y_label = data.get("y_label", "Y")
            fig = go.Figure(go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="markers",
                marker=dict(
                    size=10,
                    color=CHART_COLORS[0],
                    opacity=0.8,
                    line=dict(color="#050713", width=1.5),
                ),
                hovertemplate=(
                    f"<b>{x_label}</b>: %{{x}}<br>"
                    f"<b>{y_label}</b>: %{{y:,.2f}}<extra></extra>"
                ),
            ))
            fig.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,0.08)",
                             zeroline=False, tickfont=dict(color="#8ea4c0"),
                             linecolor="rgba(0,0,0,0)")
            fig.update_yaxes(**_Y_GRID)

        else:
            return {"error": f"Type de chart inconnu : {chart_type}"}

        fig.update_layout(title=title, **_LAYOUT)
        fig.write_html(output_path, include_plotlyjs="cdn")

        return {
            "chart_path": output_path,
            "chart_type": chart_type,
            "title":      title,
        }

    except Exception as e:
        return {"error": str(e)}
