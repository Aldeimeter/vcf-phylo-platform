from pathlib import Path
import hashlib
import shutil
import time
from config import Config


class Merger:
    def __init__(self, docker_client, logger, cache_dir="/cache/merger"):
        self.docker_client = docker_client
        self.logger = logger
        self.dataset_dir = "/dataset"
        self.image_name = f"{Config.get_registry_url()}/vcf-merger"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_dataset_cache(self):
        vcf_files = list(Path(self.dataset_dir).glob("*.vcf*"))
        file_hashes = []
        for vcf_file in vcf_files:
            file_hasher = hashlib.sha256()
            with open(vcf_file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    file_hasher.update(chunk)
            file_hashes.append(file_hasher.hexdigest())

        file_hashes.sort()

        final_hasher = hashlib.sha256()
        for file_hash in file_hashes:
            final_hasher.update(file_hash.encode())

        return final_hasher.hexdigest()

    def _get_cache_path(self, dataset_hash):
        return self.cache_dir / f"merged_{dataset_hash}"

    def _cache_exists(self, cache_path):
        return cache_path.exists() and any(cache_path.iterdir())

    def _save_to_cache(self, results_path, cache_path):
        cache_path.mkdir(parents=True, exist_ok=True)
        results_dir = Path(results_path)

        for result_file in results_dir.iterdir():
            if result_file.is_file():
                shutil.copy2(result_file, cache_path / result_file.name)

    def _restore_from_cache(self, cache_path, results_path):
        results_dir = Path(results_path)
        results_dir.mkdir(parents=True, exist_ok=True)

        for cached_file in cache_path.iterdir():
            if cached_file.is_file():
                shutil.copy2(cached_file, results_dir / cached_file.name)

    def run(self):
        try:
            dataset_files = list(Path(self.dataset_dir).glob("*.vcf*"))
            self.logger.info(
                f"Starting merger process with {len(dataset_files)} VCF files",
                extra={
                    "tool": "merger",
                    "pipeline_stage": "init",
                    "file_count": len(dataset_files),
                    "files": [f.name for f in dataset_files],
                },
            )

            self.logger.debug(
                "Calculating dataset cache key",
                extra={"tool": "merger", "pipeline_stage": "cache_check"},
            )

            cache_key = self._calculate_dataset_cache()
            cache_path = self._get_cache_path(cache_key)

            self.logger.debug(f"Cache key: {cache_key}, path: {cache_path}")

            if self._cache_exists(cache_path):
                self.logger.info(
                    f"Cache HIT! Using cached result: {cache_key[:12]}",
                    extra={
                        "tool": "merger",
                        "cache_key": cache_key[:12],
                        "cache_path": str(cache_path),
                        "pipeline_stage": "cache_hit",
                    },
                )
                self._restore_from_cache(cache_path, "/results/merger")
                return True

            self.logger.info(
                f"Cache MISS! Using merger to create cache: {cache_key[:12]}",
                extra={"tool": "merger", "cache_key": cache_key[:12]},
            )
            self.logger.info(
                f"Pulling Docker image: {self.image_name}",
                extra={
                    "tool": "merger", 
                    "pipeline_stage": "image_pull",
                    "image_name": self.image_name,
                    "registry": Config.get_registry_url()
                },
            )
            pull_start = time.time()
            try:
                image = self.docker_client.images.pull(self.image_name)
                pull_time = round(time.time() - pull_start, 2)
                self.logger.info(
                    f"Successfully pulled image {self.image_name} in {pull_time}s",
                    extra={
                        "tool": "merger", 
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
                        "tool": "merger",
                        "pipeline_stage": "image_pull_failed", 
                        "image_name": self.image_name,
                        "pull_time": pull_time,
                        "error": str(pull_error)
                    }
                )
                raise

            self.logger.info(
                "Starting merger container execution",
                extra={
                    "tool": "merger",
                    "pipeline_stage": "container_start",
                    "image_name": self.image_name,
                    "command": "sh /app/merge-vcf.sh",
                    "input_volume": self.dataset_dir,
                    "output_volume": "/results/merger"
                }
            )
            
            container_start = time.time()
            try:
                result = self.docker_client.containers.run(
                    image=self.image_name,
                    command=["sh", "/app/merge-vcf.sh"],
                    volumes={
                        self.dataset_dir: {"bind": "/data", "mode": "ro"},
                        "/results/merger": {"bind": "/results", "mode": "rw"},
                    },
                    remove=True,
                    detach=False,
                )
                container_time = round(time.time() - container_start, 2)
                self.logger.info(
                    f"Container execution completed in {container_time}s",
                    extra={
                        "tool": "merger",
                        "pipeline_stage": "container_complete",
                        "execution_time": container_time,
                        "exit_code": 0
                    }
                )
            except Exception as container_error:
                container_time = round(time.time() - container_start, 2)
                self.logger.error(
                    f"Container execution failed after {container_time}s: {str(container_error)}",
                    extra={
                        "tool": "merger",
                        "pipeline_stage": "container_failed",
                        "execution_time": container_time,
                        "error": str(container_error)
                    }
                )
                raise

            self._save_to_cache("/results/merger", cache_path)
            self.logger.info(
                f"Results cached for future use: {cache_key[:12]}",
                extra={"tool": "merger", "cache_key": cache_key[:12]},
            )

            return True
        except Exception as e:
            self.logger.error(
                f"Merge failed: {str(e)}", extra={"tool": "merger", "error": str(e)}
            )
            return False
