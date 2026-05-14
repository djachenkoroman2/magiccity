from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import math
from typing import Any, Callable

from .classes import POINT_CLASSES
from .config import CityGenConfig
from .fences import sample_fence_segment
from .generator import Scene, surface_kind
from .geometry import Building, Point, Rect, stable_rng, terrain_height
from .mobile_lidar import sample_mobile_lidar
from .roofs import default_flat_roof
from .trees import sample_tree


ProgressCallback = Callable[[str, str, dict[str, Any] | None], None]


def sample_scene(config: CityGenConfig, scene: Scene, progress: ProgressCallback | None = None) -> list[Point]:
    _emit_progress(progress, "sampling", "started")
    surface_points = _sample_surface_scene(config, scene, progress)
    if not config.mobile_lidar.enabled:
        if progress is not None:
            _emit_progress(
                progress,
                "sampling",
                "done",
                {
                    "surface_points": len(surface_points),
                    "final_points": len(surface_points),
                    "class_counts": _class_counts(surface_points),
                },
            )
        return surface_points

    if progress is not None:
        _emit_progress(
            progress,
            "sampling",
            "done",
            {
                "surface_points": len(surface_points),
                "class_counts": _class_counts(surface_points),
            },
        )

    _emit_progress(progress, "mobile_lidar", "started")
    lidar_result = sample_mobile_lidar(
        config,
        scene,
        progress,
        progress_stage="sampling",
        progress_substage="mobile_lidar_rays",
    )
    lidar_points = _crop_points(lidar_result.points, scene.bbox)
    if config.mobile_lidar.output_mode == "lidar_only":
        if progress is not None:
            _emit_progress(
                progress,
                "mobile_lidar",
                "done",
                _mobile_lidar_progress_details(lidar_result.metadata, len(lidar_points), len(lidar_points)),
            )
        return lidar_points
    points = _crop_points(surface_points + lidar_points, scene.bbox)
    if progress is not None:
        _emit_progress(
            progress,
            "mobile_lidar",
            "done",
            _mobile_lidar_progress_details(lidar_result.metadata, len(lidar_points), len(points)),
        )
    return points


