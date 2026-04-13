import pandas as pd
import json
import os

SEUILS = {
    "taux_annulation": {"warning": 0.05, "critical": 0.10},
    "taux_retour":     {"warning": 0.05, "critical": 0.10},
}

def run_analysis(file_path: str, run_id: str) -> dict:
    """
    Analyse le dataset e-commerce et calcule les KPIs.
    Détecte les alertes selon les seuils et produit des insights.
    Retourne un dictionnaire complet avec kpis, alertes, insights et output_path.
    """
    if not os.path.exists(file_path):
        return {"error": f"Fichier introuvable : {file_path}"}

    try:
        df = pd.read_csv(file_path, low_memory=False)

        # ── Création colonne Revenue si nécessaire ─────────
        if "Sales" not in df.columns:
            if "Quantity" in df.columns and "UnitPrice" in df.columns:
                df["Sales"] = df["Quantity"] * df["UnitPrice"]
            else:
                df["Sales"] = 0.0

        kpis = {}

        # ── CA total et moyen ─────────────────────────────
        kpis["CA_total"]      = round(float(df["Revenue"].sum()), 2)
        kpis["revenue_moyen"] = round(float(df["Sales"].mean()), 2)

        # ── CA par mois ───────────────────────────────────
        if "InvoiceDate" in df.columns:
            df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
            df["Month"]       = df["InvoiceDate"].dt.to_period("M").astype(str)
            ca_mois           = df.groupby("Month")["Sales"].sum().round(2)
            kpis["CA_par_mois"] = ca_mois.to_dict()

        # ── CA par pays ───────────────────────────────────
        if "Country" in df.columns:
            ca_pays = (
                df.groupby("Country")["Sales"]
                  .sum()
                  .sort_values(ascending=False)
                  .head(10)
                  .round(2)
            )
            kpis["CA_par_pays_top10"] = ca_pays.to_dict()

        # ── Clients ───────────────────────────────────────
        if "CustomerID" in df.columns:
            kpis["nb_clients_uniques"] = int(df["CustomerID"].nunique())

        # ── Commandes et panier moyen ────────────────────
        if "InvoiceNo" in df.columns:
            total_commandes      = df["InvoiceNo"].nunique()
            kpis["nb_commandes"] = total_commandes
            if total_commandes > 0:
                panier_moyen         = df.groupby("InvoiceNo")["Sales"].sum().mean()
                kpis["panier_moyen"] = round(float(panier_moyen), 2)

        # ── Top produits par revenue ──────────────────────
        if "Description" in df.columns:
            top_produits = (
                df.groupby("Description")["Sales"]
                  .sum()
                  .sort_values(ascending=False)
                  .head(10)
                  .round(2)
            )
            kpis["top_10_produits"] = top_produits.to_dict()

        # ── Taux annulation ───────────────────────────────
        if "InvoiceNo" in df.columns:
            total_inv             = df["InvoiceNo"].nunique()
            cancel_inv            = df["InvoiceNo"].astype(str).str.startswith("C").sum()
            kpis["taux_annulation"] = round(cancel_inv / max(total_inv, 1), 4)

        # ── Data Quality Score ────────────────────────────
        dq_score                   = df.notna().mean().mean()
        kpis["data_quality_score"] = round(dq_score, 2)

        # ── Alertes ───────────────────────────────────────
        alertes = []
        for kpi_name, seuils in SEUILS.items():
            if kpi_name in kpis:
                valeur = kpis[kpi_name]
                if valeur >= seuils["critical"]:
                    alertes.append({
                        "kpi":     kpi_name,
                        "valeur":  valeur,
                        "niveau":  "critical",
                        "seuil":   seuils["critical"],
                        "message": f"{kpi_name} = {valeur:.1%} dépasse le seuil critique {seuils['critical']:.1%}"
                    })
                elif valeur >= seuils["warning"]:
                    alertes.append({
                        "kpi":     kpi_name,
                        "valeur":  valeur,
                        "niveau":  "warning",
                        "seuil":   seuils["warning"],
                        "message": f"{kpi_name} = {valeur:.1%} dépasse le seuil warning {seuils['warning']:.1%}"
                    })

        # ── Insights textuels ─────────────────────────────
        insights = []
        if "CA_total" in kpis:
            insights.append(f"CA total : £{kpis['CA_total']:,.0f}")
        if "nb_clients_uniques" in kpis:
            insights.append(f"Nombre de clients uniques : {kpis['nb_clients_uniques']:,}")
        if "panier_moyen" in kpis:
            insights.append(f"Panier moyen par commande : £{kpis['panier_moyen']:.2f}")
        if "CA_par_pays_top10" in kpis:
            top_pays = list(kpis["CA_par_pays_top10"].keys())[0]
            insights.append(f"Premier pays par CA : {top_pays}")
        if alertes:
            for a in alertes:
                insights.append(f"Alerte {a['niveau']} : {a['message']}")

        # ── Sauvegarder le fichier insights ───────────────
        output_path = f"runs/{run_id}/artifacts/insights.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(
                {
                    "kpis":        kpis,
                    "alertes":     alertes,
                    "insights":    insights,
                    "output_path": output_path
                },
                f,
                indent=2
            )

        return {
            "output_path": output_path,
            "kpis":        kpis,
            "alertes":     alertes,
            "insights":    insights,
            "nb_alertes":  len(alertes),
        }

    except Exception as e:
        return {"error": str(e)}
