from __future__ import annotations

from dataclasses import dataclass
import math

from .config import UrbanFieldsConfig
from .fields import sample_urban_fields
from .geometry import BBox


@dataclass(frozen=True)
class BiomeParams:
    name: str
    build_probability: float
    footprint_scale: float
    height_min_multiplier: float
    height_max_multiplier: float
    setback_scale: float
    preferred_road_model: str


BIOME_PARAMS: dict[str, BiomeParams] = {
    "downtown": BiomeParams(
        name="downtown",
        build_probability=0.94,
        footprint_scale=1.08,
        height_min_multiplier=1.45,
        height_max_multiplier=1.75,
        setback_scale=0.65,
        preferred_road_model="radial_ring",
    ),
    "residential": BiomeParams(
        name="residential",
        build_probability=0.78,
        footprint_scale=0.92,
        height_min_multiplier=0.85,
        height_max_multiplier=0.82,
        setback_scale=1.0,
        preferred_road_model="grid",
    ),
    "industrial": BiomeParams(
        name="industrial",
        build_probability=0.64,
        footprint_scale=1.45,
        height_min_multiplier=0.9,
        height_max_multiplier=0.75,
        setback_scale=0.85,
        preferred_road_model="linear",
    ),
    "suburb": BiomeParams(
        name="suburb",
        build_probability=0.38,
        footprint_scale=0.72,
        height_min_multiplier=0.55,
        height_max_multiplier=0.45,
        setback_scale=1.45,
        preferred_road_model="organic",
    ),
}


def classify_biome(seed: int, config: UrbanFieldsConfig, x: float, y: float) -> str:
    if not config.enabled:
        return "residential"

    fields = sample_urban_fields(seed, config, x, y)
    if fields.centrality >= 0.68 and fields.density >= 0.58:
        return "downtown"
    if fields.industrialness >= 0.58 and fields.centrality <= 0.78:
        return "industrial"
    if fields.density <= 0.38 or (fields.green_index >= 0.68 and fields.centrality <= 0.55):
        return "suburb"
    return "residential"


def biome_params(name: str) -> BiomeParams:
    return BIOME_PARAMS.get(name, BIOME_PARAMS["residential"])


def preferred_road_model_for_biome(name: str) -> str:
    return biome_params(name).preferred_road_model


def sample_biome_counts(seed: int, config: UrbanFieldsConfig, bbox: BBox, step_m: float) -> dict[str, int]:
    counts: dict[str, int] = {}
    x_count = max(1, int(math.floor(bbox.width / step_m)) + 1)
    y_count = max(1, int(math.floor(bbox.depth / step_m)) + 1)
    for ix in range(x_count):
        x = min(bbox.min_x + ix * step_m, bbox.max_x)
        for iy in range(y_count):
            y = min(bbox.min_y + iy * step_m, bbox.max_y)
            name = classify_biome(seed, config, x, y)
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))