def _sample_surface_scene(config: CityGenConfig, scene: Scene, progress: ProgressCallback | None = None) -> list[Point]:
    points: list[Point] = []

    tile_points = _sample_tile_surfaces(config, scene, progress)
    points.extend(tile_points)

    building_points: list[Point] = []
    if progress is not None:
        _emit_sampling_progress(
            progress,
            "buildings",
            "started",
            {"buildings": len(scene.buildings)},
        )
    total_roof_points = 0
    total_facade_points = 0
    for building_index, building in enumerate(scene.buildings, start=1):
        sampled = _sample_building(config, scene, building)
        building_points.extend(sampled)
        roof_points = _count_points(sampled, "building_roof")
        facade_points = _count_points(sampled, "building_facade")
        total_roof_points += roof_points
        total_facade_points += facade_points
        if progress is not None:
            _emit_sampling_progress(
                progress,
                "buildings",
                "item_done",
                {
                    "building": building_index,
                    "buildings": len(scene.buildings),
                    "building_id": building.id,
                    "points": len(sampled),
                    "roof_points": roof_points,
                    "facade_points": facade_points,
                    "total_building_points": len(building_points),
                    "total_roof_points": total_roof_points,
                    "total_facade_points": total_facade_points,
                },
            )
    points.extend(building_points)
    if progress is not None:
        _emit_sampling_progress(
            progress,
            "buildings",
            "done",
            {
                "buildings": len(scene.buildings),
                "points": len(building_points),
                "roof_points": total_roof_points,
                "facade_points": total_facade_points,
                "total_roof_points": total_roof_points,
                "total_facade_points": total_facade_points,
            },
        )

    fence_points: list[Point] = []
    if scene.fences:
        if progress is not None:
            _emit_sampling_progress(
                progress,
                "fences",
                "started",
                {"fence_segments": len(scene.fences)},
            )
        total_fence_body_points = 0
        total_foundation_points = 0
        for fence_index, fence in enumerate(scene.fences, start=1):
            sampled = sample_fence_segment(config, fence)
            fence_points.extend(sampled)
            segment_fence_points = _count_points(sampled, "fence")
            segment_foundation_points = _count_points(sampled, "fence_foundation")
            total_fence_body_points += segment_fence_points
            total_foundation_points += segment_foundation_points
            if progress is not None:
                _emit_sampling_progress(
                    progress,
                    "fences",
                    "item_done",
                    {
                        "segment": fence_index,
                        "fence_segments": len(scene.fences),
                        "segment_id": fence.id,
                        "points": len(sampled),
                        "fence_points": segment_fence_points,
                        "foundation_points": segment_foundation_points,
                        "total_fence_points": len(fence_points),
                        "total_fence_body_points": total_fence_body_points,
                        "total_foundation_points": total_foundation_points,
                    },
                )
        points.extend(fence_points)
        if progress is not None:
            _emit_sampling_progress(
                progress,
                "fences",
                "done",
                {
                    "fence_segments": len(scene.fences),
                    "points": len(fence_points),
                    "fence_points": total_fence_body_points,
                    "foundation_points": total_foundation_points,
                    "total_fence_body_points": total_fence_body_points,
                    "total_foundation_points": total_foundation_points,
                },
            )

    tree_points: list[Point] = []
    if scene.trees:
        if progress is not None:
            _emit_sampling_progress(
                progress,
                "trees",
                "started",
                {"trees": len(scene.trees)},
            )
        total_trunk_points = 0
        total_crown_points = 0
        for tree_index, tree in enumerate(scene.trees, start=1):
            sampled = sample_tree(config, tree)
            tree_points.extend(sampled)
            trunk_points = _count_points(sampled, "tree_trunk")
            crown_points = _count_points(sampled, "tree_crown")
            total_trunk_points += trunk_points
            total_crown_points += crown_points
            if progress is not None:
                _emit_sampling_progress(
                    progress,
                    "trees",
                    "item_done",
                    {
                        "tree": tree_index,
                        "trees": len(scene.trees),
                        "tree_id": tree.id,
                        "points": len(sampled),
                        "trunk_points": trunk_points,
                        "crown_points": crown_points,
                        "total_tree_points": len(tree_points),
                        "total_trunk_points": total_trunk_points,
                        "total_crown_points": total_crown_points,
                    },
                )
        points.extend(tree_points)
        if progress is not None:
            _emit_sampling_progress(
                progress,
                "trees",
                "done",
                {
                    "trees": len(scene.trees),
                    "points": len(tree_points),
                    "trunk_points": total_trunk_points,
                    "crown_points": total_crown_points,
                    "total_trunk_points": total_trunk_points,
                    "total_crown_points": total_crown_points,
                },
            )

    cropped = _crop_points(points, scene.bbox)
    if progress is not None:
        cropped_class_counts = _class_counts(cropped)
        _emit_sampling_progress(
            progress,
            "surface_total",
            "done",
            {
                "tile_surface_points": len(tile_points),
                "building_points": len(building_points),
                "fence_points": len(fence_points),
                "ground_points": cropped_class_counts.get("ground", 0),
                "hardscape_points": _hardscape_points(cropped_class_counts),
                "cropped_building_points": _building_points(cropped_class_counts),
                "cropped_fence_points": _fence_points(cropped_class_counts),
                "cropped_tree_points": _tree_points(cropped_class_counts),
                "surface_points_before_crop": len(points),
                "surface_points": len(cropped),
                "class_counts": cropped_class_counts,
            },
        )
    return cropped


