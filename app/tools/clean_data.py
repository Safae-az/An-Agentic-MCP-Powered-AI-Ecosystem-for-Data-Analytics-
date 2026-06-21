import pandas as pd
import json
import os
from groq import Groq
from dotenv import load_dotenv
from app.tools.log_artifact import log_artifact

load_dotenv()


# ─────────────────────────────────────────────────────────────────────
# CONSTANTES GÉNÉRIQUES
# ─────────────────────────────────────────────────────────────────────

# Colonnes où le préfixe C peut être normal
SKIP_PREFIX_COLS = {
    "stockcode", "country", "code", "currency", "category",
    "class", "continent", "city"
}

# Colonnes où les valeurs négatives peuvent être normales
SIGNED_ALLOWED_HINTS = {
    "change", "variation", "difference", "delta",
    "growth", "z_score", "score", "temperature",
    "balance", "profit", "loss"
}

# Colonnes où les valeurs négatives sont généralement invalides
NON_NEGATIVE_HINTS = {
    "age", "count", "number", "total", "population",
    "rate", "percentage", "percent", "prevalence",
    "incidence", "burden", "deaths", "cases",
    "quantity", "qty", "price", "amount", "cost"
}

# Colonnes qui peuvent représenter des annulations e-commerce
CANCELLATION_HINTS = {
    "invoice", "order", "transaction", "bill", "receipt"
}

# Colonnes identifiants / codes : ne jamais convertir en numérique
IDENTIFIER_HINTS = {
    "id", "code", "ref", "invoice", "stock",
    "sku", "product", "customer", "client",
    "user", "zip", "postal"
}

# Mapping attribut dt -> nom de colonne cible
DATE_ATTR_MAP = {
    "year"           : "Year",
    "month"          : "Month",
    "to_period('m')" : "YearMonth",
    "to_period_m"    : "YearMonth",
    "to_period('M')" : "YearMonth",
    "to_period_M"    : "YearMonth",
}


def should_remove_negative(col: str) -> bool:
    """
    Décide si les valeurs négatives doivent être supprimées.
    Ne supprime pas automatiquement les négatifs pour tous les datasets.
    """
    name = col.lower()

    if any(k in name for k in SIGNED_ALLOWED_HINTS):
        return False

    return any(k in name for k in NON_NEGATIVE_HINTS)


def is_cancellation_column(col: str) -> bool:
    """
    Détecte si une colonne ressemble à une colonne d'annulation e-commerce.
    Exemple : InvoiceNo, OrderID, TransactionCode.
    """
    name = col.lower()

    if name in SKIP_PREFIX_COLS:
        return False

    return any(k in name for k in CANCELLATION_HINTS)


def is_identifier_column(col: str) -> bool:
    """
    Détecte les colonnes identifiants/codes.
    Même si elles ressemblent à des nombres, elles doivent rester en texte.

    Exemples :
    - Invoice
    - StockCode
    - Customer ID
    - ProductCode
    - SKU
    - Ref
    """
    name = col.lower()
    return any(k in name for k in IDENTIFIER_HINTS)


# ─────────────────────────────────────────────────────────────────────
# FALLBACK — RÈGLES HEURISTIQUES SI GROQ INACCESSIBLE
# ─────────────────────────────────────────────────────────────────────

