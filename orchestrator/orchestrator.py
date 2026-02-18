from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import docker
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class ToolStatuses(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStage(Enum):
    MERGE = "merge"
    PARALLEL_INFERENCE = "parallel_inference"
    COMPARISON = "comparison"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineStatus:
    stage: PipelineStage = PipelineStage.MERGE

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

        self.run()

    def update_tool_status(self, tool_name: str, status: ToolStatuses):
        with self.status_lock:
            setattr(self.pipeline_status, tool_name, status)
            print(f"[{datetime.now()}] {tool_name}: {status.value}")
            # TODO: add http callback

    def update_pipeline_stage(self, stage: PipelineStage):
        with self.status_lock:
            self.pipeline_status.stage = stage
            print(f"[{datetime.now()}] Pipeline stage: {stage.value}")

    def run(self):
        try:
            if not self._run_tool("merger"):
                raise Exception("Merger failed")

            self.update_pipeline_stage(PipelineStage.PARALLEL_INFERENCE)
            if not self.run_parallel_inference():
                raise Exception("Inference failed")

            self.update_pipeline_stage(PipelineStage.COMPARISON)
            if not self._run_tool("comparison"):
                raise Exception("Comparison failed")

            self.update_pipeline_stage(PipelineStage.COMPLETED)

        except Exception as e:
            print(f"Pipeline failed with exception: {e}")
            self.update_pipeline_stage(PipelineStage.FAILED)

        self.completed_at = datetime.now()

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

        try:
            print(f"[Thread-{threading.current_thread().name}] Starting {tool_name}")
            module_name, class_name = tool_mapping[tool_name]
            module = __import__(module_name, fromlist=[class_name])
            tool_class = getattr(module, class_name)

            tool = tool_class(self.docker_client)
            return tool.run()

        except Exception as e:
            print(f"{tool_name} failed: {e}")
            return False

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
                    success = future.result()
                    status = ToolStatuses.COMPLETED if success else ToolStatuses.FAILED
                    self.update_tool_status(tool_name, status)
                except Exception as e:
                    print(f"{tool_name} failed with exception: {e}")
                    self.update_tool_status(tool_name, ToolStatuses.FAILED)
        return self.any_inference_succeeded()

    def any_inference_succeeded(self) -> bool:
        return any(
            [
                self.pipeline_status.iqtree == ToolStatuses.COMPLETED,
                self.pipeline_status.fastreer == ToolStatuses.COMPLETED,
                self.pipeline_status.mrbayes == ToolStatuses.COMPLETED,
            ]
        )
