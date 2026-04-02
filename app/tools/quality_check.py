import pandas as pd
import os


def quality_check(file_path: str) -> dict:
    """
    Analyse la qualité du dataset brut.
    Détecte : nulls, doublons, valeurs aberrantes.
    Calcule un Data Quality Score sur 100.
    Codé par P2.
    """
    if not os.path.exists(file_path):
        return {"error": f"Fichier introuvable : {file_path}"}

    try:
        if file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path, engine="openpyxl")
        else:
            df = pd.read_csv(file_path, encoding="unicode_escape", low_memory=False)

        total = len(df)
        problemes = []

        # ── 1. Valeurs manquantes ─────────────────────────
        nulls = df.isnull().sum()
        null_rate = df.isnull().sum().sum() / (total * len(df.columns))
        for col, count in nulls.items():
            if count > 0:
                pct = round(count / total * 100, 2)
                problemes.append({
                    "type":    "valeur_manquante",
                    "colonne": col,
                    "count":   int(count),
                    "pct":     pct
                })

        # ── 2. Doublons ───────────────────────────────────
        nb_doublons = int(df.duplicated().sum())
        if nb_doublons > 0:
            problemes.append({
                "type":  "doublon",
                "count": nb_doublons,
                "pct":   round(nb_doublons / total * 100, 2)
            })

        # ── 3. Colonnes numériques négatives ──────────────
        for col in df.select_dtypes(include=["number"]).columns:
            nb_neg = int((df[col] < 0).sum())
            if nb_neg > 0:
                problemes.append({
                    "type":    "valeur_negative",
                    "colonne": col,
                    "count":   nb_neg,
                    "pct":     round(nb_neg / total * 100, 2)
                })

        # ── 4. Calcul du Data Quality Score ───────────────
        score = 100.0
        score -= min(30, null_rate * 100)
        score -= min(10, nb_doublons / total * 100)
        neg_cols = sum(1 for p in problemes if p["type"] == "valeur_negative")
        score -= min(10, neg_cols * 5)
        score = round(max(0, score), 1)

        niveau = "excellent" if score >= 90 else \
                 "bon"       if score >= 75 else \
                 "moyen"     if score >= 50 else "mauvais"

        return {
            "score":     score,
            "niveau":    niveau,
            "nb_lignes": total,
            "problemes": problemes,
            "resume": {
                "nulls_total":  int(df.isnull().sum().sum()),
                "doublons":     nb_doublons,
                "taux_nulls":   round(null_rate * 100, 2),
            }
        }

    except Exception as e:
        return {"error": str(e)}