def _fallback_rules(profile: dict) -> list:
    """
    Règles heuristiques si Groq est inaccessible.
    Version générique multi-datasets.
    """
    print("[clean_data] Fallback pandas — règles heuristiques")

    rules = []
    rid = 1

    columns_info = profile.get("columns_info", {})
    duplicate_rows = int(profile.get("duplicate_rows", 0))

    # Doublons globaux
    if duplicate_rows > 0:
        rules.append({
            "rule_id": rid,
            "column": "global",
            "action": "drop_duplicates",
            "params": {"subset": None},
            "description": "Remove duplicate rows"
        })
        rid += 1

    for col, info in columns_info.items():
        neg = int(info.get("negative_count", info.get("numeric_negative_count", 0)))
        null_rate = float(info.get("null_rate_pct", 0))
        prefix_c = int(info.get("prefix_counts", {}).get("C", 0))
        is_dt = bool(info.get("parseable_as_datetime", False))
        is_numeric_text = bool(info.get("parseable_as_numeric", False))

        # Valeurs négatives : supprimer seulement si la colonne doit être non négative
        if neg > 0 and should_remove_negative(col):
            rules.append({
                "rule_id": rid,
                "column": col,
                "action": "drop_rows_where",
                "params": {"condition": f"`{col}` < 0"},
                "description": f"Remove invalid negative values in {col}"
            })
            rid += 1

        # Préfixe C : supprimer seulement si colonne facture/commande/transaction
        if prefix_c > 0 and is_cancellation_column(col):
            rules.append({
                "rule_id": rid,
                "column": col,
                "action": "filter_prefix",
                "params": {"prefix": "C", "keep": False},
                "description": f"Remove cancellation records in {col}"
            })
            rid += 1

        # Valeurs manquantes
        if null_rate > 0:
            col_lower = col.lower()

            if is_identifier_column(col):
                val = "Anonymous"
            elif any(k in col_lower for k in ["country", "entity", "name", "category", "class"]):
                val = "Unknown"
            else:
                val = "median" if info.get("dtype", "").startswith(("int", "float")) else "Unknown"

            rules.append({
                "rule_id": rid,
                "column": col,
                "action": "fill_nulls",
                "params": {"value": val},
                "description": f"Fill nulls in {col}"
            })
            rid += 1

        # Nombres stockés comme texte
        # IMPORTANT : ne jamais convertir les identifiants/codes en float.
        if is_numeric_text and not is_identifier_column(col):
            rules.append({
                "rule_id": rid,
                "column": col,
                "action": "convert_dtype",
                "params": {"dtype": "float"},
                "description": f"Convert numeric text column {col} to float"
            })
            rid += 1

        # Dates
        if is_dt:
            rules.append({
                "rule_id": rid,
                "column": col,
                "action": "convert_dtype",
                "params": {"dtype": "datetime"},
                "description": f"Convert {col} to datetime"
            })
            rid += 1

            for new_col, formula in [
                ("Year", f"{col}.dt.year"),
                ("Month", f"{col}.dt.month"),
                ("YearMonth", f"{col}.dt.to_period('M')")
            ]:
                rules.append({
                    "rule_id": rid,
                    "column": new_col,
                    "action": "create_column",
                    "params": {"formula": formula, "round": None},
                    "description": f"Create {new_col} from {col}"
                })
                rid += 1

    print(f"[clean_data] Fallback : {len(rules)} règles générées")
    return rules


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 1 — DEMANDER À GROQ LES RÈGLES DE NETTOYAGE
# ─────────────────────────────────────────────────────────────────────

