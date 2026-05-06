from __future__ import annotations

from dataclasses import dataclass
import math

from .biomes import classify_biome, preferred_road_model_for_biome
from .config import CityGenConfig
from .geometry import BBox, Rect, stable_rng


@dataclass(frozen=True)
class InfiniteLinePrimitive:
    point_x: float
    point_z: float
    dir_x: float
    dir_z: float

    def distance_to(self, x: float, z: float) -> float:
        return abs((x - self.point_x) * -self.dir_z + (z - self.point_z) * self.dir_x)


@dataclass(frozen=True)
class SegmentPrimitive:
    x0: float
    z0: float
    x1: float
    z1: float

    def distance_to(self, x: float, z: float) -> float:
        return _distance_to_segment(x, z, self.x0, self.z0, self.x1, self.z1)


@dataclass(frozen=True)
class RingPrimitive:
    center_x: float
    center_z: float
    radius_m: float

    def distance_to(self, x: float, z: float) -> float:
        return abs(math.hypot(x - self.center_x, z - self.center_z) - self.radius_m)


@dataclass(frozen=True)
class PolylinePrimitive:
    points: tuple[tuple[float, float], ...]

    def distance_to(self, x: float, z: float) -> float:
        if len(self.points) < 2:
            return math.inf
        return min(
            _distance_to_segment(x, z, x0, z0, x1, z1)
            for (x0, z0), (x1, z1) in zip(self.points, self.points[1:])
        )


RoadPrimitive = InfiniteLinePrimitive | SegmentPrimitive | RingPrimitive | PolylinePrimitive


@dataclass(frozen=True)
class RoadNetwork:
    model: str
    primitives: tuple[RoadPrimitive, ...]
    effective_models: tuple[str, ...]

    def nearest_distance(self, x: float, z: float) -> float:
        if not self.primitives:
            return math.inf
        return min(primitive.distance_to(x, z) for primitive in self.primitives)

    def surface_kind(self, config: CityGenConfig, x: float, z: float) -> str:
        distance = self.nearest_distance(x, z)
        road_half = config.roads.width_m * 0.5
        sidewalk_half = road_half + config.roads.sidewalk_width_m
        if distance <= road_half:
            return "road"
        if distance <= sidewalk_half:
            return "sidewalk"
        return "ground"

    def road_model_at(self, _config: CityGenConfig, _x: float, _z: float) -> str:
        return self.model

    def rect_is_clear(self, rect: Rect, clearance_m: float) -> bool:
        x_values = (rect.min_x, rect.center_x, rect.max_x)
        z_values = (rect.min_z, rect.center_z, rect.max_z)
        for x in x_values:
            for z in z_values:
                if self.nearest_distance(x, z) <= clearance_m:
                    return False
        return True


@dataclass(frozen=True)
class MixedRoadNetwork:
    config: CityGenConfig
    networks: dict[str, RoadNetwork]
    effective_models: tuple[str, ...]

    @property
    def model(self) -> str:
        return "mixed"

    @property
    def primitives(self) -> tuple[RoadPrimitive, ...]:
        result: list[RoadPrimitive] = []
        for network in self.networks.values():
            result.extend(network.primitives)
        return tuple(result)

    def nearest_distance(self, x: float, z: float) -> float:
        network = self._network_for(x, z)
        return network.nearest_distance(x, z)

    def surface_kind(self, config: CityGenConfig, x: float, z: float) -> str:
        network = self._network_for(x, z)
        return network.surface_kind(config, x, z)

    def road_model_at(self, config: CityGenConfig, x: float, z: float) -> str:
        biome = classify_biome(config.seed, config.urban_fields, x, z)
        return preferred_road_model_for_biome(biome)

    def rect_is_clear(self, rect: Rect, clearance_m: float) -> bool:
        x_values = (rect.min_x, rect.center_x, rect.max_x)
        z_values = (rect.min_z, rect.center_z, rect.max_z)
        for x in x_values:
            for z in z_values:
                if self.nearest_distance(x, z) <= clearance_m:
                    return False
        return True

    def _network_for(self, x: float, z: float) -> RoadNetwork:
        biome = classify_biome(self.config.seed, self.config.urban_fields, x, z)
        model = preferred_road_model_for_biome(biome)
        return self.networks.get(model, self.networks["grid"])


RoadNetworkLike = RoadNetwork | MixedRoadNetwork

