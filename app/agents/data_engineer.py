# app/agents/data_engineer.py
from app.tools.load_dataset import load_dataset
from app.tools.profile_data import profile_data
from app.tools.clean_data   import clean_data
from app.tools.log_artifact import log_artifact

class DataEngineerAgent:

    SYSTEM_PROMPT = """
    Tu es le Data Engineer d'une equipe d'agents IA.
    Tu charges, profiles et nettoies des datasets.
    Tu utilises toujours ces outils dans cet ordre :
    1. load_dataset  -> charger le fichier
    2. profile_data  -> analyser la qualite
    3. clean_data    -> nettoyer les donnees
    Tu retournes toujours un rapport JSON structure.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.name   = "DataEngineer"
        print(f"[{self.name}] Agent initialise — run: {self.run_id}")

    def run(self, file_path: str) -> dict:
        print(f"\n{'='*50}")
        print(f"  DATA ENGINEER AGENT — {self.run_id}")
        print(f"{'='*50}")

        # Outil 1 : Charger
        df, load_result = load_dataset(file_path, self.run_id)
        if load_result["status"] == "error":
            log_artifact(self.run_id, "agent_error", load_result)
            return load_result

        # Outil 2 : Profiler
        profile = profile_data(df, self.run_id)

        # Outil 3 : Nettoyer
        df_clean, clean_report = clean_data(df, self.run_id)

        # Resultat final
        result = {
            "status"        : "success",
            "agent"         : self.name,
            "run_id"        : self.run_id,
            "clean_path"    : clean_report["output_path"],
            "initial_rows"  : clean_report["initial_rows"],
            "final_rows"    : clean_report["final_rows"],
            "quality_score" : profile["quality_score"]
        }

        log_artifact(self.run_id, "agent_completed", result)

        print(f"\n  PIPELINE TERMINE !")
        print(f"  Dataset propre : {result['clean_path']}")
        print(f"  Lignes finales : {result['final_rows']:,}")
        print(f"  Score qualite  : {result['quality_score']}")
        print(f"{'='*50}\n")

        return result