def _ask_groq_cleaning_rules(profile: dict) -> list:
    """
    Demande à Groq une liste de règles de nettoyage.
    Si Groq échoue, fallback pandas.
    """
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        print("[clean_data] GROQ_API_KEY absente — fallback heuristique")
        return _fallback_rules(profile)

    client = Groq(api_key=api_key)

    system_prompt = """You are a senior Data Engineer.
You receive a data quality profile of a dataset.
Your job is to produce a precise list of cleaning rules to apply to this dataset.

Respond ONLY with a valid JSON array — no explanation, no markdown, no backticks.

Each rule must have this exact structure:
{
  "rule_id": <integer starting at 1>,
  "column": "<exact column name from the profile or 'global' only for drop_duplicates>",
  "action": "<one of: drop_rows_where, fill_nulls, convert_dtype, create_column, drop_duplicates, filter_prefix>",
  "params": { <action-specific parameters> },
  "description": "<short English description>"
}

Action parameters:
- drop_rows_where : { "condition": "<pandas eval string, e.g. `Column` < 0>" }
- filter_prefix   : { "prefix": "<string>", "keep": false }
- fill_nulls      : { "value": "<'Unknown' | 'Anonymous' | 'mean' | 'median' | 'mode'>" }
- convert_dtype   : { "dtype": "<datetime | int | float | str>" }
- create_column   : { "formula": "<pandas eval expression>", "round": <int or null> }
- drop_duplicates : { "subset": [<col names>] or null }

Important generic cleaning rules:
1. Be generic and adaptive. Do NOT assume the dataset is sales, retail, or e-commerce.
2. Do NOT create Sales, Revenue, CA, or business KPI columns. KPI creation belongs to the data science step.
3. Do NOT remove negative values automatically.
4. Remove negative values only when the column name clearly represents a non-negative measure:
   age, count, total, population, rate, percentage, prevalence, incidence, burden, deaths, cases, quantity, price, amount.
5. Do NOT treat values starting with C as cancellations unless the column name clearly refers to invoice, order, transaction, bill, or receipt.
6. If parseable_as_numeric=true, convert it to numeric only if the column is not an identifier/code column.
7. If parseable_as_datetime=true, convert it to datetime and optionally create Year, Month, YearMonth.
8. If duplicate_rows > 0, add one drop_duplicates rule with column='global'.
9. For ID/customer/client/user/code/ref/invoice/stock/sku/product columns, fill missing values with 'Anonymous', not mean.
10. Never convert identifier/code columns to numeric, even if they look numeric.
    Keep columns such as Invoice, StockCode, Customer ID, ID, Code, Ref, SKU, ProductCode as string/text.
11. Do not add rules for columns with no problems."""

    profile_summary = {
        "total_rows"        : profile.get("total_rows"),
        "total_columns"     : profile.get("total_columns"),
        "duplicate_rows"    : profile.get("duplicate_rows", 0),
        "duplicate_rate_pct": profile.get("duplicate_rate_pct", 0),
        "columns_info"      : profile.get("columns_info"),
        "problems"          : profile.get("problems"),
        "cleaning_hints"    : profile.get("cleaning_hints"),
    }

    user_prompt = f"""Data quality profile:

{json.dumps(profile_summary, indent=2, ensure_ascii=False)}

Return the JSON array of cleaning rules."""

    import time

    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=2500
            )
            break

        except Exception as e:
            print(f"[clean_data] Tentative {attempt}/3 échouée : {type(e).__name__} — {e}")

            if attempt < 3:
                time.sleep(2 * attempt)

    else:
        print("[clean_data] Groq inaccessible — fallback heuristique")
        return _fallback_rules(profile)

    raw_text = response.choices[0].message.content.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    raw_text = raw_text.strip()

    try:
        rules = json.loads(raw_text)

        if not isinstance(rules, list):
            print("[clean_data] WARNING: Groq n'a pas retourné une liste — fallback")
            return _fallback_rules(profile)

        print(f"[clean_data] Groq a généré {len(rules)} règles")
        return rules

    except json.JSONDecodeError as e:
        print(f"[clean_data] WARNING: JSON parse échoué — {e}")
        return _fallback_rules(profile)


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — APPLIQUER LES RÈGLES
# ─────────────────────────────────────────────────────────────────────

