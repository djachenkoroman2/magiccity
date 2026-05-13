from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math

from .biomes import classify_biome, preferred_road_model_for_biome
from .config import CityGenConfig, RoadProfileConfig
from .geometry import BBox, Rect, stable_rng
from .selectors import select_weighted_id


@dataclass(frozen=True)
class InfiniteLinePrimitive:
    point_x: float
    point_y: float
    dir_x: float
    dir_y: float

    def distance_to(self, x: float, y: float) -> float:
        return abs((x - self.point_x) * -self.dir_y + (y - self.point_y) * self.dir_x)


@dataclass(frozen=True)
class SegmentPrimitive:
    x0: float
    y0: float
    x1: float
    y1: float

    def distance_to(self, x: float, y: float) -> float:
        return _distance_to_segment(x, y, self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class RingPrimitive:
    center_x: float
    center_y: float
    radius_m: float

    def distance_to(self, x: float, y: float) -> float:
        return abs(math.hypot(x - self.center_x, y - self.center_y) - self.radius_m)


@dataclass(frozen=True)
class PolylinePrimitive:
    points: tuple[tuple[float, float], ...]

    def distance_to(self, x: float, y: float) -> float:
        if len(self.points) < 2:
            return math.inf
        return min(
            _distance_to_segment(x, y, x0, y0, x1, y1)
            for (x0, y0), (x1, y1) in zip(self.points, self.points[1:])
        )


RoadPrimitive = InfiniteLinePrimitive | SegmentPrimitive | RingPrimitive | PolylinePrimitive


@dataclass(frozen=True)
class RoadPrimitiveInstance:
    primitive: RoadPrimitive
    model: str
    index: int
    profile_name: str
    profile: RoadProfileConfig
    biome: str

    def distance_to(self, x: float, y: float) -> float:
        return self.primitive.distance_to(x, y)


@dataclass(frozen=True)
class RoadSurfaceHit:
    kind: str
    distance_m: float
    instance: RoadPrimitiveInstance


@dataclass(frozen=True)
class RoadNetwork:
    model: str
    instances: tuple[RoadPrimitiveInstance, ...]
    effective_models: tuple[str, ...]

    @property
    def primitives(self) -> tuple[RoadPrimitive, ...]:
        return tuple(instance.primitive for instance in self.instances)

    def nearest_distance(self, x: float, y: float) -> float:
        if not self.instances:
            return math.inf
        return min(instance.distance_to(x, y) for instance in self.instances)

    def nearest_hardscape_distance(self, x: float, y: float) -> float:
        if not self.instances:
            return math.inf
        return min(
            instance.distance_to(x, y) - instance.profile.hardscape_half_width_m
            for instance in self.instances
        )

    def surface_kind(self, config: CityGenConfig, x: float, y: float) -> str:
        return self.surface_hit(config, x, y).kind

    def surface_hit(self, _config: CityGenConfig, x: float, y: float) -> RoadSurfaceHit:
        hits: list[RoadSurfaceHit] = []
        for instance in self.instances:
            distance = instance.distance_to(x, y)
            kind = _surface_kind_for_profile(distance, instance.profile)
            if kind != "ground":
                hits.append(RoadSurfaceHit(kind=kind, distance_m=distance, instance=instance))
        return _select_surface_hit(hits)

    def road_model_at(self, _config: CityGenConfig, _x: float, _y: float) -> str:
        return self.model

    def rect_is_clear(self, rect: Rect, clearance_m: float) -> bool:
        x_values = (rect.min_x, rect.center_x, rect.max_x)
        y_values = (rect.min_y, rect.center_y, rect.max_y)
        for x in x_values:
            for y in y_values:
                if self.nearest_hardscape_distance(x, y) <= clearance_m:
                    return False
        return True

    def road_profile_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(instance.profile_name for instance in self.instances).items()))

    def road_profile_counts_by_biome(self) -> dict[str, dict[str, int]]:
        result: dict[str, Counter[str]] = {}
        for instance in self.instances:
            counts = result.setdefault(instance.biome, Counter())
            counts[instance.profile_name] += 1
        return {
            biome: dict(sorted(counts.items()))
            for biome, counts in sorted(result.items())
        }

    def road_widths(self) -> dict[str, float]:
        return _road_widths(self.instances)

    def road_median_info(self) -> dict[str, object]:
        profiles = sorted(
            {
                instance.profile_name
                for instance in self.instances
                if instance.profile.median_width_m > 0
            }
        )
        return {"enabled": bool(profiles), "profiles": profiles}


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

    def nearest_distance(self, x: float, y: float) -> float:
        network = self._network_for(x, y)
        return network.nearest_distance(x, y)

    def nearest_hardscape_distance(self, x: float, y: float) -> float:
        network = self._network_for(x, y)
        return network.nearest_hardscape_distance(x, y)

    def surface_kind(self, config: CityGenConfig, x: float, y: float) -> str:
        network = self._network_for(x, y)
        return network.surface_kind(config, x, y)

    def surface_hit(self, config: CityGenConfig, x: float, y: float) -> RoadSurfaceHit:
        network = self._network_for(x, y)
        return network.surface_hit(config, x, y)

    def road_model_at(self, config: CityGenConfig, x: float, y: float) -> str:
        biome = classify_biome(config.seed, config.urban_fields, x, y)
        return preferred_road_model_for_biome(biome)

    def rect_is_clear(self, rect: Rect, clearance_m: float) -> bool:
        x_values = (rect.min_x, rect.center_x, rect.max_x)
        y_values = (rect.min_y, rect.center_y, rect.max_y)
        for x in x_values:
            for y in y_values:
                if self.nearest_hardscape_distance(x, y) <= clearance_m:
                    return False
        return True

    def road_profile_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for network in self.networks.values():
            counts.update(network.road_profile_counts())
        return dict(sorted(counts.items()))

    def road_profile_counts_by_biome(self) -> dict[str, dict[str, int]]:
        result: dict[str, Counter[str]] = {}
        for network in self.networks.values():
            for biome, counts in network.road_profile_counts_by_biome().items():
                target = result.setdefault(biome, Counter())
                target.update(counts)
        return {
            biome: dict(sorted(counts.items()))
            for biome, counts in sorted(result.items())
        }

    def road_widths(self) -> dict[str, float]:
        instances = [instance for network in self.networks.values() for instance in network.instances]
        return _road_widths(instances)

    def road_median_info(self) -> dict[str, object]:
        profiles = sorted(
            {
                instance.profile_name
                for network in self.networks.values()
                for instance in network.instances
                if instance.profile.median_width_m > 0
            }
        )
        return {"enabled": bool(profiles), "profiles": profiles}

    def _network_for(self, x: float, y: float) -> RoadNetwork:
        biome = classify_biome(self.config.seed, self.config.urban_fields, x, y)
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
    instances = _primitive_instances(config, bbox, model, primitives)
    return RoadNetwork(model=model, instances=instances, effective_models=(model,))


