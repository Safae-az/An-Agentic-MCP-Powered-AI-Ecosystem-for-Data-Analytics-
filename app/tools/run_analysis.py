# app/tools/run_analysis.py
"""
run_analysis — Système générique avec détection libre du domaine par Groq.

Groq détecte LIBREMENT le domaine (pas de liste fixe).
Groq génère les KPIs VRAIMENT pertinents pour CE dataset.
Pandas exécute le plan. Data Quality toujours calculée.
Tous les résultats → insights[] lisibles.

Correction v2 :
  - Protection des formules invalides dans action=computed
  - Protection action=count quand Groq génère une expression au lieu d'un nom de colonne
  - Fallback propre sur chaque KPI en erreur sans bloquer le reste
"""

import os
import json
import re
import time
import pandas as pd
from groq import Groq
from dotenv import load_dotenv
from app.tools.log_artifact import log_artifact

load_dotenv()

ANONYMOUS_COLUMN_PATTERN = re.compile(
    r"^(?:[a-z]\d+|\d+|[a-z]|(?:col(?:umn)?|feature|feat|var|field|attr|unnamed)[_\- ]?\d*)$",
    re.IGNORECASE,
)
ANONYMOUS_DATASET_THRESHOLD = 0.5


def _is_anonymous_column(column: object) -> bool:
    """Detect generic headers such as x1, A, col_2 or Unnamed: 0."""
    name = str(column).strip().lower().replace(":", "")
    return bool(ANONYMOUS_COLUMN_PATTERN.fullmatch(name))


def _anonymous_columns(columns) -> list[str]:
    return [str(column) for column in columns if _is_anonymous_column(column)]


def _sanitize_alias(value: object) -> str:
    alias = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return alias[:64]


def _infer_column_semantic(series: pd.Series, original_name: str) -> str:
    """Infer a stable provisional alias when Groq is unavailable."""
    base = _sanitize_alias(original_name) or "column"
    non_null = series.dropna()
    if non_null.empty:
        return f"{base}_value"

    unique_count = int(non_null.nunique(dropna=True))
    unique_ratio = unique_count / max(len(non_null), 1)
    numeric = pd.to_numeric(non_null, errors="coerce")
    is_numeric = numeric.notna().mean() >= 0.95
    if unique_count == 2:
        return f"{base}_rate"
    if unique_count <= 5:
        return f"{base}_type"
    if unique_ratio >= 0.98:
        return f"{base}_id"
    if not is_numeric:
        return f"{base}_category" if unique_count <= 30 else f"{base}_text"

    values = numeric.dropna()
    if values.between(0, 1).all():
        return f"{base}_score"
    if (values < 0).any():
        return f"{base}_balance"
    median = float(values.median())
    if median > 1000:
        return f"{base}_revenue"
    if median > 100:
        return f"{base}_total"
    if ((values % 1) == 0).all() and (values >= 0).all():
        return f"{base}_count"
    return f"{base}_value"


def _anonymous_column_summary(df: pd.DataFrame, columns: list[str]) -> dict:
    summary = {}
    sample = df[columns].head(500)
    for column in columns:
        series = sample[column]
        numeric = pd.to_numeric(series, errors="coerce")
        info = {
            "dtype": str(series.dtype),
            "null_ratio": round(float(series.isna().mean()), 4),
            "unique_count": int(series.nunique(dropna=True)),
            "examples": [str(value)[:80] for value in series.dropna().head(3).tolist()],
        }
        if numeric.notna().any():
            values = numeric.dropna()
            info.update({
                "numeric_ratio": round(float(numeric.notna().mean()), 4),
                "min": round(float(values.min()), 4),
                "max": round(float(values.max()), 4),
                "mean": round(float(values.mean()), 4),
            })
        summary[column] = info
    return summary


