from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any

from .biomes import classify_biome
from .catalogs import VEHICLE_TYPE_ALIASES, VEHICLE_TYPE_DEFINITIONS
from .classes import POINT_CLASSES
from .config import CityGenConfig, VehiclesConfig
from .fences import FenceSegment
from .geometry import BBox, Building, Point, normalize_degrees, stable_rng, terrain_height
from .parcels import Parcel
from .roads import (
    InfiniteLinePrimitive,
    PolylinePrimitive,
    RingPrimitive,
    RoadNetworkLike,
    RoadPrimitiveInstance,
    SegmentPrimitive,
)
from .selectors import select_weighted_id
from .trees import Tree


VEHICLE_TYPES: tuple[str, ...] = tuple(VEHICLE_TYPE_DEFINITIONS)

_BIOME_TYPE_WEIGHT_MULTIPLIERS = {
    "downtown": {"car": 1.25, "truck": 0.55, "bus": 1.65, "emergency": 1.25, "tractor": 0.0},
    "residential": {"car": 1.25, "truck": 0.65, "bus": 0.55, "emergency": 0.8, "tractor": 0.15},
    "suburb": {"car": 1.15, "truck": 0.75, "bus": 0.25, "emergency": 0.65, "tractor": 1.15},
    "industrial": {"car": 0.35, "truck": 1.7, "bus": 0.15, "emergency": 1.0, "tractor": 1.35},
}


@dataclass(frozen=True)
class VehicleSpec:
    vehicle_type: str
    length_m: float
    width_m: float
    height_m: float
    wheel_radius_m: float
    body_color: tuple[int, int, int]
    allowed_placement_modes: tuple[str, ...]
    tags: tuple[str, ...]

    @property
    def bbox_radius_m(self) -> float:
        return math.hypot(self.length_m, self.width_m) * 0.5


@dataclass(frozen=True)
class Vehicle:
    id: str
    vehicle_type: str
    x: float
    y: float
    base_z: float
    length_m: float
    width_m: float
    height_m: float
    wheel_radius_m: float
    orientation_degrees: float
    biome: str
    placement_mode: str
    body_color: tuple[int, int, int]
    road_profile_name: str | None = None
    parcel_id: str | None = None

    @property
    def bbox_radius_m(self) -> float:
        return math.hypot(self.length_m, self.width_m) * 0.5

    @property
    def top_z(self) -> float:
        return self.base_z + self.height_m


def build_vehicles(
    config: CityGenConfig,
    bbox: BBox,
    road_network: RoadNetworkLike,
    buildings: list[Building],
    fences: tuple[FenceSegment, ...],
    trees: tuple[Tree, ...],
    parcels: tuple[Parcel, ...],
) -> tuple[Vehicle, ...]:
    vehicles_config = config.vehicles
    if not vehicles_config.enabled:
        return ()
    if vehicles_config.density_per_km <= 0 and vehicles_config.parking_density_per_ha <= 0:
        return ()
    if max(vehicles_config.biome_density_multipliers.values(), default=0.0) <= 0:
        return ()

    vehicles: list[Vehicle] = []
    if "road" in vehicles_config.placement_modes and vehicles_config.density_per_km > 0:
        vehicles.extend(
            _build_road_vehicles(config, bbox, road_network, buildings, fences, trees, vehicles)
        )
    if (
        {"parking", "industrial_yard"} & set(vehicles_config.placement_modes)
        and vehicles_config.parking_density_per_ha > 0
        and parcels
    ):
        vehicles.extend(
            _build_parcel_vehicles(config, bbox, road_network, buildings, fences, trees, parcels, vehicles)
        )
    return tuple(sorted(vehicles, key=lambda vehicle: vehicle.id))


def vehicle_counts(vehicles: tuple[Vehicle, ...]) -> dict[str, Any]:
    if not vehicles:
        return {
            "total": 0,
            "by_type": {},
            "by_placement_mode": {},
            "by_biome": {},
            "dimensions_m": {
                "length": {"average": 0.0, "min": 0.0, "max": 0.0},
                "width": {"average": 0.0, "min": 0.0, "max": 0.0},
                "height": {"average": 0.0, "min": 0.0, "max": 0.0},
            },
        }

    return {
        "total": len(vehicles),
        "by_type": dict(sorted(Counter(vehicle.vehicle_type for vehicle in vehicles).items())),
        "by_placement_mode": dict(sorted(Counter(vehicle.placement_mode for vehicle in vehicles).items())),
        "by_biome": dict(sorted(Counter(vehicle.biome for vehicle in vehicles).items())),
        "dimensions_m": {
            "length": _dimension_summary(vehicle.length_m for vehicle in vehicles),
            "width": _dimension_summary(vehicle.width_m for vehicle in vehicles),
            "height": _dimension_summary(vehicle.height_m for vehicle in vehicles),
        },
    }


