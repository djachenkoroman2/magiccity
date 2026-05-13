from __future__ import annotations

from dataclasses import dataclass

from .catalogs import WORLDGEN_STAGES, WorldgenCatalogs, resolve_catalogs, worldgen_summary
from .config import CityGenConfig, TileConfig
from .geometry import BBox, tile_bbox


@dataclass(frozen=True)
class WorldgenContext:
    config: CityGenConfig
    catalogs: WorldgenCatalogs
    seed: int
    tile: TileConfig
    bbox: BBox
    work_bbox: BBox


def create_worldgen_context(config: CityGenConfig) -> WorldgenContext:
    bbox = tile_bbox(config.tile.x, config.tile.y, config.tile.size_m)
    return WorldgenContext(
        config=config,
        catalogs=resolve_catalogs(),
        seed=config.seed,
        tile=config.tile,
        bbox=bbox,
        work_bbox=bbox.expand(config.tile.margin_m),
    )


def pipeline_stage_ids() -> tuple[str, ...]:
    return WORLDGEN_STAGES


def pipeline_metadata() -> dict:
    return worldgen_summary()
