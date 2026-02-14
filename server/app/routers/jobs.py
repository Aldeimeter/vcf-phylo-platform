import os
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.docker import client
from pathlib import Path

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateRequestBody(BaseModel):
    dataset_id: str


@router.post("/create")
def create_job(request_body: CreateRequestBody):
    job_id = str(uuid4())
    dataset_path = str(Path(os.environ["DATASETS_PATH"], request_body.dataset_id))
    results_path = str(Path(os.environ["RESULTS_PATH"], job_id))
    container = client.containers.run(
        image="orchestrator:latest",
        command=["python", "/app/main.py", job_id],
        volumes={
            dataset_path: {"bind": "/dataset", "mode": "ro"},
            results_path: {"bind": "/results", "mode": "rw"},
        },
        network="project_registry-net",
        remove=True,
        privileged=True,
        detach=False,
    )
    output = container.decode("utf-8")
    return {"output": output}
