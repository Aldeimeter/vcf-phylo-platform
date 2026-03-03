import os
from dataclasses import dataclass
from typing import Optional


class Config:
    @staticmethod
    def get_registry_url():
        registry_port = os.environ.get("REGISTRY_PORT", "5000")
        return f"registry:{registry_port}"


IQTREE_SEED_DEFAULT = 12345
MRBAYES_SEED_DEFAULT = 12345
MRBAYES_SWAPSEED_DEFAULT = 54321


@dataclass
class JobConfig:
    iqtree_seed: int = IQTREE_SEED_DEFAULT
    mrbayes_seed: int = MRBAYES_SEED_DEFAULT
    mrbayes_swapseed: int = MRBAYES_SWAPSEED_DEFAULT

    @staticmethod
    def from_env() -> "JobConfig":
        def parse_int(key, default):
            val = os.environ.get(key)
            return int(val) if val else default

        return JobConfig(
            iqtree_seed=parse_int("IQTREE_SEED", IQTREE_SEED_DEFAULT),
            mrbayes_seed=parse_int("MRBAYES_SEED", MRBAYES_SEED_DEFAULT),
            mrbayes_swapseed=parse_int("MRBAYES_SWAPSEED", MRBAYES_SWAPSEED_DEFAULT),
        )

    def to_dict(self) -> dict:
        return {
            "iqtree_seed": self.iqtree_seed,
            "mrbayes_seed": self.mrbayes_seed,
            "mrbayes_swapseed": self.mrbayes_swapseed,
        }