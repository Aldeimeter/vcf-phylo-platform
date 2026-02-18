import os
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.docker import client
from app.services.job_storage import job_storage, JobStatus
from pathlib import Path

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateRequestBody(BaseModel):
    dataset_id: str


@router.post("/create")
def create_job(request_body: CreateRequestBody):
    job = job_storage.create_job(request_body.dataset_id)
    job_storage.update_job(job.id, status=JobStatus.RUNNING, started_at=datetime.now())
    dataset_path = str(Path(os.environ["DATASETS_PATH"], request_body.dataset_id))
    results_path = str(Path(os.environ["RESULTS_PATH"], job.id))
    client.containers.run(
        image="orchestrator:latest",
        command=["python", "/app/main.py", job.id],
        volumes={
            dataset_path: {"bind": "/dataset", "mode": "ro"},
            results_path: {"bind": "/results", "mode": "rw"},
        },
        network="project_registry-net",
        remove=True,
        privileged=True,
        detach=True,
    )
    return {"job_id": job.id}