def _primitive_instances(
    config: CityGenConfig,
    bbox: BBox,
    model: str,
    primitives: list[RoadPrimitive],
) -> tuple[RoadPrimitiveInstance, ...]:
    instances: list[RoadPrimitiveInstance] = []
    for index, primitive in enumerate(primitives):
        anchor_x, anchor_y = _primitive_anchor(primitive, bbox)
        biome = classify_biome(config.seed, config.urban_fields, anchor_x, anchor_y)
        profile_name, profile = _select_road_profile(config, model, index, primitive, biome)
        instances.append(
            RoadPrimitiveInstance(
                primitive=primitive,
                model=model,
                index=index,
                profile_name=profile_name,
                profile=profile,
                biome=biome,
            )
        )
    return tuple(instances)


def _select_road_profile(
    config: CityGenConfig,
    model: str,
    index: int,
    primitive: RoadPrimitive,
    biome: str,
) -> tuple[str, RoadProfileConfig]:
    profiles = config.roads.profiles
    if not profiles.enabled:
        profile = config.roads.default_profile
        return profiles.default, profile

    weights = _combined_profile_weights(
        profiles.model_weights.get(model, {}),
        profiles.biome_weights.get(biome, {}),
        profiles.default,
    )
    rng = stable_rng(
        config.seed,
        "road-profile",
        config.tile.x,
        config.tile.y,
        model,
        index,
        biome,
        _primitive_key(primitive),
    )
    profile_name = select_weighted_id(
        weights,
        rng,
        fallback=profiles.default,
        ordered_ids=sorted(profiles.definitions),
    )
    return profile_name, profiles.definitions[profile_name]