def _sample_tile_surfaces(
    config: CityGenConfig,
    scene: Scene,
    progress: ProgressCallback | None = None,
) -> list[Point]:
    spacing = min(config.sampling.ground_spacing_m, config.sampling.road_spacing_m)
    rng = stable_rng(config.seed, "tile-surfaces", config.tile.x, config.tile.y)
    points: list[Point] = []
    x_rows = _grid_count(scene.bbox.min_x, scene.bbox.max_x, spacing)
    y_rows = _grid_count(scene.bbox.min_y, scene.bbox.max_y, spacing)
    total_grid_samples = x_rows * y_rows
    class_counts: Counter[str] | None = Counter() if progress is not None else None
    processed_samples = 0

    if progress is not None:
        _emit_sampling_progress(
            progress,
            "tile_surfaces",
            "started",
            {
                "grid_rows": x_rows,
                "grid_columns": y_rows,
                "grid_samples": total_grid_samples,
                "spacing_m": spacing,
            },
        )

    for row_index, x in enumerate(_grid_values(scene.bbox.min_x, scene.bbox.max_x, spacing), start=1):
        for y in _grid_values(scene.bbox.min_y, scene.bbox.max_y, spacing):
            processed_samples += 1
            jx = _jitter(rng, spacing, config.sampling.jitter_ratio)
            jy = _jitter(rng, spacing, config.sampling.jitter_ratio)
            sx = _clamp(x + jx, scene.bbox.min_x, scene.bbox.max_x)
            sy = _clamp(y + jy, scene.bbox.min_y, scene.bbox.max_y)
            if _inside_any_building(scene.buildings, sx, sy):
                continue

            kind = surface_kind(config, scene, sx, sy)
            wanted_spacing = (
                config.sampling.road_spacing_m
                if kind in {"road", "road_median", "sidewalk"}
                else config.sampling.ground_spacing_m
            )
            if spacing < wanted_spacing and rng.random() > (spacing / wanted_spacing) ** 2:
                continue

            cls = POINT_CLASSES[kind]
            z = terrain_height(config.seed, config.terrain, sx, sy)
            points.append(Point(sx, sy, z, *cls.color, cls.id))
            if class_counts is not None:
                class_counts[kind] += 1

        if progress is not None:
            _emit_sampling_progress(
                progress,
                "tile_surfaces",
                "progress",
                {
                    "rows": row_index,
                    "total_rows": x_rows,
                    "grid_samples": processed_samples,
                    "total_grid_samples": total_grid_samples,
                    "points": len(points),
                    "ground_points": class_counts.get("ground", 0) if class_counts is not None else 0,
                    "hardscape_points": _hardscape_points(class_counts) if class_counts is not None else 0,
                    "road_points": class_counts.get("road", 0) if class_counts is not None else 0,
                    "sidewalk_points": class_counts.get("sidewalk", 0) if class_counts is not None else 0,
                    "road_median_points": class_counts.get("road_median", 0) if class_counts is not None else 0,
                    "class_counts": dict(sorted(class_counts.items())) if class_counts is not None else {},
                },
            )

    if progress is not None:
        _emit_sampling_progress(
            progress,
            "tile_surfaces",
            "done",
            {
                "grid_rows": x_rows,
                "grid_samples": processed_samples,
                "points": len(points),
                "ground_points": class_counts.get("ground", 0) if class_counts is not None else 0,
                "hardscape_points": _hardscape_points(class_counts) if class_counts is not None else 0,
                "road_points": class_counts.get("road", 0) if class_counts is not None else 0,
                "sidewalk_points": class_counts.get("sidewalk", 0) if class_counts is not None else 0,
                "road_median_points": class_counts.get("road_median", 0) if class_counts is not None else 0,
                "class_counts": dict(sorted(class_counts.items())) if class_counts is not None else {},
            },
        )

    return points


def _sample_building(config: CityGenConfig, scene: Scene, building: Building) -> list[Point]:
    if not building.footprint.intersects(scene.bbox):
        return []
    spacing = config.sampling.building_spacing_m
    rng = stable_rng(config.seed, "building-sampling", building.id)
    points: list[Point] = []
    points.extend(_sample_roof(config, building, spacing, rng))
    points.extend(_sample_facades(config, building, spacing, rng))
    return points


def _sample_roof(config: CityGenConfig, building: Building, spacing: float, rng) -> list[Point]:
    cls = POINT_CLASSES["building_roof"]
    points: list[Point] = []
    bbox = building.footprint.bbox
    roof = building.roof or default_flat_roof(building.footprint, building.roof_z)
    for x in _grid_values(bbox.min_x, bbox.max_x, spacing):
        for y in _grid_values(bbox.min_y, bbox.max_y, spacing):
            sx = _clamp(
                x + _jitter(rng, spacing, config.sampling.jitter_ratio),
                bbox.min_x,
                bbox.max_x,
            )
            sy = _clamp(
                y + _jitter(rng, spacing, config.sampling.jitter_ratio),
                bbox.min_y,
                bbox.max_y,
            )
            if not building.footprint.contains_xy(sx, sy):
                continue
            points.append(Point(sx, sy, roof.height_at(sx, sy, building.footprint), *cls.color, cls.id))
    return points


