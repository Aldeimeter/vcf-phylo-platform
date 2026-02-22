class MrBayes:
    def __init__(self, docker_client, logger):
        self.docker_client = docker_client
        self.logger = logger
        self.image_name = "registry:5000/mrbayes"

    def run(self):
        try:
            self.logger.info(
                f"Pulling {self.image_name} image",
                extra={"tool": "mrbayes", "pipeline_stage": "image_pull"},
            )
            self.docker_client.images.pull(self.image_name)
            self.logger.info(
                "Image pulled",
                extra={"tool": "mrbayes", "pipeline_stage": "image_pull"},
            )
            result = self.docker_client.containers.run(
                image=self.image_name,
                command=["sh", "/app/run-mrbayes.sh"],
                volumes={
                    "/results/merger": {"bind": "/data", "mode": "ro"},
                    "/results/mrbayes": {"bind": "/results", "mode": "rw"},
                },
                remove=True,
                detach=False,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"MrBayes failed: {str(e)}", extra={"tool": "mrbayes", "error": str(e)}
            )
            return False
