from __future__ import annotations

from dataclasses import dataclass
import math

from .biomes import biome_params, classify_biome, sample_biome_counts
from .config import CityGenConfig
from .fields import sample_urban_fields
from .footprints import build_footprint, select_footprint_kind
from .geometry import BBox, Building, Rect, stable_rng, terrain_height, tile_bbox
from .roads import RoadNetworkLike, build_road_network
from .roofs import build_roof, select_roof_kind


@dataclass(frozen=True)
class Scene:
    bbox: BBox
    work_bbox: BBox
    road_network: RoadNetworkLike
    buildings: list[Building]
    biome_counts: dict[str, int]
    road_models: tuple[str, ...]


def generate_scene(config: CityGenConfig) -> Scene:
    bbox = tile_bbox(config.tile.x, config.tile.y, config.tile.size_m)
    work_bbox = bbox.expand(config.tile.margin_m)
    road_network = build_road_network(config, work_bbox)
    buildings = _generate_buildings(config, work_bbox, road_network) if config.buildings.enabled else []
    biome_step = max(32.0, config.tile.size_m / 8.0)
    biome_counts = sample_biome_counts(config.seed, config.urban_fields, bbox, biome_step)
    return Scene(
        bbox=bbox,
        work_bbox=work_bbox,
        road_network=road_network,
        buildings=buildings,
        biome_counts=biome_counts,
        road_models=road_network.effective_models,
    )


def surface_kind(config: CityGenConfig, scene: Scene, x: float, y: float) -> str:
    return scene.road_network.surface_kind(config, x, y)


def _generate_buildings(
    config: CityGenConfig,
    work_bbox: BBox,
    road_network: RoadNetworkLike,
) -> list[Building]:
    buildings_cfg = config.buildings
    candidate_step = max(12.0, config.roads.spacing_m * 0.34, buildings_cfg.footprint_min_m * 1.25)
    start_i = math.floor(work_bbox.min_x / candidate_step) - 1
    end_i = math.ceil(work_bbox.max_x / candidate_step) + 1
    start_y = math.floor(work_bbox.min_y / candidate_step) - 1
    end_y = math.ceil(work_bbox.max_y / candidate_step) + 1
    result: list[Building] = []

    for ix in range(start_i, end_i):
        for iy in range(start_y, end_y):
            rng = stable_rng(config.seed, "building", ix, iy)
            center_x = (ix + 0.5) * candidate_step + rng.uniform(
                -candidate_step * 0.32,
                candidate_step * 0.32,
            )
            center_y = (iy + 0.5) * candidate_step + rng.uniform(
                -candidate_step * 0.32,
                candidate_step * 0.32,
            )
            if not work_bbox.contains_xy(center_x, center_y):
                continue

            biome = classify_biome(config.seed, config.urban_fields, center_x, center_y)
            params = biome_params(biome)
            fields = sample_urban_fields(config.seed, config.urban_fields, center_x, center_y)
            probability = params.build_probability
            if config.urban_fields.enabled:
                probability = min(0.97, probability * (0.72 + fields.density * 0.55))
            if rng.random() > probability:
                continue

            setback = max(1.0, buildings_cfg.setback_m * params.setback_scale)
            min_fp = max(4.0, buildings_cfg.footprint_min_m * params.footprint_scale)
            max_fp = max(min_fp, buildings_cfg.footprint_max_m * params.footprint_scale)
            footprint_kind = select_footprint_kind(buildings_cfg.footprint, rng)
            footprint = build_footprint(
                footprint_kind,
                center_x,
                center_y,
                min_fp,
                max_fp,
                buildings_cfg.footprint,
                rng,
            )
            if not footprint.intersects(work_bbox):
                continue

            clearance = config.roads.width_m * 0.5 + config.roads.sidewalk_width_m + setback
            if not _footprint_is_clear(road_network, footprint, clearance):
                continue
            if _overlaps_existing(result, footprint, min(setback, 4.0)):
                continue

            min_height = buildings_cfg.min_height_m * params.height_min_multiplier
            max_height = buildings_cfg.max_height_m * params.height_max_multiplier
            if config.urban_fields.enabled:
                max_height *= 0.72 + fields.height_potential * 0.72
            max_height = max(min_height, max_height)
            height = rng.uniform(min_height, max_height)
            base_z = terrain_height(config.seed, config.terrain, footprint.center_x, footprint.center_y)
            roof_kind = select_roof_kind(buildings_cfg.roof, rng)
            roof = build_roof(roof_kind, footprint, base_z, base_z + height, buildings_cfg.roof, rng)
            result.append(
                Building(
                    id=f"building_{ix}_{iy}",
                    footprint=footprint,
                    height_m=height,
                    base_z=base_z,
                    biome=biome,
                    roof=roof,
                )
            )

    result.sort(key=lambda item: item.id)
    return result


def _footprint_is_clear(road_network: RoadNetworkLike, footprint, clearance_m: float) -> bool:
    return all(road_network.nearest_distance(x, y) > clearance_m for x, y in footprint.clearance_sample_points())


def _overlaps_existing(buildings: list[Building], footprint, clearance: float) -> bool:
    expanded = Rect(
        footprint.bbox.min_x - clearance,
        footprint.bbox.min_y - clearance,
        footprint.bbox.max_x + clearance,
        footprint.bbox.max_y + clearance,
    )
    # This remains deliberately conservative: a bbox-level post-filter keeps complex
    # footprints from visibly intersecting without pulling in a full geometry engine.
    return any(_rects_overlap(existing.footprint.bbox, expanded) for existing in buildings)


def _rects_overlap(a: Rect, b: Rect) -> bool:
    return not (
        a.max_x < b.min_x
        or a.min_x > b.max_x
        or a.max_y < b.min_y
        or a.min_y > b.max_y
    )