def vehicle_catalog_summary() -> dict[str, Any]:
    return {
        vehicle_type: {
            "length_m": definition.length_m,
            "width_m": definition.width_m,
            "height_m": definition.height_m,
            "wheel_radius_m": definition.wheel_radius_m,
            "allowed_placement_modes": list(definition.allowed_placement_modes),
            "tags": list(definition.tags),
        }
        for vehicle_type, definition in sorted(VEHICLE_TYPE_DEFINITIONS.items())
    }


def vehicle_alias_summary() -> dict[str, str]:
    return dict(sorted(VEHICLE_TYPE_ALIASES.items()))


def sample_vehicle(config: CityGenConfig, vehicle: Vehicle) -> list[Point]:
    spacing = config.vehicles.sample_spacing_m
    points: list[Point] = []
    points.extend(_sample_body(vehicle, spacing))
    points.extend(_sample_wheels(vehicle, spacing))
    points.extend(_sample_windows(vehicle, spacing))
    return _cap_points(points, config.vehicles.max_points_per_vehicle)


def vehicle_ray_hits(
    config: CityGenConfig,
    vehicle: Vehicle,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> tuple[tuple[float, str], ...]:
    distance = _intersect_oriented_box(config, vehicle, origin, direction)
    if distance is None:
        return ()
    return ((distance, "vehicle_body"),)


def _build_road_vehicles(
    config: CityGenConfig,
    bbox: BBox,
    road_network: RoadNetworkLike,
    buildings: list[Building],
    fences: tuple[FenceSegment, ...],
    trees: tuple[Tree, ...],
    existing: list[Vehicle],
) -> list[Vehicle]:
    vehicles_config = config.vehicles
    max_multiplier = max(vehicles_config.biome_density_multipliers.values(), default=0.0)
    if max_multiplier <= 0:
        return []

    max_density = vehicles_config.density_per_km * max_multiplier
    if max_density <= 0:
        return []

    candidate_step = max(vehicles_config.min_spacing_m, 1000.0 / max_density)
    result: list[Vehicle] = []
    for instance in _road_instances(road_network):
        if not _profile_allowed(vehicles_config, instance.profile_name):
            continue
        if instance.profile.carriageway_width_m <= 0:
            continue
        for segment_index, segment in enumerate(_road_segments(instance, bbox)):
            x0, y0, x1, y1 = segment
            dx = x1 - x0
            dy = y1 - y0
            length = math.hypot(dx, dy)
            if length <= 1e-6:
                continue
            direction = (dx / length, dy / length)
            normal = (-direction[1], direction[0])
            count = max(1, int(math.floor(length / candidate_step)))
            rng = stable_rng(
                config.seed,
                "vehicle-road-segment",
                config.tile.x,
                config.tile.y,
                instance.model,
                instance.index,
                segment_index,
                instance.profile_name,
            )
            start_offset = rng.uniform(0.15, 0.85) * candidate_step
            for local_index in range(count + 1):
                along = start_offset + local_index * candidate_step
                if along > length:
                    continue
                base_x = x0 + direction[0] * along
                base_y = y0 + direction[1] * along
                biome = classify_biome(config.seed, config.urban_fields, base_x, base_y)
                multiplier = vehicles_config.biome_density_multipliers.get(biome, 0.0)
                if multiplier <= 0:
                    continue
                if rng.random() > min(0.98, multiplier / max_multiplier):
                    continue
                mode = "road"
                vehicle_type = _select_vehicle_type(config, vehicles_config, biome, mode, rng)
                if vehicle_type is None:
                    continue
                spec = _vehicle_spec(config, vehicle_type)
                if spec.width_m + vehicles_config.clearance_m * 2.0 > instance.profile.carriageway_width_m * 0.5:
                    continue
                side = _road_side(vehicles_config, rng)
                offset = _road_lateral_offset(vehicles_config, instance, spec, side, rng)
                x = base_x + normal[0] * offset
                y = base_y + normal[1] * offset
                orientation = math.degrees(math.atan2(direction[1], direction[0]))
                if side < 0:
                    orientation += 180.0
                orientation += rng.uniform(
                    -vehicles_config.orientation_jitter_degrees,
                    vehicles_config.orientation_jitter_degrees,
                )
                vehicle_id = f"vehicle_road_{instance.model}_{instance.index}_{segment_index}_{local_index}"
                vehicle = _make_vehicle(
                    config,
                    spec,
                    vehicle_id,
                    x,
                    y,
                    biome,
                    mode,
                    orientation,
                    road_profile_name=instance.profile_name,
                )
                if _vehicle_location_is_clear(
                    config,
                    bbox,
                    road_network,
                    buildings,
                    fences,
                    trees,
                    existing + result,
                    vehicle,
                    require_kind="road",
                ):
                    result.append(vehicle)
    return result


def _build_parcel_vehicles(
    config: CityGenConfig,
    bbox: BBox,
    road_network: RoadNetworkLike,
    buildings: list[Building],
    fences: tuple[FenceSegment, ...],
    trees: tuple[Tree, ...],
    parcels: tuple[Parcel, ...],
    existing: list[Vehicle],
) -> list[Vehicle]:
    vehicles_config = config.vehicles
    max_multiplier = max(vehicles_config.biome_density_multipliers.values(), default=0.0)
    if max_multiplier <= 0:
        return []

    result: list[Vehicle] = []
    for parcel in parcels:
        if not parcel.buildable or parcel.buildable_geometry is None:
            continue
        modes = _parcel_placement_modes(config, parcel)
        if not modes:
            continue
        for mode, mode_scale in modes:
            multiplier = vehicles_config.biome_density_multipliers.get(parcel.biome, 0.0)
            if multiplier <= 0:
                continue
            area_ha = parcel.buildable_geometry.area_m2 / 10000.0
            expected = vehicles_config.parking_density_per_ha * multiplier * area_ha * mode_scale
            if expected <= 0:
                continue
            candidate_count = max(1, int(math.ceil(expected * 2.5)))
            rng = stable_rng(config.seed, "vehicle-parcel", config.tile.x, config.tile.y, parcel.id, mode)
            for candidate_index in range(candidate_count):
                if rng.random() > min(0.98, expected / candidate_count):
                    continue
                vehicle_type = _select_vehicle_type(config, vehicles_config, parcel.biome, mode, rng)
                if vehicle_type is None:
                    continue
                spec = _vehicle_spec(config, vehicle_type)
                inset = max(vehicles_config.clearance_m + spec.bbox_radius_m, vehicles_config.tile_margin_clearance_m)
                area = parcel.buildable_geometry.inset(inset)
                if area is None:
                    continue
                half_x = max(0.0, area.width * 0.5)
                half_y = max(0.0, area.depth * 0.5)
                x_local = rng.uniform(-half_x, half_x)
                y_local = rng.uniform(-half_y, half_y)
                x, y = area.local_to_world(x_local, y_local)
                orientation = parcel.orientation_degrees
                if rng.random() < 0.5:
                    orientation += 180.0
                orientation += rng.uniform(
                    -vehicles_config.orientation_jitter_degrees,
                    vehicles_config.orientation_jitter_degrees,
                )
                vehicle = _make_vehicle(
                    config,
                    spec,
                    f"vehicle_{mode}_{parcel.id}_{candidate_index}",
                    x,
                    y,
                    parcel.biome,
                    mode,
                    orientation,
                    parcel_id=parcel.id,
                )
                if _vehicle_location_is_clear(
                    config,
                    bbox,
                    road_network,
                    buildings,
                    fences,
                    trees,
                    existing + result,
                    vehicle,
                    require_kind="ground",
                ):
                    result.append(vehicle)
    return result


def _vehicle_spec(config: CityGenConfig, vehicle_type: str) -> VehicleSpec:
    definition = VEHICLE_TYPE_DEFINITIONS[vehicle_type]
    vehicles_config = config.vehicles
    return VehicleSpec(
        vehicle_type=vehicle_type,
        length_m=vehicles_config.length_m or definition.length_m,
        width_m=vehicles_config.width_m or definition.width_m,
        height_m=vehicles_config.height_m or definition.height_m,
        wheel_radius_m=vehicles_config.wheel_radius_m or definition.wheel_radius_m,
        body_color=definition.body_color,
        allowed_placement_modes=definition.allowed_placement_modes,
        tags=definition.tags,
    )


def _make_vehicle(
    config: CityGenConfig,
    spec: VehicleSpec,
    vehicle_id: str,
    x: float,
    y: float,
    biome: str,
    placement_mode: str,
    orientation_degrees: float,
    road_profile_name: str | None = None,
    parcel_id: str | None = None,
) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        vehicle_type=spec.vehicle_type,
        x=x,
        y=y,
        base_z=terrain_height(config.seed, config.terrain, x, y),
        length_m=spec.length_m,
        width_m=spec.width_m,
        height_m=spec.height_m,
        wheel_radius_m=spec.wheel_radius_m,
        orientation_degrees=normalize_degrees(orientation_degrees),
        biome=biome,
        placement_mode=placement_mode,
        body_color=spec.body_color,
        road_profile_name=road_profile_name,
        parcel_id=parcel_id,
    )


