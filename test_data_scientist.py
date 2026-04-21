import sys
import os

# ajouter le projet au path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.agents.data_scientist import DataScientistAgent


def main():

    RUN_ID = "test_run_001"

    FILE_PATH = "runs/test_run_001/artifacts/clean.csv"

    print("\n=================================================")
    print("   TEST — DataScientistAgent")
    print("=================================================\n")

    agent = DataScientistAgent(run_id=RUN_ID)

    result = agent.run(context={
        "run_id": RUN_ID,
        "dataset_path": FILE_PATH
    })

    print("\n================ RESULT =================")
    print(result)
    print("SCRIPT STARTED")
    


if __name__ == "__main__":
    main()
