import json
from pathlib import Path
from typing import Dict, List, Optional
from app.models.job import Job


class JobStorage:
    def __init__(self, storage_path="/app/data/jobs.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, Job] = self._load_jobs()

    def _load_jobs(self) -> Dict[str, Job]:
        if not self.storage_path.exists():
            return {}

        with open(self.storage_path, "r") as f:
            data = json.load(f)
            return {job_id: Job(**job_data) for job_id, job_data in data.items()}

    def _save_jobs(self):
        with open(self.storage_path, "w") as f:
            json.dump(
                {job_id: job.model_dump() for job_id, job in self._jobs.items()},
                f,
                indent=2,
                default=str,
            )

    def create_job(self, dataset_id: str) -> Job:
        job = Job(
            dataset_id=dataset_id,
        )
        self._jobs[job.id] = job
        self._save_jobs()
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **updates) -> Optional[Job]:
        if job_id not in self._jobs:
            return None

        for field, value in updates.items():
            setattr(self._jobs[job_id], field, value)

        self._save_jobs()
        return self._jobs[job_id]

    def list_jobs(self) -> List[Job]:
        return list(self._jobs.values())


job_storage = JobStorage()
