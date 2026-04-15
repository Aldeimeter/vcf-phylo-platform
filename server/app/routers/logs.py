from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import requests
import asyncio
import json
from typing import Dict, List
from datetime import datetime, timedelta
import os
from app.logger import logger

router = APIRouter(prefix="/logs", tags=["logs"])

# Store active WebSocket connections per job
active_connections: Dict[str, List[WebSocket]] = {}

# Store last seen timestamps per job to avoid duplicates
last_seen_timestamps: Dict[str, int] = {}

@router.websocket("/{job_id}/stream")
async def websocket_logs(websocket: WebSocket, job_id: str):
    await websocket.accept()
    
    # Add connection to job's connection list
    if job_id not in active_connections:
        active_connections[job_id] = []
    active_connections[job_id].append(websocket)
    
    try:
        # Send historical logs first (last 5 minutes)
        historical_logs = await get_historical_logs(job_id, limit=500)
        for log in historical_logs:
            await websocket.send_text(json.dumps(log))
            
        # Update last seen timestamp from historical logs
        if historical_logs:
            last_timestamp = max([int(log["timestamp_ns"]) for log in historical_logs])
            last_seen_timestamps[job_id] = last_timestamp
        
        # Keep connection alive and stream new logs
        while True:
            new_logs = await get_recent_logs(job_id)
            for log in new_logs:
                # Send to all active connections for this job
                for connection in active_connections[job_id][:]:  # Copy list to avoid modification during iteration
                    try:
                        await connection.send_text(json.dumps(log))
                    except:
                        # Remove dead connections
                        active_connections[job_id].remove(connection)
                        
            await asyncio.sleep(1)  # Poll every second
            
    except WebSocketDisconnect:
        pass
    finally:
        # Remove connection
        if job_id in active_connections and websocket in active_connections[job_id]:
            active_connections[job_id].remove(websocket)
            if not active_connections[job_id]:
                del active_connections[job_id]
                # Clean up last seen timestamp when no more connections
                if job_id in last_seen_timestamps:
                    del last_seen_timestamps[job_id]

@router.get("/{job_id}/history")
async def get_job_logs(job_id: str, limit: int = 1000):
    """Get historical logs for a job"""
    logs = await get_historical_logs(job_id, limit)
    return {"job_id": job_id, "logs": logs, "count": len(logs)}

async def get_historical_logs(job_id: str, limit: int = 1000, minutes_back: int = 60):
    """Query Loki for historical logs"""
    loki_url = os.environ.get("LOKI_URL", "http://loki:3100")
    
    # Calculate time range (last X minutes)
    now = datetime.now()
    since_time = now - timedelta(minutes=minutes_back)
    
    # Convert to nanoseconds (Loki format)
    start_ns = int(since_time.timestamp() * 1_000_000_000)
    end_ns = int(now.timestamp() * 1_000_000_000)
    
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

async def get_recent_logs(job_id: str):
    """Get logs since last check, avoiding duplicates"""
    loki_url = os.environ.get("LOKI_URL", "http://loki:3100")
    
    # Get last seen timestamp for this job
    last_seen = last_seen_timestamps.get(job_id, 0)
    
    # Calculate time range
    now = datetime.now()
    if last_seen > 0:
        # Query from last seen timestamp + 1 nanosecond to avoid duplicates
        start_ns = last_seen + 1
    else:
        # First query, get logs from last 30 seconds
        since_time = now - timedelta(seconds=30)
        start_ns = int(since_time.timestamp() * 1_000_000_000)
    
    end_ns = int(now.timestamp() * 1_000_000_000)
    
    query = f'{{job_id="{job_id}"}}'
    
    try:
        response = requests.get(
            f"{loki_url}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": start_ns,
                "end": end_ns,
                "direction": "forward",
                "limit": 100
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            logs = []
            max_timestamp = last_seen
            
            for stream in data.get("data", {}).get("result", []):
                stream_labels = stream.get("stream", {})
                for timestamp_ns, message in stream.get("values", []):
                    timestamp_int = int(timestamp_ns)
                    max_timestamp = max(max_timestamp, timestamp_int)
                    
                    # Convert to ISO format for frontend
                    timestamp_seconds = timestamp_int / 1_000_000_000
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
            
            # Update last seen timestamp for this job (only if we got new logs)
            if max_timestamp > last_seen:
                last_seen_timestamps[job_id] = max_timestamp
            
            # Sort by timestamp
            logs.sort(key=lambda x: int(x["timestamp_ns"]))
            return logs
            
    except Exception as e:
        logger.error(f"Failed to query recent logs from Loki for job {job_id}: {e}")
        return []
    
    return []

@router.get("/{job_id}/status")
async def get_log_status(job_id: str):
    """Get logging status for a job"""
    return {
        "job_id": job_id,
        "active_connections": len(active_connections.get(job_id, [])),
        "last_seen_timestamp": last_seen_timestamps.get(job_id),
        "loki_url": os.environ.get("LOKI_URL", "http://loki:3100")
    }
