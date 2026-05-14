from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable

from .biomes import biome_params, classify_biome, sample_biome_counts
from .config import CityGenConfig
from .fences import FenceSegment, build_fences, fence_counts
from .fields import sample_urban_fields
from .footprints import build_footprint, select_footprint_kind
from .geometry import BBox, Building, OrientedRect, Rect, normalize_degrees, stable_rng, terrain_height
from .parcels import Block, Parcel, build_blocks_and_parcels, parcel_counts
from .roads import RoadNetworkLike, build_road_network
from .roofs import build_roof, select_roof_kind
from .trees import Tree, build_trees, tree_counts
from .vehicles import Vehicle, build_vehicles, vehicle_counts
from .worldgen import WorldgenContext, create_worldgen_context, pipeline_stage_ids


ProgressCallback = Callable[[str, str, dict[str, Any] | None], None]


@dataclass(frozen=True)
class Scene:
    bbox: BBox
    work_bbox: BBox
    road_network: RoadNetworkLike
    buildings: list[Building]
    biome_counts: dict[str, int]
    road_models: tuple[str, ...]
    blocks: tuple[Block, ...]
    parcels: tuple[Parcel, ...]
    parcel_counts: dict
    fences: tuple[FenceSegment, ...]
    fence_counts: dict
    trees: tuple[Tree, ...]
    tree_counts: dict
    vehicles: tuple[Vehicle, ...]
    vehicle_counts: dict
    context: WorldgenContext
    worldgen_stages: tuple[str, ...]


def generate_scene(config: CityGenConfig, progress: ProgressCallback | None = None) -> Scene:
    _emit_progress(progress, "worldgen_context", "started")
    context = create_worldgen_context(config)
    bbox = context.bbox
    work_bbox = context.work_bbox
    _emit_progress(
        progress,
        "worldgen_context",
        "done",
        {
            "tile": f"{config.tile.x},{config.tile.y}",
            "bbox": f"{bbox.min_x:.1f},{bbox.min_y:.1f},{bbox.max_x:.1f},{bbox.max_y:.1f}",
            "margin_m": config.tile.margin_m,
        },
    )

    _emit_progress(progress, "roads", "started")
    road_network = build_road_network(config, work_bbox)
    _emit_progress(
        progress,
        "roads",
        "done",
        {
            "road_primitives": len(road_network.primitives),
            "road_models": ",".join(road_network.effective_models),
        },
    )

    _emit_progress(progress, "parcels", "started")
    blocks, parcels = (
        build_blocks_and_parcels(config, work_bbox, road_network)
        if config.parcels.enabled
        else ((), ())
    )
    _emit_progress(
        progress,
        "parcels",
        "done",
        {
            "blocks": len(blocks),
            "parcels": len(parcels),
            "enabled": config.parcels.enabled,
        },
    )

    _emit_progress(progress, "objects", "started")
    buildings = _build_scene_buildings(config, work_bbox, road_network, parcels)
    _emit_progress(
        progress,
        "objects",
        "done",
        {
            "buildings": len(buildings),
            "enabled": config.buildings.enabled,
        },
    )

    _emit_progress(progress, "fences", "started")
    fences = build_fences(config, parcels, buildings, road_network)
    fence_summary = fence_counts(fences)
    _emit_progress(
        progress,
        "fences",
        "done",
        {
            "fence_segments": fence_summary["segments"],
            "foundation_segments": fence_summary["foundation_segments"],
            "gate_openings": fence_summary["gate_openings"],
            "enabled": config.fences.enabled,
        },
    )

    _emit_progress(progress, "trees", "started")
    trees = build_trees(config, bbox, road_network, buildings, fences)
    tree_summary = tree_counts(trees)
    _emit_progress(
        progress,
        "trees",
        "done",
        {
            "trees": tree_summary["total"],
            "enabled": config.trees.enabled,
            "by_crown_shape": tree_summary["by_crown_shape"],
            "by_biome": tree_summary["by_biome"],
        },
    )

    _emit_progress(progress, "vehicles", "started")
    vehicles = build_vehicles(config, bbox, road_network, buildings, fences, trees, parcels)
    vehicle_summary = vehicle_counts(vehicles)
    _emit_progress(
        progress,
        "vehicles",
        "done",
        {
            "vehicles": vehicle_summary["total"],
            "enabled": config.vehicles.enabled,
            "by_type": vehicle_summary["by_type"],
            "by_placement_mode": vehicle_summary["by_placement_mode"],
            "by_biome": vehicle_summary["by_biome"],
        },
    )

    biome_step = max(32.0, config.tile.size_m / 8.0)
    biome_counts = sample_biome_counts(config.seed, config.urban_fields, bbox, biome_step)
    return Scene(
        bbox=bbox,
        work_bbox=work_bbox,
        road_network=road_network,
        buildings=buildings,
        biome_counts=biome_counts,
        road_models=road_network.effective_models,
        blocks=blocks,
        parcels=parcels,
        parcel_counts=parcel_counts(blocks, parcels, buildings),
        fences=fences,
        fence_counts=fence_summary,
        trees=trees,
        tree_counts=tree_summary,
        vehicles=vehicles,
        vehicle_counts=vehicle_summary,
        context=context,
        worldgen_stages=pipeline_stage_ids(),
    )


