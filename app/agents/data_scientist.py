# app/agents/data_scientist.py
import os
import json
import re
from app.agents.base_agent import BaseAgent

DATA_SCIENTIST_TOOLS = [
    {
        "name": "run_analysis",
        "description": (
            "Analyse complète du dataset e-commerce nettoyé. Produit 4 sections : "
            "(1) data_quality : score global + détail par colonne (complétude, doublons) ; "
            "(2) kpis : CA total, CA par mois, CA par pays, panier moyen, taux annulation, "
            "taux retour, taux rétention, top 10 produits, variation MoM ; "
            "(3) anomalies : détection IQR sur colonnes numériques ; "
            "(4) chart_hints : suggestions de charts pour le dashboard BI. "
            "Génère les alertes warning/critical selon les seuils de monitoring. "
            "Sauvegarde tout dans runs/{run_id}/artifacts/insights.json."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Chemin vers le fichier CSV nettoyé à analyser."
                },
                "run_id": {
                    "type": "string",
                    "description": "Identifiant du run en cours (ex: 'run_001')."
                }
            },
            "required": ["file_path", "run_id"]
        }
    }
]

# ---------------------------------------------------------------------------
# Mapping mots-clés → type de chart
# Ordre important : les mots-clés plus spécifiques d'abord
# ---------------------------------------------------------------------------
CHART_TYPE_MAP = [
    # distributions / répartitions → pie
    ("distribution", "pie_chart"),
    ("type",         "pie_chart"),
    ("gender",       "pie_chart"),
    ("status",       "pie_chart"),
    ("share",        "pie_chart"),
    ("mix",          "pie_chart"),
    # taux / scores / évolutions → line
    ("churn",        "line_chart"),
    ("attrition",    "line_chart"),
    ("rate",         "line_chart"),
    ("score",        "line_chart"),
    ("satisfaction", "line_chart"),
    ("retention",    "line_chart"),
    ("trend",        "line_chart"),
    # moyennes / totaux / comptages → bar
    ("average",      "bar_chart"),
    ("avg",          "bar_chart"),
    ("mean",         "bar_chart"),
    ("balance",      "bar_chart"),
    ("number",       "bar_chart"),
    ("count",        "bar_chart"),
    ("total",        "bar_chart"),
    ("complaint",    "bar_chart"),
    ("point",        "bar_chart"),
    ("earned",       "bar_chart"),
    ("product",      "bar_chart"),
    ("revenue",      "bar_chart"),
    ("salary",       "bar_chart"),
]

# Clés méta à exclure des chart_hints
META_KEYS = {"data_quality_score", "domain_detected", "domain"}


