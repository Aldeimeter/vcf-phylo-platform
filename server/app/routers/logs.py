from fastapi import APIRouter, HTTPException
import requests
from datetime import datetime, timedelta
import os
from app.logger import logger
from app.services.job_storage import job_storage

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/{job_id}/history")
async def get_job_logs(job_id: str, limit: int = 1000, service: str | None = None):
    """Get historical logs for a job, optionally filtered by service"""
    job = await job_storage.get_job(job_id)
    start_time = job.created_at if job else None
    logs = await get_historical_logs(job_id, limit, start_time=start_time, service=service)
    return {"job_id": job_id, "logs": logs, "count": len(logs)}

async def get_historical_logs(job_id: str, limit: int = 1000, start_time: datetime | None = None, service: str | None = None):
    """Query Loki for historical logs"""
    loki_url = os.environ.get("LOKI_URL", "http://loki:3100")

    now = datetime.now()
    if start_time is None:
        start_time = now - timedelta(hours=1)
    start_ns = int(start_time.timestamp() * 1_000_000_000)
    end_ns = int(now.timestamp() * 1_000_000_000)

    if service:
        op = "=~" if "|" in service else "="
        query = f'{{job_id="{job_id}", service{op}"{service}"}}'
    else:
        query = f'{{job_id="{job_id}"}}'
    
    try:
        response = requests.get(
            f"{loki_url}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": start_ns,
                "end": end_ns,
                "limit": limit,
                "direction": "forward"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            logs = []
            
            for stream in data.get("data", {}).get("result", []):
                stream_labels = stream.get("stream", {})
                for timestamp_ns, message in stream.get("values", []):
                    # Convert nanosecond timestamp to ISO format for frontend
                    timestamp_seconds = int(timestamp_ns) / 1_000_000_000
                    timestamp_iso = datetime.fromtimestamp(timestamp_seconds).isoformat()
                    
                    logs.append({
                        "timestamp": timestamp_iso,
                        "timestamp_ns": timestamp_ns,
                        "message": message,
                        "labels": stream_labels,
                        "tool": stream_labels.get("tool", "orchestrator"),
                        "level": stream_labels.get("level", "info"),
                        "job_id": job_id
                    })
            
            # Sort by timestamp to ensure proper order
            logs.sort(key=lambda x: int(x["timestamp_ns"]))
            return logs
            
    except Exception as e:
        logger.error(f"Failed to query Loki for job {job_id}: {e}")
        return []
    
    return []
