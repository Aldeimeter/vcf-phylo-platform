from beanie import Document
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


class ToolsTiming(BaseModel):
    merger: Optional[float] = None
    iqtree: Optional[float] = None
    fastreer: Optional[float] = None
    mrbayes: Optional[float] = None
    comparison: Optional[float] = None


class PipelineStatus(BaseModel):
    merger: ToolStatuses = ToolStatuses.PENDING
    iqtree: ToolStatuses = ToolStatuses.PENDING
    fastreer: ToolStatuses = ToolStatuses.PENDING
    mrbayes: ToolStatuses = ToolStatuses.PENDING
    comparison: ToolStatuses = ToolStatuses.PENDING


class PipelineConfig(BaseModel):
    iqtree_seed: int = 12345
    mrbayes_seed: int = 12345
    mrbayes_swapseed: int = 54321


class Job(Document):
    # id: str = Field(default_factory=lambda: str(uuid4()))
    dataset_id: str
    status: JobStatus = JobStatus.PENDING
    pipeline_status: PipelineStatus = Field(default_factory=PipelineStatus)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    tools_timing: Optional[ToolsTiming] = None
    pipeline_config: Optional[PipelineConfig] = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        if "id" in data:
            data["id"] = str(data["id"])
        return data

    class Settings:
        name = "jobs"
        indexes = ["dataset_id", "status", "created_at"]
