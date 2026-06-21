
import pandas as pd
import json
import os
import time
from groq import Groq
from dotenv import load_dotenv
from app.tools.log_artifact import log_artifact

load_dotenv()


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 1 — Stats brutes pandas sans LLM
# ─────────────────────────────────────────────────────────────────────

def _build_raw_profile(df: pd.DataFrame) -> dict:
    """
    Calcule les statistiques brutes de chaque colonne.
    Retourne un dictionnaire JSON-serializable.
    Compatible avec différents types de datasets.
    """
    raw = {
        "total_rows"        : int(len(df)),
        "total_columns"     : int(len(df.columns)),
        "duplicate_rows"    : int(df.duplicated().sum()),
        "duplicate_rate_pct": round(float(df.duplicated().mean() * 100), 2),
        "columns"           : {}
    }

    for col in df.columns:
        series = df[col]

        col_info = {
            "dtype"        : str(series.dtype),
            "null_count"   : int(series.isnull().sum()),
            "null_rate_pct": round(float(series.isnull().mean() * 100), 2),
            "unique_count" : int(series.nunique(dropna=True)),
        }

        # ── Colonnes numériques natives ───────────────────────────────
        if pd.api.types.is_numeric_dtype(series):
            if series.isnull().all():
                col_info["min"] = None
                col_info["max"] = None
                col_info["mean"] = None
                col_info["negative_count"] = 0
                col_info["zero_count"] = 0
            else:
                col_info["min"] = float(series.min())
                col_info["max"] = float(series.max())
                col_info["mean"] = float(series.mean())
                col_info["negative_count"] = int((series < 0).sum())
                col_info["zero_count"] = int((series == 0).sum())

        # ── Colonnes datetime natives ────────────────────────────────
        elif pd.api.types.is_datetime64_any_dtype(series):
            col_info["parseable_as_datetime"] = True
            col_info["min_date"] = str(series.min())
            col_info["max_date"] = str(series.max())
            col_info["datetime_valid_pct"] = round(
                float(series.notnull().mean() * 100), 2
            )

        # ── Colonnes texte / object ──────────────────────────────────
        elif pd.api.types.is_object_dtype(series):
            sample = series.dropna().head(5).tolist()
            col_info["sample_values"] = [str(v) for v in sample]

            # Détection des préfixes texte
            prefix_counts = {}
            for prefix in ["C", "A", "R", "T", "S"]:
                count = int(series.astype(str).str.startswith(prefix).sum())
                if count > 0:
                    prefix_counts[prefix] = count

            if prefix_counts:
                col_info["prefix_counts"] = prefix_counts

            # Détection des dates même si dtype = object
            try:
                parsed = pd.to_datetime(series, errors="coerce")
                valid_pct = float(parsed.notnull().mean())

                if valid_pct > 0.8:
                    col_info["parseable_as_datetime"] = True
                    col_info["min_date"] = str(parsed.min())
                    col_info["max_date"] = str(parsed.max())
                    col_info["datetime_valid_pct"] = round(valid_pct * 100, 2)
            except Exception:
                pass

            # Détection des nombres stockés comme texte
            try:
                cleaned = (
                    series.dropna()
                    .astype(str)
                    .str.replace("%", "", regex=False)
                    .str.replace(" ", "", regex=False)
                    .str.replace(",", ".", regex=False)
                )

                numeric = pd.to_numeric(cleaned, errors="coerce")
                numeric_valid_pct = float(numeric.notnull().mean())

                if numeric_valid_pct > 0.8:
                    col_info["parseable_as_numeric"] = True
                    col_info["numeric_valid_pct"] = round(numeric_valid_pct * 100, 2)

                    if numeric.notnull().any():
                        col_info["numeric_min"] = float(numeric.min())
                        col_info["numeric_max"] = float(numeric.max())
                        col_info["numeric_mean"] = float(numeric.mean())
                        col_info["numeric_negative_count"] = int((numeric < 0).sum())
                        col_info["numeric_zero_count"] = int((numeric == 0).sum())

            except Exception:
                pass

        # ── Autres types ─────────────────────────────────────────────
        else:
            try:
                parsed = pd.to_datetime(series, errors="coerce")
                valid_pct = float(parsed.notnull().mean())

                if valid_pct > 0.8:
                    col_info["parseable_as_datetime"] = True
                    col_info["min_date"] = str(parsed.min())
                    col_info["max_date"] = str(parsed.max())
                    col_info["datetime_valid_pct"] = round(valid_pct * 100, 2)
            except Exception:
                pass

        raw["columns"][col] = col_info

    return raw