def surface_kind(config: CityGenConfig, scene: Scene, x: float, y: float) -> str:
    return scene.road_network.surface_kind(config, x, y)


def _build_scene_buildings(
    config: CityGenConfig,
    work_bbox: BBox,
    road_network: RoadNetworkLike,
    parcels: tuple[Parcel, ...],
) -> list[Building]:
    if not config.buildings.enabled:
        return []
    if config.parcels.enabled:
        return _generate_buildings_from_parcels(config, parcels, road_network)
    return _generate_buildings(config, work_bbox, road_network)


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

            if not _footprint_is_clear(road_network, footprint, setback):
                continue
            if _overlaps_existing(result, footprint, min(setback, 4.0)):
                continue

            result.append(_build_building(config, f"building_{ix}_{iy}", footprint, biome, fields, params, rng))

    result.sort(key=lambda item: item.id)
    return result


def _generate_buildings_from_parcels(
    config: CityGenConfig,
    parcels: tuple[Parcel, ...],
    road_network: RoadNetworkLike,
) -> list[Building]:
    buildings_cfg = config.buildings
    result: list[Building] = []
    for parcel in parcels:
        if not parcel.buildable:
            continue
        rng = stable_rng(config.seed, "parcel-building", parcel.id)
        biome = parcel.biome
        params = biome_params(biome)
        fields = sample_urban_fields(config.seed, config.urban_fields, parcel.center_x, parcel.center_y)
        probability = min(0.98, params.build_probability * 1.08)
        if config.urban_fields.enabled:
            probability = min(0.98, probability * (0.74 + fields.density * 0.52))
        if rng.random() > probability:
            continue

        setback = max(0.5, buildings_cfg.setback_m * params.setback_scale * 0.35)
        buildable_area = parcel.buildable_geometry.inset(setback)
        if buildable_area is None:
            continue
        max_fit = min(buildable_area.width, buildable_area.depth)
        coverage_fit = math.sqrt(buildable_area.area_m2 * config.parcels.max_building_coverage)
        min_fp = max(4.0, buildings_cfg.footprint_min_m * params.footprint_scale * 0.82)
        max_fp = min(max_fit, coverage_fit, buildings_cfg.footprint_max_m * params.footprint_scale)
        if max_fp < min_fp:
            min_fp = max(4.0, min(max_fp, max_fit))
        if max_fp < 4.0 or min_fp > max_fp:
            continue

        footprint_kind = select_footprint_kind(buildings_cfg.footprint, rng)
        orientation = _parcel_building_orientation(config, parcel)
        footprint = build_footprint(
            footprint_kind,
            buildable_area.center_x,
            buildable_area.center_y,
            min_fp,
            max_fp,
            buildings_cfg.footprint,
            rng,
        ).with_orientation(
            orientation,
            (buildable_area.center_x, buildable_area.center_y),
        )
        if config.parcels.require_building_inside_buildable_area and not _footprint_within_oriented_rect(
            footprint,
            buildable_area,
        ):
            fallback_rng = stable_rng(config.seed, "parcel-building-fallback", parcel.id)
            footprint = build_footprint(
                "rectangle",
                buildable_area.center_x,
                buildable_area.center_y,
                min_fp,
                max_fp,
                buildings_cfg.footprint,
                fallback_rng,
            ).with_orientation(
                orientation,
                (buildable_area.center_x, buildable_area.center_y),
            )
            if not _footprint_within_oriented_rect(footprint, buildable_area):
                continue

        if not _footprint_is_clear(road_network, footprint, max(0.5, setback)):
            continue
        if _overlaps_existing(result, footprint, min(setback, 4.0)):
            continue

        result.append(
            _build_building(
                config,
                f"building_{parcel.id}",
                footprint,
                biome,
                fields,
                params,
                rng,
                parcel_id=parcel.id,
                orientation_degrees=orientation,
            )
        )

    result.sort(key=lambda item: item.id)
    return result


