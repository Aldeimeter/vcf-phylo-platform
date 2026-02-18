class MrBayes:
    def __init__(self, docker_client):
        self.docker_client = docker_client
        self.image_name = "registry:5000/mrbayes"

    def run(self):
        try:
            print(f"Pulling {self.image_name} image")
            self.docker_client.images.pull(self.image_name)
            print("Image pulled")
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
            print(f"IQ-TREE failed: {e}")
            return False
