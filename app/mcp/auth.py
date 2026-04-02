PERMISSIONS = {
    "orchestrator":   ["*"],
    "data_quality":   ["load_dataset", "quality_check", "log_artifact"],
    "data_engineer":  ["load_dataset", "profile_data", "clean_data", "log_artifact"],
    "kpi_calculator": ["run_analysis", "log_artifact"],
    "bi_agent":       ["generate_chart", "publish_dashboard", "log_artifact"],
    "reporter":       ["compile_report", "log_artifact"],
    "devops":         ["log_artifact"],
}


def is_authorized(agent: str, tool: str) -> bool:
    perms = PERMISSIONS.get(agent, [])
    return "*" in perms or tool in perms


def get_permissions(agent: str) -> list:
    return PERMISSIONS.get(agent, [])
