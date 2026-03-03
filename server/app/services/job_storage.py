import json
from pathlib import Path
from typing import Dict, List, Optional
from app.models.job import Job, JobStatus, PipelineConfig
from beanie import PydanticObjectId
from bson.errors import InvalidId


class JobStorage:
    async def create_job(self, dataset_id: str, pipeline_config: Optional[PipelineConfig] = None) -> Job:
        job = Job(dataset_id=dataset_id, pipeline_config=pipeline_config)
        await job.insert()
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        try:
            return await Job.get(job_id)
        except (InvalidId, ValueError, TypeError):
            return None

    async def update_job(self, job_id: str, **updates) -> Optional[Job]:
        try:
            job = await Job.get(job_id)
            if not job:
                return None

            for field, value in updates.items():
                if hasattr(job, field):
                    setattr(job, field, value)

            await job.save()
            return job
        except (InvalidId, ValueError, TypeError):
            return None

    async def list_jobs(
        self, dataset_id: Optional[str] = None, sort_desc: bool = True
    ) -> List[Job]:
        query = Job.find_all()

        if dataset_id:
            query = Job.find_all(Job.dataset_id == dataset_id)

        if sort_desc:
            query = query.sort(-Job.created_at)
        else:
            query = query.sort(Job.created_at)

        return await query.to_list()


job_storage = JobStorage()
