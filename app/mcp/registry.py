# Registre de tous les outils disponibles
# Chaque ami ajoute ses outils ici quand il les code

TOOL_MODULES = {
    # ── P1 (Orchestrateur) ────────────────────────────
    "log_artifact":      "app.tools.log_artifact",

    # ── P2 (Data Guy) — à remplir par P2 ─────────────
    "load_dataset":      "app.tools.load_dataset",
    "quality_check":     "app.tools.quality_check",
    "profile_data":      "app.tools.profile_data",
    "clean_data":        "app.tools.clean_data",
    "run_analysis":      "app.tools.run_analysis",

    # ── P3 (BI Agent) — à remplir par P3 ─────────────
    "generate_chart":    "app.tools.generate_chart",
    "publish_dashboard": "app.tools.publish_dashboard",

    # ── P4 (Reporter) — à remplir par P4 ─────────────
    "compile_report":    "app.tools.compile_report",
}


def get_tool_module(tool_name: str) -> str | None:
    return TOOL_MODULES.get(tool_name)


def list_tools() -> list:
    return list(TOOL_MODULES.keys())