def _combined_profile_weights(
    model_weights: dict[str, float],
    biome_weights: dict[str, float],
    default_name: str,
) -> dict[str, float]:
    if model_weights and biome_weights:
        combined = {
            name: model_weights[name] * biome_weights[name]
            for name in model_weights.keys() & biome_weights.keys()
        }
        combined = {name: weight for name, weight in combined.items() if weight > 0}
        if combined:
            return combined

    combined: Counter[str] = Counter()
    combined.update(model_weights)
    combined.update(biome_weights)
    combined = Counter({name: weight for name, weight in combined.items() if weight > 0})
    if combined:
        return dict(combined)
    return {default_name: 1.0}


def _grid_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m
    primitives: list[RoadPrimitive] = []
    for axis in _axis_values(bbox.min_x, bbox.max_x, spacing):
        primitives.append(InfiniteLinePrimitive(axis, 0.0, 0.0, 1.0))
    for axis in _axis_values(bbox.min_y, bbox.max_y, spacing):
        primitives.append(InfiniteLinePrimitive(0.0, axis, 1.0, 0.0))
    return primitives


def _radial_primitives(config: CityGenConfig, bbox: BBox, include_rings: bool) -> list[RoadPrimitive]:
    center_x, center_y = _city_center(config, bbox)
    length = _bbox_radius(bbox, center_x, center_y) + config.roads.spacing_m * 2.0
    count = config.roads.radial_count
    rotation = math.radians(config.roads.angle_degrees)
    primitives: list[RoadPrimitive] = []
    for index in range(count):
        angle = rotation + math.tau * index / count
        primitives.append(
            SegmentPrimitive(
                x0=center_x,
                y0=center_y,
                x1=center_x + math.cos(angle) * length,
                y1=center_y + math.sin(angle) * length,
            )
        )

    if include_rings:
        spacing = config.roads.ring_spacing_m or config.roads.spacing_m
        max_radius = _bbox_radius(bbox, center_x, center_y) + config.roads.spacing_m
        radius = spacing
        while radius <= max_radius:
            primitives.append(RingPrimitive(center_x=center_x, center_y=center_y, radius_m=radius))
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

    for axis in _axis_values(bbox.min_y - pad, bbox.max_y + pad, spacing):
        rng = stable_rng(config.seed, "organic-h", round(axis / spacing))
        phase = rng.uniform(0.0, math.tau)
        points: list[tuple[float, float]] = []
        x = bbox.min_x - pad
        while x <= bbox.max_x + pad:
            y = axis + wander * (
                math.sin(x / scale + phase) * 0.72
                + math.sin(x / (scale * 0.47) + phase * 1.71) * 0.28
            )
            points.append((x, y))
            x += step
        primitives.append(PolylinePrimitive(tuple(points)))

    for axis in _axis_values(bbox.min_x - pad, bbox.max_x + pad, spacing * 1.35):
        rng = stable_rng(config.seed, "organic-v", round(axis / spacing))
        phase = rng.uniform(0.0, math.tau)
        points = []
        y = bbox.min_y - pad
        while y <= bbox.max_y + pad:
            x = axis + wander * 0.65 * (
                math.sin(y / (scale * 1.15) + phase) * 0.75
                + math.cos(y / (scale * 0.61) - phase * 0.83) * 0.25
            )
            points.append((x, y))
            y += step
        primitives.append(PolylinePrimitive(tuple(points)))
    return primitives


