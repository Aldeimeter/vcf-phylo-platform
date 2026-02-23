import os


class Config:
    @staticmethod
    def get_registry_url():
        registry_port = os.environ.get("REGISTRY_PORT", "5000")
        return f"registry:{registry_port}"