import os
import re
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.docker import client

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATASETS_PATH = "/app/data/datasets"

_upload_status: dict = {}  # name -> {"status": "processing"|"ready"|"failed", "error": str}


@router.get("/")
def get_datasets():
    try:
        entries = os.listdir(DATASETS_PATH)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Datasets directory not found: {DATASETS_PATH}")

    def vcf_count(folder):
        return sum(1 for f in os.listdir(folder) if f.endswith(".vcf") or f.endswith(".vcf.gz"))

    processing = {name for name, s in _upload_status.items() if s["status"] == "processing"}

    result = []
    for e in entries:
        if e in processing:
            continue
        path = os.path.join(DATASETS_PATH, e)
        if os.path.isdir(path):
            count = vcf_count(path)
            if count > 0:
                result.append({"name": e, "vcf_count": count})
    return result


def _validate_name(name: str):
    if not re.match(r"^[a-zA-Z0-9_\-]+$", name):
        raise HTTPException(
            status_code=400,
            detail="Dataset name may only contain letters, numbers, hyphens, and underscores",
        )
    if os.path.exists(os.path.join(DATASETS_PATH, name)):
        raise HTTPException(status_code=409, detail=f"Dataset '{name}' already exists")


@router.post("/{name}/validate-name")
def validate_dataset_name(name: str):
    _validate_name(name)
    return {"valid": True}


@router.get("/{name}/status")
def get_upload_status(name: str):
    if name not in _upload_status:
        raise HTTPException(status_code=404, detail=f"No upload status found for '{name}'")
    return _upload_status[name]


def _docker_error_message(e: Exception) -> str:
    if hasattr(e, "explanation") and e.explanation:
        return e.explanation.decode() if isinstance(e.explanation, bytes) else str(e.explanation)
    if hasattr(e, "stderr") and e.stderr:
        return e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
    return str(e)


def _run_compressor(name: str, dataset_path_host: str):
    try:
        client.containers.run(
            image="vcf-compressor:latest",
            command=["sh", "/app/compress.sh"],
            volumes={dataset_path_host: {"bind": "/data", "mode": "rw"}},
            remove=True,
            detach=False,
        )
        _upload_status[name] = {"status": "ready", "error": ""}
    except Exception as e:
        shutil.rmtree(os.path.join(DATASETS_PATH, name), ignore_errors=True)
        _upload_status[name] = {"status": "failed", "error": f"Compression failed: {_docker_error_message(e)}"}


@router.post("/{name}/upload", status_code=202)
async def upload_dataset(
    name: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    datasets_path_host = os.environ.get("DATASETS_PATH")
    if not datasets_path_host:
        raise HTTPException(status_code=500, detail="DATASETS_PATH environment variable is not set")

    _validate_name(name)

    for f in files:
        if not (f.filename.endswith(".vcf") or f.filename.endswith(".vcf.gz")):
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' is not a VCF file. Only .vcf and .vcf.gz are accepted.",
            )

    try:
        client.images.get("vcf-compressor:latest")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="vcf-compressor image not found. Run ./startup.sh to build required images.",
        )

    dataset_path_internal = os.path.join(DATASETS_PATH, name)
    dataset_path_host = str(Path(datasets_path_host) / name)

    os.makedirs(dataset_path_internal)
    try:
        has_plain_vcf = False
        for upload_file in files:
            dest = os.path.join(dataset_path_internal, upload_file.filename)
            with open(dest, "wb") as out:
                shutil.copyfileobj(upload_file.file, out)
            if upload_file.filename.endswith(".vcf"):
                has_plain_vcf = True
    except Exception as e:
        shutil.rmtree(dataset_path_internal, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to save files: {e}")

    if has_plain_vcf:
        _upload_status[name] = {"status": "processing", "error": ""}
        background_tasks.add_task(_run_compressor, name, dataset_path_host)
    else:
        _upload_status[name] = {"status": "ready", "error": ""}

    return JSONResponse(status_code=202, content={"name": name, "status": _upload_status[name]["status"]})