def _apply_rules(df: pd.DataFrame, rules: list) -> tuple:
    """
    Applique les règles de nettoyage sur le DataFrame.
    Retourne df_clean, steps.
    """
    steps = []

    for rule in rules:
        rule_id = rule.get("rule_id", "?")
        column = rule.get("column", "global")
        action = rule.get("action", "")
        params = rule.get("params", {})
        desc = rule.get("description", "")

        print(f"  [règle {rule_id}] {action} | '{column}' — {desc}")

        try:
            before = len(df)

            # ── filter_prefix ────────────────────────────────────────
            if action == "filter_prefix":
                if column in df.columns:
                    prefix = params.get("prefix", "")
                    keep = params.get("keep", False)

                    mask = df[column].astype(str).str.startswith(prefix)
                    df = df[mask] if keep else df[~mask]

                    removed = before - len(df)

                    steps.append({
                        "rule_id": rule_id,
                        "action": action,
                        "column": column,
                        "prefix": prefix,
                        "rows_removed": removed
                    })

                    print(f"    -> {removed:,} lignes supprimées, préfixe '{prefix}'")
                else:
                    print(f"    WARNING colonne '{column}' introuvable")

            # ── drop_rows_where ──────────────────────────────────────
            elif action == "drop_rows_where":
                condition = params.get("condition", "")

                try:
                    mask = df.eval(condition)
                    df = df[~mask]

                    removed = before - len(df)

                    steps.append({
                        "rule_id": rule_id,
                        "action": action,
                        "column": column,
                        "condition": condition,
                        "rows_removed": removed
                    })

                    print(f"    -> {removed:,} lignes supprimées ({condition})")

                except Exception as e:
                    print(f"    WARNING drop_rows_where échoue : {e}")

            # ── fill_nulls ───────────────────────────────────────────
            elif action == "fill_nulls":
                if column in df.columns:
                    fill_value = params.get("value", "Unknown")
                    null_count = int(df[column].isnull().sum())
                    col_lower = column.lower()

                    if fill_value == "mean" and is_identifier_column(column):
                        fill_value = "Anonymous"
                        print("    [correction] fill 'mean' -> 'Anonymous' pour colonne ID/code")

                    if fill_value == "mean":
                        if pd.api.types.is_numeric_dtype(df[column]):
                            df[column] = df[column].fillna(df[column].mean())
                        else:
                            df[column] = df[column].fillna("Unknown")

                    elif fill_value == "median":
                        if pd.api.types.is_numeric_dtype(df[column]):
                            df[column] = df[column].fillna(df[column].median())
                        else:
                            df[column] = df[column].fillna("Unknown")

                    elif fill_value == "mode":
                        mode = df[column].mode()
                        value = mode.iloc[0] if not mode.empty else "Unknown"
                        df[column] = df[column].fillna(value)

                    elif fill_value == "Anonymous":
                        df[column] = df[column].astype(object)
                        df[column] = df[column].where(df[column].notna(), "Anonymous")

                    else:
                        df[column] = df[column].fillna(fill_value)

                    steps.append({
                        "rule_id": rule_id,
                        "action": action,
                        "column": column,
                        "rows_filled": null_count,
                        "fill_value": fill_value
                    })

                    print(f"    -> {null_count:,} nulls remplis avec '{fill_value}'")
                else:
                    print(f"    WARNING colonne '{column}' introuvable")

            # ── convert_dtype ────────────────────────────────────────
            elif action == "convert_dtype":
                if column in df.columns:
                    dtype = params.get("dtype", "str")

                    # Protection très importante :
                    # Les identifiants/codes doivent rester en texte.
                    if dtype in ("int", "float") and is_identifier_column(column):
                        df[column] = df[column].astype(str)

                        steps.append({
                            "rule_id": rule_id,
                            "action": "skip_numeric_conversion_identifier",
                            "column": column,
                            "requested_dtype": dtype,
                            "final_dtype": "str"
                        })

                        print(f"    -> conversion numérique ignorée pour identifiant/code '{column}'")
                        continue

                    if dtype == "datetime":
                        df[column] = pd.to_datetime(df[column], errors="coerce")

                    elif dtype == "int":
                        cleaned = (
                            df[column]
                            .astype(str)
                            .str.replace("%", "", regex=False)
                            .str.replace(" ", "", regex=False)
                            .str.replace(",", ".", regex=False)
                        )
                        df[column] = pd.to_numeric(cleaned, errors="coerce").astype("Int64")

                    elif dtype == "float":
                        cleaned = (
                            df[column]
                            .astype(str)
                            .str.replace("%", "", regex=False)
                            .str.replace(" ", "", regex=False)
                            .str.replace(",", ".", regex=False)
                        )
                        df[column] = pd.to_numeric(cleaned, errors="coerce")

                    elif dtype == "str":
                        df[column] = df[column].astype(str)

                    steps.append({
                        "rule_id": rule_id,
                        "action": action,
                        "column": column,
                        "dtype": dtype
                    })

                    print(f"    -> '{column}' converti en {dtype}")
                else:
                    print(f"    WARNING colonne '{column}' introuvable")

            # ── create_column ────────────────────────────────────────
            elif action == "create_column":
                formula = params.get("formula", "")
                round_val = params.get("round", None)

                if ".dt." in formula:
                    parts = formula.split(".dt.")
                    src_col = parts[0].strip()
                    attr = parts[1].strip() if len(parts) > 1 else ""

                    if column in ("global", "", None):
                        column = DATE_ATTR_MAP.get(
                            attr.lower(),
                            DATE_ATTR_MAP.get(attr, "DateDerived")
                        )

                    if src_col in df.columns:
                        src = pd.to_datetime(df[src_col], errors="coerce")

                        if attr == "year":
                            df[column] = src.dt.year

                        elif attr == "month":
                            df[column] = src.dt.month

                        elif attr.lower() in ("to_period_m", "to_period('m')", "to_period('M')"):
                            df[column] = src.dt.to_period("M").astype(str)

                        else:
                            print(f"    WARNING attribut date non supporté : {attr}")
                            continue

                        steps.append({
                            "rule_id": rule_id,
                            "action": action,
                            "column": column,
                            "formula": formula
                        })

                        print(f"    -> '{column}' créé depuis {formula}")

                    else:
                        print(f"    WARNING colonne source '{src_col}' introuvable")

                else:
                    try:
                        series = df.eval(formula)

                        if round_val is not None:
                            series = series.round(round_val)

                        df[column] = series

                        steps.append({
                            "rule_id": rule_id,
                            "action": action,
                            "column": column,
                            "formula": formula
                        })

                        print(f"    -> '{column}' créé : {formula}")

                    except Exception as e:
                        print(f"    WARNING create_column échoue : {e}")

            # ── drop_duplicates ──────────────────────────────────────
            elif action == "drop_duplicates":
                subset = params.get("subset", None)

                before2 = len(df)
                df = df.drop_duplicates(subset=subset)
                removed = before2 - len(df)

                steps.append({
                    "rule_id": rule_id,
                    "action": action,
                    "subset": subset,
                    "rows_removed": removed
                })

                print(f"    -> {removed:,} doublons supprimés")

            else:
                print(f"    WARNING action inconnue '{action}' — ignorée")

        except Exception as e:
            print(f"  WARNING règle {rule_id} échouée : {e}")

            steps.append({
                "rule_id": rule_id,
                "action": action,
                "column": column,
                "error": str(e)
            })

    return df, steps


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 3 — POST-TRAITEMENT DE SÉCURITÉ
# ─────────────────────────────────────────────────────────────────────

