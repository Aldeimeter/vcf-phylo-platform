from dataclasses import dataclass, asdict
import time
from datetime import datetime
from pathlib import Path
from enum import Enum
import docker
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import requests
from logger import setup_logging


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
        self.logger = setup_logging(job_id)
        self.logger.info(
            "Orchestrator initialized",
            extra={"tool": "orchestrator", "pipeline_stage": "init"},
        )
        self.run()

    def update_tool_status(self, tool_name: str, status: ToolStatuses):
        with self.status_lock:
            setattr(self.pipeline_status, tool_name, status)
            self.logger.info(
                f"{tool_name} status updated",
                extra={
                    "tool": tool_name,
                    "status": status.value,
                    "pipeline_stage": "status_update",
                },
            )
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
            self.logger.error(
                f"Failed to update job status: {str(e)}",
                extra={"tool": "orchestrator", "error": str(e)},
            )

    def return_tools_timing(self):
        fastapi_url = os.environ.get("FASTAPI_URL", "http://fastapi:8000")

        payload = {"tools_timing": asdict(self.tools_timing)}
        try:
            response = requests.post(
                f"{fastapi_url}/jobs/{self.job_id}/timing", json=payload, timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Failed to update job timing: {str(e)}",
                extra={"tool": "orchestrator", "error": str(e)},
            )

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
            self.logger.error(
                f"Pipeline failed with exception: {str(e)}",
                extra={"tool": "orchestrator", "error": str(e)},
            )
            self.update_job_status(JobStatus.FAILED)
        finally:
            self._cleanup_merger_results()
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
            self.logger.error(
                f"Unknown tool: {tool_name}",
                extra={"tool": "orchestrator", "pipeline_stage": "tool_error"},
            )
            return False

        self.update_tool_status(tool_name, ToolStatuses.RUNNING)

        start_time = time.time()
        try:
            self.logger.info(
                f"Starting {tool_name}",
                extra={
                    "tool": tool_name,
                    "pipeline_stage": "tool_start",
                    "thread_name": threading.current_thread().name,
                },
            )
            module_name, class_name = tool_mapping[tool_name]
            module = __import__(module_name, fromlist=[class_name])
            tool_class = getattr(module, class_name)

            tool = tool_class(self.docker_client, self.logger)
            success = tool.run()

            if success:
                self.update_tool_status(tool_name, ToolStatuses.COMPLETED)
                self.logger.info(
                    f"{tool_name} completed successfully",
                    extra={"tool": tool_name, "pipeline_stage": "tool_complete"},
                )
            else:
                self.update_tool_status(tool_name, ToolStatuses.FAILED)
                self.logger.error(
                    f"{tool_name} failed",
                    extra={"tool": tool_name, "pipeline_stage": "tool_failed"},
                )

            return success

        except Exception as e:
            self.logger.error(
                f"{tool_name} failed with exception: {str(e)}",
                extra={
                    "tool": tool_name,
                    "pipeline_stage": "tool_error",
                    "error": str(e),
                },
            )
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
                    self.logger.error(
                        f"{tool_name} failed with exception: {e}",
                        extra={"tool": tool_name, "error": str(e)},
                    )

        return self.any_inference_succeeded()

    def any_inference_succeeded(self) -> bool:
        return any(
            [
                self.pipeline_status.iqtree == ToolStatuses.COMPLETED,
                self.pipeline_status.fastreer == ToolStatuses.COMPLETED,
                self.pipeline_status.mrbayes == ToolStatuses.COMPLETED,
            ]
        )

    def _cleanup_merger_results(self):
        import shutil

        merger_results_path = Path("/results/merger")

        if merger_results_path.exists():
            self.logger.info(
                "Cleaning up merger results (cached separately)",
                extra={"tool": "orchestrator", "pipeline_stage": "cleanup"},
            )
            shutil.rmtree(merger_results_path)
            self.logger.info(
                "Merger results cleaned up",
                extra={"tool": "orchestrator", "pipeline_stage": "cleanup"},
            )