def _build_building(
    config: CityGenConfig,
    building_id: str,
    footprint,
    biome: str,
    fields,
    params,
    rng,
    parcel_id: str | None = None,
    orientation_degrees: float | None = None,
) -> Building:
    buildings_cfg = config.buildings
    min_height = buildings_cfg.min_height_m * params.height_min_multiplier
    max_height = buildings_cfg.max_height_m * params.height_max_multiplier
    if config.urban_fields.enabled:
        max_height *= 0.72 + fields.height_potential * 0.72
    max_height = max(min_height, max_height)
    height = rng.uniform(min_height, max_height)
    base_z = terrain_height(config.seed, config.terrain, footprint.center_x, footprint.center_y)
    roof_kind = select_roof_kind(buildings_cfg.roof, rng)
    roof = build_roof(roof_kind, footprint, base_z, base_z + height, buildings_cfg.roof, rng)
    return Building(
        id=building_id,
        footprint=footprint,
        height_m=height,
        base_z=base_z,
        biome=biome,
        roof=roof,
        parcel_id=parcel_id,
        orientation_degrees=footprint.orientation_degrees if orientation_degrees is None else orientation_degrees,
    )


def _footprint_is_clear(road_network: RoadNetworkLike, footprint, clearance_m: float) -> bool:
    return all(
        road_network.nearest_hardscape_distance(x, y) > clearance_m
        for x, y in footprint.clearance_sample_points()
    )


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


def _footprint_within_rect(footprint, rect: Rect) -> bool:
    bbox = footprint.bbox
    if (
        bbox.min_x < rect.min_x
        or bbox.max_x > rect.max_x
        or bbox.min_y < rect.min_y
        or bbox.max_y > rect.max_y
    ):
        return False
    return all(rect.contains_xy(x, y) for x, y in footprint.clearance_sample_points())


def _footprint_within_oriented_rect(footprint, rect: OrientedRect) -> bool:
    if not _rects_overlap(footprint.bbox, rect.bbox):
        return False
    return all(rect.contains_xy(x, y) for x, y in footprint.clearance_sample_points())


def _parcel_building_orientation(config: CityGenConfig, parcel: Parcel) -> float:
    if config.parcels.building_alignment == "global":
        base = 0.0
    else:
        base = parcel.orientation_degrees
    jitter = config.parcels.orientation_jitter_degrees
    if jitter <= 0:
        return normalize_degrees(base)
    rng = stable_rng(config.seed, "parcel-building-orientation", parcel.id)
    return normalize_degrees(base + rng.uniform(-jitter, jitter))


def _inset_rect(rect: Rect, inset: float) -> Rect | None:
    if inset <= 0:
        return rect
    inner = Rect(rect.min_x + inset, rect.min_y + inset, rect.max_x - inset, rect.max_y - inset)
    if inner.width <= 0 or inner.depth <= 0:
        return None
    return inner


def _rects_overlap(a: Rect, b: Rect) -> bool:
    return not (
        a.max_x < b.min_x
        or a.min_x > b.max_x
        or a.max_y < b.min_y
        or a.min_y > b.max_y
    )


def _emit_progress(
    progress: ProgressCallback | None,
    stage: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    if progress is not None:
        progress(stage, status, details)
