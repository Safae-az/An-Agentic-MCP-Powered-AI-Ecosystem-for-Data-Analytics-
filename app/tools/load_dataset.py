
import pandas as pd
import os
import requests
import zipfile
from urllib.parse import urlparse
from app.tools.log_artifact import log_artifact


SUPPORTED = {
    ".csv"    : "delimited",
    ".tsv"    : "tsv",
    ".txt"    : "delimited",
    ".xlsx"   : "excel",
    ".xls"    : "excel",
    ".json"   : "json",
    ".parquet": "parquet",
}

DOWNLOAD_HEADERS = {
    "User-Agent": "KPI-Monitoring-System/1.0",
    "Accept": "application/json, text/csv, text/plain, application/vnd.ms-excel, "
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, */*",
}


def _validate_http_url(value: str, label: str = "URL") -> str:
    value = str(value or "").strip()
    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label} invalide : utilisez une URL http(s) complete.")

    return value


def _load_json_smart(file_path: str) -> pd.DataFrame:
    """
    Charge n'importe quel JSON en DataFrame plat.
    Gère : tableau plat, objet avec tableau imbriqué (OpenWeather, etc.),
    objet JSON imbriqué profond.
    """
    import json as _json

    with open(file_path, "r", encoding="utf-8") as f:
        data = _json.load(f)

    # Cas 1 : tableau de dicts  [{...}, {...}]
    if isinstance(data, list):
        df = pd.json_normalize(data)
        return _flatten_nested_columns(df)

    # Cas 2 : objet dict  {"list": [{...}], "city": {...}}
    if isinstance(data, dict):
        # Cherche le premier champ qui est une liste de dicts (données principales)
        for _key, val in data.items():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                df = pd.json_normalize(val)
                return _flatten_nested_columns(df)
        # Pas de liste trouvée → normalise l'objet entier sur 1 ligne
        df = pd.json_normalize([data])
        return _flatten_nested_columns(df)

    raise ValueError("Format JSON non reconnu")


def _flatten_nested_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convertit les colonnes encore imbriquées (dict/list) en chaînes JSON.
    Exemple : colonne roi = {'times': 35.5, 'currency': 'btc'} -> str
    """
    import json as _json
    for col in df.columns:
        sample = df[col].dropna()
        if sample.empty:
            continue
        first = sample.iloc[0]
        if isinstance(first, (dict, list)):
            df[col] = df[col].apply(
                lambda v: _json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            )
    return df


def _load_file(file_path: str) -> pd.DataFrame:
    """
    Charge un fichier selon son extension.
    Supporte CSV/TXT avec détection automatique du séparateur.
    Essaie plusieurs encodings pour les fichiers texte.
    """
    ext = os.path.splitext(file_path)[1].lower()
    fmt = SUPPORTED.get(ext)

    if fmt is None:
        raise ValueError(f"Format non supporté : {ext}")

    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    if fmt == "delimited":
        last_error = None

        for encoding in encodings:
            try:
              return pd.read_csv(
                 file_path,
                 encoding=encoding,
                 sep=None,
                 engine="python"
)
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

        raise ValueError(
            f"Impossible de charger le fichier délimité : {file_path}. "
            f"Erreur : {last_error}"
        )

    elif fmt == "tsv":
        last_error = None

        for encoding in encodings:
            try:
                return pd.read_csv(
                    file_path,
                    sep="\t",
                    encoding=encoding,
                    low_memory=False
                )
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

        raise ValueError(
            f"Impossible de charger le TSV : {file_path}. "
            f"Erreur : {last_error}"
        )

    elif fmt == "excel":
        return pd.read_excel(file_path)

    elif fmt == "json":
        return _load_json_smart(file_path)

    elif fmt == "parquet":
        return pd.read_parquet(file_path)

    else:
        raise ValueError(f"Format non supporté : {ext}")


def _safe_preview(df: pd.DataFrame, n: int = 3) -> list:
    """
    Retourne n lignes en dict JSON-safe.
    Convertit NaN et types pandas/numpy vers des types simples.
    """
    preview = df.head(n).copy()

    for col in preview.columns:
        dtype_str = str(preview[col].dtype)

        if dtype_str == "bool":
            preview[col] = preview[col].astype(str)

        elif "int" in dtype_str or "float" in dtype_str:
            preview[col] = preview[col].astype(object)

    return preview.where(preview.notna(), other=None).to_dict(orient="records")


def load_dataset(file_path: str, run_id: str) -> dict:
    """
    Charge un fichier de données : CSV, TXT, TSV, Excel, JSON, Parquet.
    Compatible MCP Server — retourne un dict JSON-safe.
    """
    print(f"[load_dataset] Chargement de {file_path}...")

    if not os.path.exists(file_path):
        result = {
            "status": "error",
            "message": f"Fichier introuvable : {file_path}"
        }
        log_artifact(run_id, "load_dataset", result)
        return result

    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED:
        result = {
            "status": "error",
            "message": f"Format '{ext}' non supporté. Acceptés : {list(SUPPORTED.keys())}"
        }
        log_artifact(run_id, "load_dataset", result)
        return result

    try:
        df = _load_file(file_path)
    except Exception as e:
        result = {
            "status": "error",
            "message": f"Erreur chargement : {str(e)}"
        }
        log_artifact(run_id, "load_dataset", result)
        return result

    file_size_kb = round(os.path.getsize(file_path) / 1024, 1)

    result = {
        "status"      : "success",
        "run_id"      : run_id,
        "file_path"   : file_path,
        "file_format" : SUPPORTED[ext],
        "file_size_kb": file_size_kb,
        "rows"        : int(len(df)),
        "columns"     : list(df.columns),
        "dtypes"      : {col: str(df[col].dtype) for col in df.columns},
        "preview"     : _safe_preview(df),
    }

    print(
        f"[load_dataset] OK — {len(df):,} lignes × "
        f"{len(df.columns)} colonnes ({file_size_kb} KB)"
    )

    log_artifact(run_id, "load_dataset", {
        "status"     : "success",
        "rows"       : int(len(df)),
        "file_format": SUPPORTED[ext],
    })

    return result


# ---------------------------------------------------------------------------
# Méthode 2 : chargement via lien direct (URL)
# ---------------------------------------------------------------------------

def _guess_ext_from_response(response: requests.Response, url: str) -> str:
    """
    Devine l'extension du fichier depuis le Content-Type ou l'URL.
    Retourne une extension parmi SUPPORTED, ou .csv par défaut.
    """
    content_type = response.headers.get("Content-Type", "")

    if "csv" in content_type or "text/plain" in content_type:
        return ".csv"
    if "json" in content_type:
        return ".json"
    if "zip" in content_type:
        return ".zip"
    if "parquet" in content_type:
        return ".parquet"
    if "excel" in content_type or "spreadsheetml" in content_type:
        return ".xlsx"

    # Fallback : extension depuis l'URL
    parsed_ext = os.path.splitext(urlparse(url).path)[1].lower()
    if parsed_ext == ".zip":
        return ".zip"
    if parsed_ext in SUPPORTED:
        return parsed_ext

    return ".csv"


def _save_response_as_dataset(
    response: requests.Response,
    source_url: str,
    run_id: str,
    prefix: str,
) -> tuple[str | None, str | None]:
    """
    Sauvegarde une reponse HTTP dans uploads/.
    Si la reponse est un ZIP (cas frequent avec Kaggle), extrait le premier
    fichier supporte et retourne son chemin local.
    """
    ext = _guess_ext_from_response(response, source_url)
    os.makedirs("uploads", exist_ok=True)

    if ext == ".zip":
        zip_path = os.path.join("uploads", f"{prefix}_{run_id}.zip")
        with open(zip_path, "wb") as f:
            f.write(response.content)

        try:
            with zipfile.ZipFile(zip_path) as archive:
                for member in archive.infolist():
                    member_ext = os.path.splitext(member.filename)[1].lower()
                    if member.is_dir() or member_ext not in SUPPORTED:
                        continue

                    safe_name = os.path.basename(member.filename)
                    local_path = os.path.join("uploads", f"{prefix}_{run_id}_{safe_name}")
                    with archive.open(member) as src, open(local_path, "wb") as dst:
                        dst.write(src.read())
                    return local_path, None
        except zipfile.BadZipFile:
            return None, "La reponse API/URL ressemble a un ZIP, mais le fichier est invalide."

        return None, "Aucun fichier supporte trouve dans le ZIP telecharge."

    filename = f"{prefix}_{run_id}{ext}"
    local_path = os.path.join("uploads", filename)

    with open(local_path, "wb") as f:
        f.write(response.content)

    return local_path, None


def load_from_url(url: str, run_id: str) -> dict:
    """
    Méthode via lien direct — télécharge le fichier depuis une URL publique
    et lance load_dataset() sur le fichier local obtenu.

    Exemples d'URLs supportées :
      https://exemple.com/data.csv
      https://raw.githubusercontent.com/.../dataset.json
    """
    try:
        url = _validate_http_url(url, "URL")
    except ValueError as e:
        result = {"status": "error", "message": str(e), "url": url}
        log_artifact(run_id, "load_from_url", result)
        return result

    print(f"[load_dataset] Telechargement URL : {url}")

    try:
        response = requests.get(url, headers=DOWNLOAD_HEADERS, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        result = {
            "status" : "error",
            "message": f"Impossible de télécharger l'URL : {str(e)}",
            "url"    : url,
        }
        log_artifact(run_id, "load_from_url", result)
        return result

    local_path, error = _save_response_as_dataset(response, url, run_id, "url_data")
    if error:
        result = {"status": "error", "message": error, "url": url}
        log_artifact(run_id, "load_from_url", result)
        return result

    print(f"[load_dataset] Fichier sauvegarde -> {local_path}")
    return load_dataset(local_path, run_id)


# ---------------------------------------------------------------------------
# Méthode 3 : chargement via clé API
# ---------------------------------------------------------------------------

def load_from_api(api_url: str, api_key: str, run_id: str,
                  key_param: str = "") -> dict:
    """
    Méthode via clé API — interroge un endpoint REST avec authentification
    et charge le résultat comme dataset.

    Stratégie d'authentification (tentée dans cet ordre) :
      1. Header  Authorization: Bearer <api_key>
      2. Header  X-API-Key: <api_key>
      3. Paramètre URL ?<key_param>=<api_key>  (si key_param fourni)

    Sites courants :
      Kaggle      → https://www.kaggle.com/api/v1/datasets/...
      OpenWeather → https://api.openweathermap.org/data/2.5/...?appid=KEY
      data.gouv   → https://www.data.gouv.fr/api/1/datasets/...
    """
    try:
        api_url = _validate_http_url(api_url, "URL API")
    except ValueError as e:
        result = {"status": "error", "message": str(e), "api_url": api_url}
        log_artifact(run_id, "load_from_api", result)
        return result

    api_key = str(api_key or "").strip()
    if not api_key:
        result = {"status": "error", "message": "Cle API obligatoire.", "api_url": api_url}
        log_artifact(run_id, "load_from_api", result)
        return result

    key_param = str(key_param or "").strip()

    print(f"[load_dataset] Appel API : {api_url}")

    headers = {
        **DOWNLOAD_HEADERS,
        "Authorization": f"Bearer {api_key}",
        "X-API-Key"    : api_key,
    }

    params = {key_param: api_key} if key_param else {}

    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        result = {
            "status" : "error",
            "message": f"Erreur API : {str(e)}",
            "api_url": api_url,
        }
        log_artifact(run_id, "load_from_api", result)
        return result

    local_path, error = _save_response_as_dataset(response, api_url, run_id, "api_data")
    if error:
        result = {"status": "error", "message": error, "api_url": api_url}
        log_artifact(run_id, "load_from_api", result)
        return result

    print(f"[load_dataset] Donnees API sauvegardees -> {local_path}")
    return load_dataset(local_path, run_id)