class DataScientistAgent(BaseAgent):
    """
    Agent LLM spécialisé dans le Data Quality Monitoring et la génération de KPIs.
    Thème : AI Multi-Agent System for Data Quality and Business KPI Monitoring
            with Automated Dashboard Generation

    FIX v3 :
    - _generate_chart_hints() : génère chart_hints depuis les clés KPI si vides.
    - _enrich_chart_hints()   : complète les hints incomplets + ajoute KPIs manquants.
    - _patch_insights_json()  : écrit les chart_hints générés dans insights.json sur
      disque, pour que le BI Agent lise un fichier à jour.
    - _parse_output()         : retourne toujours chart_hints=[] depuis le fallback
      disque, pour forcer la regénération via _generate_chart_hints().
    """

    agent_name = "data_scientist"

    def __init__(self, run_id: str = ""):
        self.agent_name    = "data_scientist"
        self.system_prompt = """Tu es un Data Scientist expert en Data Quality Monitoring et KPI Business Analytics.
Tu travailles dans un système multi-agent dont le thème est :
"AI Multi-Agent System for Data Quality and Business KPI Monitoring with Automated Dashboard Generation"
Ton rôle dans le pipeline :
1. Recevoir un fichier CSV nettoyé et un run_id.
2. Appeler l'outil run_analysis avec file_path et run_id.
3. Analyser les résultats sur 4 axes :
   - Data Quality   : score global, colonnes problématiques, doublons
   - KPI Monitoring : CA, tendances, panier moyen, rétention, alertes
   - Anomalies      : colonnes avec valeurs aberrantes détectées
   - Dashboard      : chart_hints pour guider le BI Agent
4. Retourner un JSON structuré avec EXACTEMENT ces champs :
   {
     "data_quality" : { "score_global": ..., "nb_doublons": ..., "colonnes": {...} },
     "kpis"         : { "CA_total": ..., "panier_moyen": ..., ... },
     "anomalies"    : { "colonne": { "nb_anomalies": ..., "severite": ... } },
     "alertes"      : [ { "kpi": ..., "niveau": ..., "message": ... } ],
     "insights"     : [ "phrase 1", "phrase 2", ... ],
     "chart_hints"  : [ { "chart_id": ..., "type": ..., "title": ... } ],
     "output_path"  : "runs/run_001/artifacts/insights.json",
     "anonymous_columns": [],
     "alias_map": {},
     "anonymous_detection": {},
     "success"      : true
   }
Règles importantes :
- Appelle TOUJOURS run_analysis — ne calcule jamais les KPIs toi-même.
- Transmets fidèlement TOUS les champs retournés par run_analysis.
- Les chart_hints sont critiques : le BI Agent en a besoin pour générer le dashboard.
- Si run_analysis retourne une erreur, retourne success: false avec le message.
- Réponds TOUJOURS avec un JSON valide uniquement, sans texte autour."""

        super().__init__(run_id=run_id)

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------
    def run(self, step: str = "", context: dict = {}) -> dict:
        run_id = context.get("run_id", self.run_id)

        # ── Résoudre le chemin du fichier nettoyé ──
        file_path = (
            context.get("artifacts", {}).get("last_file")
            or context.get("artifacts", {})
                      .get("data_engineer", {})
                      .get("output_path")
            or context.get("artifacts", {})
                      .get("data_engineer", {})
                      .get("clean_path")
            or context.get("dataset_path", "")
        )

        # ── Vérification robuste du fichier ──
        if not file_path or not os.path.exists(file_path):
            print(f"[DataScientist] ERREUR — fichier introuvable : '{file_path}'")
            return {
                "status"      : "error",
                "agent"       : self.agent_name,
                "step"        : "run_analysis",
                "message"     : f"Fichier introuvable : '{file_path}'",
                "data_quality": {},
                "kpis"        : {},
                "anomalies"   : {},
                "alertes"     : [],
                "insights"    : [],
                "chart_hints" : []
            }

        print(f"\n{'='*55}")
        print(f"  DATA SCIENTIST AGENT — {run_id}")
        print(f"  LLM tool-calling via MCP Server")
        print(f"{'='*55}")
        print(f"\n[DataScientist] Fichier : {file_path}")

        # ── LLM loop avec tool-calling ──
        task_description = (
            f"Effectue l'analyse Data Quality et KPI Monitoring du dataset reçu.\n\n"
            f"run_id    : {run_id}\n"
            f"file_path : {file_path}\n\n"
            f"Étapes :\n"
            f"1. Appelle run_analysis(file_path='{file_path}', run_id='{run_id}').\n"
            f"2. run_analysis détecte automatiquement le domaine du dataset.\n"
            f"3. Transmets EXACTEMENT ce que run_analysis retourne sans modifier les KPIs.\n"
            f"4. Retourne le JSON complet avec domain, data_quality, kpis, anomalies, "
            f"alertes, insights, chart_hints, anonymous_columns, alias_map, "
            f"anonymous_detection, output_path et success."
        )

        messages   = [{"role": "user", "content": task_description}]
        raw_output = self._run_loop(messages, DATA_SCIENTIST_TOOLS, run_id)

        print(f"[DataScientist] LLM terminé — parsing JSON...")
        result = self._parse_output(raw_output, run_id)
        result = self._merge_analysis_metadata(result, run_id)

        # ── FIX v3 : garantir des chart_hints complets ───────────────────
        kpis  = result.get("kpis", {})
        hints = result.get("chart_hints", [])

        if not hints:
            # Cas le plus fréquent : LLM ou fichier disque retourne chart_hints: []
            # → génération automatique depuis les clés KPI
            hints = self._generate_chart_hints(kpis)
            print(f"[DataScientist] chart_hints générés automatiquement : {len(hints)}")
        else:
            # Hints présents mais peut-être incomplets
            hints = self._enrich_chart_hints(hints, kpis)
            print(f"[DataScientist] chart_hints enrichis : {len(hints)}")

        result["chart_hints"] = hints

        # FIX v3 : patcher insights.json sur disque avec les hints générés
        # → le BI Agent lit ce fichier directement, il doit être à jour
        output_path = result.get("output_path", f"runs/{run_id}/artifacts/insights.json")
        self._patch_insights_json(
            run_id=run_id,
            chart_hints=hints,
            output_path=output_path,
        )
        # ─────────────────────────────────────────────────────────────────

        print(f"[DataScientist] Score qualite : {kpis.get('data_quality_score', '?')}")
        domain = result.get("domain", "unknown")
        print(f"[DataScientist] Domaine        : {domain}")
        print(f"[DataScientist] Nb KPIs        : {len(kpis)}")
        print(f"[DataScientist] KPIs calculés  : {', '.join(list(kpis.keys())[:5])}")
        print(f"[DataScientist] Alertes        : {len(result.get('alertes', []))}")

        # ── Résultat final enrichi ──
        final = {
            "status"      : "success",
            "agent"       : self.agent_name,
            "run_id"      : run_id,
            "domain"      : domain,
            "data_quality": result.get("data_quality", {
                "score_global": kpis.get("data_quality_score", 0),
                "nb_doublons" : 0,
                "colonnes"    : {}
            }),
            "kpis"        : kpis,
            "anomalies"   : result.get("anomalies", {}),
            "alertes"     : result.get("alertes", []),
            "insights"    : result.get("insights", []),
            "chart_hints" : hints,
            "output_path" : output_path,
            "anonymous_columns": result.get("anonymous_columns", []),
            "alias_map"   : result.get("alias_map", {}),
            "anonymous_detection": result.get("anonymous_detection", {}),
            "columns_after_aliasing": result.get("columns_after_aliasing", []),
        }

        print(f"\n{'='*55}")
        print(f"  ANALYSE TERMINEE !")
        print(f"  Insights    : {len(final['insights'])}")
        print(f"  Charts      : {len(final['chart_hints'])}")
        print(f"  Alertes     : {len(final['alertes'])}")
        print(f"  Output      : {final['output_path']}")
        print(f"{'='*55}\n")

        return final

    # ------------------------------------------------------------------
    # Génération automatique de chart_hints depuis les clés KPI
    # ------------------------------------------------------------------
    def _generate_chart_hints(self, kpis: dict) -> list:
        """
        Génère chart_hints depuis les clés KPI quand le LLM retourne [].
        - Ignore les clés méta (data_quality_score, domain_detected, domain).
        - Type inféré via CHART_TYPE_MAP, défaut bar_chart.
        """
        hints = []

        for kpi_key in kpis:
            if kpi_key in META_KEYS:
                continue

            hints.append({
                "chart_id": kpi_key,
                "type"    : self._infer_chart_type(kpi_key),
                "title"   : kpi_key.replace("_", " ").title(),
            })

        return hints

    def _enrich_chart_hints(self, hints: list, kpis: dict) -> list:
        """
        Complète les chart_hints existants et ajoute les KPIs non couverts.
        """
        enriched = []
        covered  = set()

        for hint in hints:
            if not isinstance(hint, dict):
                continue

            chart_id = (
                hint.get("chart_id")
                or hint.get("key")
                or hint.get("kpi")
                or ""
            )
            if not chart_id:
                continue

            chart_id = str(chart_id)
            covered.add(chart_id)

            enriched.append({
                "chart_id": chart_id,
                "type"    : (
                    hint.get("type")
                    or hint.get("chart_type")
                    or self._infer_chart_type(chart_id)
                ),
                "title"   : hint.get("title") or chart_id.replace("_", " ").title(),
            })

        # Ajouter les KPIs non couverts par les hints existants
        for kpi_key in kpis:
            if kpi_key in META_KEYS or kpi_key in covered:
                continue

            enriched.append({
                "chart_id": kpi_key,
                "type"    : self._infer_chart_type(kpi_key),
                "title"   : kpi_key.replace("_", " ").title(),
            })

        return enriched

    def _infer_chart_type(self, key: str) -> str:
        """Retourne le type de chart le plus adapté à une clé KPI."""
        key_lower = str(key).lower()

        for keyword, chart_type in CHART_TYPE_MAP:
            if keyword in key_lower:
                return chart_type

        return "bar_chart"

    # ------------------------------------------------------------------
    # FIX v3 — Patch insights.json sur disque avec les chart_hints générés
    # ------------------------------------------------------------------
    def _merge_analysis_metadata(self, result: dict, run_id: str) -> dict:
        """Restore alias metadata from disk when the LLM omitted it."""
        path = result.get("output_path") or f"runs/{run_id}/artifacts/insights.json"
        if not os.path.exists(path):
            return result
        try:
            with open(path, "r", encoding="utf-8") as file:
                stored = json.load(file)
            for key in (
                "anonymous_columns",
                "alias_map",
                "anonymous_detection",
                "columns_after_aliasing",
            ):
                if key not in result and key in stored:
                    result[key] = stored[key]
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[DataScientist] Lecture metadata alias impossible: {exc}")
        return result

    def _patch_insights_json(
        self,
        run_id: str,
        chart_hints: list,
        output_path: str = "",
    ) -> None:
        """
        Met à jour chart_hints dans insights.json sur disque.

        Pourquoi c'est nécessaire :
        run_analysis() sauvegarde insights.json avec chart_hints: [] avant que
        _generate_chart_hints() soit appelé dans run(). Le BI Agent lit ce fichier
        directement depuis le disque via _resolve_insights_payload() → sans ce
        patch il reçoit toujours chart_hints: [] peu importe ce qu'on génère.
        """
        path = output_path or f"runs/{run_id}/artifacts/insights.json"

        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["chart_hints"] = chart_hints

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"[DataScientist] insights.json patché — {len(chart_hints)} chart_hints")

        except (json.JSONDecodeError, OSError) as e:
            print(f"[DataScientist] Patch insights.json échoué : {e}")

    # ------------------------------------------------------------------
    # Parsing de la réponse LLM
    # ------------------------------------------------------------------
    def _parse_output(self, raw: str, run_id: str = "") -> dict:
        """
        Extrait le JSON de la réponse du LLM, avec fallback disque.

        IMPORTANT : le fallback disque retourne intentionnellement chart_hints=[]
        pour forcer la regénération via _generate_chart_hints() dans run().
        Le fichier disque est ensuite patché par _patch_insights_json().
        """

        # Essai 1 : bloc ```json ... ```
        match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Essai 2 : JSON brut { ... }
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Essai 3 : fallback — lire insights.json du run courant sur disque
        if run_id:
            insights_path = f"runs/{run_id}/artifacts/insights.json"
            if os.path.exists(insights_path):
                try:
                    with open(insights_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    stored_run_id = data.get("run_id") or data.get("output_path", "")
                    if stored_run_id and run_id not in str(stored_run_id):
                        print(f"[DataScientist] AVERTISSEMENT — insights.json appartient à un autre run, ignoré")
                    else:
                        print(f"[DataScientist] Fallback — lecture de {insights_path}")
                        return {
                            "success"     : True,
                            "output_path" : insights_path,
                            "domain"      : data.get("domain", "unknown"),
                            "data_quality": data.get("data_quality", {}),
                            "kpis"        : data.get("kpis", {}),
                            "anomalies"   : data.get("anomalies", {}),
                            "alertes"     : data.get("alertes", []),
                            "insights"    : data.get("insights", []),
                            # Toujours [] ici → run() appellera _generate_chart_hints()
                            # puis _patch_insights_json() pour mettre le fichier à jour.
                            "chart_hints" : [],
                        }
                except (json.JSONDecodeError, OSError) as e:
                    print(f"[DataScientist] Fallback échoué : {e}")

        # Fallback final sécurisé
        return {
            "success"     : False,
            "error"       : "Parsing échoué et insights.json introuvable.",
            "raw_output"  : raw,
            "data_quality": {},
            "kpis"        : {},
            "anomalies"   : {},
            "alertes"     : [],
            "insights"    : [],
            "chart_hints" : [],
        }
