class IqTree:
    def __init__(self, docker_client, logger):
        self.docker_client = docker_client
        self.logger = logger
        self.image_name = "registry:5000/iqtree3"

    def run(self):
        try:
            self.logger.info(
                f"Pulling {self.image_name} image",
                extra={"tool": "iqtree", "pipeline_stage": "image_pull"},
            )
            self.docker_client.images.pull(self.image_name)
            self.logger.info(
                "Image pulled",
                extra={"tool": "iqtree", "pipeline_stage": "image_pull"},
            )
            result = self.docker_client.containers.run(
                image=self.image_name,
                command=["sh", "/app/run-iqtree.sh"],
                volumes={
                    "/results/merger": {"bind": "/data", "mode": "ro"},
                    "/results/iqtree": {"bind": "/results", "mode": "rw"},
                },
                remove=True,
                detach=False,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"IQ-TREE failed: {str(e)}", extra={"tool": "iqtree", "error": str(e)}
            )
            return False
