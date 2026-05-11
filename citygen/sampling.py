from __future__ import annotations

from collections.abc import Iterable
import math

from .classes import POINT_CLASSES
from .config import CityGenConfig
from .generator import Scene, surface_kind
from .geometry import Building, Point, Rect, stable_rng, terrain_height
from .roofs import default_flat_roof


def sample_scene(config: CityGenConfig, scene: Scene) -> list[Point]:
    points: list[Point] = []
    points.extend(_sample_tile_surfaces(config, scene))
    for building in scene.buildings:
        points.extend(_sample_building(config, scene, building))
    return _crop_points(points, scene.bbox)


def _sample_tile_surfaces(config: CityGenConfig, scene: Scene) -> list[Point]:
    spacing = min(config.sampling.ground_spacing_m, config.sampling.road_spacing_m)
    rng = stable_rng(config.seed, "tile-surfaces", config.tile.x, config.tile.y)
    points: list[Point] = []

    for x in _grid_values(scene.bbox.min_x, scene.bbox.max_x, spacing):
        for y in _grid_values(scene.bbox.min_y, scene.bbox.max_y, spacing):
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


def _jitter(rng, spacing: float, ratio: float) -> float:
    if ratio <= 0:
        return 0.0
    return rng.uniform(-spacing * ratio, spacing * ratio)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
