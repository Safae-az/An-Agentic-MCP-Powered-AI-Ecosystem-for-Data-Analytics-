import pandas as pd
import json
import os


SEUILS = {
    "taux_annulation": {"warning": 0.05, "critical": 0.10},
    "taux_retour":     {"warning": 0.05, "critical": 0.10},
}


def run_analysis(file_path: str, run_id: str) -> dict:
    """
    Calcule tous les KPIs business e-commerce.
    Détecte les alertes selon les seuils définis.
    Sauvegarde les insights en JSON.
    Codé par P2.
    """
    if not os.path.exists(file_path):
        return {"error": f"Fichier introuvable : {file_path}"}

    try:
        df = pd.read_csv(file_path, low_memory=False)

        # S'assurer que les colonnes existent
        if "Revenue" not in df.columns and "Quantity" in df.columns and "UnitPrice" in df.columns:
            df["Revenue"] = df["Quantity"] * df["UnitPrice"]

        kpis = {}

        # ── KPIs Revenus ──────────────────────────────────
        if "Revenue" in df.columns:
            kpis["CA_total"]      = round(float(df["Revenue"].sum()), 2)
            kpis["revenue_moyen"] = round(float(df["Revenue"].mean()), 2)

        # ── CA par mois ───────────────────────────────────
        if "Month" in df.columns and "Revenue" in df.columns:
            ca_mois = df.groupby("Month")["Revenue"].sum().round(2)
            kpis["CA_par_mois"] = ca_mois.to_dict()

        # ── CA par pays ───────────────────────────────────
        if "Country" in df.columns and "Revenue" in df.columns:
            ca_pays = df.groupby("Country")["Revenue"].sum().sort_values(ascending=False).head(10).round(2)
            kpis["CA_par_pays_top10"] = ca_pays.to_dict()

        # ── Clients ───────────────────────────────────────
        if "CustomerID" in df.columns:
            kpis["nb_clients_uniques"] = int(df["CustomerID"].nunique())

        # ── Commandes ─────────────────────────────────────
        if "InvoiceNo" in df.columns:
            kpis["nb_commandes"] = int(df["InvoiceNo"].nunique())
            if "Revenue" in df.columns:
                panier = df.groupby("InvoiceNo")["Revenue"].sum().mean()
                kpis["panier_moyen"] = round(float(panier), 2)

        # ── Top produits ──────────────────────────────────
        if "Description" in df.columns and "Revenue" in df.columns:
            top = df.groupby("Description")["Revenue"].sum().sort_values(ascending=False).head(10).round(2)
            kpis["top_10_produits"] = top.to_dict()

        # ── Taux annulation ───────────────────────────────
        if "InvoiceNo" in df.columns:
            total_inv  = df["InvoiceNo"].nunique()
            cancel_inv = df["InvoiceNo"].astype(str).str.startswith("C").sum()
            if total_inv > 0:
                kpis["taux_annulation"] = round(cancel_inv / total_inv, 4)

        # ── Pays ─────────────────────────────────────────
        if "Country" in df.columns:
            kpis["nb_pays"] = int(df["Country"].nunique())

        # ── Alertes ───────────────────────────────────────
        alertes = []
        for kpi_name, seuils in SEUILS.items():
            if kpi_name in kpis:
                valeur = kpis[kpi_name]
                if valeur >= seuils["critical"]:
                    alertes.append({
                        "kpi":    kpi_name,
                        "valeur": valeur,
                        "niveau": "critical",
                        "seuil":  seuils["critical"],
                        "message": f"{kpi_name} = {valeur:.1%} dépasse le seuil critique {seuils['critical']:.1%}"
                    })
                elif valeur >= seuils["warning"]:
                    alertes.append({
                        "kpi":    kpi_name,
                        "valeur": valeur,
                        "niveau": "warning",
                        "seuil":  seuils["warning"],
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

        # ── Sauvegarder le fichier insights ───────────────
        output_path = f"runs/{run_id}/artifacts/insights.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({"kpis": kpis, "alertes": alertes, "insights": insights}, f, indent=2)

        return {
            "output_path": output_path,
            "kpis":        kpis,
            "alertes":     alertes,
            "insights":    insights,
            "nb_alertes":  len(alertes),
        }

    except Exception as e:
        return {"error": str(e)}
