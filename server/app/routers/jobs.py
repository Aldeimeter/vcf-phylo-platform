import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from pydantic import BaseModel

from app.services.docker import client
from app.models.job import JobStatus, PipelineStatus, ToolsTiming
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


@router.get("/{job_id}/results")
def get_job_results(job_id: str):
    job = job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    results_path = Path(os.environ["STATIC_PATH"], job_id)
    if not results_path:
        raise HTTPException(status_code=404, detail="Results directory not found")

    nwk_files = []
    results_json = None

    for tool_dir in results_path.iterdir():
        if tool_dir.is_dir():
            for nwk_file in tool_dir.glob("*.nwk"):
                nwk_files.append(
                    {
                        "tool": tool_dir.name,
                        "filename": nwk_file.name,
                        "url": f"/static/results/{job_id}/{tool_dir.name}/{nwk_file.name}",
                    }
                )
            json_file = tool_dir / "results.json"
            if json_file.exists():
                results_json = {
                    "tool": tool_dir.name,
                    "filename": "results.json",
                    "url": f"/static/results/{job_id}/{tool_dir.name}/results.json",
                }
    return {"job_id": job_id, "nwk_files": nwk_files, "results_json": results_json}


@router.get("")
def list_jobs(
    dataset_id: Optional[str] = Query(None, description="Filter jobs by dataset ID"),
    sort_order: Optional[str] = Query(
        "desc", description="Sort order: 'asc' for ascending, 'desc' for descending"
    ),
):
    jobs = job_storage.list_jobs()

    if dataset_id:
        jobs = [job for job in jobs if job.dataset_id == dataset_id]

    reverse_order = sort_order.lower() != "asc"
    jobs.sort(key=lambda job: job.created_at, reverse=reverse_order)

    return {"jobs": jobs}


class CreateJobTimingRequest(BaseModel):
    tools_timing: ToolsTiming


@router.post("/{job_id}/timing")
def create_job_timing(request_body: CreateJobTimingRequest, job_id: str):
    job = job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_storage.update_job(job.id, tools_timing=request_body.tools_timing)

    return {"success": True}
