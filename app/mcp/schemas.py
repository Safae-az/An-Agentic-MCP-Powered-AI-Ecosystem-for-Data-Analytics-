# Format entrée/sortie de chaque outil
# Claude LLM utilise ces schemas pour savoir comment appeler les outils

TOOL_SCHEMAS = [
    {
        "name": "load_dataset",
        "description": "Charge un fichier CSV ou Excel en mémoire et retourne un aperçu",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Chemin vers le fichier CSV/Excel"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "quality_check",
        "description": "Analyse la qualité du dataset : nulls, doublons, anomalies, score qualité",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Chemin vers le fichier à analyser"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "profile_data",
        "description": "Profil statistique du dataset : types, distributions, stats descriptives",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Chemin vers le fichier"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "clean_data",
        "description": "Nettoie le dataset : supprime nulls, doublons, corrige les anomalies",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path":   {"type": "string", "description": "Fichier brut à nettoyer"},
                "output_path": {"type": "string", "description": "Où sauvegarder le fichier nettoyé"},
                "run_id":      {"type": "string", "description": "ID du run en cours"}
            },
            "required": ["file_path", "output_path", "run_id"]
        }
    },
    {
    "name": "run_analysis",
    "description": (
        "Calcule les KPIs business d'un dataset e-commerce nettoyé : "
        "CA total, CA par mois, CA par pays, panier moyen, "
        "taux d'annulation (factures uniques commençant par 'C'), "
        "taux de retour (lignes Quantity < 0), top 10 produits, "
        "data quality score. Génère des alertes warning/critical "
        "selon les seuils configurés et produit des insights textuels."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": (
                    "Chemin vers le fichier CSV nettoyé à analyser. "
                    "Colonnes requises : InvoiceNo, Quantity, UnitPrice. "
                    "Colonnes optionnelles : InvoiceDate, Country, CustomerID, Description."
                )
            },
            "run_id": {
                "type": "string",
                "description": (
                    "ID unique du run en cours. "
                    "Utilisé pour sauvegarder les résultats sous "
                    "runs/{run_id}/artifacts/insights.json."
                )
            }
        },
        "required": ["file_path", "run_id"],
        "additionalProperties": False
    }
},
    
    {
        "name": "generate_chart",
        "description": "Génère un graphique interactif Plotly (bar, line, pie, scatter)",
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {"type": "string", "description": "Type : bar / line / pie / scatter"},
                "title":      {"type": "string", "description": "Titre du graphique"},
                "data":       {"type": "object", "description": "Données à visualiser"},
                "run_id":     {"type": "string", "description": "ID du run en cours"}
            },
            "required": ["chart_type", "title", "data", "run_id"]
        }
    },
    {
        "name": "publish_dashboard",
        "description": "Assemble tous les charts en un dashboard HTML interactif",
        "input_schema": {
            "type": "object",
            "properties": {
                "charts": {"type": "array",  "description": "Liste des chemins vers les charts HTML"},
                "kpis":   {"type": "object", "description": "KPIs à afficher en haut du dashboard"},
                "run_id": {"type": "string", "description": "ID du run en cours"}
            },
            "required": ["charts", "run_id"]
        }
    },
    {
        "name": "log_artifact",
        "description": "Sauvegarde un artifact (fichier produit) dans le store du run",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id":    {"type": "string", "description": "ID du run"},
                "type":      {"type": "string", "description": "Type : cleaned_data / chart / report / insights"},
                "path":      {"type": "string", "description": "Chemin vers le fichier"},
                "producer":  {"type": "string", "description": "Nom de l'agent qui a produit ce fichier"},
                "metadata":  {"type": "object", "description": "Infos supplémentaires (optionnel)"}
            },
            "required": ["run_id", "type", "path", "producer"]
        }
    },
    {
        "name": "compile_report",
        "description": "Génère le rapport PDF final à partir de tous les artifacts du run",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "ID du run dont on veut le rapport"}
            },
            "required": ["run_id"]
        }
    },
]


def get_schemas_for_agent(agent_name: str) -> list:
    """Retourne uniquement les schemas des outils autorisés pour un agent."""
    from app.mcp.auth import get_permissions
    perms = get_permissions(agent_name)
    if "*" in perms:
        return TOOL_SCHEMAS
    return [s for s in TOOL_SCHEMAS if s["name"] in perms]