def _is_index_like_series(series: pd.Series) -> bool:
    """Identify exported row indexes without discarding real anonymous data."""
    non_null = series.dropna()
    if non_null.empty:
        return True
    numeric = pd.to_numeric(non_null, errors="coerce")
    if numeric.isna().any():
        return False
    values = numeric.astype(float).tolist()
    zero_based = [float(index) for index in range(len(values))]
    one_based = [float(index) for index in range(1, len(values) + 1)]
    return values == zero_based or values == one_based


def _post_process(df: pd.DataFrame, profile: dict) -> tuple:
    """
    Corrige ce que Groq ou le fallback peut rater.
    Version générique multi-datasets.
    """
    steps = []
    columns_info = profile.get("columns_info", {})

    # 1. Supprimer colonnes parasites
    PARASITE_NAMES = {"global", "unnamed", "index", "level_0"}

    parasite_candidates = [
        c for c in df.columns
        if str(c).lower().strip() in PARASITE_NAMES
        or str(c).lower().startswith("unnamed:")
    ]
    parasites = [
        c for c in parasite_candidates
        if df[c].isnull().all() or _is_index_like_series(df[c])
    ]

    if parasites:
        df = df.drop(columns=parasites)

        steps.append({
            "action": "post_drop_parasite_columns",
            "columns": parasites
        })

        print(f"  [post] Colonnes parasites supprimées : {parasites}")

    # 2. Supprimer colonnes 100% vides
    all_null = [c for c in df.columns if df[c].isnull().all()]

    if all_null:
        df = df.drop(columns=all_null)

        steps.append({
            "action": "post_drop_all_null_columns",
            "columns": all_null
        })

        print(f"  [post] Colonnes 100% vides supprimées : {all_null}")

    # 3. Supprimer les négatifs seulement si la colonne doit être non négative
    for col, info in columns_info.items():
        if col not in df.columns:
            continue

        neg = int(info.get("negative_count", info.get("numeric_negative_count", 0)))

        if neg > 0 and pd.api.types.is_numeric_dtype(df[col]) and should_remove_negative(col):
            before = len(df)
            df = df[df[col] >= 0]
            removed = before - len(df)

            if removed > 0:
                steps.append({
                    "action": "post_remove_negative",
                    "column": col,
                    "rows_removed": removed
                })

                print(f"  [post] '{col}' négatifs invalides : {removed:,} lignes supprimées")

    # 4. Annulations restantes C* seulement pour colonnes e-commerce
    for col, info in columns_info.items():
        if col not in df.columns:
            continue

        if col.lower() in SKIP_PREFIX_COLS:
            continue

        prefix_counts = info.get("prefix_counts", {})

        if "C" in prefix_counts and prefix_counts["C"] > 0 and is_cancellation_column(col):
            before = len(df)
            mask = df[col].astype(str).str.match(r"^C\d")

            if mask.sum() > 0:
                df = df[~mask]
                removed = before - len(df)

                steps.append({
                    "action": "post_remove_cancellation_prefix_C",
                    "column": col,
                    "rows_removed": removed
                })

                print(f"  [post] '{col}' annulations C* restantes : {removed:,} supprimées")

    # 5. Outliers extrêmes génériques, sans toucher aux colonnes ID/date/code
    SKIP_OUTLIER = {
        "year", "month", "id", "code", "zip", "postal",
        "latitude", "longitude", "invoice", "stock", "sku"
    }

    for col in df.select_dtypes(include="number").columns:
        if any(k in col.lower() for k in SKIP_OUTLIER):
            continue

        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1

        if pd.isna(iqr) or iqr == 0:
            continue

        lower = q1 - 10 * iqr
        upper = q3 + 10 * iqr

        before = len(df)
        df = df[(df[col] >= lower) & (df[col] <= upper)]
        removed = before - len(df)

        if removed > 0:
            steps.append({
                "action": "post_remove_extreme_outliers",
                "column": col,
                "rows_removed": removed,
                "bounds": [round(float(lower), 2), round(float(upper), 2)]
            })

            print(f"  [post] '{col}' outliers extrêmes IQR x10 : {removed:,} lignes supprimées")

    # 6. Encodage texte cassé U+FFFD
    for col in df.select_dtypes(include="object").columns:
        if df[col].astype(str).str.contains("\ufffd", na=False).any():
            df[col] = df[col].astype(str).str.replace("\ufffd", "", regex=False)

            steps.append({
                "action": "post_fix_encoding",
                "column": col
            })

            print(f"  [post] '{col}' encodage cassé corrigé")

    # 7. Convertir colonnes numériques stockées comme texte
    # IMPORTANT : ne jamais convertir les colonnes identifiants/codes.
    for col, info in columns_info.items():
        if col not in df.columns:
            continue

        if (
            info.get("parseable_as_numeric", False)
            and df[col].dtype == object
            and not is_identifier_column(col)
        ):
            cleaned = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
            )

            converted = pd.to_numeric(cleaned, errors="coerce")
            valid_pct = converted.notnull().mean()

            if valid_pct > 0.8:
                df[col] = converted

                steps.append({
                    "action": "post_convert_numeric_text",
                    "column": col,
                    "valid_pct": round(float(valid_pct * 100), 2)
                })

                print(f"  [post] '{col}' converti texte -> numérique")

    # 8. Dates invalides et création Year / Month / YearMonth
    date_col = None

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_col = col
            break

        if df[col].dtype == object and not is_identifier_column(col):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                valid_pct = parsed.notnull().mean()

                if valid_pct > 0.8:
                    df[col] = parsed
                    date_col = col

                    steps.append({
                        "action": "post_convert_datetime",
                        "column": col,
                        "valid_pct": round(float(valid_pct * 100), 2)
                    })

                    print(f"  [post] '{col}' converti en datetime")
                    break

            except Exception:
                pass

    if date_col:
        src = pd.to_datetime(df[date_col], errors="coerce")

        nat_count = int(src.isnull().sum())

        if nat_count > 0:
            before = len(df)
            df = df[src.notnull()]
            src = pd.to_datetime(df[date_col], errors="coerce")
            removed = before - len(df)

            steps.append({
                "action": "post_remove_invalid_dates",
                "column": date_col,
                "rows_removed": removed
            })

            print(f"  [post] '{date_col}' dates invalides : {removed:,} lignes supprimées")

        for new_col, extractor in [
            ("Year", lambda s: s.dt.year),
            ("Month", lambda s: s.dt.month),
            ("YearMonth", lambda s: s.dt.to_period("M").astype(str)),
        ]:
            if new_col not in df.columns:
                df[new_col] = extractor(src)

                steps.append({
                    "action": f"post_create_{new_col}",
                    "from": date_col
                })

                print(f"  [post] '{new_col}' créé depuis '{date_col}'")

    # 9. Protection finale : identifiants/codes restent en texte
    for col in df.columns:
        if is_identifier_column(col):
            df[col] = df[col].astype(str)

            # Corriger les textes "nan" créés par astype(str)
            df[col] = df[col].replace({"nan": "Anonymous", "None": "Anonymous", "<NA>": "Anonymous"})

    print(f"  [post] {len(steps)} corrections appliquées")
    return df, steps


