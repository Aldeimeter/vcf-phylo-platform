import sys
from orchestrator import Orchestrator

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <dataset_id>")
        sys.exit(1)

    job_id = sys.argv[1]
    orchestrator = Orchestrator(job_id)