# ─────────────────────────────────────────────────────────────────────
# FALLBACK — Analyse qualité sans LLM
# ─────────────────────────────────────────────────────────────────────

def _fallback_profile(raw_profile: dict) -> dict:
    """
    Détecte les problèmes courants sans LLM.
    Utilisé quand Groq est inaccessible ou retourne du JSON invalide.
    """
    print("[profile_data] Fallback pandas — détection heuristique")

    problems = []
    cleaning_hints = []
    total_rows = max(int(raw_profile.get("total_rows", 1)), 1)
    deductions = 0.0
    priority = 1

    duplicate_rows = int(raw_profile.get("duplicate_rows", 0))
    duplicate_rate_pct = float(raw_profile.get("duplicate_rate_pct", 0))

    # Doublons globaux
    if duplicate_rows > 0:
        severity = "high" if duplicate_rate_pct > 20 else "medium" if duplicate_rate_pct > 5 else "low"

        problems.append({
            "column": "global",
            "type": "duplicate_rows",
            "description": f"{duplicate_rows:,} duplicate rows detected",
            "severity": severity,
            "affected_rows_estimate": duplicate_rows
        })

        cleaning_hints.append({
            "column": "global",
            "action": "drop duplicate rows",
            "priority": str(priority)
        })

        priority += 1
        deductions += min(duplicate_rows / total_rows, 0.2)

    for col, info in raw_profile.get("columns", {}).items():
        null_rate = float(info.get("null_rate_pct", 0))
        neg_count = int(info.get("negative_count", info.get("numeric_negative_count", 0)))
        prefix_c = int(info.get("prefix_counts", {}).get("C", 0))
        is_dt = bool(info.get("parseable_as_datetime", False))
        is_numeric_text = bool(info.get("parseable_as_numeric", False))

        # Valeurs manquantes
        if null_rate > 0:
            severity = "high" if null_rate > 20 else "medium" if null_rate > 5 else "low"

            problems.append({
                "column": col,
                "type": "missing_values",
                "description": f"{null_rate}% null values",
                "severity": severity,
                "affected_rows_estimate": int(null_rate * total_rows / 100)
            })

            cleaning_hints.append({
                "column": col,
                "action": "fill nulls with a suitable value or drop rows if necessary",
                "priority": str(priority)
            })

            priority += 1
            deductions += (null_rate / 100) * (0.3 if severity == "high" else 0.1)

        # Valeurs négatives : seulement signaler, ne pas supposer automatiquement qu'elles sont invalides
        if neg_count > 0:
            problems.append({
                "column": col,
                "type": "negative_values_detected",
                "description": f"{neg_count:,} negative values detected; validate if negatives are meaningful for this column",
                "severity": "medium",
                "affected_rows_estimate": neg_count
            })

            cleaning_hints.append({
                "column": col,
                "action": "validate negative values according to column meaning before removing",
                "priority": str(priority)
            })

            priority += 1
            deductions += min((neg_count / total_rows) * 0.1, 0.1)

        # Préfixe C : seulement signaler, ne pas supposer automatiquement une annulation
        if prefix_c > 0:
            problems.append({
                "column": col,
                "type": "prefix_C_detected",
                "description": f"{prefix_c:,} values start with 'C'; verify whether this is normal category/code data or cancellation data",
                "severity": "low",
                "affected_rows_estimate": prefix_c
            })

            cleaning_hints.append({
                "column": col,
                "action": "inspect prefix C values before filtering",
                "priority": str(priority)
            })

            priority += 1
            deductions += min((prefix_c / total_rows) * 0.05, 0.05)

        # Dates détectées
        if is_dt:
            cleaning_hints.append({
                "column": col,
                "action": "convert to datetime and optionally create Year, Month, YearMonth",
                "priority": str(priority)
            })

            priority += 1

        # Numériques stockés comme texte
        if is_numeric_text:
            problems.append({
                "column": col,
                "type": "numeric_stored_as_text",
                "description": "Column appears numeric but is stored as text",
                "severity": "medium",
                "affected_rows_estimate": None
            })

            cleaning_hints.append({
                "column": col,
                "action": "convert text values to numeric",
                "priority": str(priority)
            })

            priority += 1
            deductions += 0.03

    quality_score = round(max(0.0, 1.0 - deductions), 3)

    return {
        "problems": problems,
        "quality_score": quality_score,
        "quality_summary": f"Heuristic analysis: {len(problems)} issues detected",
        "cleaning_hints": cleaning_hints,
    }


