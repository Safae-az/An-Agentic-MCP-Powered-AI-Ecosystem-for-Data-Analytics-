from app.storage.artifact_store import ArtifactStore

store = ArtifactStore()


class RunStore:
    """
    Interface haut niveau pour gérer les runs.
    Utilisé par l'UI (P4) pour afficher l'historique.
    """

    def get_all_runs(self) -> list:
        return store.list_runs()

    def get_run(self, run_id: str) -> dict:
        return store.get_metadata(run_id)

    def get_run_logs(self, run_id: str) -> list:
        return store.get_logs(run_id)