def build_road_network(config: CityGenConfig, bbox: BBox) -> RoadNetworkLike:
    if config.roads.model == "mixed":
        networks = {
            "grid": _build_simple_network(config, bbox, "grid"),
            "radial_ring": _build_simple_network(config, bbox, "radial_ring"),
            "linear": _build_simple_network(config, bbox, "linear"),
            "organic": _build_simple_network(config, bbox, "organic"),
        }
        network = MixedRoadNetwork(
            config=config,
            networks=networks,
            effective_models=("grid", "linear", "organic", "radial_ring"),
        )
        return network
    return _build_simple_network(config, bbox, config.roads.model)


def _build_simple_network(config: CityGenConfig, bbox: BBox, model: str) -> RoadNetwork:
    if model == "grid":
        primitives = _grid_primitives(config, bbox)
    elif model == "radial_ring":
        primitives = _radial_primitives(config, bbox, include_rings=True)
    elif model == "radial":
        primitives = _radial_primitives(config, bbox, include_rings=False)
    elif model == "linear":
        primitives = _linear_primitives(config, bbox)
    elif model == "organic":
        primitives = _organic_primitives(config, bbox)
    elif model == "free":
        primitives = _free_primitives(config, bbox)
    else:
        primitives = ()
    return RoadNetwork(model=model, primitives=tuple(primitives), effective_models=(model,))


def _grid_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m
    primitives: list[RoadPrimitive] = []
    for axis in _axis_values(bbox.min_x, bbox.max_x, spacing):
        primitives.append(InfiniteLinePrimitive(axis, 0.0, 0.0, 1.0))
    for axis in _axis_values(bbox.min_z, bbox.max_z, spacing):
        primitives.append(InfiniteLinePrimitive(0.0, axis, 1.0, 0.0))
    return primitives


def _radial_primitives(config: CityGenConfig, bbox: BBox, include_rings: bool) -> list[RoadPrimitive]:
    center_x, center_z = _city_center(config, bbox)
    length = _bbox_radius(bbox, center_x, center_z) + config.roads.spacing_m * 2.0
    count = config.roads.radial_count
    rotation = math.radians(config.roads.angle_degrees)
    primitives: list[RoadPrimitive] = []
    for index in range(count):
        angle = rotation + math.tau * index / count
        primitives.append(
            SegmentPrimitive(
                x0=center_x,
                z0=center_z,
                x1=center_x + math.cos(angle) * length,
                z1=center_z + math.sin(angle) * length,
            )
        )

    if include_rings:
        spacing = config.roads.ring_spacing_m or config.roads.spacing_m
        max_radius = _bbox_radius(bbox, center_x, center_z) + config.roads.spacing_m
        radius = spacing
        while radius <= max_radius:
            primitives.append(RingPrimitive(center_x=center_x, center_z=center_z, radius_m=radius))
            radius += spacing
    return primitives


def _linear_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    angle = math.radians(config.roads.angle_degrees)
    direction = (math.cos(angle), math.sin(angle))
    cross_direction = (-direction[1], direction[0])
    primitives = _parallel_lines_for_bbox(direction, config.roads.spacing_m, bbox)
    primitives.extend(_parallel_lines_for_bbox(cross_direction, config.roads.spacing_m * 2.5, bbox))
    return primitives


def _organic_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m
    pad = spacing * 2.0
    step = max(spacing * 0.45, 12.0)
    wander = config.roads.organic_wander_m or min(
        spacing * 0.42,
        spacing * 0.16 + config.terrain.height_noise_m * 1.2 + 5.0,
    )
    scale = spacing * (2.4 + config.terrain.height_noise_m * 0.12)
    primitives: list[RoadPrimitive] = []

    for axis in _axis_values(bbox.min_z - pad, bbox.max_z + pad, spacing):
        rng = stable_rng(config.seed, "organic-h", round(axis / spacing))
        phase = rng.uniform(0.0, math.tau)
        points: list[tuple[float, float]] = []
        x = bbox.min_x - pad
        while x <= bbox.max_x + pad:
            z = axis + wander * (
                math.sin(x / scale + phase) * 0.72
                + math.sin(x / (scale * 0.47) + phase * 1.71) * 0.28
            )
            points.append((x, z))
            x += step
        primitives.append(PolylinePrimitive(tuple(points)))

    for axis in _axis_values(bbox.min_x - pad, bbox.max_x + pad, spacing * 1.35):
        rng = stable_rng(config.seed, "organic-v", round(axis / spacing))
        phase = rng.uniform(0.0, math.tau)
        points = []
        z = bbox.min_z - pad
        while z <= bbox.max_z + pad:
            x = axis + wander * 0.65 * (
                math.sin(z / (scale * 1.15) + phase) * 0.75
                + math.cos(z / (scale * 0.61) - phase * 0.83) * 0.25
            )
            points.append((x, z))
            z += step
        primitives.append(PolylinePrimitive(tuple(points)))
    return primitives


