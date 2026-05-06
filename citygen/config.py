from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a YAML config is missing fields or has invalid values."""


SUPPORTED_ROAD_MODELS = {
    "grid",
    "radial_ring",
    "radial",
    "linear",
    "organic",
    "mixed",
    "free",
}


SUPPORTED_FOOTPRINT_MODELS = {
    "rectangle",
    "square",
    "circle",
    "slab",
    "courtyard",
    "l_shape",
    "u_shape",
    "t_shape",
    "mixed",
}

SUPPORTED_CONCRETE_FOOTPRINT_MODELS = SUPPORTED_FOOTPRINT_MODELS - {"mixed"}

FOOTPRINT_MODEL_ALIASES = {
    "rotunda": "circle",
    "perimeter": "courtyard",
    "strip": "slab",
    "plate": "slab",
    "g_shape": "l_shape",
    "p_shape": "u_shape",
}

DEFAULT_MIXED_FOOTPRINT_WEIGHTS = {
    "rectangle": 0.30,
    "square": 0.10,
    "circle": 0.08,
    "slab": 0.12,
    "courtyard": 0.12,
    "l_shape": 0.10,
    "u_shape": 0.10,
    "t_shape": 0.08,
}


SUPPORTED_ROOF_MODELS = {
    "flat",
    "shed",
    "gable",
    "hip",
    "half_hip",
    "pyramid",
    "mansard",
    "dome",
    "barrel",
    "cone",
    "mixed",
}

SUPPORTED_CONCRETE_ROOF_MODELS = SUPPORTED_ROOF_MODELS - {"mixed"}

ROOF_MODEL_ALIASES = {
    "single_slope": "shed",
    "mono_pitch": "shed",
    "dual_pitch": "gable",
    "pitched": "gable",
    "hipped": "hip",
    "half_hipped": "half_hip",
    "tent": "pyramid",
    "vault": "barrel",
    "arched": "barrel",
    "conical": "cone",
}

DEFAULT_MIXED_ROOF_WEIGHTS = {
    "flat": 0.22,
    "shed": 0.10,
    "gable": 0.16,
    "hip": 0.14,
    "half_hip": 0.08,
    "pyramid": 0.08,
    "mansard": 0.08,
    "dome": 0.06,
    "barrel": 0.04,
    "cone": 0.04,
}


@dataclass(frozen=True)
class TileConfig:
    x: int = 0
    y: int = 0
    size_m: float = 256.0
    margin_m: float = 32.0


@dataclass(frozen=True)
class TerrainConfig:
    base_height_m: float = 0.0
    height_noise_m: float = 1.5


@dataclass(frozen=True)
class RoadsConfig:
    model: str = "grid"
    spacing_m: float = 64.0
    width_m: float = 10.0
    sidewalk_width_m: float = 3.0
    angle_degrees: float = 0.0
    radial_count: int = 12
    ring_spacing_m: float = 0.0
    organic_wander_m: float = 0.0


@dataclass(frozen=True)
class FootprintConfig:
    model: str = "rectangle"
    weights: dict[str, float] = field(default_factory=dict)
    circle_segments: int = 24
    courtyard_ratio: float = 0.45
    wing_width_ratio: float = 0.35
    min_part_width_m: float = 5.0
    align_to_roads: bool = True


@dataclass(frozen=True)
class RoofConfig:
    model: str = "flat"
    weights: dict[str, float] = field(default_factory=dict)
    pitch_degrees: float = 28.0
    pitch_jitter_degrees: float = 8.0
    flat_slope_degrees: float = 0.0
    eave_overhang_m: float = 0.0
    ridge_height_ratio: float = 0.35
    mansard_break_ratio: float = 0.45
    dome_segments: int = 16
    align_to_long_axis: bool = True


@dataclass(frozen=True)
class BuildingsConfig:
    enabled: bool = True
    min_height_m: float = 8.0
    max_height_m: float = 60.0
    setback_m: float = 6.0
    footprint_min_m: float = 12.0
    footprint_max_m: float = 36.0
    footprint: FootprintConfig = field(default_factory=FootprintConfig)
    roof: RoofConfig = field(default_factory=RoofConfig)


@dataclass(frozen=True)
class SamplingConfig:
    mode: str = "surface"
    ground_spacing_m: float = 2.0
    road_spacing_m: float = 1.5
    building_spacing_m: float = 2.0
    jitter_ratio: float = 0.18


@dataclass(frozen=True)
class OutputConfig:
    format: str = "ply"
    include_rgb: bool = True
    include_class: bool = True


@dataclass(frozen=True)
class UrbanFieldsConfig:
    enabled: bool = False
    center_x: float = 0.0
    center_y: float = 0.0
    city_radius_m: float = 1200.0
    noise_scale_m: float = 350.0
    density_bias: float = 0.0
    industrial_bias: float = 0.0
    green_bias: float = 0.0


@dataclass(frozen=True)
class CityGenConfig:
    seed: int
    tile: TileConfig = TileConfig()
    terrain: TerrainConfig = TerrainConfig()
    roads: RoadsConfig = RoadsConfig()
    buildings: BuildingsConfig = BuildingsConfig()
    sampling: SamplingConfig = SamplingConfig()
    output: OutputConfig = OutputConfig()
    urban_fields: UrbanFieldsConfig = UrbanFieldsConfig()
    tiles: tuple[TileConfig, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path) -> CityGenConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config must be a YAML mapping.")
    if "seed" not in raw:
        raise ConfigError("Missing required field: seed")

    tile = _tile_config(_section(raw, "tile"))
    tiles = _tiles_config(raw.get("tiles"), tile)
    cfg = CityGenConfig(
        seed=_int(raw, "seed"),
        tile=tiles[0] if tiles else tile,
        terrain=_terrain_config(_section(raw, "terrain")),
        roads=_roads_config(_section(raw, "roads")),
        buildings=_buildings_config(_section(raw, "buildings")),
        sampling=_sampling_config(_section(raw, "sampling")),
        output=_output_config(_section(raw, "output")),
        urban_fields=_urban_fields_config(_section(raw, "urban_fields")),
        tiles=tiles,
    )
    _validate(cfg)
    return cfg


def iter_tile_configs(config: CityGenConfig) -> tuple[CityGenConfig, ...]:
    if not config.tiles:
        return (config,)
    return tuple(replace(config, tile=tile, tiles=()) for tile in config.tiles)


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"Section '{key}' must be a mapping.")
    return value


def _tile_config(raw: dict[str, Any]) -> TileConfig:
    defaults = TileConfig()
    return TileConfig(
        x=_int(raw, "x", defaults.x),
        y=_int(raw, "y", defaults.y),
        size_m=_float(raw, "size_m", defaults.size_m),
        margin_m=_float(raw, "margin_m", defaults.margin_m),
    )


def _tiles_config(raw: Any, base_tile: TileConfig) -> tuple[TileConfig, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise ConfigError("Section 'tiles' must be a mapping.")

    default_size = _float(raw, "size_m", base_tile.size_m)
    default_margin = _float(raw, "margin_m", base_tile.margin_m)
    tiles: list[TileConfig] = []

    if "items" in raw:
        items = raw["items"]
        if not isinstance(items, list):
            raise ConfigError("tiles.items must be a list.")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ConfigError(f"tiles.items[{index}] must be a mapping.")
            tiles.append(
                TileConfig(
                    x=_int(item, "x"),
                    y=_int(item, "y"),
                    size_m=_float(item, "size_m", default_size),
                    margin_m=_float(item, "margin_m", default_margin),
                )
            )
    elif "x_range" in raw or "y_range" in raw:
        x_start, x_stop = _int_range(raw, "x_range")
        y_start, y_stop = _int_range(raw, "y_range")
        for x in range(x_start, x_stop):
            for y in range(y_start, y_stop):
                tiles.append(TileConfig(x=x, y=y, size_m=default_size, margin_m=default_margin))
    else:
        raise ConfigError("tiles must define either 'items' or 'x_range' and 'y_range'.")

    if not tiles:
        raise ConfigError("tiles must contain at least one tile.")
    return tuple(tiles)


def _terrain_config(raw: dict[str, Any]) -> TerrainConfig:
    defaults = TerrainConfig()
    return TerrainConfig(
        base_height_m=_float(raw, "base_height_m", defaults.base_height_m),
        height_noise_m=_float(raw, "height_noise_m", defaults.height_noise_m),
    )


def _roads_config(raw: dict[str, Any]) -> RoadsConfig:
    defaults = RoadsConfig()
    return RoadsConfig(
        model=_str(raw, "model", defaults.model),
        spacing_m=_float(raw, "spacing_m", defaults.spacing_m),
        width_m=_float(raw, "width_m", defaults.width_m),
        sidewalk_width_m=_float(raw, "sidewalk_width_m", defaults.sidewalk_width_m),
        angle_degrees=_float(raw, "angle_degrees", defaults.angle_degrees),
        radial_count=_int(raw, "radial_count", defaults.radial_count),
        ring_spacing_m=_float(raw, "ring_spacing_m", defaults.ring_spacing_m),
        organic_wander_m=_float(raw, "organic_wander_m", defaults.organic_wander_m),
    )


def _buildings_config(raw: dict[str, Any]) -> BuildingsConfig:
    defaults = BuildingsConfig()
    return BuildingsConfig(
        enabled=_bool(raw, "enabled", defaults.enabled),
        min_height_m=_float(raw, "min_height_m", defaults.min_height_m),
        max_height_m=_float(raw, "max_height_m", defaults.max_height_m),
        setback_m=_float(raw, "setback_m", defaults.setback_m),
        footprint_min_m=_float(raw, "footprint_min_m", defaults.footprint_min_m),
        footprint_max_m=_float(raw, "footprint_max_m", defaults.footprint_max_m),
        footprint=_footprint_config(raw.get("footprint"), defaults.footprint),
        roof=_roof_config(raw.get("roof"), defaults.roof),
    )


def _footprint_config(raw: Any, defaults: FootprintConfig) -> FootprintConfig:
    if raw is None:
        return defaults
    if not isinstance(raw, dict):
        raise ConfigError("buildings.footprint must be a mapping.")

    model = _normalize_footprint_model(_str(raw, "model", defaults.model))
    weights = _footprint_weights(raw.get("weights"), model)
    return FootprintConfig(
        model=model,
        weights=weights,
        circle_segments=_int(raw, "circle_segments", defaults.circle_segments),
        courtyard_ratio=_float(raw, "courtyard_ratio", defaults.courtyard_ratio),
        wing_width_ratio=_float(raw, "wing_width_ratio", defaults.wing_width_ratio),
        min_part_width_m=_float(raw, "min_part_width_m", defaults.min_part_width_m),
        align_to_roads=_bool(raw, "align_to_roads", defaults.align_to_roads),
    )


def _footprint_weights(raw: Any, model: str) -> dict[str, float]:
    if raw is None:
        return dict(DEFAULT_MIXED_FOOTPRINT_WEIGHTS) if model == "mixed" else {}
    if not isinstance(raw, dict):
        raise ConfigError("buildings.footprint.weights must be a mapping.")

    weights: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ConfigError("buildings.footprint.weights keys must be strings.")
        canonical = _normalize_footprint_model(key)
        if canonical == "mixed":
            raise ConfigError("buildings.footprint.weights cannot contain 'mixed'.")
        if isinstance(value, bool):
            raise ConfigError(f"buildings.footprint.weights.{key} must be a number.")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"buildings.footprint.weights.{key} must be a number.") from exc
        weights[canonical] = weight
    return weights


def _roof_config(raw: Any, defaults: RoofConfig) -> RoofConfig:
    if raw is None:
        return defaults
    if not isinstance(raw, dict):
        raise ConfigError("buildings.roof must be a mapping.")

    model = _normalize_roof_model(_str(raw, "model", defaults.model))
    weights = _roof_weights(raw.get("weights"), model)
    return RoofConfig(
        model=model,
        weights=weights,
        pitch_degrees=_float(raw, "pitch_degrees", defaults.pitch_degrees),
        pitch_jitter_degrees=_float(raw, "pitch_jitter_degrees", defaults.pitch_jitter_degrees),
        flat_slope_degrees=_float(raw, "flat_slope_degrees", defaults.flat_slope_degrees),
        eave_overhang_m=_float(raw, "eave_overhang_m", defaults.eave_overhang_m),
        ridge_height_ratio=_float(raw, "ridge_height_ratio", defaults.ridge_height_ratio),
        mansard_break_ratio=_float(raw, "mansard_break_ratio", defaults.mansard_break_ratio),
        dome_segments=_int(raw, "dome_segments", defaults.dome_segments),
        align_to_long_axis=_bool(raw, "align_to_long_axis", defaults.align_to_long_axis),
    )


def _roof_weights(raw: Any, model: str) -> dict[str, float]:
    if raw is None:
        return dict(DEFAULT_MIXED_ROOF_WEIGHTS) if model == "mixed" else {}
    if not isinstance(raw, dict):
        raise ConfigError("buildings.roof.weights must be a mapping.")

    weights: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ConfigError("buildings.roof.weights keys must be strings.")
        canonical = _normalize_roof_model(key)
        if canonical == "mixed":
            raise ConfigError("buildings.roof.weights cannot contain 'mixed'.")
        if isinstance(value, bool):
            raise ConfigError(f"buildings.roof.weights.{key} must be a number.")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"buildings.roof.weights.{key} must be a number.") from exc
        weights[canonical] = weight
    return weights


def _sampling_config(raw: dict[str, Any]) -> SamplingConfig:
    defaults = SamplingConfig()
    return SamplingConfig(
        mode=_str(raw, "mode", defaults.mode),
        ground_spacing_m=_float(raw, "ground_spacing_m", defaults.ground_spacing_m),
        road_spacing_m=_float(raw, "road_spacing_m", defaults.road_spacing_m),
        building_spacing_m=_float(raw, "building_spacing_m", defaults.building_spacing_m),
        jitter_ratio=_float(raw, "jitter_ratio", defaults.jitter_ratio),
    )


def _output_config(raw: dict[str, Any]) -> OutputConfig:
    defaults = OutputConfig()
    return OutputConfig(
        format=_str(raw, "format", defaults.format),
        include_rgb=_bool(raw, "include_rgb", defaults.include_rgb),
        include_class=_bool(raw, "include_class", defaults.include_class),
    )


def _urban_fields_config(raw: dict[str, Any]) -> UrbanFieldsConfig:
    defaults = UrbanFieldsConfig()
    return UrbanFieldsConfig(
        enabled=_bool(raw, "enabled", defaults.enabled),
        center_x=_float(raw, "center_x", defaults.center_x),
        center_y=_float(raw, "center_y", defaults.center_y),
        city_radius_m=_float(raw, "city_radius_m", defaults.city_radius_m),
        noise_scale_m=_float(raw, "noise_scale_m", defaults.noise_scale_m),
        density_bias=_float(raw, "density_bias", defaults.density_bias),
        industrial_bias=_float(raw, "industrial_bias", defaults.industrial_bias),
        green_bias=_float(raw, "green_bias", defaults.green_bias),
    )


def _validate(cfg: CityGenConfig) -> None:
    for tile in (cfg.tile, *cfg.tiles):
        if tile.size_m <= 0:
            raise ConfigError("tile.size_m must be positive.")
        if tile.margin_m <= 0:
            raise ConfigError("tile.margin_m must be positive.")

    positive_fields = [
        ("roads.spacing_m", cfg.roads.spacing_m),
        ("roads.width_m", cfg.roads.width_m),
        ("roads.sidewalk_width_m", cfg.roads.sidewalk_width_m),
        ("buildings.min_height_m", cfg.buildings.min_height_m),
        ("buildings.max_height_m", cfg.buildings.max_height_m),
        ("buildings.setback_m", cfg.buildings.setback_m),
        ("buildings.footprint_min_m", cfg.buildings.footprint_min_m),
        ("buildings.footprint_max_m", cfg.buildings.footprint_max_m),
        ("buildings.footprint.min_part_width_m", cfg.buildings.footprint.min_part_width_m),
        ("buildings.roof.dome_segments", cfg.buildings.roof.dome_segments),
        ("sampling.ground_spacing_m", cfg.sampling.ground_spacing_m),
        ("sampling.road_spacing_m", cfg.sampling.road_spacing_m),
        ("sampling.building_spacing_m", cfg.sampling.building_spacing_m),
        ("urban_fields.city_radius_m", cfg.urban_fields.city_radius_m),
        ("urban_fields.noise_scale_m", cfg.urban_fields.noise_scale_m),
    ]
    for name, value in positive_fields:
        if value <= 0:
            raise ConfigError(f"{name} must be positive.")

    if cfg.roads.model not in SUPPORTED_ROAD_MODELS:
        supported = ", ".join(sorted(SUPPORTED_ROAD_MODELS))
        raise ConfigError(f"Unsupported roads.model='{cfg.roads.model}'. Supported models: {supported}.")
    if cfg.buildings.footprint.model not in SUPPORTED_FOOTPRINT_MODELS:
        supported = ", ".join(sorted(SUPPORTED_FOOTPRINT_MODELS))
        raise ConfigError(
            "Unsupported buildings.footprint.model="
            f"'{cfg.buildings.footprint.model}'. Supported models: {supported}."
        )
    for name, weight in cfg.buildings.footprint.weights.items():
        if name not in SUPPORTED_CONCRETE_FOOTPRINT_MODELS:
            supported = ", ".join(sorted(SUPPORTED_CONCRETE_FOOTPRINT_MODELS))
            raise ConfigError(
                f"Unsupported buildings.footprint.weights key='{name}'. "
                f"Supported footprint types: {supported}."
            )
        if weight < 0:
            raise ConfigError(f"buildings.footprint.weights.{name} must be >= 0.")
    if cfg.buildings.footprint.model == "mixed" and sum(cfg.buildings.footprint.weights.values()) <= 0:
        raise ConfigError("buildings.footprint.weights must have a positive sum for model='mixed'.")
    if cfg.buildings.footprint.circle_segments < 8:
        raise ConfigError("buildings.footprint.circle_segments must be >= 8.")
    if not 0 < cfg.buildings.footprint.courtyard_ratio < 0.8:
        raise ConfigError("buildings.footprint.courtyard_ratio must be between 0 and 0.8.")
    if not 0 < cfg.buildings.footprint.wing_width_ratio < 0.8:
        raise ConfigError("buildings.footprint.wing_width_ratio must be between 0 and 0.8.")
    if cfg.buildings.roof.model not in SUPPORTED_ROOF_MODELS:
        supported = ", ".join(sorted(SUPPORTED_ROOF_MODELS))
        raise ConfigError(
            "Unsupported buildings.roof.model="
            f"'{cfg.buildings.roof.model}'. Supported models: {supported}."
        )
    for name, weight in cfg.buildings.roof.weights.items():
        if name not in SUPPORTED_CONCRETE_ROOF_MODELS:
            supported = ", ".join(sorted(SUPPORTED_CONCRETE_ROOF_MODELS))
            raise ConfigError(
                f"Unsupported buildings.roof.weights key='{name}'. "
                f"Supported roof types: {supported}."
            )
        if weight < 0:
            raise ConfigError(f"buildings.roof.weights.{name} must be >= 0.")
    if cfg.buildings.roof.model == "mixed" and sum(cfg.buildings.roof.weights.values()) <= 0:
        raise ConfigError("buildings.roof.weights must have a positive sum for model='mixed'.")
    if not 0 <= cfg.buildings.roof.pitch_degrees <= 75:
        raise ConfigError("buildings.roof.pitch_degrees must be between 0 and 75.")
    if cfg.buildings.roof.pitch_jitter_degrees < 0:
        raise ConfigError("buildings.roof.pitch_jitter_degrees must be >= 0.")
    if not 0 <= cfg.buildings.roof.flat_slope_degrees <= 15:
        raise ConfigError("buildings.roof.flat_slope_degrees must be between 0 and 15.")
    if cfg.buildings.roof.eave_overhang_m < 0:
        raise ConfigError("buildings.roof.eave_overhang_m must be >= 0.")
    if not 0 < cfg.buildings.roof.ridge_height_ratio <= 0.8:
        raise ConfigError("buildings.roof.ridge_height_ratio must be between 0 and 0.8.")
    if not 0.1 <= cfg.buildings.roof.mansard_break_ratio <= 0.9:
        raise ConfigError("buildings.roof.mansard_break_ratio must be between 0.1 and 0.9.")
    if cfg.buildings.roof.dome_segments < 8:
        raise ConfigError("buildings.roof.dome_segments must be >= 8.")
    if cfg.roads.radial_count < 3:
        raise ConfigError("roads.radial_count must be >= 3.")
    if cfg.roads.ring_spacing_m < 0:
        raise ConfigError("roads.ring_spacing_m must be >= 0.")
    if cfg.roads.organic_wander_m < 0:
        raise ConfigError("roads.organic_wander_m must be >= 0.")
    if cfg.sampling.mode != "surface":
        raise ConfigError("Only sampling.mode='surface' is supported in the MVP.")
    if cfg.output.format != "ply":
        raise ConfigError("Only output.format='ply' is supported in the MVP.")
    if cfg.buildings.max_height_m < cfg.buildings.min_height_m:
        raise ConfigError("buildings.max_height_m must be >= buildings.min_height_m.")
    if cfg.buildings.footprint_max_m < cfg.buildings.footprint_min_m:
        raise ConfigError("buildings.footprint_max_m must be >= buildings.footprint_min_m.")
    if cfg.roads.width_m + 2 * cfg.roads.sidewalk_width_m >= cfg.roads.spacing_m:
        raise ConfigError("Road width plus sidewalks must be smaller than road spacing.")
    if not 0 <= cfg.sampling.jitter_ratio <= 0.45:
        raise ConfigError("sampling.jitter_ratio must be between 0 and 0.45.")


def _int_range(raw: dict[str, Any], key: str) -> tuple[int, int]:
    value = raw.get(key)
    if (
        not isinstance(value, list)
        or len(value) != 2
        or isinstance(value[0], bool)
        or isinstance(value[1], bool)
    ):
        raise ConfigError(f"tiles.{key} must be a two-item integer list.")
    try:
        start = int(value[0])
        stop = int(value[1])
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"tiles.{key} must be a two-item integer list.") from exc
    if stop <= start:
        raise ConfigError(f"tiles.{key} stop must be greater than start.")
    return start, stop


def _int(raw: dict[str, Any], key: str, default: int | None = None) -> int:
    value = raw.get(key, default)
    if value is None:
        raise ConfigError(f"Missing required integer field: {key}")
    if isinstance(value, bool):
        raise ConfigError(f"{key} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be an integer.") from exc


def _float(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key, default)
    if isinstance(value, bool):
        raise ConfigError(f"{key} must be a number.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be a number.") from exc


def _str(raw: dict[str, Any], key: str, default: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{key} must be a string.")
    return value


def _bool(raw: dict[str, Any], key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be true or false.")
    return value


def _normalize_footprint_model(value: str) -> str:
    return FOOTPRINT_MODEL_ALIASES.get(value, value)


def _normalize_roof_model(value: str) -> str:
    return ROOF_MODEL_ALIASES.get(value, value)
