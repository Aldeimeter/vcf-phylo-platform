from datetime import datetime
from enum import Enum
import docker


class PipelineStatus(Enum):
    MERGE = "merge"
    IQTREE = "iqtree"
    FASTREER = "fastreer"
    MRBAYES = "mrbayes"
    COMPARISON = "comparison"
    FAILED = "failed"
    COMPLETED = "completed"


class Orchestrator:
    def __init__(self, job_id):
        self.docker_client = docker.from_env()
        self.job_id = job_id
        self.started_at = datetime.now()
        self.completed_at = None
        self.run()

    def updateStatus(self, step: PipelineStatus):
        self.step = step
        # TODO: post http callback to update job status

    def run(self):
        self.merge()

    def merge(self):
        print("Running merger")
        self.updateStatus(PipelineStatus.MERGE)

        from tools.merger import VCFMerger

        merger = VCFMerger(self.docker_client)

        success = merger.merge()
        if success:
            print("VCF files merged successfully")
            self.updateStatus(PipelineStatus.IQTREE)
        else:
            print("Error occured")
            self.updateStatus(PipelineStatus.FAILED)
