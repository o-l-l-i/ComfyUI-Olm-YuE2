"""Graph values retain upstream stage results and their execution provenance."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from .._vendor.yue2.pipeline import SymbolicPlan, SemanticResult


@dataclass(frozen=True)
class ModelSelection:
    model: str
    vae: str


@dataclass(frozen=True)
class PlanArtifact:
    value: "SymbolicPlan"
    info: dict


@dataclass(frozen=True)
class SemanticArtifact:
    value: "SemanticResult"
    info: dict


@dataclass(frozen=True)
class LatentArtifact:
    value: "np.ndarray"
    semantic: SemanticArtifact
    info: dict