def _free_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m * 1.8
    start_i = math.floor(bbox.min_x / spacing) - 1
    end_i = math.ceil(bbox.max_x / spacing) + 1
    start_y = math.floor(bbox.min_y / spacing) - 1
    end_y = math.ceil(bbox.max_y / spacing) + 1
    primitives: list[RoadPrimitive] = []

    for ix in range(start_i, end_i):
        for iy in range(start_y, end_y):
            here = _free_node(config.seed, ix, iy, spacing)
            right = _free_node(config.seed, ix + 1, iy, spacing)
            up = _free_node(config.seed, ix, iy + 1, spacing)
            rng = stable_rng(config.seed, "free-edge", ix, iy)
            if rng.random() < 0.72:
                primitives.append(SegmentPrimitive(here[0], here[1], right[0], right[1]))
            if rng.random() < 0.58:
                primitives.append(SegmentPrimitive(here[0], here[1], up[0], up[1]))
    return primitives


def _parallel_lines_for_bbox(direction: tuple[float, float], spacing: float, bbox: BBox) -> list[RoadPrimitive]:
    dir_x, dir_y = _normalize(direction[0], direction[1])
    normal_x, normal_y = -dir_y, dir_x
    projections = [
        x * normal_x + y * normal_y
        for x in (bbox.min_x, bbox.max_x)
        for y in (bbox.min_y, bbox.max_y)
    ]
    start = math.floor(min(projections) / spacing) - 1
    end = math.ceil(max(projections) / spacing) + 1
    primitives: list[RoadPrimitive] = []
    for index in range(start, end + 1):
        offset = index * spacing
        primitives.append(
            InfiniteLinePrimitive(
                point_x=normal_x * offset,
                point_y=normal_y * offset,
                dir_x=dir_x,
                dir_y=dir_y,
            )
        )
    return primitives


def _axis_values(start: float, stop: float, spacing: float) -> list[float]:
    first = math.floor(start / spacing) - 1
    last = math.ceil(stop / spacing) + 1
    return [index * spacing for index in range(first, last + 1)]


def _city_center(config: CityGenConfig, bbox: BBox) -> tuple[float, float]:
    if config.urban_fields.enabled:
        return config.urban_fields.center_x, config.urban_fields.center_y
    return bbox.min_x + bbox.width * 0.5, bbox.min_y + bbox.depth * 0.5


def _bbox_radius(bbox: BBox, center_x: float, center_y: float) -> float:
    return max(
        math.hypot(x - center_x, y - center_y)
        for x in (bbox.min_x, bbox.max_x)
        for y in (bbox.min_y, bbox.max_y)
    )


def _free_node(seed: int, ix: int, iy: int, spacing: float) -> tuple[float, float]:
    rng = stable_rng(seed, "free-node", ix, iy)
    return (
        (ix + 0.5) * spacing + rng.uniform(-spacing * 0.28, spacing * 0.28),
        (iy + 0.5) * spacing + rng.uniform(-spacing * 0.28, spacing * 0.28),
    )


def _surface_kind_for_profile(distance_m: float, profile: RoadProfileConfig) -> str:
    median_half = profile.median_width_m * 0.5
    road_outer_half = median_half + profile.carriageway_width_m * 0.5
    sidewalk_outer_half = road_outer_half + profile.sidewalk_width_m
    if profile.median_width_m > 0 and distance_m <= median_half:
        return "road_median"
    if distance_m <= road_outer_half:
        return "road"
    if distance_m <= sidewalk_outer_half:
        return "sidewalk"
    return "ground"


