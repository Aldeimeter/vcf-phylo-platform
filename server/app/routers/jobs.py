import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from pydantic import BaseModel

from app.services.docker import client
from app.models.job import JobStatus, PipelineStatus, ToolsTiming, PipelineConfig
from app.services.job_storage import job_storage
from app.logger import logger
from pathlib import Path

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateRequestBody(BaseModel):
    dataset_id: str
    config: Optional[PipelineConfig] = None


@router.post("/create")
async def create_job(request_body: CreateRequestBody):
    try:
        client.images.get("orchestrator:latest")
    except Exception as e:
        logger.error(f"Orchestrator image not found: {e}")
        raise HTTPException(
            status_code=500,
            detail="Orchestrator image not found. Run ./startup.sh to build required images."
        )

    logger.info(f"Creating job for dataset '{request_body.dataset_id}'")
    job = await job_storage.create_job(request_body.dataset_id, pipeline_config=request_body.config)
    await job_storage.update_job(
        job.id, status=JobStatus.RUNNING, started_at=datetime.now()
    )
    job_id = str(job.id)
    logger.info(f"Job created: {job_id} for dataset '{request_body.dataset_id}'")
    dataset_path = str(Path(os.environ["DATASETS_PATH"], request_body.dataset_id))
    results_path = str(Path(os.environ["RESULTS_PATH"], job_id))

    orchestrator_env = {
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
        "CONSOLE_LOG_LEVEL": os.environ.get("CONSOLE_LOG_LEVEL", "INFO"),
        "LOKI_LOG_LEVEL": os.environ.get("LOKI_LOG_LEVEL", "INFO"),
        "FASTAPI_URL": os.environ.get("FASTAPI_URL", "http://fastapi:8000"),
        "LOKI_URL": os.environ.get("LOKI_URL", "http://loki:3100"),
        "REGISTRY_PORT": os.environ.get("REGISTRY_PORT", "5000"),
    }
    if request_body.config:
        cfg = request_body.config
        if cfg.iqtree_seed is not None:
            orchestrator_env["IQTREE_SEED"] = str(cfg.iqtree_seed)
        if cfg.mrbayes_seed is not None:
            orchestrator_env["MRBAYES_SEED"] = str(cfg.mrbayes_seed)
        if cfg.mrbayes_swapseed is not None:
            orchestrator_env["MRBAYES_SWAPSEED"] = str(cfg.mrbayes_swapseed)

    logger.debug(f"Spawning orchestrator container for job {job_id}")
    try:
        client.containers.run(
            image="orchestrator:latest",
            command=["python", "/app/main.py", job_id],
            volumes={
                dataset_path: {"bind": "/dataset", "mode": "ro"},
                results_path: {"bind": "/results", "mode": "rw"},
                os.environ["CACHE_PATH"]: {"bind": "/cache", "mode": "rw"},
            },
            environment=orchestrator_env,
            network=os.environ.get("DOCKER_NETWORK", "phylo-net"),
            remove=True,
            privileged=True,
            detach=True,
        )
    except Exception as e:
        logger.error(f"Failed to spawn orchestrator container for job {job_id}: {e}")
        await job_storage.update_job(job_id, status=JobStatus.FAILED, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")

    logger.info(f"Orchestrator container started for job {job_id}")
    return {"job_id": job_id}


class StatusUpdateBody(BaseModel):
    status: Optional[JobStatus] = None
    pipeline_status: Optional[PipelineStatus] = None
    error: Optional[str] = None


@router.post("/{job_id}/status")
async def update_job_status(job_id: str, update: StatusUpdateBody):
    job = await job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    updates = update.model_dump(exclude_unset=True)

    if updates.get("status"):
        if updates["status"] == JobStatus.RUNNING and job.status == JobStatus.PENDING:
            updates["started_at"] = datetime.now()
        elif updates["status"] in [JobStatus.COMPLETED, JobStatus.FAILED]:
            updates["completed_at"] = datetime.now()

    new_status = updates.get("status")
    if new_status == JobStatus.FAILED:
        logger.error(f"Job {job_id} failed: {updates.get('error', 'no error message')}")
    elif new_status == JobStatus.COMPLETED:
        logger.info(f"Job {job_id} completed")
    else:
        logger.debug(f"Job {job_id} status update: {updates}")
    await job_storage.update_job(job_id, **updates)
    return {"success": True}


@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    job = await job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return job


@router.get("/{job_id}/results")
async def get_job_results(job_id: str):
    job = await job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    results_path = Path(os.environ["STATIC_PATH"], job_id)
    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Results for job '{job_id}' not found — the job may still be running or may have failed")

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
async def list_jobs(
    dataset_id: Optional[str] = Query(None, description="Filter jobs by dataset ID"),
    sort_order: Optional[str] = Query(
        "desc", description="Sort order: 'asc' for ascending, 'desc' for descending"
    ),
):
    jobs = await job_storage.list_jobs()

    if dataset_id:
        jobs = [job for job in jobs if job.dataset_id == dataset_id]

    reverse_order = sort_order.lower() != "asc"
    jobs.sort(key=lambda job: job.created_at, reverse=reverse_order)

    return {"jobs": jobs}


class SaveJobConfigRequest(BaseModel):
    pipeline_config: PipelineConfig


@router.post("/{job_id}/config")
async def save_job_config(request_body: SaveJobConfigRequest, job_id: str):
    job = await job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    await job_storage.update_job(job.id, pipeline_config=request_body.pipeline_config)
    return {"success": True}


class CreateJobTimingRequest(BaseModel):
    tools_timing: ToolsTiming


@router.post("/{job_id}/timing")
async def create_job_timing(request_body: CreateJobTimingRequest, job_id: str):
    job = await job_storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    await job_storage.update_job(job.id, tools_timing=request_body.tools_timing)

    return {"success": True}
