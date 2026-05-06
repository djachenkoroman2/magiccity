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
    rng = stable_rng(config.seed, "tile-surfaces", config.tile.x, config.tile.z)
    points: list[Point] = []

    for x in _grid_values(scene.bbox.min_x, scene.bbox.max_x, spacing):
        for z in _grid_values(scene.bbox.min_z, scene.bbox.max_z, spacing):
            jx = _jitter(rng, spacing, config.sampling.jitter_ratio)
            jz = _jitter(rng, spacing, config.sampling.jitter_ratio)
            sx = _clamp(x + jx, scene.bbox.min_x, scene.bbox.max_x)
            sz = _clamp(z + jz, scene.bbox.min_z, scene.bbox.max_z)
            if _inside_any_building(scene.buildings, sx, sz):
                continue

            kind = surface_kind(config, scene, sx, sz)
            wanted_spacing = (
                config.sampling.road_spacing_m
                if kind in {"road", "sidewalk"}
                else config.sampling.ground_spacing_m
            )
            if spacing < wanted_spacing and rng.random() > (spacing / wanted_spacing) ** 2:
                continue

            cls = POINT_CLASSES[kind]
            y = terrain_height(config.seed, config.terrain, sx, sz)
            points.append(Point(sx, y, sz, *cls.color, cls.id))

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
    roof = building.roof or default_flat_roof(building.footprint, building.roof_y)
    for x in _grid_values(bbox.min_x, bbox.max_x, spacing):
        for z in _grid_values(bbox.min_z, bbox.max_z, spacing):
            sx = _clamp(
                x + _jitter(rng, spacing, config.sampling.jitter_ratio),
                bbox.min_x,
                bbox.max_x,
            )
            sz = _clamp(
                z + _jitter(rng, spacing, config.sampling.jitter_ratio),
                bbox.min_z,
                bbox.max_z,
            )
            if not building.footprint.contains_xy(sx, sz):
                continue
            points.append(Point(sx, roof.height_at(sx, sz, building.footprint), sz, *cls.color, cls.id))
    return points


def _sample_facades(config: CityGenConfig, building: Building, spacing: float, rng) -> list[Point]:
    cls = POINT_CLASSES["building_facade"]
    points: list[Point] = []
    eave_y = building.eave_y
    verticals = list(_grid_values(building.base_y, eave_y, spacing))
    for segment in building.footprint.boundary_segments():
        length = segment.length
        if length == 0:
            continue
        for offset in _grid_values(0.0, length, spacing):
            for y in verticals:
                jo = _jitter(rng, spacing, config.sampling.jitter_ratio)
                jy = _jitter(rng, spacing, config.sampling.jitter_ratio)
                along = _clamp(offset + jo, 0.0, length)
                t = along / length
                sx = segment.x0 + (segment.x1 - segment.x0) * t
                sz = segment.z0 + (segment.z1 - segment.z0) * t
                yy = _clamp(y + jy, building.base_y, eave_y)
                points.append(Point(sx, yy, sz, *cls.color, cls.id))
    return points


def _crop_points(points: Iterable[Point], bbox: Rect) -> list[Point]:
    return [point for point in points if bbox.contains_xy(point.x, point.z)]


def _inside_any_building(buildings: list[Building], x: float, z: float) -> bool:
    return any(building.footprint.contains_xy(x, z) for building in buildings)


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