# ─────────────────────────────────────────────────────────────────────
# JSON SAFE
# ─────────────────────────────────────────────────────────────────────

def _safe(obj):
    """
    Convertit les types numpy/pandas en types JSON-safe.
    """
    import numpy as np

    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}

    elif isinstance(obj, list):
        return [_safe(i) for i in obj]

    elif isinstance(obj, np.integer):
        return int(obj)

    elif isinstance(obj, np.floating):
        return float(obj)

    elif isinstance(obj, np.bool_):
        return bool(obj)

    elif obj is None:
        return None

    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    if hasattr(obj, "strftime"):
        return str(obj)

    return obj


# ─────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE — COMPATIBLE MCP SERVER
# ─────────────────────────────────────────────────────────────────────

def _smart_read(file_path: str) -> pd.DataFrame:
    """Charge CSV ou JSON (plat ou imbriqué) selon l'extension."""
    from app.tools.load_dataset import _load_json_smart
    if os.path.splitext(file_path)[1].lower() == ".json":
        return _load_json_smart(file_path)
    return pd.read_csv(file_path, low_memory=False)


def clean_data(file_path: str, run_id: str) -> dict:
    """
    Nettoie un dataset déjà chargé/profilé.
    Compatible MCP Server.
    Même signature qu'avant : clean_data(file_path, run_id).
    """
    print(f"[clean_data] Chargement de {file_path}...")

    try:
        df = _smart_read(file_path)
    except Exception as e:
        result = {
            "status": "error",
            "run_id": run_id,
            "file_path": file_path,
            "message": f"Erreur lecture fichier : {str(e)}"
        }
        log_artifact(run_id, "clean_data", result)
        return result

    initial_rows = len(df)

    print(f"[clean_data] {initial_rows:,} lignes x {len(df.columns)} colonnes")

    # Charger le profil existant
    profile_path = f"runs/{run_id}/artifacts/profile.json"

    if os.path.exists(profile_path):
        print(f"[clean_data] Profil trouvé : {profile_path}")

        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

    else:
        print("[clean_data] Profil non trouvé — génération d'un profil brut")

        from app.tools.profile_data import _build_raw_profile

        raw = _build_raw_profile(df)

        profile = {
            "status": "success",
            "run_id": run_id,
            "file_path": file_path,
            "total_rows": raw.get("total_rows"),
            "total_columns": raw.get("total_columns"),
            "duplicate_rows": raw.get("duplicate_rows", 0),
            "duplicate_rate_pct": raw.get("duplicate_rate_pct", 0),
            "columns_info": raw.get("columns", {}),
            "problems": [],
            "cleaning_hints": []
        }

    # Génération des règles
    print("[clean_data] Génération des règles via Groq...")
    rules = _ask_groq_cleaning_rules(profile)

    artifacts_dir = f"runs/{run_id}/artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)

    rules_path = f"{artifacts_dir}/cleaning_rules.json"

    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

    print(f"[clean_data] Règles sauvegardées : {rules_path}")

    # Application des règles Groq/fallback
    print(f"[clean_data] Application de {len(rules)} règles...")
    df_clean, steps = _apply_rules(df, rules)

    # Post-traitement sécurité
    print("[clean_data] Post-traitement de sécurité...")
    df_clean, post_steps = _post_process(df_clean, profile)

    steps.extend(post_steps)

    # Sauvegarde clean.csv
    csv_path = f"{artifacts_dir}/clean.csv"
    df_clean.to_csv(csv_path, index=False)

    removal_rate = 0.0

    if initial_rows > 0:
        removal_rate = round((initial_rows - len(df_clean)) / initial_rows * 100, 2)

    report = {
        "status": "success",
        "run_id": run_id,
        "initial_rows": int(initial_rows),
        "final_rows": int(len(df_clean)),
        "rows_removed": int(initial_rows - len(df_clean)),
        "removal_rate": removal_rate,
        "rules_applied": int(len(rules)),
        "steps": _safe(steps),
        "output_path": csv_path,
        "rules_path": rules_path,
        "columns_final": list(df_clean.columns)
    }

    print("\n[clean_data] RÉSUMÉ")
    print(f"  {initial_rows:,} -> {len(df_clean):,} lignes ({report['removal_rate']}% supprimés)")
    print(f"  Règles appliquées : {len(rules)}")
    print(f"  Colonnes finales  : {list(df_clean.columns)}")
    print(f"  clean.csv         : {csv_path}")

    log_artifact(run_id, "clean_data", {
        "status": "success",
        "initial_rows": initial_rows,
        "final_rows": len(df_clean),
        "rules_applied": len(rules),
        "output_path": csv_path
    })

    return report
