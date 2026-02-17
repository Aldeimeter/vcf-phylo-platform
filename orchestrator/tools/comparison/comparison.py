class Comparison:
    def __init__(self, docker_client):
        self.docker_client = docker_client
        self.image_name = "registry:5000/comparison"

    def run(self):
        try:
            print(f"Pulling {self.image_name} image")
            self.docker_client.images.pull(self.image_name)
            print("Image pulled")

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
            print(f"Comparison failed: {e}")
            return False
