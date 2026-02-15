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
        # TODO: Better to have statuses as Merge : Complete | Failed | Running | Pending
        self.step = step
        # TODO: post http callback to update job status

    def run(self):
        self.merge()
        # self.iqtree()
        self.fastreer()

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

    def iqtree(self):
        print("Running iqtree")
        self.updateStatus(PipelineStatus.IQTREE)

        from tools.iqtree import IqTree

        iqtree = IqTree(self.docker_client)

        success = iqtree.build()
        if success:
            print("Iqtree tree built successfully")
            self.updateStatus(PipelineStatus.IQTREE)
        else:
            print("Error occured")
            self.updateStatus(PipelineStatus.FAILED)

    def fastreer(self):
        print("Running fastreer")
        self.updateStatus(PipelineStatus.FASTREER)

        from tools.fastreer import FastreeR

        fastreer = FastreeR(self.docker_client)

        success = fastreer.build()
        if success:
            print("Iqtree tree built successfully")
            self.updateStatus(PipelineStatus.IQTREE)
        else:
            print("Error occured")
            self.updateStatus(PipelineStatus.FAILED)
