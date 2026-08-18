from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..domain.models import KnowledgeGraphInput


Pair = tuple[str, str]
Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class GraphConfiguration:
    seed: int = 20260816
    dependency_regularization_eta: float = 0.15
    distance_min: float = 0.8
    distance_max: float = 7.0
    distance_gamma: float = 1.35
    relatedness_beta: float = 1.4
    radius_min: float = 1.1
    radius_max: float = 5.8
    radial_loss_lambda: float = 1.8
    repulsion_loss_lambda: float = 0.12
    repulsion_epsilon: float = 1.0
    repulsion_delta: float = 0.12
    learning_rate: float = 0.025
    optimization_steps: int = 3500
    gradient_clip: float = 8.0
    adam_beta1: float = 0.9
    adam_beta2: float = 0.999
    adam_epsilon: float = 1e-8
    hierarchy_sigma: float = 1.15
    hierarchy_threshold: float = 0.55
    density_grid_size: int = 11

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True)
class ScopeMetric:
    raw: float
    normalized: float


@dataclass(frozen=True)
class DepthMetric:
    raw: float
    normalized: float


@dataclass(frozen=True)
class ConnectivityMetric:
    raw: float
    normalized: float


@dataclass(frozen=True)
class LayoutPair:
    left: str
    right: str
    relatedness: float
    weight: float
    desired_distance: float
    actual_distance: float | None = None


@dataclass(frozen=True)
class LossComponents:
    relatedness: float
    radial: float
    repel: float
    weighted_radial: float
    weighted_repel: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return {
            "relatedness": self.relatedness,
            "radial": self.radial,
            "repel": self.repel,
            "weightedRadial": self.weighted_radial,
            "weightedRepel": self.weighted_repel,
            "total": self.total,
        }


@dataclass(frozen=True)
class NodeMetrics:
    scope: ScopeMetric
    dependency_depth: DepthMetric
    target_radius: float
    actual_radius: float
    connectivity: ConnectivityMetric


@dataclass(frozen=True)
class GraphDiagnostics:
    loss: LossComponents
    optimization_trace: tuple[dict[str, float], ...]
    depth_radius_pearson: float
    target_radius_mean_absolute_error: float
    minimum_pair_distance: float
    coordinate_finite: bool


@dataclass(frozen=True)
class GraphSnapshot:
    source: KnowledgeGraphInput
    configuration: GraphConfiguration
    transitive_membership: dict[Pair, float]
    hierarchy_members: dict[str, tuple[str, ...]]
    nodes: dict[str, NodeMetrics]
    coordinates: dict[str, Point3]
    layout_pairs: tuple[LayoutPair, ...]
    hierarchy_regions: dict[str, Any]
    diagnostics: GraphDiagnostics
