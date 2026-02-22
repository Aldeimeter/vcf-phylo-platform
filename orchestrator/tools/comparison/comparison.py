class Comparison:
    def __init__(self, docker_client, logger):
        self.docker_client = docker_client
        self.logger = logger
        self.image_name = "registry:5000/comparison"

    def run(self):
        try:
            self.logger.info(
                f"Pulling {self.image_name} image",
                extra={"tool": "comparison", "pipeline_stage": "image_pull"},
            )
            self.docker_client.images.pull(self.image_name)
            self.logger.info(
                "Image pulled",
                extra={"tool": "comparison", "pipeline_stage": "image_pull"},
            )

            volumes = {"/results/comparison": {"bind": "/results", "mode": "rw"}}
            for tool in ["iqtree", "fastreer", "mrbayes"]:
                volumes[f"/results/{tool}"] = {"bind": f"/data/{tool}", "mode": "ro"}

            result = self.docker_client.containers.run(
                image=self.image_name,
                command=["uv", "run", "python", "main.py"],
                volumes=volumes,
                remove=True,
                detach=False,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Comparison failed: {str(e)}", extra={"tool": "comparison", "error": str(e)}
            )
            return False