def _select_vehicle_type(
    config: CityGenConfig,
    vehicles_config: VehiclesConfig,
    biome: str,
    placement_mode: str,
    rng,
) -> str | None:
    if vehicles_config.vehicle_type != "mixed":
        spec = _vehicle_spec(config, vehicles_config.vehicle_type)
        return vehicles_config.vehicle_type if placement_mode in spec.allowed_placement_modes else None

    multipliers = _BIOME_TYPE_WEIGHT_MULTIPLIERS.get(biome, {})
    weights = {
        vehicle_type: weight * multipliers.get(vehicle_type, 1.0)
        for vehicle_type, weight in vehicles_config.weights.items()
        if weight > 0
        and placement_mode in VEHICLE_TYPE_DEFINITIONS[vehicle_type].allowed_placement_modes
    }
    weights = {vehicle_type: weight for vehicle_type, weight in weights.items() if weight > 0}
    if not weights:
        return None
    return select_weighted_id(weights, rng, fallback=next(iter(weights)), ordered_ids=VEHICLE_TYPES)


def _vehicle_location_is_clear(
    config: CityGenConfig,
    bbox: BBox,
    road_network: RoadNetworkLike,
    buildings: list[Building],
    fences: tuple[FenceSegment, ...],
    trees: tuple[Tree, ...],
    vehicles: list[Vehicle],
    vehicle: Vehicle,
    require_kind: str,
) -> bool:
    vehicles_config = config.vehicles
    if not _inside_vehicle_bbox(bbox, vehicles_config, vehicle):
        return False
    kind = road_network.surface_kind(config, vehicle.x, vehicle.y)
    if require_kind == "road":
        if kind != "road" and not (vehicles_config.allow_road_medians and kind == "road_median"):
            return False
    elif kind != "ground":
        return False
    if _near_building(buildings, vehicle, vehicles_config.building_clearance_m):
        return False
    if _near_fence(fences, vehicle, vehicles_config.fence_clearance_m):
        return False
    if _near_tree(trees, vehicle, vehicles_config.tree_clearance_m):
        return False
    return not _near_existing_vehicle(vehicles, vehicle, vehicles_config.min_spacing_m)