def _select_surface_hit(hits: list[RoadSurfaceHit]) -> RoadSurfaceHit:
    if not hits:
        return RoadSurfaceHit(
            kind="ground",
            distance_m=math.inf,
            instance=RoadPrimitiveInstance(
                primitive=InfiniteLinePrimitive(0.0, 0.0, 1.0, 0.0),
                model="none",
                index=-1,
                profile_name="none",
                profile=RoadProfileConfig(1.0, 1.0, 0.0),
                biome="none",
            ),
        )
    if len(hits) > 1 and any(hit.kind == "road_median" for hit in hits):
        road_like = min(hits, key=lambda hit: (hit.distance_m, hit.instance.model, hit.instance.index))
        return RoadSurfaceHit(kind="road", distance_m=road_like.distance_m, instance=road_like.instance)

    priority = {"sidewalk": 1, "road_median": 2, "road": 3}
    return max(
        hits,
        key=lambda hit: (
            priority[hit.kind],
            -hit.distance_m,
            hit.instance.model,
            -hit.instance.index,
        ),
    )


def _road_widths(instances) -> dict[str, float]:
    profiles = [instance.profile for instance in instances]
    if not profiles:
        return {
            "min_carriageway_width_m": 0.0,
            "max_carriageway_width_m": 0.0,
            "max_median_width_m": 0.0,
            "max_total_corridor_width_m": 0.0,
        }
    return {
        "min_carriageway_width_m": round(min(profile.carriageway_width_m for profile in profiles), 3),
        "max_carriageway_width_m": round(max(profile.carriageway_width_m for profile in profiles), 3),
        "max_median_width_m": round(max(profile.median_width_m for profile in profiles), 3),
        "max_total_corridor_width_m": round(max(profile.total_corridor_width_m for profile in profiles), 3),
    }


def _primitive_anchor(primitive: RoadPrimitive, bbox: BBox) -> tuple[float, float]:
    center_x = bbox.min_x + bbox.width * 0.5
    center_y = bbox.min_y + bbox.depth * 0.5
    if isinstance(primitive, InfiniteLinePrimitive):
        dx = center_x - primitive.point_x
        dy = center_y - primitive.point_y
        t = dx * primitive.dir_x + dy * primitive.dir_y
        return primitive.point_x + primitive.dir_x * t, primitive.point_y + primitive.dir_y * t
    if isinstance(primitive, SegmentPrimitive):
        return (primitive.x0 + primitive.x1) * 0.5, (primitive.y0 + primitive.y1) * 0.5
    if isinstance(primitive, RingPrimitive):
        return primitive.center_x + primitive.radius_m, primitive.center_y
    if isinstance(primitive, PolylinePrimitive) and primitive.points:
        return primitive.points[len(primitive.points) // 2]
    return center_x, center_y


def _primitive_key(primitive: RoadPrimitive) -> str:
    if isinstance(primitive, InfiniteLinePrimitive):
        return (
            f"line:{primitive.point_x:.3f}:{primitive.point_y:.3f}:"
            f"{primitive.dir_x:.3f}:{primitive.dir_y:.3f}"
        )
    if isinstance(primitive, SegmentPrimitive):
        return f"seg:{primitive.x0:.3f}:{primitive.y0:.3f}:{primitive.x1:.3f}:{primitive.y1:.3f}"
    if isinstance(primitive, RingPrimitive):
        return f"ring:{primitive.center_x:.3f}:{primitive.center_y:.3f}:{primitive.radius_m:.3f}"
    if isinstance(primitive, PolylinePrimitive):
        first = primitive.points[0] if primitive.points else (0.0, 0.0)
        last = primitive.points[-1] if primitive.points else (0.0, 0.0)
        return f"poly:{len(primitive.points)}:{first[0]:.3f}:{first[1]:.3f}:{last[0]:.3f}:{last[1]:.3f}"
    return "unknown"


def _distance_to_segment(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = x1 - x0
    dy = y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(x - x0, y - y0)
    t = ((x - x0) * dx + (y - y0) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    px = x0 + t * dx
    py = y0 + t * dy
    return math.hypot(x - px, y - py)


def _normalize(x: float, y: float) -> tuple[float, float]:
    length = math.hypot(x, y)
    if length == 0:
        return 1.0, 0.0
    return x / length, y / length
