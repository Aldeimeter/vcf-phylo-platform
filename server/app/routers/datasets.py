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

    def vcf_count(folder):
        return sum(1 for f in os.listdir(folder) if f.endswith(".vcf") or f.endswith(".vcf.gz"))

    result = []
    for e in entries:
        path = os.path.join(DATASETS_PATH, e)
        if os.path.isdir(path):
            count = vcf_count(path)
            if count > 0:
                result.append({"name": e, "vcf_count": count})
    return result