def _inside_vehicle_bbox(bbox: BBox, config: VehiclesConfig, vehicle: Vehicle) -> bool:
    clearance = config.tile_margin_clearance_m + vehicle.bbox_radius_m
    return (
        bbox.min_x + clearance <= vehicle.x <= bbox.max_x - clearance
        and bbox.min_y + clearance <= vehicle.y <= bbox.max_y - clearance
    )


def _near_building(buildings: list[Building], vehicle: Vehicle, clearance: float) -> bool:
    radius = vehicle.bbox_radius_m + clearance
    for building in buildings:
        if building.footprint.contains_xy(vehicle.x, vehicle.y):
            return True
        if _distance_to_rect(vehicle.x, vehicle.y, building.footprint.bbox) <= radius:
            return True
    return False


def _near_fence(fences: tuple[FenceSegment, ...], vehicle: Vehicle, clearance: float) -> bool:
    radius = vehicle.bbox_radius_m + clearance
    return any(
        _distance_to_segment(vehicle.x, vehicle.y, fence.x0, fence.y0, fence.x1, fence.y1) <= radius
        for fence in fences
    )


def _near_tree(trees: tuple[Tree, ...], vehicle: Vehicle, clearance: float) -> bool:
    for tree in trees:
        threshold = vehicle.bbox_radius_m + max(tree.trunk_radius_m, tree.crown_radius_m * 0.75) + clearance
        if math.hypot(vehicle.x - tree.x, vehicle.y - tree.y) <= threshold:
            return True
    return False