def _sample_facades(config: CityGenConfig, building: Building, spacing: float, rng) -> list[Point]:
    cls = POINT_CLASSES["building_facade"]
    points: list[Point] = []
    eave_z = building.eave_z
    verticals = list(_grid_values(building.base_z, eave_z, spacing))
    for segment in building.footprint.boundary_segments():
        length = segment.length
        if length == 0:
            continue
        for offset in _grid_values(0.0, length, spacing):
            for z in verticals:
                jo = _jitter(rng, spacing, config.sampling.jitter_ratio)
                jz = _jitter(rng, spacing, config.sampling.jitter_ratio)
                along = _clamp(offset + jo, 0.0, length)
                t = along / length
                sx = segment.x0 + (segment.x1 - segment.x0) * t
                sy = segment.y0 + (segment.y1 - segment.y0) * t
                zz = _clamp(z + jz, building.base_z, eave_z)
                points.append(Point(sx, sy, zz, *cls.color, cls.id))
    return points


def _crop_points(points: Iterable[Point], bbox: Rect) -> list[Point]:
    return [point for point in points if bbox.contains_xy(point.x, point.y)]


def _inside_any_building(buildings: list[Building], x: float, y: float) -> bool:
    return any(building.footprint.contains_xy(x, y) for building in buildings)


def _grid_values(start: float, stop: float, spacing: float) -> Iterable[float]:
    count = max(1, int(math.floor((stop - start) / spacing)) + 1)
    for index in range(count):
        value = start + index * spacing
        yield min(value, stop)


def _grid_count(start: float, stop: float, spacing: float) -> int:
    return max(1, int(math.floor((stop - start) / spacing)) + 1)


def _jitter(rng, spacing: float, ratio: float) -> float:
    if ratio <= 0:
        return 0.0
    return rng.uniform(-spacing * ratio, spacing * ratio)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _mobile_lidar_progress_details(metadata: dict[str, Any], lidar_points: int, final_points: int) -> dict[str, Any]:
    return {
        "lidar_points": lidar_points,
        "final_points": final_points,
        "sensor_positions": metadata.get("sensor_positions", 0),
        "emitted_rays": metadata.get("emitted_rays", 0),
        "successful_hits": metadata.get("successful_hits", 0),
        "missed_rays": metadata.get("missed_rays", 0),
        "dropped_rays": metadata.get("dropped_rays", 0),
        "attenuated_rays": metadata.get("attenuated_rays", 0),
    }


def _emit_sampling_progress(
    progress: ProgressCallback | None,
    substage: str,
    event: str,
    details: dict[str, Any] | None = None,
) -> None:
    payload = {"substage": substage, "event": event}
    if details:
        payload.update(details)
    _emit_progress(progress, "sampling", "progress", payload)


def _progress_interval(total: int, steps: int = 4) -> int:
    return max(1, math.ceil(total / max(1, steps)))


def _count_points(points: Iterable[Point], class_name: str) -> int:
    class_id = POINT_CLASSES[class_name].id
    return sum(1 for point in points if point.class_id == class_id)


def _class_counts(points: Iterable[Point]) -> dict[str, int]:
    names_by_id = {point_class.id: name for name, point_class in POINT_CLASSES.items()}
    counts: Counter[str] = Counter()
    for point in points:
        counts[names_by_id.get(point.class_id, str(point.class_id))] += 1
    return dict(sorted(counts.items()))


def _hardscape_points(counts: dict[str, int] | Counter[str]) -> int:
    return sum(counts.get(class_name, 0) for class_name in ("road", "sidewalk", "road_median"))


def _building_points(counts: dict[str, int] | Counter[str]) -> int:
    return sum(counts.get(class_name, 0) for class_name in ("building_roof", "building_facade"))


def _fence_points(counts: dict[str, int] | Counter[str]) -> int:
    return sum(counts.get(class_name, 0) for class_name in ("fence", "fence_foundation"))


def _tree_points(counts: dict[str, int] | Counter[str]) -> int:
    return sum(counts.get(class_name, 0) for class_name in ("tree_trunk", "tree_crown"))


def _emit_progress(
    progress: ProgressCallback | None,
    stage: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    if progress is not None:
        progress(stage, status, details)
