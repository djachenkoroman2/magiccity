from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any, Callable

from .classes import POINT_CLASSES
from .config import CityGenConfig
from .fences import FenceSegment
from .geometry import BBox, Building, Point, Rect, stable_rng, terrain_height
from .roads import InfiniteLinePrimitive, PolylinePrimitive, RingPrimitive, SegmentPrimitive
from .roofs import default_flat_roof


@dataclass(frozen=True)
class RayHit:
    distance_m: float
    class_name: str
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class MobileLidarResult:
    points: list[Point]
    metadata: dict[str, Any]


ProgressCallback = Callable[[str, str, dict[str, Any] | None], None]


def sample_mobile_lidar(
    config: CityGenConfig,
    scene,
    progress: ProgressCallback | None = None,
) -> MobileLidarResult:
    lidar = config.mobile_lidar
    if not lidar.enabled:
        return MobileLidarResult(points=[], metadata=_disabled_metadata(config))

    positions = _trajectory_positions(config, scene)
    horizontal_offsets = _horizontal_offsets(lidar.horizontal_fov_degrees, lidar.horizontal_step_degrees)
    vertical_angles = _vertical_angles(lidar.vertical_center_degrees, lidar.vertical_fov_degrees, lidar.vertical_channels)
    total_rays = len(positions) * len(horizontal_offsets) * len(vertical_angles)

    emitted = 0
    dropped = 0
    missed = 0
    attenuated = 0
    points: list[Point] = []
    hit_counts: Counter[str] = Counter()
    milestone_interval = _progress_interval(len(positions))

    if progress is not None:
        _emit_mobile_lidar_progress(
            progress,
            "rays",
            "started",
            {
                "sensor_positions": len(positions),
                "horizontal_angles": len(horizontal_offsets),
                "vertical_channels": len(vertical_angles),
                "total_rays": total_rays,
            },
        )

    for position_index, (sensor_x, sensor_y, yaw_degrees) in enumerate(positions):
        sensor_z = terrain_height(config.seed, config.terrain, sensor_x, sensor_y) + lidar.sensor_height_m
        for horizontal_index, horizontal_offset in enumerate(horizontal_offsets):
            for vertical_index, vertical_angle in enumerate(vertical_angles):
                emitted += 1
                rng = stable_rng(
                    config.seed,
                    "mobile-lidar-ray",
                    config.tile.x,
                    config.tile.y,
                    position_index,
                    horizontal_index,
                    vertical_index,
                )
                if rng.random() < lidar.drop_probability:
                    dropped += 1
                    continue

                yaw = yaw_degrees + horizontal_offset
                pitch = vertical_angle
                if lidar.angle_jitter_degrees > 0:
                    yaw += rng.uniform(-lidar.angle_jitter_degrees, lidar.angle_jitter_degrees)
                    pitch += rng.uniform(-lidar.angle_jitter_degrees, lidar.angle_jitter_degrees)
                direction = _ray_direction(yaw, pitch)
                hit = _trace_ray(config, scene, (sensor_x, sensor_y, sensor_z), direction)
                if hit is None:
                    missed += 1
                    continue

                attenuation_probability = min(
                    0.95,
                    max(0.0, hit.distance_m / lidar.max_range_m) * lidar.distance_attenuation,
                )
                if attenuation_probability > 0 and rng.random() < attenuation_probability:
                    attenuated += 1
                    continue

                distance = hit.distance_m
                if lidar.range_noise_m > 0:
                    distance += rng.gauss(0.0, lidar.range_noise_m)
                    distance = max(lidar.min_range_m, min(lidar.max_range_m, distance))
                x = sensor_x + direction[0] * distance
                y = sensor_y + direction[1] * distance
                z = sensor_z + direction[2] * distance
                cls = POINT_CLASSES[hit.class_name]
                points.append(Point(x, y, z, *cls.color, cls.id))
                hit_counts[hit.class_name] += 1

        if progress is not None:
            _emit_mobile_lidar_progress(
                progress,
                "rays",
                "item_done",
                _ray_progress_details(
                    position_index + 1,
                    len(positions),
                    emitted,
                    total_rays,
                    dropped,
                    missed,
                    attenuated,
                    points,
                    hit_counts,
                ),
            )
            if position_index + 1 == len(positions) or (position_index + 1) % milestone_interval == 0:
                _emit_mobile_lidar_progress(
                    progress,
                    "rays",
                    "progress",
                    _ray_progress_details(
                        position_index + 1,
                        len(positions),
                        emitted,
                        total_rays,
                        dropped,
                        missed,
                        attenuated,
                        points,
                        hit_counts,
                    ),
                )

    metadata = _metadata(config, positions, emitted, dropped, missed, attenuated, hit_counts)
    if progress is not None:
        _emit_mobile_lidar_progress(
            progress,
            "rays",
            "done",
            {
                "sensor_positions": len(positions),
                "processed_rays": emitted,
                "total_rays": total_rays,
                "emitted_rays": emitted,
                "successful_hits": metadata.get("successful_hits", 0),
                "dropped_rays": dropped,
                "missed_rays": missed,
                "attenuated_rays": attenuated,
                "lidar_points": len(points),
                "hit_counts_by_class": dict(sorted(hit_counts.items())),
            },
        )
    return MobileLidarResult(points=points, metadata=metadata)


