from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum
from uuid import uuid4


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolStatuses(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStatus(BaseModel):
    merger: ToolStatuses = ToolStatuses.PENDING
    iqtree: ToolStatuses = ToolStatuses.PENDING
    fastreer: ToolStatuses = ToolStatuses.PENDING
    mrbayes: ToolStatuses = ToolStatuses.PENDING
    comparison: ToolStatuses = ToolStatuses.PENDING


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    dataset_id: str
    status: JobStatus = JobStatus.PENDING
    pipeline_status: PipelineStatus = Field(default_factory=PipelineStatus)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
