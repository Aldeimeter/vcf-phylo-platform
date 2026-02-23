import time


class IqTree:
    def __init__(self, docker_client, logger):
        self.docker_client = docker_client
        self.logger = logger
        self.image_name = "registry:5000/iqtree3"

    def run(self):
        try:
            self.logger.info(
                f"Pulling Docker image: {self.image_name}",
                extra={
                    "tool": "iqtree", 
                    "pipeline_stage": "image_pull",
                    "image_name": self.image_name,
                    "registry": "registry:5000"
                },
            )
            pull_start = time.time()
            try:
                image = self.docker_client.images.pull(self.image_name)
                pull_time = round(time.time() - pull_start, 2)
                self.logger.info(
                    f"Successfully pulled image {self.image_name} in {pull_time}s",
                    extra={
                        "tool": "iqtree", 
                        "pipeline_stage": "image_pull_complete",
                        "image_name": self.image_name,
                        "image_id": image.id[:12],
                        "pull_time": pull_time,
                        "image_size": getattr(image.attrs, 'Size', 'unknown') if hasattr(image, 'attrs') else 'unknown'
                    }
                )
            except Exception as pull_error:
                pull_time = round(time.time() - pull_start, 2)
                self.logger.error(
                    f"Failed to pull image {self.image_name} after {pull_time}s: {str(pull_error)}",
                    extra={
                        "tool": "iqtree",
                        "pipeline_stage": "image_pull_failed", 
                        "image_name": self.image_name,
                        "pull_time": pull_time,
                        "error": str(pull_error)
                    }
                )
                raise

            self.logger.info(
                "Starting IQ-TREE container execution",
                extra={
                    "tool": "iqtree",
                    "pipeline_stage": "container_start",
                    "image_name": self.image_name,
                    "command": "sh /app/run-iqtree.sh",
                    "input_volume": "/results/merger",
                    "output_volume": "/results/iqtree"
                }
            )
            
            container_start = time.time()
            try:
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
                container_time = round(time.time() - container_start, 2)
                self.logger.info(
                    f"IQ-TREE container execution completed in {container_time}s",
                    extra={
                        "tool": "iqtree",
                        "pipeline_stage": "container_complete",
                        "execution_time": container_time,
                        "exit_code": 0
                    }
                )
            except Exception as container_error:
                container_time = round(time.time() - container_start, 2)
                self.logger.error(
                    f"IQ-TREE container execution failed after {container_time}s: {str(container_error)}",
                    extra={
                        "tool": "iqtree",
                        "pipeline_stage": "container_failed",
                        "execution_time": container_time,
                        "error": str(container_error)
                    }
                )
                raise
                
            return True
        except Exception as e:
            self.logger.error(
                f"IQ-TREE failed: {str(e)}", extra={"tool": "iqtree", "error": str(e)}
            )
            return False