def _near_existing_vehicle(vehicles: list[Vehicle], vehicle: Vehicle, min_spacing: float) -> bool:
    for other in vehicles:
        threshold = max(min_spacing, vehicle.bbox_radius_m + other.bbox_radius_m)
        if math.hypot(vehicle.x - other.x, vehicle.y - other.y) < threshold:
            return True
    return False


def _profile_allowed(config: VehiclesConfig, profile_name: str) -> bool:
    return not config.allowed_road_profiles or profile_name in config.allowed_road_profiles


def _road_side(config: VehiclesConfig, rng) -> int:
    if config.side_of_road == "left":
        return 1
    if config.side_of_road == "right":
        return -1
    return 1 if rng.random() < 0.5 else -1


def _road_lateral_offset(
    config: VehiclesConfig,
    instance: RoadPrimitiveInstance,
    spec: VehicleSpec,
    side: int,
    rng,
) -> float:
    profile = instance.profile
    median_half = profile.median_width_m * 0.5
    carriage_half = profile.carriageway_width_m * 0.5
    min_abs = median_half + spec.width_m * 0.5 + config.clearance_m
    max_abs = median_half + max(min_abs, carriage_half - spec.width_m * 0.5 - config.clearance_m)
    if config.lane_offset_m is not None:
        offset_abs = median_half + config.lane_offset_m
    else:
        offset_abs = min_abs if max_abs <= min_abs else rng.uniform(min_abs, max_abs)
    return side * max(min_abs, min(offset_abs, max_abs))


def _parcel_placement_modes(config: CityGenConfig, parcel: Parcel) -> tuple[tuple[str, float], ...]:
    vehicles_config = config.vehicles
    has_parking = "parking" in vehicles_config.placement_modes
    has_yard = "industrial_yard" in vehicles_config.placement_modes
    if parcel.biome == "industrial" and has_yard and has_parking:
        parking_scale = vehicles_config.parked_ratio
        yard_scale = 1.0 - vehicles_config.parked_ratio
        modes: list[tuple[str, float]] = []
        if yard_scale > 0:
            modes.append(("industrial_yard", yard_scale))
        if parking_scale > 0:
            modes.append(("parking", parking_scale))
        return tuple(modes)
    if parcel.biome == "industrial" and has_yard:
        return (("industrial_yard", 1.0),)
    if "parking" in vehicles_config.placement_modes:
        return (("parking", 1.0),)
    return ()


def _road_instances(road_network: RoadNetworkLike) -> tuple[RoadPrimitiveInstance, ...]:
    if hasattr(road_network, "instances"):
        return tuple(road_network.instances)
    networks = getattr(road_network, "networks", {})
    instances: list[RoadPrimitiveInstance] = []
    for network in networks.values():
        instances.extend(network.instances)
    return tuple(instances)


def _road_segments(
    instance: RoadPrimitiveInstance,
    bbox: BBox,
) -> tuple[tuple[float, float, float, float], ...]:
    primitive = instance.primitive
    if isinstance(primitive, InfiniteLinePrimitive):
        center_x = bbox.min_x + bbox.width * 0.5
        center_y = bbox.min_y + bbox.depth * 0.5
        dx = primitive.dir_x
        dy = primitive.dir_y
        projection = (center_x - primitive.point_x) * dx + (center_y - primitive.point_y) * dy
        cx = primitive.point_x + dx * projection
        cy = primitive.point_y + dy * projection
        half = math.hypot(bbox.width, bbox.depth) * 0.75 + 8.0
        return ((cx - dx * half, cy - dy * half, cx + dx * half, cy + dy * half),)
    if isinstance(primitive, SegmentPrimitive):
        return ((primitive.x0, primitive.y0, primitive.x1, primitive.y1),)
    if isinstance(primitive, PolylinePrimitive):
        return tuple(
            (x0, y0, x1, y1)
            for (x0, y0), (x1, y1) in zip(primitive.points, primitive.points[1:])
        )
    if isinstance(primitive, RingPrimitive):
        segments: list[tuple[float, float, float, float]] = []
        count = max(24, int(math.ceil(math.tau * primitive.radius_m / 24.0)))
        for index in range(count):
            a0 = math.tau * index / count
            a1 = math.tau * (index + 1) / count
            segments.append(
                (
                    primitive.center_x + math.cos(a0) * primitive.radius_m,
                    primitive.center_y + math.sin(a0) * primitive.radius_m,
                    primitive.center_x + math.cos(a1) * primitive.radius_m,
                    primitive.center_y + math.sin(a1) * primitive.radius_m,
                )
            )
        return tuple(segments)
    return ()


