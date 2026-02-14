class VCFMerger:
    def __init__(self, docker_client):
        self.docker_client = docker_client
        self.image_name = "registry:5000/vcf-merger"

    def merge(self):
        try:
            print("Pulling merger image")
            self.docker_client.images.pull(self.image_name)
            print("Image pulled")

            result = self.docker_client.containers.run(
                image=self.image_name,
                command=["sh", "/app/merge-vcf.sh"],
                volumes={
                    "/dataset": {"bind": "/data", "mode": "ro"},
                    "/results": {"bind": "/results", "mode": "rw"},
                },
                remove=True,
                detach=False,
            )
            return True
        except Exception as e:
            print(f"Merge failed: {e}")
            return False
