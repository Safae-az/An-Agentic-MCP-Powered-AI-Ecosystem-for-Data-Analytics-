# app/tools/clean_data.py — VERSION MCP
# Accepte file_path au lieu de df directement
import pandas as pd
import os
from app.tools.log_artifact import log_artifact

def clean_data(file_path: str, run_id: str) -> dict:
    """
    Charge le CSV depuis file_path et applique 7 regles.
    Accepte un chemin de fichier (compatible MCP).
    """
    print(f"[clean_data] Chargement de {file_path}...")
    df = pd.read_csv(file_path)

    print(f"[clean_data] Nettoyage de {len(df):,} lignes...")
    initial_rows = len(df)
    steps = []

    # 1. Supprimer annulations
    mask = df['Invoice'].astype(str).str.startswith('C')
    df   = df[~mask]
    steps.append({"step": "remove_cancellations",
                  "rows_removed": int(mask.sum())})
    print(f"  Annulations supprimees : {mask.sum():,}")

    # 2. Supprimer qty negatives
    mask = df['Quantity'] <= 0
    df   = df[~mask]
    steps.append({"step": "remove_negative_qty",
                  "rows_removed": int(mask.sum())})
    print(f"  Qty negatives supprimees : {mask.sum():,}")

    # 3. Supprimer prix nuls
    mask = df['Price'] <= 0
    df   = df[~mask]
    steps.append({"step": "remove_bad_price",
                  "rows_removed": int(mask.sum())})
    print(f"  Prix nuls supprimes : {mask.sum():,}")

    # 4. Customer ID manquant → Anonymous
    null_c = int(df['Customer ID'].isnull().sum())
    df['Customer ID'] = df['Customer ID'].fillna(0).astype(int).astype(str)
    df['Customer ID'] = df['Customer ID'].replace('0', 'Anonymous')
    steps.append({"step": "fill_customer_id", "rows_filled": null_c})
    print(f"  Customer ID anonymises : {null_c:,}")

    # 5. Description manquante → Unknown
    df['Description'] = df['Description'].fillna('Unknown')
    steps.append({"step": "fill_description"})

    # 6. Creer colonne Sales
    df['Sales'] = (df['Quantity'] * df['Price']).round(2)
    steps.append({"step": "create_sales_column"})
    print(f"  Colonne Sales creee")

    # 7. Extraire colonnes date
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
    df['Year']        = df['InvoiceDate'].dt.year
    df['Month']       = df['InvoiceDate'].dt.month
    df['YearMonth']   = df['InvoiceDate'].dt.to_period('M').astype(str)
    steps.append({"step": "extract_date_columns"})
    print(f"  Colonnes date extraites")

    # Sauvegarder dans artifacts/
    artifacts_dir = f"runs/{run_id}/artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)
    csv_path = f"{artifacts_dir}/clean.csv"
    df.to_csv(csv_path, index=False)

    report = {
        "status"        : "success",
        "run_id"        : run_id,
        "initial_rows"  : initial_rows,
        "final_rows"    : len(df),
        "rows_removed"  : initial_rows - len(df),
        "removal_rate"  : round((initial_rows-len(df))/initial_rows*100, 2),
        "steps"         : steps,
        "output_path"   : csv_path,
        "columns_final" : list(df.columns)
    }

    print(f"\n  {initial_rows:,} → {len(df):,} lignes")
    print(f"  Sauvegarde : {csv_path}")

    log_artifact(run_id, "clean_data", report)

    return report