def mobile_lidar_metadata(config: CityGenConfig, scene) -> dict[str, Any]:
    return sample_mobile_lidar(config, scene).metadata


def _trace_ray(
    config: CityGenConfig,
    scene,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> RayHit | None:
    hits: list[RayHit] = []

    terrain_hit = _intersect_terrain(config, scene, origin, direction)
    if terrain_hit is not None:
        hits.append(terrain_hit)

    for building in scene.buildings:
        facade_hit = _intersect_building_facade(config, building, origin, direction)
        if facade_hit is not None:
            hits.append(facade_hit)
        roof_hit = _intersect_building_roof(config, building, origin, direction)
        if roof_hit is not None:
            hits.append(roof_hit)

    if config.mobile_lidar.occlusions_enabled:
        for fence in scene.fences:
            fence_hit = _intersect_fence(config, fence, origin, direction)
            if fence_hit is not None:
                hits.append(fence_hit)

    if not hits:
        return None
    if config.mobile_lidar.occlusions_enabled:
        return min(hits, key=lambda hit: hit.distance_m)
    return max(hits, key=lambda hit: hit.distance_m)


def _intersect_terrain(
    config: CityGenConfig,
    scene,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> RayHit | None:
    lidar = config.mobile_lidar
    if direction[2] >= 0:
        return None

    def contains(x: float, y: float) -> bool:
        return scene.work_bbox.contains_xy(x, y)

    def height_at(x: float, y: float) -> float:
        return terrain_height(config.seed, config.terrain, x, y)

    distance = _intersect_height_field(config, origin, direction, contains, height_at)
    if distance is None:
        return None
    x, y, z = _point_on_ray(origin, direction, distance)
    class_name = scene.road_network.surface_kind(config, x, y)
    return RayHit(distance, class_name, x, y, z)


def _intersect_building_facade(
    config: CityGenConfig,
    building: Building,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> RayHit | None:
    best: RayHit | None = None
    for segment in building.footprint.boundary_segments():
        intersection = _intersect_ray_segment_xy(
            origin[0],
            origin[1],
            direction[0],
            direction[1],
            segment.x0,
            segment.y0,
            segment.x1,
            segment.y1,
        )
        if intersection is None:
            continue
        distance, _along = intersection
        if not _distance_in_range(config, distance):
            continue
        x, y, z = _point_on_ray(origin, direction, distance)
        if building.base_z - 1e-6 <= z <= building.eave_z + 1e-6:
            hit = RayHit(distance, "building_facade", x, y, z)
            if best is None or hit.distance_m < best.distance_m:
                best = hit
    return best


def _intersect_building_roof(
    config: CityGenConfig,
    building: Building,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> RayHit | None:
    roof = building.roof or default_flat_roof(building.footprint, building.roof_z)

    def contains(x: float, y: float) -> bool:
        return building.footprint.contains_xy(x, y)

    def height_at(x: float, y: float) -> float:
        return roof.height_at(x, y, building.footprint)

    distance = _intersect_height_field(config, origin, direction, contains, height_at, downward_crossing_only=True)
    if distance is None:
        return None
    x, y, z = _point_on_ray(origin, direction, distance)
    return RayHit(distance, "building_roof", x, y, z)


def _intersect_fence(
    config: CityGenConfig,
    fence: FenceSegment,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> RayHit | None:
    intersection = _intersect_ray_segment_xy(
        origin[0],
        origin[1],
        direction[0],
        direction[1],
        fence.x0,
        fence.y0,
        fence.x1,
        fence.y1,
    )
    if intersection is None:
        return None

    distance, along_ratio = intersection
    if not _distance_in_range(config, distance):
        return None

    x, y, z = _point_on_ray(origin, direction, distance)
    base_z = terrain_height(config.seed, config.terrain, x, y)
    foundation_top = base_z + (fence.foundation_height_m if fence.has_foundation else 0.0)
    body_top = foundation_top + fence.height_m
    if fence.has_foundation and base_z - 1e-6 <= z <= foundation_top + 1e-6:
        return RayHit(distance, "fence_foundation", x, y, z)
    if foundation_top - 1e-6 <= z <= body_top + 1e-6:
        along_m = max(0.0, min(1.0, along_ratio)) * fence.length_m
        z_delta = z - foundation_top
        if _fence_blocks_ray(fence, along_m, z_delta):
            return RayHit(distance, "fence", x, y, z)
    return None


def _intersect_height_field(
    config: CityGenConfig,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    contains,
    height_at,
    downward_crossing_only: bool = False,
) -> float | None:
    lidar = config.mobile_lidar
    step = max(0.25, lidar.ray_step_m)
    previous_distance: float | None = None
    previous_delta: float | None = None
    distance = lidar.min_range_m

    while distance <= lidar.max_range_m + 1e-9:
        x, y, z = _point_on_ray(origin, direction, distance)
        if contains(x, y):
            delta = z - height_at(x, y)
            if previous_delta is not None:
                crosses_down = previous_delta >= 0 and delta <= 0
                crosses_any = previous_delta == 0 or delta == 0 or previous_delta * delta < 0
                if crosses_down or (not downward_crossing_only and crosses_any):
                    return _refine_height_field_hit(
                        origin,
                        direction,
                        previous_distance if previous_distance is not None else distance,
                        distance,
                        height_at,
                    )
            if delta <= 0 and previous_delta is None and not downward_crossing_only:
                return distance
            previous_distance = distance
            previous_delta = delta
        else:
            previous_distance = None
            previous_delta = None
        distance += step
    return None


def _refine_height_field_hit(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    low: float,
    high: float,
    height_at,
) -> float:
    for _ in range(10):
        mid = (low + high) * 0.5
        x, y, z = _point_on_ray(origin, direction, mid)
        delta = z - height_at(x, y)
        if delta > 0:
            low = mid
        else:
            high = mid
    return high


def _trajectory_positions(config: CityGenConfig, scene) -> tuple[tuple[float, float, float], ...]:
    lidar = config.mobile_lidar
    path: tuple[tuple[float, float], ...] | None = None
    fallback_yaw = lidar.direction_degrees

    if (
        lidar.trajectory == "line"
        and lidar.start_x is not None
        and lidar.start_y is not None
        and lidar.end_x is not None
        and lidar.end_y is not None
    ):
        path = ((lidar.start_x, lidar.start_y), (lidar.end_x, lidar.end_y))
    elif lidar.trajectory == "road":
        path = _road_trajectory(scene.bbox, scene.road_network.primitives)
    if path is None:
        start, end = _centerline(scene.bbox, lidar.direction_degrees)
        path = (start, end)

    return _positions_along_path(path, lidar.position_step_m, fallback_yaw)


def _positions_along_path(
    path: tuple[tuple[float, float], ...],
    step_m: float,
    fallback_yaw: float,
) -> tuple[tuple[float, float, float], ...]:
    if len(path) < 2:
        x, y = path[0] if path else (0.0, 0.0)
        return ((x, y, fallback_yaw),)

    segments: list[tuple[float, float, float, float, float, float, float, float]] = []
    total = 0.0
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            continue
        yaw = math.degrees(math.atan2(dy, dx))
        segments.append((total, total + length, x0, y0, dx, dy, length, yaw))
        total += length
    if not segments:
        x, y = path[0]
        return ((x, y, fallback_yaw),)

    distances: list[float] = []
    count = max(1, int(math.floor(total / step_m)) + 1)
    for index in range(count):
        distances.append(min(total, index * step_m))
    if abs(distances[-1] - total) > 1e-9:
        distances.append(total)

    positions: list[tuple[float, float, float]] = []
    segment_index = 0
    for distance in distances:
        while segment_index + 1 < len(segments) and distance > segments[segment_index][1] + 1e-9:
            segment_index += 1
        seg = segments[segment_index]
        local = max(0.0, min(seg[6], distance - seg[0]))
        ratio = local / seg[6]
        x = seg[2] + seg[4] * ratio
        y = seg[3] + seg[5] * ratio
        positions.append((x, y, seg[7]))
    return tuple(positions)


def _road_trajectory(
    bbox: BBox,
    primitives: tuple[InfiniteLinePrimitive | SegmentPrimitive | RingPrimitive | PolylinePrimitive, ...],
) -> tuple[tuple[float, float], ...] | None:
    if not primitives:
        return None
    center_x = bbox.min_x + bbox.width * 0.5
    center_y = bbox.min_y + bbox.depth * 0.5
    for primitive in sorted(primitives, key=lambda item: item.distance_to(center_x, center_y)):
        path = _primitive_path(primitive, bbox)
        if path is not None and len(path) >= 2:
            return path
    return None


def _primitive_path(
    primitive: InfiniteLinePrimitive | SegmentPrimitive | RingPrimitive | PolylinePrimitive,
    bbox: BBox,
) -> tuple[tuple[float, float], ...] | None:
    if isinstance(primitive, InfiniteLinePrimitive):
        angle = math.degrees(math.atan2(primitive.dir_y, primitive.dir_x))
        start, end = _centerline(bbox, angle)
        return (start, end)
    if isinstance(primitive, SegmentPrimitive):
        points = _path_inside_bbox(((primitive.x0, primitive.y0), (primitive.x1, primitive.y1)), bbox)
        return points if len(points) >= 2 else None
    if isinstance(primitive, PolylinePrimitive):
        points = _path_inside_bbox(primitive.points, bbox)
        return points if len(points) >= 2 else None
    return None


def _path_inside_bbox(points: tuple[tuple[float, float], ...], bbox: BBox) -> tuple[tuple[float, float], ...]:
    clamped = [
        (
            min(max(point[0], bbox.min_x), bbox.max_x),
            min(max(point[1], bbox.min_y), bbox.max_y),
        )
        for point in points
    ]
    deduped: list[tuple[float, float]] = []
    for point in clamped:
        if not deduped or abs(deduped[-1][0] - point[0]) > 1e-9 or abs(deduped[-1][1] - point[1]) > 1e-9:
            deduped.append(point)
    return tuple(deduped)


def _centerline(bbox: BBox, angle_degrees: float) -> tuple[tuple[float, float], tuple[float, float]]:
    center_x = bbox.min_x + bbox.width * 0.5
    center_y = bbox.min_y + bbox.depth * 0.5
    radians = math.radians(angle_degrees)
    direction = (math.cos(radians), math.sin(radians))
    candidates: list[tuple[float, float, float]] = []

    if abs(direction[0]) > 1e-9:
        for x in (bbox.min_x, bbox.max_x):
            t = (x - center_x) / direction[0]
            y = center_y + direction[1] * t
            if bbox.min_y - 1e-6 <= y <= bbox.max_y + 1e-6:
                candidates.append((t, x, y))
    if abs(direction[1]) > 1e-9:
        for y in (bbox.min_y, bbox.max_y):
            t = (y - center_y) / direction[1]
            x = center_x + direction[0] * t
            if bbox.min_x - 1e-6 <= x <= bbox.max_x + 1e-6:
                candidates.append((t, x, y))

    if len(candidates) < 2:
        return (bbox.min_x, center_y), (bbox.max_x, center_y)
    candidates.sort(key=lambda item: item[0])
    return (candidates[0][1], candidates[0][2]), (candidates[-1][1], candidates[-1][2])


def _horizontal_offsets(fov_degrees: float, step_degrees: float) -> tuple[float, ...]:
    if fov_degrees >= 360.0:
        count = max(1, int(math.floor(360.0 / step_degrees)))
        return tuple(-180.0 + index * (360.0 / count) for index in range(count))
    count = max(1, int(math.floor(fov_degrees / step_degrees)) + 1)
    start = -fov_degrees * 0.5
    return tuple(min(fov_degrees * 0.5, start + index * step_degrees) for index in range(count))


def _vertical_angles(center_degrees: float, fov_degrees: float, channels: int) -> tuple[float, ...]:
    if channels <= 1:
        return (center_degrees,)
    start = center_degrees - fov_degrees * 0.5
    step = fov_degrees / (channels - 1)
    return tuple(start + index * step for index in range(channels))


def _ray_direction(yaw_degrees: float, pitch_degrees: float) -> tuple[float, float, float]:
    yaw = math.radians(yaw_degrees)
    pitch = math.radians(pitch_degrees)
    horizontal = math.cos(pitch)
    return (
        horizontal * math.cos(yaw),
        horizontal * math.sin(yaw),
        math.sin(pitch),
    )


def _intersect_ray_segment_xy(
    origin_x: float,
    origin_y: float,
    ray_x: float,
    ray_y: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> tuple[float, float] | None:
    seg_x = x1 - x0
    seg_y = y1 - y0
    denominator = _cross(ray_x, ray_y, seg_x, seg_y)
    if abs(denominator) < 1e-9:
        return None
    qx = x0 - origin_x
    qy = y0 - origin_y
    distance = _cross(qx, qy, seg_x, seg_y) / denominator
    along = _cross(qx, qy, ray_x, ray_y) / denominator
    if distance < 0 or along < -1e-9 or along > 1.0 + 1e-9:
        return None
    return distance, along


def _fence_blocks_ray(fence: FenceSegment, along_m: float, z_delta: float) -> bool:
    if fence.openness <= 0.08:
        return True
    post_spacing = 2.4
    element_spacing = 0.45
    if fence.fence_type in {"metal_chain_link", "metal_welded", "metal_forged"}:
        element_spacing = 0.55 if fence.fence_type == "metal_chain_link" else 0.42
    if fence.fence_type in {"stone", "brick", "wood_solid", "metal_profile"} and fence.openness < 0.25:
        return True
    tolerance = 0.14 + (1.0 - fence.openness) * 0.18
    if _near_multiple(along_m, post_spacing, tolerance):
        return True
    rail_levels = (0.22, 0.55, 0.88) if fence.decorative else (0.25, 0.80)
    for level in rail_levels:
        if abs(z_delta - fence.height_m * level) <= tolerance:
            return True
    if fence.fence_type == "metal_chain_link":
        return _near_multiple(along_m + z_delta * 0.75, element_spacing, tolerance)
    return _near_multiple(along_m, element_spacing + fence.openness * 0.35, tolerance)


def _near_multiple(value: float, spacing: float, tolerance: float) -> bool:
    if spacing <= 0:
        return False
    return abs(value - round(value / spacing) * spacing) <= tolerance


def _point_on_ray(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    distance_m: float,
) -> tuple[float, float, float]:
    return (
        origin[0] + direction[0] * distance_m,
        origin[1] + direction[1] * distance_m,
        origin[2] + direction[2] * distance_m,
    )


def _distance_in_range(config: CityGenConfig, distance_m: float) -> bool:
    return config.mobile_lidar.min_range_m <= distance_m <= config.mobile_lidar.max_range_m


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _ray_progress_details(
    position_index: int,
    position_total: int,
    emitted: int,
    total_rays: int,
    dropped: int,
    missed: int,
    attenuated: int,
    points: list[Point],
    hit_counts: Counter[str],
) -> dict[str, Any]:
    return {
        "positions": position_index,
        "total_positions": position_total,
        "processed_rays": emitted,
        "total_rays": total_rays,
        "successful_hits": sum(hit_counts.values()),
        "dropped_rays": dropped,
        "missed_rays": missed,
        "attenuated_rays": attenuated,
        "lidar_points": len(points),
        "hit_counts_by_class": dict(sorted(hit_counts.items())),
    }


def _emit_mobile_lidar_progress(
    progress: ProgressCallback | None,
    substage: str,
    event: str,
    details: dict[str, Any] | None = None,
) -> None:
    payload = {"substage": substage, "event": event}
    if details:
        payload.update(details)
    _emit_progress(progress, "mobile_lidar", "progress", payload)


def _progress_interval(total: int, steps: int = 4) -> int:
    return max(1, math.ceil(total / max(1, steps)))


def _emit_progress(
    progress: ProgressCallback | None,
    stage: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    if progress is not None:
        progress(stage, status, details)


def _metadata(
    config: CityGenConfig,
    positions: tuple[tuple[float, float, float], ...],
    emitted: int,
    dropped: int,
    missed: int,
    attenuated: int,
    hit_counts: Counter[str],
) -> dict[str, Any]:
    lidar = config.mobile_lidar
    successful = sum(hit_counts.values())
    return {
        "enabled": True,
        "output_mode": lidar.output_mode,
        "trajectory": lidar.trajectory,
        "sensor_positions": len(positions),
        "emitted_rays": emitted,
        "successful_hits": successful,
        "dropped_rays": dropped,
        "missed_rays": missed,
        "max_range_misses": missed,
        "attenuated_rays": attenuated,
        "hit_counts_by_class": dict(sorted(hit_counts.items())),
        "parameters": {
            "sensor_height_m": lidar.sensor_height_m,
            "direction_degrees": lidar.direction_degrees,
            "start_x": lidar.start_x,
            "start_y": lidar.start_y,
            "end_x": lidar.end_x,
            "end_y": lidar.end_y,
            "position_step_m": lidar.position_step_m,
            "min_range_m": lidar.min_range_m,
            "max_range_m": lidar.max_range_m,
            "horizontal_fov_degrees": lidar.horizontal_fov_degrees,
            "horizontal_step_degrees": lidar.horizontal_step_degrees,
            "vertical_fov_degrees": lidar.vertical_fov_degrees,
            "vertical_center_degrees": lidar.vertical_center_degrees,
            "vertical_channels": lidar.vertical_channels,
            "angle_jitter_degrees": lidar.angle_jitter_degrees,
            "range_noise_m": lidar.range_noise_m,
            "drop_probability": lidar.drop_probability,
            "distance_attenuation": lidar.distance_attenuation,
            "occlusions_enabled": lidar.occlusions_enabled,
            "ray_step_m": lidar.ray_step_m,
        },
    }


def _disabled_metadata(config: CityGenConfig) -> dict[str, Any]:
    return {
        "enabled": False,
        "output_mode": config.mobile_lidar.output_mode,
        "trajectory": config.mobile_lidar.trajectory,
        "sensor_positions": 0,
        "emitted_rays": 0,
        "successful_hits": 0,
        "dropped_rays": 0,
        "missed_rays": 0,
        "max_range_misses": 0,
        "attenuated_rays": 0,
        "hit_counts_by_class": {},
        "parameters": {
            "sensor_height_m": config.mobile_lidar.sensor_height_m,
            "direction_degrees": config.mobile_lidar.direction_degrees,
            "start_x": config.mobile_lidar.start_x,
            "start_y": config.mobile_lidar.start_y,
            "end_x": config.mobile_lidar.end_x,
            "end_y": config.mobile_lidar.end_y,
            "position_step_m": config.mobile_lidar.position_step_m,
            "min_range_m": config.mobile_lidar.min_range_m,
            "max_range_m": config.mobile_lidar.max_range_m,
            "horizontal_fov_degrees": config.mobile_lidar.horizontal_fov_degrees,
            "horizontal_step_degrees": config.mobile_lidar.horizontal_step_degrees,
            "vertical_fov_degrees": config.mobile_lidar.vertical_fov_degrees,
            "vertical_center_degrees": config.mobile_lidar.vertical_center_degrees,
            "vertical_channels": config.mobile_lidar.vertical_channels,
            "angle_jitter_degrees": config.mobile_lidar.angle_jitter_degrees,
            "range_noise_m": config.mobile_lidar.range_noise_m,
            "drop_probability": config.mobile_lidar.drop_probability,
            "distance_attenuation": config.mobile_lidar.distance_attenuation,
            "occlusions_enabled": config.mobile_lidar.occlusions_enabled,
            "ray_step_m": config.mobile_lidar.ray_step_m,
        },
    }