# ─────────────────────────────────────────────────────────────────────
# ÉTAPE 2 — Analyse Groq
# ─────────────────────────────────────────────────────────────────────

def _ask_groq(raw_profile: dict) -> dict:
    """
    Envoie un profil compacté à Groq pour analyse intelligente.
    Retry 3 fois.
    Fallback pandas si Groq échoue.
    """
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        print("[profile_data] GROQ_API_KEY absente — fallback pandas")
        return _fallback_profile(raw_profile)

    client = Groq(api_key=api_key)

    system_prompt = """You are a senior Data Engineer specialized in data quality assessment.
You receive a raw statistical profile of a dataset.
Your job is to detect data quality problems WITHOUT assuming a specific business domain.

Respond ONLY with a valid JSON object — no explanation, no markdown, no backticks.

The JSON must have exactly this structure:
{
  "problems": [
    {
      "column": "<column_name or 'global'>",
      "type": "<problem_type>",
      "description": "<short description in English>",
      "severity": "<high|medium|low>",
      "affected_rows_estimate": <integer or null>
    }
  ],
  "quality_score": <float between 0.0 and 1.0>,
  "quality_summary": "<one sentence summary>",
  "cleaning_hints": [
    {
      "column": "<column_name or 'global'>",
      "action": "<what to do>",
      "priority": "<1=first, 2=second, etc.>"
    }
  ]
}

Important rules:
1. Be generic and adaptive.
2. Do not assume this is a sales or e-commerce dataset.
3. Do not assume negative values are always invalid.
4. Do not assume values starting with C are cancellations.
5. If duplicate_rows > 0, report a global duplicate_rows problem.
6. If parseable_as_datetime=true, suggest datetime conversion.
7. If parseable_as_numeric=true, suggest numeric conversion.
8. Penalize quality_score based on actual severity and affected rows.
9. Round quality_score to 3 decimal places."""

    compact_columns = {}

    for col, info in raw_profile.get("columns", {}).items():
        compact_columns[col] = {
            "dtype"                  : info.get("dtype"),
            "null_count"             : info.get("null_count"),
            "null_rate_pct"          : info.get("null_rate_pct"),
            "unique_count"           : info.get("unique_count"),
            "negative_count"         : info.get("negative_count", 0),
            "zero_count"             : info.get("zero_count", 0),
            "min"                    : info.get("min"),
            "max"                    : info.get("max"),
            "mean"                   : info.get("mean"),
            "sample_values"          : info.get("sample_values", [])[:3],
            "prefix_counts"          : info.get("prefix_counts", {}),
            "parseable_as_datetime"  : info.get("parseable_as_datetime", False),
            "datetime_valid_pct"     : info.get("datetime_valid_pct"),
            "parseable_as_numeric"   : info.get("parseable_as_numeric", False),
            "numeric_valid_pct"      : info.get("numeric_valid_pct"),
            "numeric_min"            : info.get("numeric_min"),
            "numeric_max"            : info.get("numeric_max"),
            "numeric_mean"           : info.get("numeric_mean"),
            "numeric_negative_count" : info.get("numeric_negative_count", 0),
            "numeric_zero_count"     : info.get("numeric_zero_count", 0),
        }

    compact_profile = {
        "total_rows"        : raw_profile.get("total_rows"),
        "total_columns"     : raw_profile.get("total_columns"),
        "duplicate_rows"    : raw_profile.get("duplicate_rows", 0),
        "duplicate_rate_pct": raw_profile.get("duplicate_rate_pct", 0),
        "columns"           : compact_columns,
    }

    user_prompt = f"""Here is the raw statistical profile of the dataset:

{json.dumps(compact_profile, indent=2, ensure_ascii=False)}

Analyze this profile and return the JSON quality report."""

    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            break

        except Exception as e:
            print(f"[profile_data] Tentative {attempt}/3 échouée : {type(e).__name__} — {e}")

            if attempt < 3:
                wait = 2 * attempt
                print(f"[profile_data] Nouvel essai dans {wait}s...")
                time.sleep(wait)

    else:
        print("[profile_data] Groq inaccessible — fallback pandas")
        return _fallback_profile(raw_profile)

    raw_text = response.choices[0].message.content.strip()

    # Nettoyage si le modèle retourne ```json
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]

        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)

    except json.JSONDecodeError as e:
        print(f"[profile_data] WARNING: JSON parse failed — {e}")
        return _fallback_profile(raw_profile)


