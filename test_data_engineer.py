# # test_data_engineer.py
# import sys, os
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# from app.agents.data_engineer import DataEngineerAgent

# agent  = DataEngineerAgent(run_id="run_001")
# result = agent.run(file_path="data/online_retail_II.csv")

# print("\n=== RESULTAT FINAL ===")
# print(f"Status        : {result['status']}")
# print(f"Clean path    : {result['clean_path']}")
# print(f"Lignes finales: {result['final_rows']:,}")
# print(f"Score qualite : {result['quality_score']}")


# test_data_engineer.py
# Maintenant on passe par engine.py — comme dans le vrai système

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.orchestrator.engine import Engine

# Créer et lancer l'engine
engine = Engine()
result = engine.run(
    file_path = "data/online_retail_II.csv",
    run_id    = "run_001"
)

print("\n=== RESUME FINAL ===")
print(f"Status    : {result['status']}")
print(f"Completes : {result['completed']}")
print(f"Artifacts : {result['artifacts']}")