def _sample_body(vehicle: Vehicle, spacing: float) -> list[Point]:
    points: list[Point] = []
    body_bottom = max(0.12, vehicle.wheel_radius_m * 0.75)
    top = vehicle.height_m
    x_values = tuple(_grid_values(-vehicle.length_m * 0.5, vehicle.length_m * 0.5, spacing))
    y_values = tuple(_grid_values(-vehicle.width_m * 0.5, vehicle.width_m * 0.5, spacing))
    z_values = tuple(_grid_values(body_bottom, top, max(0.25, spacing)))

    for lx in x_values:
        for ly in y_values:
            points.append(_vehicle_point(vehicle, lx, ly, top, "vehicle_body", vehicle.body_color))
    for lx in x_values:
        for lz in z_values:
            points.append(_vehicle_point(vehicle, lx, -vehicle.width_m * 0.5, lz, "vehicle_body", vehicle.body_color))
            points.append(_vehicle_point(vehicle, lx, vehicle.width_m * 0.5, lz, "vehicle_body", vehicle.body_color))
    for ly in y_values:
        for lz in z_values:
            points.append(_vehicle_point(vehicle, -vehicle.length_m * 0.5, ly, lz, "vehicle_body", vehicle.body_color))
            points.append(_vehicle_point(vehicle, vehicle.length_m * 0.5, ly, lz, "vehicle_body", vehicle.body_color))
    return points


def _sample_wheels(vehicle: Vehicle, spacing: float) -> list[Point]:
    cls = POINT_CLASSES["vehicle_wheel"]
    points: list[Point] = []
    wheel_x = vehicle.length_m * 0.32
    wheel_y = vehicle.width_m * 0.52
    radius = vehicle.wheel_radius_m
    ring_count = max(8, int(math.ceil(math.tau * radius / max(0.18, spacing * 0.45))))
    thickness_offsets = (-0.08, 0.08)
    for lx in (-wheel_x, wheel_x):
        for side in (-1.0, 1.0):
            ly = wheel_y * side
            for offset in thickness_offsets:
                for index in range(ring_count):
                    angle = math.tau * index / ring_count
                    local_x = lx + math.cos(angle) * radius
                    local_y = ly + offset * side
                    local_z = radius + math.sin(angle) * radius
                    x, y, z = _local_to_world(vehicle, local_x, local_y, local_z)
                    points.append(Point(x, y, z, *cls.color, cls.id))
    return points


def _sample_windows(vehicle: Vehicle, spacing: float) -> list[Point]:
    points: list[Point] = []
    window_bottom = vehicle.height_m * 0.56
    window_top = vehicle.height_m * 0.84
    window_length_ratio = 0.55 if vehicle.vehicle_type in {"bus", "truck"} else 0.38
    x_values = tuple(
        _grid_values(
            -vehicle.length_m * window_length_ratio * 0.5,
            vehicle.length_m * window_length_ratio * 0.5,
            max(0.25, spacing),
        )
    )
    z_values = tuple(_grid_values(window_bottom, window_top, max(0.25, spacing * 0.75)))
    for side in (-1.0, 1.0):
        ly = side * (vehicle.width_m * 0.5 + 0.01)
        for lx in x_values:
            for lz in z_values:
                points.append(_vehicle_point(vehicle, lx, ly, lz, "vehicle_window"))

    y_values = tuple(_grid_values(-vehicle.width_m * 0.22, vehicle.width_m * 0.22, max(0.25, spacing)))
    for lx in (-vehicle.length_m * 0.5 - 0.01, vehicle.length_m * 0.5 + 0.01):
        for ly in y_values:
            for lz in z_values:
                points.append(_vehicle_point(vehicle, lx, ly, lz, "vehicle_window"))
    return points


