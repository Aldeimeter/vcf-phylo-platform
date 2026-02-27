import os
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATASETS_PATH = "/app/data/datasets"


@router.get("/")
def get_datasets():
    try:
        entries = os.listdir(DATASETS_PATH)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Datasets directory not found: {DATASETS_PATH}")

    def has_vcf(folder):
        return any(f.endswith(".vcf") or f.endswith(".vcf.gz") for f in os.listdir(folder))

    return [
        e for e in entries
        if os.path.isdir(path := os.path.join(DATASETS_PATH, e)) and has_vcf(path)
    ]
