from fastapi import APIRouter

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/")
def get_datasets():
    return ["CRUK0052", "CRUK0055"]
