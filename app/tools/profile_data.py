# app/tools/profile_data.py — VERSION MCP
# Accepte file_path au lieu de df directement
import pandas as pd
from app.tools.log_artifact import log_artifact

def profile_data(file_path: str, run_id: str) -> dict:
    """
    Charge le CSV depuis file_path et analyse la qualite.
    Accepte un chemin de fichier (compatible MCP).
    """
    print(f"[profile_data] Chargement de {file_path}...")
    df = pd.read_csv(file_path)

    print(f"[profile_data] Profilage de {len(df):,} lignes...")

    profile = {
        "run_id"         : run_id,
        "total_rows"     : len(df),
        "missing_values" : {},
        "problems"       : {},
        "quality_score"  : 0.0
    }

    for col in df.columns:
        nulls = int(df[col].isnull().sum())
        if nulls > 0:
            profile["missing_values"][col] = {
                "count" : nulls,
                "rate"  : round(nulls / len(df) * 100, 2)
            }

    cancels   = df[df['Invoice'].astype(str).str.startswith('C')]
    neg_qty   = df[df['Quantity'] < 0]
    bad_price = df[df['Price'] <= 0]
    cust_null = int(df['Customer ID'].isnull().sum())

    profile["problems"] = {
        "annulations"      : {"count": len(cancels),
                              "pct": round(len(cancels)/len(df)*100, 2)},
        "qty_negative"     : {"count": len(neg_qty),
                              "pct": round(len(neg_qty)/len(df)*100, 2)},
        "price_zero"       : {"count": len(bad_price),
                              "pct": round(len(bad_price)/len(df)*100, 2)},
        "customer_id_null" : {"count": cust_null,
                              "pct": round(cust_null/len(df)*100, 2)}
    }

    total_issues = len(cancels) + len(neg_qty) + len(bad_price)
    profile["quality_score"] = round(1 - (total_issues / len(df)), 3)

    print(f"[profile_data] Score qualite : {profile['quality_score']}")
    log_artifact(run_id, "profile_data", profile)
    return profile