def _ask_groq_for_aliases(
    df: pd.DataFrame, anonymous: list[str], known_columns: list[str]
) -> dict[str, str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {}
    payload = {
        "known_columns": known_columns,
        "anonymous_columns": _anonymous_column_summary(df, anonymous),
    }
    prompt = (
        "Infer cautious provisional business aliases for anonymous dataset columns. "
        "Use known column names as context, statistics and value examples. Do not claim certainty. "
        "Return ONLY a JSON object mapping every anonymous original name to one short unique "
        "snake_case alias. Example: {\"x1\":\"customer_id\",\"x2\":\"purchase_amount\"}.\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        response = Groq(api_key=api_key).chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        aliases = json.loads(content)
        if isinstance(aliases, dict) and isinstance(aliases.get("aliases"), dict):
            aliases = aliases["aliases"]
        if not isinstance(aliases, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in aliases.items()
            if str(key) in anonymous
        }
    except Exception as exc:
        print(f"[run_analysis] Alias Groq indisponible, fallback local: {exc}")
        return {}


def _make_aliases_unique(
    df: pd.DataFrame, anonymous: list[str], proposed: dict[str, str]
) -> dict[str, str]:
    used = {str(column).lower() for column in df.columns if str(column) not in anonymous}
    aliases = {}
    for original in anonymous:
        alias = _sanitize_alias(proposed.get(original, ""))
        if not alias or _is_anonymous_column(alias):
            alias = _infer_column_semantic(df[original], original)
        candidate = alias
        suffix = 2
        while candidate.lower() in used:
            candidate = f"{alias}_{suffix}"
            suffix += 1
        aliases[original] = candidate
        used.add(candidate.lower())
    return aliases


def _resolve_column_aliases(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Rename generic columns only when at least half the dataset is anonymous."""
    anonymous = _anonymous_columns(df.columns)
    ratio = len(anonymous) / max(len(df.columns), 1)
    metadata = {
        "is_anonymous_dataset": ratio >= ANONYMOUS_DATASET_THRESHOLD,
        "threshold": ANONYMOUS_DATASET_THRESHOLD,
        "anonymous_ratio": round(ratio, 4),
        "original_columns": anonymous,
        "alias_map": {},
        "resolution_method": "not_required",
    }
    if ratio < ANONYMOUS_DATASET_THRESHOLD:
        return df, metadata

    known = [str(column) for column in df.columns if str(column) not in anonymous]
    proposed = _ask_groq_for_aliases(df, anonymous, known)
    aliases = _make_aliases_unique(df, anonymous, proposed)
    metadata["alias_map"] = aliases
    metadata["resolution_method"] = "groq_with_local_fallback" if proposed else "local_fallback"
    return df.rename(columns=aliases).copy(), metadata


# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 1 — PROFIL COMPACT (pandas uniquement, envoyé à Groq)
# ─────────────────────────────────────────────────────────────────────────────
def _build_profile(df: pd.DataFrame) -> dict:
    profile = {
        "total_rows":    int(len(df)),
        "total_columns": int(len(df.columns)),
        "column_names":  df.columns.tolist(),
        "columns":       {}
    }
    for col in df.columns:
        series   = df[col]
        col_info = {
            "dtype":        str(series.dtype),
            "null_count":   int(series.isna().sum()),
            "unique_count": int(series.nunique()),
            "sample":       [str(v) for v in series.dropna().head(5).tolist()]
        }
        if pd.api.types.is_numeric_dtype(series):
            num = pd.to_numeric(series, errors="coerce").dropna()
            if not num.empty:
                col_info.update({
                    "min":            round(float(num.min()), 4),
                    "max":            round(float(num.max()), 4),
                    "mean":           round(float(num.mean()), 4),
                    "negative_count": int((num < 0).sum()),
                })
        elif str(series.dtype) == "object":
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().mean() > 0.8:
                col_info["parseable_as_datetime"] = True
                col_info["min_date"] = str(parsed.min())
                col_info["max_date"] = str(parsed.max())
        profile["columns"][col] = col_info
    return profile


# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — GROQ : DÉTECTION LIBRE + PLAN KPIs
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Data Scientist. Return ONLY valid JSON, no text.

{
  "domain": "text",
  "domain_explanation": "why",
  "kpis": [{"kpi_id":1,"name":"snake","action":"sum|mean|median|std|min|max|count|nunique|value_counts|groupby_sum|groupby_mean|groupby_count|corr_matrix|describe|computed","column":"col_or_null","group_by":"col_or_null","top_n":5,"formula":"ColA*ColB","result_label":"label"}]
}

Rules:
1. Max 8 KPIs.
2. Only existing columns. Never invent columns.
3. Binary 0/1 columns → action=mean for rates.
4. groupby KPIs → groupby_sum/groupby_mean not computed.
5. formula: arithmetic only (ColA*ColB). No Python functions.
6. count/nunique never for rates.
7. group_by must be null not string 'null'.
8. Numeric actions only on numeric dtype columns."""
# Nettoyage du plan avant retour
def _clean_plan(plan: dict, df_columns: list[str]) -> dict:
    cleaned_kpis = []

    SKIP_IF_COUNT = [
        "retention", "frequency", "churn",
        "conversion", "lifetime", "order_frequency"
        "exit_rate", "exited", "churn_rate"
    ]

    GROUPBY_HINTS = {
        "country":    ["country",     "Country"],
        "year":       ["year",        "Year"],
        "month":      ["month",       "Month"],
        "yearmonth":  ["yearmonth",   "YearMonth"],
        "category":   ["category",    "Category"],
        "product":    ["product_name","Description", "StockCode"],
        "region":     ["region",      "Region"],
        "channel":    ["channel",     "Channel"],
        "status":     ["status",      "Status"],
        "department": ["department",  "Department"],
    }

    GROUPBY_SALES_KEYWORDS = [
        "country", "yearly", "monthly", "year", "month",
        "yearmonth", "category", "region", "channel",
        "product", "department", "status"
    ]

    # Mapping colonnes quantity et price
    col_qty   = next((c for c in df_columns if c.lower() in ["quantity", "qty"]), None)
    col_price = next((c for c in df_columns if c.lower() in ["price", "unitprice", "unit_price"]), None)

    for item in plan.get("kpis", []):
        print(f"[DEBUG KPI] name={item.get('name')} | action={item.get('action')} | column={item.get('column')} | group_by={item.get('group_by')} | formula={item.get('formula')}")
        

        # ── Corriger strings "null" → None ────────────────────────────────
        if item.get("group_by") in ("null", "none", "None", "NULL", ""):
            item["group_by"] = None
        if item.get("column") in ("null", "none", "None", "NULL", ""):
            item["column"] = None

        # ── Corriger top_n None → 5 ───────────────────────────────────────
        if not item.get("top_n"):
            item["top_n"] = 5

        # ── Si column contient une formule → computed ─────────────────────
        col = item.get("column", "") or ""
        if any(op in col for op in ["*", "+", "-", "/"]):
            item["formula"] = col
            item["column"]  = None
            item["action"]  = "computed"

        name   = item.get("name", "").lower()
        label  = item.get("result_label", "").lower()
        action = item.get("action", "")

        # ── Correction AOV / Total Sales scalaire → computed ──────────────
        SALES_KEYWORDS = [
            "aov", "order_value", "average_order",
            "total_sales", "total_revenue", "revenue", "sales"
            "average_price", "avg_price"
            
        ]
        if any(k in name or k in label for k in SALES_KEYWORDS):
            if item.get("group_by") is None:
                if col_qty and col_price:
                    item["action"]   = "computed"
                    item["formula"]  = f"{col_qty} * {col_price}"
                    item["column"]   = None
                    item["group_by"] = None

        # ── Correction groupby sales mal générés comme computed ───────────
        if item.get("formula") and item.get("group_by") is None:
            matched_hint = next(
                (h for h in GROUPBY_SALES_KEYWORDS if h in name or h in label),
                None
            )
            if matched_hint:
                candidates = GROUPBY_HINTS.get(matched_hint, [])
                if not candidates:
                    candidates = [c for c in df_columns
                                  if matched_hint in c.lower()]
                grp_col = next((c for c in candidates if c in df_columns), None)
                if grp_col and "Sales" in df_columns:
                    item["action"]   = "groupby_sum"
                    item["column"]   = "Sales"
                    item["group_by"] = grp_col
                    item["formula"]  = None
                    item["top_n"]    = item.get("top_n") or 10

        # ── Correction return_rate ────────────────────────────────────────
        if "return" in name and item.get("action") in ("count", "nunique"):
            if "return_flag" in df_columns:
                item["action"]       = "mean"
                item["column"]       = "return_flag"
                item["group_by"]     = None
                item["result_label"] = "Return Rate"
            else:
                continue

        # ── Supprimer KPIs complexes mal calculés par Groq ────────────────
        if any(k in name or k in label for k in SKIP_IF_COUNT):
            if item.get("action") in ("count", "nunique"):
                continue

        # ── Vérification existence des colonnes ───────────────────────────
        column   = item.get("column")
        group_by = item.get("group_by")

        if column and column not in df_columns and column != "Sales":
            continue
        if group_by and group_by not in df_columns:
            item["group_by"] = None
            if item.get("action") in ("groupby_sum", "groupby_mean",
                                      "groupby_count", "groupby_nunique"):
                continue

        cleaned_kpis.append(item)

    plan["kpis"] = cleaned_kpis
    return plan


def _ask_groq(profile: dict, df: pd.DataFrame) -> dict | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[run_analysis] GROQ_API_KEY absente — fallback pandas")
        return None

    client = Groq(api_key=api_key)

    def _build_payload(char_limit: int) -> str:
        compact = {
            "rows": profile["total_rows"],
            "cols": profile["column_names"],
            "types": {
                col: info["dtype"]
                for col, info in profile["columns"].items()
            },
            # ── No samples — saves ~30-40% tokens ─────────────────────────
        }
        s = json.dumps(compact, ensure_ascii=False)
        return s[:char_limit] + ("..." if len(s) > char_limit else "")

    # Start conservative: 400 chars is enough for names + types
    char_limits = [400, 300, 200]

    for attempt, char_limit in enumerate(char_limits, start=1):
        profile_str = _build_payload(char_limit)
        user_message = (
            f"Dataset profile:\n{profile_str}\n\n"
            "Detect the domain and generate KPI plan. Return ONLY the JSON."
        )
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                temperature=0.1,
                max_tokens=1000,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
            plan = json.loads(raw)

            plan = _clean_plan(plan, df.columns.tolist())

            if "domain" not in plan or "kpis" not in plan:
                print("[run_analysis] JSON invalide — champs manquants")
                return None
            if not isinstance(plan["kpis"], list) or len(plan["kpis"]) == 0:
                print("[run_analysis] Plan KPIs vide")
                return None

            print(f"[run_analysis] Domaine : {plan['domain']}")
            print(f"[run_analysis] KPIs    : {len(plan['kpis'])}")
            return plan

        except json.JSONDecodeError as e:
            print(f"[run_analysis] Tentative {attempt}/3 — JSON invalide : {e}")

        except Exception as e:
            err_str = str(e)
            print(f"[run_analysis] Tentative {attempt}/3 échouée : {type(e).__name__} — {e}")
            if "413" in err_str or "too large" in err_str.lower() or "rate_limit" in err_str.lower():
                print(f"[run_analysis] Profil tronqué à {char_limits[attempt] if attempt < len(char_limits) else 200} chars — nouvel essai...")
            else:
                # Non-size error: no point retrying with smaller payload
                break

        if attempt < len(char_limits):
            wait = 2 * attempt
            print(f"[run_analysis] Nouvel essai dans {wait}s...")
            time.sleep(wait)

    print("[run_analysis] Groq inaccessible — fallback pandas")
    return None
# ─────────────────────────────────────────────────────────────────────────────
# ÉTAPE 3 — EXÉCUTION DU PLAN PAR PANDAS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_formula(formula: str, df: pd.DataFrame) -> pd.Series | None:
    """
    Évalue une formule arithmétique simple sur le DataFrame.
    Retourne None si la formule est invalide ou contient des fonctions Python.
    """
    forbidden = ["count(", "len(", "sum(", "nunique(", "mean(", ".str", ".dt",
                 "lambda", "import", "eval", "exec", "__"]
    for f in forbidden:
        if f in formula:
            return None

    safe = formula
    for col_name in sorted(df.columns, key=len, reverse=True):
        if col_name in safe:
            safe = safe.replace(
                col_name,
                f"pd.to_numeric(df['{col_name}'], errors='coerce')"
            )
    try:
        result = eval(safe)  # noqa: S307
        if isinstance(result, pd.Series):
            return result
        return None
    except Exception:
        return None


def _execute_plan(df: pd.DataFrame, plan: dict) -> tuple[dict, list[str]]:
    """
    Exécute le plan de KPIs généré par Groq sur le DataFrame réel.
    Fixes v3 :
      - computed respecte group_by
      - value_counts filtre les valeurs parasites (Unknown, N/A, etc.)
    """
    PARASITES = {"unknown", "n/a", "none", "null", "na", "-", ""}

    kpis     = {}
    insights = []
    ok       = 0
    total    = len(plan.get("kpis", []))

    for item in plan.get("kpis", []):
        kpi_id       = item.get("kpi_id", "?")
        name         = item.get("name", f"kpi_{kpi_id}")
        action       = item.get("action", "")
        column       = item.get("column")
        group_by     = item.get("group_by")
        top_n        = int(item.get("top_n") or 10)
        formula      = item.get("formula", "")
        result_label = item.get("result_label", name)

        if column and column not in df.columns:
            insights.append(f"  [Ignoré] '{name}' : colonne '{column}' introuvable.")
            continue
        if group_by and group_by not in df.columns:
            insights.append(f"  [Ignoré] '{name}' : group_by '{group_by}' introuvable.")
            continue

        try:
            # ── Scalaires ────────────────────────────────────────────────
            if action == "sum":
                val = round(float(pd.to_numeric(df[column], errors="coerce").sum()), 2)
                kpis[name] = val
                insights.append(f"{result_label} : {val:,.2f}")

            elif action == "mean":
                val = round(float(pd.to_numeric(df[column], errors="coerce").mean()), 4)
                kpis[name] = val
                insights.append(f"{result_label} (moyenne) : {val:,.4f}")

            elif action == "median":
                val = round(float(pd.to_numeric(df[column], errors="coerce").median()), 4)
                kpis[name] = val
                insights.append(f"{result_label} (médiane) : {val:,.4f}")

            elif action == "std":
                val = round(float(pd.to_numeric(df[column], errors="coerce").std()), 4)
                kpis[name] = val
                insights.append(f"{result_label} (écart-type) : {val:,.4f}")

            elif action == "min":
                val = round(float(pd.to_numeric(df[column], errors="coerce").min()), 4)
                kpis[name] = val
                insights.append(f"{result_label} (min) : {val:,.4f}")

            elif action == "max":
                val = round(float(pd.to_numeric(df[column], errors="coerce").max()), 4)
                kpis[name] = val
                insights.append(f"{result_label} (max) : {val:,.4f}")

            elif action == "count":
                if not column or column not in df.columns:
                    insights.append(f"  [Ignoré] '{name}' : count nécessite un nom de colonne valide.")
                    continue
                val = int(df[column].count())
                kpis[name] = val
                insights.append(f"{result_label} : {val:,}")

            elif action == "nunique":
                val = int(df[column].nunique())
                kpis[name] = val
                insights.append(f"{result_label} (valeurs distinctes) : {val:,}")

            # ── Distributions ─────────────────────────────────────────────
            elif action == "value_counts":
                series = df[column].copy()
                # FIX 3 — filtrer les valeurs parasites
                mask = series.astype(str).str.strip().str.lower().isin(PARASITES)
                if mask.any():
                    print(f"[run_analysis] value_counts '{column}' : {mask.sum()} valeurs parasites exclues")
                    series = series[~mask]
                vc = series.value_counts().head(top_n).to_dict()
                kpis[name] = vc
                insights.append(f"{result_label} — top {min(top_n, len(vc))} :")
                for val, cnt in vc.items():
                    insights.append(f"    · {val} : {cnt:,}")

            # ── GroupBy ───────────────────────────────────────────────────
            elif action == "groupby_sum":
                tmp = df.copy()
                tmp[column] = pd.to_numeric(tmp[column], errors="coerce")
                grp = (tmp.groupby(group_by)[column]
                          .sum()
                          .sort_values(ascending=False)
                          .head(top_n)
                          .round(2))
                kpis[name] = grp.to_dict()
                insights.append(f"{result_label} (total par {group_by}) :")
                for k, v in grp.items():
                    insights.append(f"    · {k} : {v:,.2f}")

            elif action == "groupby_mean":
                tmp = df.copy()
                tmp[column] = pd.to_numeric(tmp[column], errors="coerce")
                grp = (tmp.groupby(group_by)[column]
                          .mean()
                          .sort_values(ascending=False)
                          .head(top_n)
                          .round(4))
                kpis[name] = grp.to_dict()
                insights.append(f"{result_label} (moyenne par {group_by}) :")
                for k, v in grp.items():
                    insights.append(f"    · {k} : {v:,.4f}")

            elif action == "groupby_count":
                grp = (df.groupby(group_by)
                          .size()
                          .sort_values(ascending=False)
                          .head(top_n))
                kpis[name] = grp.to_dict()
                insights.append(f"{result_label} (volume par {group_by}) :")
                for k, v in grp.items():
                    insights.append(f"    · {k} : {v:,} lignes")

            elif action == "groupby_nunique":
                grp = (df.groupby(group_by)[column]
                          .nunique()
                          .sort_values(ascending=False)
                          .head(top_n))
                kpis[name] = grp.to_dict()
                insights.append(f"{result_label} (nb distincts '{column}' par '{group_by}') :")
                for k, v in grp.items():
                    insights.append(f"    · {k} : {v:,}")

            # ── Describe complet ──────────────────────────────────────────
            elif action == "describe":
                series = pd.to_numeric(df[column], errors="coerce").dropna()
                if not series.empty:
                    desc = {
                        "count":  int(series.count()),
                        "mean":   round(float(series.mean()),         4),
                        "std":    round(float(series.std()),          4),
                        "min":    round(float(series.min()),          4),
                        "q25":    round(float(series.quantile(0.25)), 4),
                        "median": round(float(series.median()),       4),
                        "q75":    round(float(series.quantile(0.75)), 4),
                        "max":    round(float(series.max()),          4),
                    }
                    kpis[name] = desc
                    insights.append(
                        f"{result_label} — "
                        f"n={desc['count']:,} | "
                        f"moyenne={desc['mean']:,.4f} | "
                        f"médiane={desc['median']:,.4f} | "
                        f"min={desc['min']:,.4f} | "
                        f"max={desc['max']:,.4f} | "
                        f"écart-type={desc['std']:,.4f} | "
                        f"Q25={desc['q25']:,.4f} | Q75={desc['q75']:,.4f}"
                    )

            # ── Corrélation ───────────────────────────────────────────────
            elif action == "corr_matrix":
                num_df = df.select_dtypes(include="number")
                if len(num_df.columns) >= 2:
                    corr       = num_df.corr().round(3)
                    kpis[name] = corr.to_dict()
                    cols_list  = num_df.columns.tolist()
                    pairs = []
                    for i in range(len(cols_list)):
                        for j in range(i + 1, len(cols_list)):
                            r = float(corr.iloc[i, j])
                            if abs(r) >= 0.5:
                                pairs.append((cols_list[i], cols_list[j], r))
                    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                    if pairs:
                        insights.append("Corrélations fortes (|r| ≥ 0.5) :")
                        for c1, c2, r in pairs[:8]:
                            direction = "positive" if r > 0 else "négative"
                            insights.append(f"    · {c1} ↔ {c2} : r={r:.3f} ({direction})")
                    else:
                        insights.append("Corrélations : aucune corrélation forte détectée.")

            # ── Formule calculée — FIX 2 : group_by supporté ─────────────
            elif action == "computed":
                if not formula:
                    insights.append(f"  [Ignoré] '{name}' : action computed sans formula.")
                    continue

                computed_series = _safe_formula(formula, df)
                if computed_series is None:
                    insights.append(
                        f"  [Ignoré] '{name}' : formule invalide ou non arithmétique → '{formula}'"
                    )
                    continue

                if group_by and group_by in df.columns:
                    # FIX 2 — groupby sur la série calculée
                    tmp         = df.copy()
                    tmp["_val"] = computed_series
                    grp = (tmp.groupby(group_by)["_val"]
                              .sum()
                              .sort_values(ascending=False)
                              .head(top_n)
                              .round(2))
                    kpis[name] = grp.to_dict()
                    insights.append(f"{result_label} [{formula}] par {group_by} :")
                    for k, v in grp.items():
                        insights.append(f"    · {k} : {v:,.2f}")
                else:
                    # Scalaire
                    total_val  = round(float(computed_series.sum()),  2)
                    mean_val   = round(float(computed_series.mean()), 4)
                    kpis[name] = {"total": total_val, "mean": mean_val, "formula": formula}
                    insights.append(
                        f"{result_label} [{formula}] — "
                        f"total : {total_val:,.2f} | moyenne : {mean_val:,.4f}"
                    )

            else:
                insights.append(f"  [Ignoré] '{name}' : action '{action}' non reconnue.")
                continue

            ok += 1

        except Exception as e:
            insights.append(f"  [Ignoré] '{name}' : {type(e).__name__} — {e}")

    insights.insert(0, f"Plan Groq : {ok}/{total} KPIs calculés avec succès.")
    return kpis, insights
# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK — Stats universelles si Groq indisponible
# ─────────────────────────────────────────────────────────────────────────────
def _fallback_analysis(df: pd.DataFrame) -> tuple[str, str, dict, list[str]]:
    kpis     = {}
    insights = ["[Fallback pandas] Groq indisponible — statistiques génériques calculées."]

    numeric_cols     = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(include="object").columns.tolist()

    if numeric_cols:
        kpis["stats_descriptives"] = {}
        insights.append(f"Colonnes numériques ({len(numeric_cols)}) :")
        for col in numeric_cols[:15]:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                continue
            stats = {
                "count":  int(series.count()),
                "mean":   round(float(series.mean()),         4),
                "median": round(float(series.median()),       4),
                "std":    round(float(series.std()),          4),
                "min":    round(float(series.min()),          4),
                "q25":    round(float(series.quantile(0.25)), 4),
                "q75":    round(float(series.quantile(0.75)), 4),
                "max":    round(float(series.max()),          4),
            }
            kpis["stats_descriptives"][col] = stats
            insights.append(
                f"  [{col}] n={stats['count']:,} | "
                f"moyenne={stats['mean']:,.4f} | médiane={stats['median']:,.4f} | "
                f"min={stats['min']:,.4f} | max={stats['max']:,.4f} | "
                f"Q25={stats['q25']:,.4f} | Q75={stats['q75']:,.4f}"
            )

    if categorical_cols:
        kpis["distributions"] = {}
        insights.append(f"Colonnes catégorielles ({len(categorical_cols)}) :")
        for col in categorical_cols[:10]:
            vc = df[col].value_counts().head(5).to_dict()
            kpis["distributions"][col] = vc
            insights.append(f"  [{col}] {df[col].nunique()} valeurs distinctes — top 5 :")
            for val, cnt in vc.items():
                insights.append(f"    · {val} : {cnt:,}")

    if len(numeric_cols) >= 2:
        corr  = df[numeric_cols[:10]].corr().round(3)
        kpis["correlations"] = corr.to_dict()
        pairs = []
        cols  = numeric_cols[:10]
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                r = float(corr.iloc[i, j])
                if abs(r) >= 0.5:
                    pairs.append((cols[i], cols[j], r))
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        if pairs:
            insights.append("Corrélations fortes (|r| ≥ 0.5) :")
            for c1, c2, r in pairs[:8]:
                insights.append(f"    · {c1} ↔ {c2} : r={r:.3f} ({'positive' if r > 0 else 'négative'})")

    kpis["outliers"] = {}
    for col in numeric_cols[:10]:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr     = q3 - q1
        n_out   = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())
        if n_out > 0:
            kpis["outliers"][col] = n_out
            insights.append(f"  [{col}] outliers IQR : {n_out:,} valeurs extrêmes")

    return "unknown", "Groq indisponible — aucune détection possible.", kpis, insights


# ─────────────────────────────────────────────────────────────────────────────
# DATA QUALITY (universelle, toujours calculée)
# ─────────────────────────────────────────────────────────────────────────────
def _compute_data_quality(df: pd.DataFrame) -> tuple[dict, list[str]]:
    missing_map = {
        col: {
            "count": int(df[col].isna().sum()),
            "rate":  round(float(df[col].isna().mean() * 100), 2)
        }
        for col in df.columns
        if df[col].isna().sum() > 0
    }
    total_missing_rate = round(float(df.isna().mean().mean()), 4)
    dq = {
        "score_global":       round(1 - total_missing_rate, 2),
        "missing_rate":       total_missing_rate,
        "nb_lignes":          int(len(df)),
        "nb_colonnes":        int(len(df.columns)),
        "nb_doublons":        int(df.duplicated().sum()),
        "valeurs_manquantes": missing_map,
        "colonnes_ok":        [c for c in df.columns if df[c].isna().sum() == 0],
    }

    dq_insights = [
        f"Score qualité global : {dq['score_global']} | "
        f"{dq['nb_lignes']:,} lignes | {dq['nb_colonnes']} colonnes"
    ]
    if dq["nb_doublons"] > 0:
        dq_insights.append(f"Doublons résiduels : {dq['nb_doublons']:,} lignes dupliquées")
    else:
        dq_insights.append("Doublons : aucun doublon résiduel détecté.")

    if missing_map:
        dq_insights.append(f"Colonnes avec valeurs manquantes ({len(missing_map)}) :")
        for col, info in missing_map.items():
            dq_insights.append(f"    · {col} : {info['count']:,} nulls ({info['rate']}%)")
    else:
        dq_insights.append("Valeurs manquantes : aucune — dataset complet.")

    if dq["colonnes_ok"]:
        dq_insights.append(
            f"Colonnes sans null ({len(dq['colonnes_ok'])}) : "
            f"{', '.join(dq['colonnes_ok'][:10])}"
            f"{'...' if len(dq['colonnes_ok']) > 10 else ''}"
        )

    return dq, dq_insights


# ─────────────────────────────────────────────────────────────────────────────
# ALERTES
# ─────────────────────────────────────────────────────────────────────────────
def _compute_alerts(kpis: dict, dq: dict) -> tuple[list[dict], list[str]]:
    alertes        = []
    alert_insights = []

    if dq["nb_doublons"] > 0:
        msg = f"{dq['nb_doublons']:,} doublons résiduels présents dans clean.csv"
        alertes.append({"kpi": "doublons", "valeur": dq["nb_doublons"],
                        "niveau": "warning", "message": msg})
        alert_insights.append(f"  [WARNING] {msg}")

    if dq["missing_rate"] >= 0.25:
        msg = f"Taux de valeurs manquantes : {dq['missing_rate']:.1%} — critique"
        alertes.append({"kpi": "missing_rate", "valeur": dq["missing_rate"],
                        "niveau": "critical", "message": msg})
        alert_insights.append(f"  [CRITICAL] {msg}")
    elif dq["missing_rate"] >= 0.10:
        msg = f"Taux de valeurs manquantes : {dq['missing_rate']:.1%} — attention"
        alertes.append({"kpi": "missing_rate", "valeur": dq["missing_rate"],
                        "niveau": "warning", "message": msg})
        alert_insights.append(f"  [WARNING] {msg}")

    SEUILS_KPIS = {
        "taux_annulation": {"warning": 0.05, "critical": 0.10},
        "return_rate":     {"warning": 0.10, "critical": 0.25},
        "late_rate":       {"warning": 0.10, "critical": 0.20},
    }
    for kpi_name, thresholds in SEUILS_KPIS.items():
        valeur = kpis.get(kpi_name)
        if valeur is None:
            continue
        if valeur >= thresholds["critical"]:
            msg = f"{kpi_name} = {valeur:.1%} dépasse le seuil critique {thresholds['critical']:.1%}"
            alertes.append({"kpi": kpi_name, "valeur": valeur, "niveau": "critical", "message": msg})
            alert_insights.append(f"  [CRITICAL] {msg}")
        elif valeur >= thresholds["warning"]:
            msg = f"{kpi_name} = {valeur:.1%} dépasse le seuil warning {thresholds['warning']:.1%}"
            alertes.append({"kpi": kpi_name, "valeur": valeur, "niveau": "warning", "message": msg})
            alert_insights.append(f"  [WARNING] {msg}")

    return alertes, alert_insights


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
def run_analysis(file_path: str, run_id: str) -> dict:
    """
    Analyse adaptative du clean.csv produit par le Data Engineer.
    Groq détecte LIBREMENT le domaine et génère les KPIs pertinents.
    Pandas exécute le plan. Data Quality toujours calculée.
    Tous les résultats → insights[] lisibles.
    """
    if not os.path.exists(file_path):
        return {"error": f"Fichier introuvable : {file_path}"}

    try:
        from app.tools.load_dataset import _load_json_smart
        print(f"[run_analysis] Chargement de {file_path}...")
        if os.path.splitext(file_path)[1].lower() == ".json":
            df = _load_json_smart(file_path)
        else:
            df = pd.read_csv(file_path, low_memory=False)

        df, anonymous_detection = _resolve_column_aliases(df)
        if anonymous_detection["is_anonymous_dataset"]:
            print(
                "[run_analysis] Dataset anonyme detecte: "
                f"{anonymous_detection['anonymous_ratio']:.0%} des colonnes; "
                f"methode={anonymous_detection['resolution_method']}"
            )
        print(f"[run_analysis] {len(df):,} lignes × {len(df.columns)} colonnes")
        
        
        col_qty   = next((c for c in df.columns if c.lower() in ["quantity", "qty"]), None)
        col_price = next((c for c in df.columns if c.lower() in ["price", "unitprice", "unit_price"]), None)
        if col_qty and col_price and "Sales" not in df.columns:
              df["Sales"] = pd.to_numeric(df[col_qty], errors="coerce") * \
                            pd.to_numeric(df[col_price], errors="coerce")
              print(f"[run_analysis] Colonne Sales créée : {col_qty} * {col_price}")
       
        

        # ── 1. Data Quality ────────────────────────────────────────────────
        dq, dq_insights = _compute_data_quality(df)

        # ── 2. Profil compact pour Groq ────────────────────────────────────
        profile = _build_profile(df)

        # ── 3. Groq : détection libre + plan KPIs ──────────────────────────
        print("[run_analysis] Appel Groq...")
        plan = _ask_groq(profile,df)

        # ── 4. Exécution plan Groq OU fallback ─────────────────────────────
        if plan:
            domain             = plan["domain"]
            domain_explanation = plan.get("domain_explanation", "Non fourni.")
            groq_used          = True
            kpis, kpi_insights = _execute_plan(df, plan)
        else:
            domain, domain_explanation, kpis, kpi_insights = _fallback_analysis(df)
            groq_used = False

        # ── 5. Alertes ─────────────────────────────────────────────────────
        alertes, alert_insights = _compute_alerts(kpis, dq)

        # ── 6. Assemblage TOUS les insights ────────────────────────────────
        all_insights = []

        all_insights.append("=" * 55)
        all_insights.append(f"DOMAINE DÉTECTÉ : {domain}")
        all_insights.append(f"{domain_explanation}")
        all_insights.append(f"Moteur : {'Groq LLM' if groq_used else 'Fallback pandas'}")
        all_insights.append("=" * 55)

        all_insights.append("")
        all_insights.append("--- DATA QUALITY ---")
        all_insights.extend(dq_insights)

        all_insights.append("")
        all_insights.append("--- KPIs ---")
        all_insights.extend(kpi_insights)

        all_insights.append("")
        if alert_insights:
            all_insights.append("--- ALERTES ---")
            all_insights.extend(alert_insights)
        else:
            all_insights.append("--- ALERTES : aucune alerte déclenchée ---")

        kpis["data_quality_score"] = dq["score_global"]
        kpis["domain_detected"]    = domain

        print(f"[run_analysis] {len(all_insights)} insights | {len(alertes)} alerte(s)")

        # ── 7. Sauvegarde ──────────────────────────────────────────────────
        output_path = f"runs/{run_id}/artifacts/insights.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "domain":             domain,
                "domain_explanation": domain_explanation,
                "groq_used":          groq_used,
                "data_quality":       dq,
                "kpis":               kpis,
                "alertes":            alertes,
                "insights":           all_insights,
                "anonymous_columns":  anonymous_detection["original_columns"],
                "alias_map":          anonymous_detection["alias_map"],
                "anonymous_detection": anonymous_detection,
                "columns_after_aliasing": [str(column) for column in df.columns],
                "output_path":        output_path,
            }, f, indent=2, ensure_ascii=False)

        print(f"[run_analysis] Sauvegarde terminee: {output_path}")

        log_artifact(run_id, "run_analysis", {
            "status":        "success",
            "domain":        domain,
            "groq_used":     groq_used,
            "nb_kpis":       len(kpis),
            "nb_insights":   len(all_insights),
            "nb_alertes":    len(alertes),
            "quality_score": dq["score_global"],
            "anonymous_dataset": anonymous_detection["is_anonymous_dataset"],
            "alias_method": anonymous_detection["resolution_method"],
            "output_path":   output_path,
        })

        return {
            "domain":             domain,
            "domain_explanation": domain_explanation,
            "groq_used":          groq_used,
            "output_path":        output_path,
            "data_quality":       dq,
            "kpis":               kpis,
            "alertes":            alertes,
            "insights":           all_insights,
            "nb_alertes":         len(alertes),
            "anonymous_columns":  anonymous_detection["original_columns"],
            "alias_map":          anonymous_detection["alias_map"],
            "anonymous_detection": anonymous_detection,
            "columns_after_aliasing": [str(column) for column in df.columns],
        }

    except Exception as e:
        error_result = {"error": str(e), "run_id": run_id, "file_path": file_path}
        log_artifact(run_id, "run_analysis", {"status": "error", "message": str(e)})
        return error_result
