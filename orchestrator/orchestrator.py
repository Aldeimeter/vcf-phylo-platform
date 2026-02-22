from dataclasses import dataclass, asdict
import time
from datetime import datetime
from enum import Enum
import docker
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import requests


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolStatuses(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolsTiming:
    merger: float = None
    iqtree: float = None
    fastreer: float = None
    mrbayes: float = None
    comparison: float = None


@dataclass
class PipelineStatus:
    merger: ToolStatuses = ToolStatuses.PENDING
    iqtree: ToolStatuses = ToolStatuses.PENDING
    fastreer: ToolStatuses = ToolStatuses.PENDING
    mrbayes: ToolStatuses = ToolStatuses.PENDING
    comparison: ToolStatuses = ToolStatuses.PENDING


class Orchestrator:
    def __init__(self, job_id):
        self.docker_client = docker.from_env()
        self.job_id = job_id
        self.started_at = datetime.now()
        self.completed_at = None

        self.pipeline_status = PipelineStatus()
        self.status_lock = threading.Lock()
        self.tools_timing = ToolsTiming()

        self.run()

    def update_tool_status(self, tool_name: str, status: ToolStatuses):
        with self.status_lock:
            setattr(self.pipeline_status, tool_name, status)
            print(f"[{datetime.now()}] {tool_name}: {status.value}")
            self.update_job_status()

    def update_job_status(self, status: JobStatus = None, error: str = None):
        fastapi_url = os.environ.get("FASTAPI_URL", "http://fastapi:8000")
        payload = {}

        if status:
            payload["status"] = status
        payload["pipeline_status"] = {
            field.name: getattr(self.pipeline_status, field.name).value
            for field in self.pipeline_status.__dataclass_fields__.values()
        }

        if error:
            payload["error"] = error
        try:
            response = requests.post(
                f"{fastapi_url}/jobs/{self.job_id}/status",
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to update job status: {e}")

    def return_tools_timing(self):
        fastapi_url = os.environ.get("FASTAPI_URL", "http://fastapi:8000")

        payload = {"tools_timing": asdict(self.tools_timing)}
        try:
            response = requests.post(
                f"{fastapi_url}/jobs/{self.job_id}/timing", json=payload, timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to update job timing: {e}")

    def run(self):
        try:
            self.update_job_status(JobStatus.RUNNING)
            if not self._run_tool("merger"):
                raise Exception("Merger failed")

            if not self.run_parallel_inference():
                raise Exception("Inference failed")

            if not self._run_tool("comparison"):
                raise Exception("Comparison failed")

            self.update_job_status(JobStatus.COMPLETED)
        except Exception as e:
            print(f"Pipeline failed with exception: {e}")
            self.update_job_status(JobStatus.FAILED)
        finally:
            self.return_tools_timing()

    def _run_tool(self, tool_name: str):
        tool_mapping = {
            "iqtree": ("tools.iqtree", "IqTree"),
            "fastreer": ("tools.fastreer", "FastreeR"),
            "mrbayes": ("tools.mrbayes", "MrBayes"),
            "comparison": ("tools.comparison", "Comparison"),
            "merger": ("tools.merger", "Merger"),
        }

        if tool_name not in tool_mapping:
            print(f"Unknown tool: {tool_name}")
            return False

        self.update_tool_status(tool_name, ToolStatuses.RUNNING)

        start_time = time.time()
        try:
            print(f"[Thread-{threading.current_thread().name}] Starting {tool_name}")
            module_name, class_name = tool_mapping[tool_name]
            module = __import__(module_name, fromlist=[class_name])
            tool_class = getattr(module, class_name)

            tool = tool_class(self.docker_client)
            success = tool.run()

            if success:
                self.update_tool_status(tool_name, ToolStatuses.COMPLETED)
            else:
                self.update_tool_status(tool_name, ToolStatuses.FAILED)

            return success

        except Exception as e:
            print(f"{tool_name} failed: {e}")
            self.update_tool_status(tool_name, ToolStatuses.FAILED)
            return False
        finally:
            end_time = time.time()
            execution_time = round(end_time - start_time, 1)
            setattr(self.tools_timing, tool_name, execution_time)

    def run_parallel_inference(self) -> bool:
        inference_tools = ["iqtree", "fastreer", "mrbayes"]

        with ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="inference"
        ) as executor:
            future_to_tool = {
                executor.submit(self._run_tool, tool_name): tool_name
                for tool_name in inference_tools
            }

            for future in as_completed(future_to_tool):
                tool_name = future_to_tool[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"{tool_name} failed with exception: {e}")

        return self.any_inference_succeeded()

    def any_inference_succeeded(self) -> bool:
        return any(
            [
                self.pipeline_status.iqtree == ToolStatuses.COMPLETED,
                self.pipeline_status.fastreer == ToolStatuses.COMPLETED,
                self.pipeline_status.mrbayes == ToolStatuses.COMPLETED,
            ]
        )
