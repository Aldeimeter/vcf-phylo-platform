import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from typing import Optional

from pydantic import BaseModel

from app.services.docker import client
from app.models.job import JobStatus, PipelineStatus
from app.services.job_storage import job_storage
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


class StatusUpdateBody(BaseModel):
    status: Optional[JobStatus] = None
    pipeline_status: Optional[PipelineStatus] = None
    error: Optional[str] = None


@router.post("/{job_id}/status")
def update_job_status(job_id: str, update: StatusUpdateBody):
    job = job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    updates = update.model_dump(exclude_unset=True)

    if updates.get("status"):
        if updates["status"] == JobStatus.RUNNING and job.status == JobStatus.PENDING:
            updates["started_at"] = datetime.now()
        elif updates["status"] in [JobStatus.COMPLETED, JobStatus.FAILED]:
            updates["completed_at"] = datetime.now()

    job_storage.update_job(job_id, **updates)
    return {"success": True}


@router.get("/{job_id}/status")
def get_job_status(job_id: str):
    job = job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job
