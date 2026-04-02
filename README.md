# 🚀 KPI Monitoring System — Run Guide

## Prérequis
- Python 3.10+
- pip

## Installation

```bash
# 1. Cloner le repo
git clone <url-du-repo>
cd project

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer la clé API
cp .env.example .env
# Éditer .env et mettre ta clé Anthropic :
# ANTHROPIC_API_KEY=sk-ant-xxxxxxx
```

## Lancement

### Terminal 1 — MCP Server (port 8000)
```bash
uvicorn app.mcp.server:app --port 8000 --reload
```

### Terminal 2 — API principale (port 8001)
```bash
uvicorn app.main:app --port 8001 --reload
```

## Tester le système

```bash
# Test 1 : MCP Server opérationnel ?
curl http://localhost:8000/health

# Test 2 : Lister les outils disponibles
curl http://localhost:8000/tools

# Test 3 : Vérifier les permissions d'un agent
curl http://localhost:8000/permissions/data_engineer

# Test 4 : Lancer un pipeline complet
curl -X POST http://localhost:8001/run/start \
  -F "file=@online_retail_raw.csv" \
  -F "objective=Analyse les KPIs de ventes et génère un dashboard"

# Test 5 : Voir les logs d'un run
curl http://localhost:8001/run/run_20241201_120000/logs
```

## Structure des fichiers produits

```
runs/
  run_20241201_120000/
    metadata.json              ← info du run
    decisions.jsonl            ← décisions des agents
    tool_calls.jsonl           ← appels MCP
    artifacts/
      cleaned_data.csv         ← produit par Data Engineer
      insights.json            ← KPIs produits par Data Scientist
      report.html              ← rapport final produit par Reporter
      charts/
        ca_mensuel.html        ← graphiques produits par BI Agent
        top_pays.html
        repartition.html
      dashboard.html           ← dashboard assemblé par BI Agent
```

## Responsabilités par personne

| Fichier                        | Codé par |
|-------------------------------|----------|
| app/mcp/server.py             | P1       |
| app/orchestrator/engine.py    | P1       |
| app/agents/devops_agent.py    | P1       |
| app/storage/artifact_store.py | P1       |
| app/tools/load_dataset.py     | P2       |
| app/tools/quality_check.py    | P2       |
| app/tools/clean_data.py       | P2       |
| app/tools/run_analysis.py     | P2       |
| app/agents/data_engineer.py   | P2       |
| app/agents/data_scientist.py  | P2       |
| app/tools/generate_chart.py   | P3       |
| app/tools/publish_dashboard.py| P3       |
| app/agents/bi_agent.py        | P3       |
| app/tools/compile_report.py   | P4       |
| app/agents/reporter.py        | P4       |
| app/main.py (UI backend)      | P4       |
