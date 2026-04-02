import os
import json


def publish_dashboard(charts: list, run_id: str, kpis: dict = {}) -> dict:
    """
    Assemble tous les charts en un dashboard HTML interactif.
    Affiche les KPIs en haut avec alertes visuelles.
    Codé par P3.
    """
    try:
        output_path = f"runs/{run_id}/artifacts/dashboard.html"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # ── KPIs cards HTML ───────────────────────────────
        kpi_cards_html = ""
        kpi_display = {
            "CA_total":          ("💰 CA Total",          "£{:,.0f}"),
            "nb_clients_uniques":("👥 Clients",           "{:,}"),
            "panier_moyen":      ("🛒 Panier Moyen",      "£{:.2f}"),
            "nb_commandes":      ("📦 Commandes",         "{:,}"),
            "nb_pays":           ("🌍 Pays",              "{}"),
            "taux_annulation":   ("❌ Taux Annulation",   "{:.1%}"),
        }

        for key, (label, fmt) in kpi_display.items():
            if key in kpis:
                val = kpis[key]
                try:
                    formatted = fmt.format(val)
                except:
                    formatted = str(val)

                color = "#FDECEA" if key == "taux_annulation" and val > 0.05 else "#E8F4FD"
                icon  = "🔴" if key == "taux_annulation" and val > 0.10 else \
                        "🟠" if key == "taux_annulation" and val > 0.05 else "✅"

                kpi_cards_html += f"""
                <div class="kpi-card" style="background:{color}">
                    <div class="kpi-label">{label} {icon}</div>
                    <div class="kpi-value">{formatted}</div>
                </div>"""

        # ── Charts iframes HTML ───────────────────────────
        charts_html = ""
        for chart_path in charts:
            if chart_path and os.path.exists(chart_path):
                abs_path = os.path.abspath(chart_path)
                charts_html += f"""
                <div class="chart-container">
                    <iframe src="file://{abs_path}"
                            width="100%" height="450"
                            frameborder="0"
                            scrolling="no">
                    </iframe>
                </div>"""

        # ── HTML complet ──────────────────────────────────
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KPI Dashboard — Run {run_id}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: Arial, sans-serif;
            background: #F5F7FA;
            color: #333;
        }}
        header {{
            background: #1F4E79;
            color: white;
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        header h1 {{ font-size: 22px; }}
        header span {{ font-size: 13px; opacity: 0.8; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 30px 20px; }}
        .section-title {{
            font-size: 16px;
            font-weight: bold;
            color: #1F4E79;
            margin: 25px 0 15px 0;
            padding-bottom: 6px;
            border-bottom: 2px solid #2E75B6;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .kpi-card {{
            border-radius: 10px;
            padding: 18px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border: 1px solid #E0E0E0;
        }}
        .kpi-label {{ font-size: 13px; color: #555; margin-bottom: 8px; }}
        .kpi-value {{ font-size: 22px; font-weight: bold; color: #1F4E79; }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(560px, 1fr));
            gap: 20px;
        }}
        .chart-container {{
            background: white;
            border-radius: 10px;
            padding: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border: 1px solid #E0E0E0;
        }}
        footer {{
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: #999;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>📊 KPI Monitoring Dashboard</h1>
        <span>Run ID : {run_id}</span>
    </header>
    <div class="container">
        <div class="section-title">📈 KPIs Principaux</div>
        <div class="kpi-grid">
            {kpi_cards_html}
        </div>
        <div class="section-title">📊 Visualisations</div>
        <div class="charts-grid">
            {charts_html}
        </div>
    </div>
    <footer>Généré automatiquement par le système Multi-Agent KPI Monitoring</footer>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return {
            "dashboard_path": output_path,
            "nb_charts":      len(charts),
            "published":      True,
        }

    except Exception as e:
        return {"error": str(e)}
