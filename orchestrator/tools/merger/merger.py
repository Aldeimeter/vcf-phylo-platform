from pathlib import Path
import hashlib
import shutil


class Merger:
    def __init__(self, docker_client, cache_dir="/cache/merger"):
        self.docker_client = docker_client
        self.dataset_dir = "/dataset"
        self.image_name = "registry:5000/vcf-merger"
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
            print("Looking for dataset cache")
            cache_key = self._calculate_dataset_cache()
            cache_path = self._get_cache_path(cache_key)

            if self._cache_exists(cache_path):
                print(f"Cache HIT! Using cached result: {cache_key[:12]}")
                self._restore_from_cache(cache_path, "/results/merger")
                return True

            print(f"Cache MISS! Using merger to create cache: {cache_key[:12]}")
            print("Pulling merger image")
            self.docker_client.images.pull(self.image_name)
            print("Image pulled")

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

            self._save_to_cache("/results/merger", cache_path)
            print(f"Results cached for future use: {cache_key[:12]}")

            return True
        except Exception as e:
            print(f"Merge failed: {e}")
            return False