def _free_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m * 1.8
    start_i = math.floor(bbox.min_x / spacing) - 1
    end_i = math.ceil(bbox.max_x / spacing) + 1
    start_j = math.floor(bbox.min_z / spacing) - 1
    end_j = math.ceil(bbox.max_z / spacing) + 1
    primitives: list[RoadPrimitive] = []

    for ix in range(start_i, end_i):
        for iz in range(start_j, end_j):
            here = _free_node(config.seed, ix, iz, spacing)
            right = _free_node(config.seed, ix + 1, iz, spacing)
            up = _free_node(config.seed, ix, iz + 1, spacing)
            rng = stable_rng(config.seed, "free-edge", ix, iz)
            if rng.random() < 0.72:
                primitives.append(SegmentPrimitive(here[0], here[1], right[0], right[1]))
            if rng.random() < 0.58:
                primitives.append(SegmentPrimitive(here[0], here[1], up[0], up[1]))
    return primitives


def _parallel_lines_for_bbox(direction: tuple[float, float], spacing: float, bbox: BBox) -> list[RoadPrimitive]:
    dir_x, dir_z = _normalize(direction[0], direction[1])
    normal_x, normal_z = -dir_z, dir_x
    projections = [
        x * normal_x + z * normal_z
        for x in (bbox.min_x, bbox.max_x)
        for z in (bbox.min_z, bbox.max_z)
    ]
    start = math.floor(min(projections) / spacing) - 1
    end = math.ceil(max(projections) / spacing) + 1
    primitives: list[RoadPrimitive] = []
    for index in range(start, end + 1):
        offset = index * spacing
        primitives.append(
            InfiniteLinePrimitive(
                point_x=normal_x * offset,
                point_z=normal_z * offset,
                dir_x=dir_x,
                dir_z=dir_z,
            )
        )
    return primitives


def _axis_values(start: float, stop: float, spacing: float) -> list[float]:
    first = math.floor(start / spacing) - 1
    last = math.ceil(stop / spacing) + 1
    return [index * spacing for index in range(first, last + 1)]


def _city_center(config: CityGenConfig, bbox: BBox) -> tuple[float, float]:
    if config.urban_fields.enabled:
        return config.urban_fields.center_x, config.urban_fields.center_z
    return bbox.min_x + bbox.width * 0.5, bbox.min_z + bbox.depth * 0.5


def _bbox_radius(bbox: BBox, center_x: float, center_z: float) -> float:
    return max(
        math.hypot(x - center_x, z - center_z)
        for x in (bbox.min_x, bbox.max_x)
        for z in (bbox.min_z, bbox.max_z)
    )


def _free_node(seed: int, ix: int, iz: int, spacing: float) -> tuple[float, float]:
    rng = stable_rng(seed, "free-node", ix, iz)
    return (
        (ix + 0.5) * spacing + rng.uniform(-spacing * 0.28, spacing * 0.28),
        (iz + 0.5) * spacing + rng.uniform(-spacing * 0.28, spacing * 0.28),
    )


def _distance_to_segment(x: float, z: float, x0: float, z0: float, x1: float, z1: float) -> float:
    dx = x1 - x0
    dz = z1 - z0
    length_sq = dx * dx + dz * dz
    if length_sq == 0:
        return math.hypot(x - x0, z - z0)
    t = ((x - x0) * dx + (z - z0) * dz) / length_sq
    t = max(0.0, min(1.0, t))
    px = x0 + t * dx
    pz = z0 + t * dz
    return math.hypot(x - px, z - pz)


def _normalize(x: float, z: float) -> tuple[float, float]:
    length = math.hypot(x, z)
    if length == 0:
        return 1.0, 0.0
    return x / length, z / length