# ─────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE — compatible MCP Server
# ─────────────────────────────────────────────────────────────────────

def _smart_read(file_path: str) -> pd.DataFrame:
    """Charge CSV ou JSON (plat ou imbriqué) selon l'extension."""
    from app.tools.load_dataset import _load_json_smart
    if os.path.splitext(file_path)[1].lower() == ".json":
        return _load_json_smart(file_path)
    return pd.read_csv(file_path, low_memory=False)


def profile_data(file_path: str, run_id: str) -> dict:
    """
    1. Charge le CSV/JSON généré par load_dataset/data_engineer
    2. Calcule le profil brut avec pandas
    3. Analyse avec Groq ou fallback pandas
    4. Sauvegarde profile.json
    5. Log l'artifact
    """
    print(f"[profile_data] Chargement de {file_path}...")

    try:
        df = _smart_read(file_path)
    except Exception as e:
        result = {
            "status": "error",
            "run_id": run_id,
            "file_path": file_path,
            "message": f"Erreur lecture fichier : {str(e)}"
        }
        log_artifact(run_id, "profile_data", result)
        return result

    print(f"[profile_data] {len(df):,} lignes × {len(df.columns)} colonnes")

    print("[profile_data] Calcul du profil brut...")
    raw_profile = _build_raw_profile(df)

    print("[profile_data] Analyse Groq en cours...")
    groq_analysis = _ask_groq(raw_profile)

    result = {
        "status"            : "success",
        "run_id"            : run_id,
        "file_path"         : file_path,
        "total_rows"        : raw_profile["total_rows"],
        "total_columns"     : raw_profile["total_columns"],
        "duplicate_rows"    : raw_profile.get("duplicate_rows", 0),
        "duplicate_rate_pct": raw_profile.get("duplicate_rate_pct", 0),
        "columns_info"      : raw_profile["columns"],
        "problems"          : groq_analysis.get("problems", []),
        "quality_score"     : groq_analysis.get("quality_score", 0.0),
        "quality_summary"   : groq_analysis.get("quality_summary", ""),
        "cleaning_hints"    : groq_analysis.get("cleaning_hints", []),
    }

    print(f"[profile_data] Score qualité : {result['quality_score']}")
    print(f"[profile_data] Problèmes     : {len(result['problems'])}")
    print(f"[profile_data] Doublons      : {result['duplicate_rows']}")

    artifacts_dir = f"runs/{run_id}/artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)

    profile_path = f"{artifacts_dir}/profile.json"

    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[profile_data] Profil sauvegardé → {profile_path}")

    log_artifact(run_id, "profile_data", {
        "status"            : "success",
        "rows"              : result["total_rows"],
        "quality_score"     : result["quality_score"],
        "problems_count"    : len(result["problems"]),
        "duplicate_rows"    : result["duplicate_rows"],
        "duplicate_rate_pct": result["duplicate_rate_pct"],
        "profile_path"      : profile_path
    })

    return result