# app/agents/data_engineer.py
# VERSION CORRIGEE — passe par MCP Server
from app.agents.base_agent import BaseAgent

class DataEngineerAgent(BaseAgent):
    """
    Agent Data Engineer — P2
    CORRECTION : appelle les outils via MCP Server
    au lieu d'appels directs Python.
    """

    agent_name = "data_engineer"

    system_prompt = """
    Tu es le Data Engineer d'une equipe d'agents IA.
    Tu charges, profiles et nettoies des datasets.
    Tu utilises toujours ces outils dans cet ordre :
    1. load_dataset  -> charger le fichier
    2. profile_data  -> analyser la qualite
    3. clean_data    -> nettoyer les donnees
    Tous les appels passent par le MCP Server.
    """

    def __init__(self, run_id: str = ""):
        # CORRECTION : ne pas passer agent_name à super().__init__()
        # agent_name est déjà défini comme attribut de classe ci-dessus
        super().__init__(run_id=run_id)

    def run(self, file_path: str) -> dict:
        print(f"\n{'='*55}")
        print(f"  DATA ENGINEER AGENT — {self.run_id}")
        print(f"  Tous les appels passent par MCP Server")
        print(f"{'='*55}")

        # ── Outil 1 : load_dataset via MCP ──
        print(f"\n[DataEngineer] Etape 1/3 — load_dataset")
        load_result = self._call_mcp("load_dataset", {
            "file_path" : file_path,
            "run_id"    : self.run_id
        }, self.run_id)

        if load_result.get("status") == "error":
            print(f"[DataEngineer] ERREUR load_dataset : {load_result}")
            return {"status": "error", "agent": self.agent_name,
                    "step": "load_dataset", "message": load_result.get("message")}

        print(f"[DataEngineer] load_dataset OK — {load_result.get('rows', '?')} lignes")

        # ── Outil 2 : profile_data via MCP ──
        print(f"\n[DataEngineer] Etape 2/3 — profile_data")
        profile_result = self._call_mcp("profile_data", {
            "file_path" : file_path,
            "run_id"    : self.run_id
        }, self.run_id)

        quality_score = profile_result.get("quality_score", 0)
        print(f"[DataEngineer] profile_data OK — score qualite : {quality_score}")

        # ── Outil 3 : clean_data via MCP ──
        print(f"\n[DataEngineer] Etape 3/3 — clean_data")
        clean_result = self._call_mcp("clean_data", {
            "file_path" : file_path,
            "run_id"    : self.run_id
        }, self.run_id)

        if clean_result.get("status") == "error":
            print(f"[DataEngineer] ERREUR clean_data : {clean_result}")
            return {"status": "error", "agent": self.agent_name,
                    "step": "clean_data", "message": clean_result.get("message")}

        clean_path  = clean_result.get("output_path", "")
        final_rows  = clean_result.get("final_rows", 0)
        print(f"[DataEngineer] clean_data OK — {final_rows} lignes propres")

        # ── Resultat final ──
        result = {
            "status"        : "success",
            "agent"         : self.agent_name,
            "run_id"        : self.run_id,
            "clean_path"    : clean_path,
            "initial_rows"  : clean_result.get("initial_rows", 0),
            "final_rows"    : final_rows,
            "quality_score" : quality_score
        }

        print(f"\n{'='*55}")
        print(f"  DATA ENGINEER TERMINE !")
        print(f"  Dataset propre : {clean_path}")
        print(f"  Lignes finales : {final_rows:,}")
        print(f"  Score qualite  : {quality_score}")
        print(f"{'='*55}\n")

        return result