def _vehicle_point(
    vehicle: Vehicle,
    local_x: float,
    local_y: float,
    local_z: float,
    class_name: str,
    color: tuple[int, int, int] | None = None,
) -> Point:
    cls = POINT_CLASSES[class_name]
    rgb = color or cls.color
    x, y, z = _local_to_world(vehicle, local_x, local_y, local_z)
    return Point(x, y, z, *rgb, cls.id)


def _local_to_world(vehicle: Vehicle, local_x: float, local_y: float, local_z: float) -> tuple[float, float, float]:
    angle = math.radians(vehicle.orientation_degrees)
    forward = (math.cos(angle), math.sin(angle))
    right = (-math.sin(angle), math.cos(angle))
    x = vehicle.x + forward[0] * local_x + right[0] * local_y
    y = vehicle.y + forward[1] * local_x + right[1] * local_y
    return x, y, vehicle.base_z + local_z


def _world_to_local_xy(vehicle: Vehicle, x: float, y: float) -> tuple[float, float]:
    angle = math.radians(vehicle.orientation_degrees)
    forward = (math.cos(angle), math.sin(angle))
    right = (-math.sin(angle), math.cos(angle))
    dx = x - vehicle.x
    dy = y - vehicle.y
    return dx * forward[0] + dy * forward[1], dx * right[0] + dy * right[1]


def _intersect_oriented_box(
    config: CityGenConfig,
    vehicle: Vehicle,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> float | None:
    ox, oy = _world_to_local_xy(vehicle, origin[0], origin[1])
    oz = origin[2] - vehicle.base_z
    angle = math.radians(vehicle.orientation_degrees)
    forward = (math.cos(angle), math.sin(angle))
    right = (-math.sin(angle), math.cos(angle))
    dx = direction[0] * forward[0] + direction[1] * forward[1]
    dy = direction[0] * right[0] + direction[1] * right[1]
    dz = direction[2]

    bounds = (
        (-vehicle.length_m * 0.5, vehicle.length_m * 0.5, ox, dx),
        (-vehicle.width_m * 0.5, vehicle.width_m * 0.5, oy, dy),
        (0.0, vehicle.height_m, oz, dz),
    )
    near = -math.inf
    far = math.inf
    for lower, upper, value, delta in bounds:
        if abs(delta) < 1e-12:
            if value < lower or value > upper:
                return None
            continue
        t0 = (lower - value) / delta
        t1 = (upper - value) / delta
        if t0 > t1:
            t0, t1 = t1, t0
        near = max(near, t0)
        far = min(far, t1)
        if near > far:
            return None
    distance = near if near >= 0 else far
    if config.mobile_lidar.min_range_m <= distance <= config.mobile_lidar.max_range_m:
        return distance
    return None


def _grid_values(start: float, stop: float, spacing: float):
    count = max(1, int(math.floor((stop - start) / spacing)) + 1)
    for index in range(count):
        value = start + index * spacing
        yield min(value, stop)


def _cap_points(points: list[Point], cap: int) -> list[Point]:
    if cap <= 0 or len(points) <= cap:
        return points
    by_class: dict[int, list[Point]] = {}
    for point in points:
        by_class.setdefault(point.class_id, []).append(point)
    capped: list[Point] = []
    class_ids = sorted(by_class)
    remaining = cap
    for index, class_id in enumerate(class_ids):
        source = by_class[class_id]
        allowance = max(1, remaining // (len(class_ids) - index))
        if len(source) <= allowance:
            capped.extend(source)
            remaining -= len(source)
            continue
        step = len(source) / allowance
        capped.extend(source[min(len(source) - 1, int(i * step))] for i in range(allowance))
        remaining -= allowance
    return capped[:cap]


def _dimension_summary(values) -> dict[str, float]:
    values = list(values)
    if not values:
        return {"average": 0.0, "min": 0.0, "max": 0.0}
    return {
        "average": round(sum(values) / len(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def _distance_to_rect(x: float, y: float, rect) -> float:
    dx = max(rect.min_x - x, 0.0, x - rect.max_x)
    dy = max(rect.min_y - y, 0.0, y - rect.max_y)
    return math.hypot(dx, dy)


def _distance_to_segment(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = x1 - x0
    dy = y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(x - x0, y - y0)
    t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / length_sq))
    px = x0 + dx * t
    py = y0 + dy * t
    return math.hypot(x - px, y - py)
