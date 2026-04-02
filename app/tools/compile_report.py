import os
import json
from datetime import datetime


def compile_report(run_id: str) -> dict:
    """
    Génère un rapport HTML complet à partir des artifacts du run.
    Codé par P4.
    """
    try:
        base = f"runs/{run_id}"

        # ── Lire les artifacts ────────────────────────────
        metadata  = {}
        insights  = {}
        decisions = []

        meta_path = f"{base}/metadata.json"
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                metadata = json.load(f)

        insights_path = f"{base}/artifacts/insights.json"
        if os.path.exists(insights_path):
            with open(insights_path) as f:
                insights = json.load(f)

        decisions_path = f"{base}/decisions.jsonl"
        if os.path.exists(decisions_path):
            with open(decisions_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        decisions.append(json.loads(line))

        kpis    = insights.get("kpis",    {})
        alertes = insights.get("alertes", [])
        ins     = insights.get("insights", [])

        # ── Alertes HTML ──────────────────────────────────
        alertes_html = ""
        for a in alertes:
            color = "#FDECEA" if a["niveau"] == "critical" else "#FEF9E7"
            icon  = "🔴" if a["niveau"] == "critical" else "🟠"
            alertes_html += f"""
            <div style="background:{color};border-radius:8px;padding:12px;margin:8px 0;border-left:4px solid {'#C0392B' if a['niveau']=='critical' else '#E67E22'}">
                {icon} <strong>{a['kpi']}</strong> = {a['valeur']:.2%} — {a['message']}
            </div>"""

        if not alertes_html:
            alertes_html = '<p style="color:green">✅ Aucune alerte détectée</p>'

        # ── KPIs HTML ─────────────────────────────────────
        kpis_html = ""
        kpi_labels = {
            "CA_total":           ("💰 CA Total",           "£{:,.0f}"),
            "nb_clients_uniques": ("👥 Clients Uniques",    "{:,}"),
            "panier_moyen":       ("🛒 Panier Moyen",       "£{:.2f}"),
            "nb_commandes":       ("📦 Commandes",          "{:,}"),
            "nb_pays":            ("🌍 Pays",               "{}"),
            "taux_annulation":    ("❌ Taux Annulation",    "{:.1%}"),
        }
        for key, (label, fmt) in kpi_labels.items():
            if key in kpis:
                try:
                    val = fmt.format(kpis[key])
                except:
                    val = str(kpis[key])
                kpis_html += f"""
                <tr>
                    <td style="padding:8px 12px;border-bottom:1px solid #eee"><strong>{label}</strong></td>
                    <td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:bold;color:#1F4E79">{val}</td>
                </tr>"""

        # ── Décisions HTML ────────────────────────────────
        decisions_html = ""
        for d in decisions[-20:]:
            decisions_html += f"""
            <tr>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px">{d.get('timestamp','')[:19]}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px"><strong>{d.get('agent','')}</strong></td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px">{d.get('decision','')}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:12px">{str(d.get('reason',''))[:80]}</td>
            </tr>"""

        # ── Insights HTML ─────────────────────────────────
        insights_html = "".join(f"<li style='margin:6px 0'>{i}</li>" for i in ins)

        # ── Rapport HTML complet ──────────────────────────
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Rapport Final — {run_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; color: #333; max-width: 960px; margin: 0 auto; padding: 30px; }}
        h1 {{ color: #1F4E79; border-bottom: 3px solid #2E75B6; padding-bottom: 10px; }}
        h2 {{ color: #2E75B6; margin-top: 30px; }}
        .meta {{ background: #E8F4FD; border-radius: 8px; padding: 15px; margin: 15px 0; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th {{ background: #1F4E79; color: white; padding: 10px 12px; text-align: left; }}
    </style>
</head>
<body>
    <h1>📊 Rapport Final — KPI Monitoring</h1>

    <div class="meta">
        <strong>Run ID :</strong> {run_id}<br>
        <strong>Objectif :</strong> {metadata.get('objective', 'N/A')}<br>
        <strong>Statut :</strong> {metadata.get('status', 'N/A')}<br>
        <strong>Démarré :</strong> {metadata.get('started_at', '')[:19]}<br>
        <strong>Terminé :</strong> {metadata.get('finished_at', '')[:19]}<br>
        <strong>Généré le :</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>

    <h2>🚨 Alertes</h2>
    {alertes_html}

    <h2>📈 KPIs Business</h2>
    <table>
        <tr><th>Indicateur</th><th>Valeur</th></tr>
        {kpis_html}
    </table>

    <h2>💡 Insights Clés</h2>
    <ul>{insights_html}</ul>

    <h2>🤖 Décisions des Agents</h2>
    <table>
        <tr><th>Timestamp</th><th>Agent</th><th>Décision</th><th>Raison</th></tr>
        {decisions_html}
    </table>
</body>
</html>"""

        output_path = f"{base}/artifacts/report.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return {
            "report_path": output_path,
            "run_id":      run_id,
            "nb_kpis":     len(kpis),
            "nb_alertes":  len(alertes),
            "generated":   True,
        }

    except Exception as e:
        return {"error": str(e)}
