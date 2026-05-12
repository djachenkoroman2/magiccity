from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from .catalogs import (
    BIOME_DEFINITIONS,
    DEFAULT_MIXED_FOOTPRINT_WEIGHTS,
    DEFAULT_MIXED_ROOF_WEIGHTS,
    DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS,
    DEFAULT_ROAD_PROFILE_MODEL_WEIGHTS,
    FOOTPRINT_DEFINITIONS,
    FOOTPRINT_MODEL_ALIASES,
    ROAD_MODEL_DEFINITIONS,
    ROOF_DEFINITIONS,
    ROOF_MODEL_ALIASES,
    validate_catalogs,
)


class ConfigError(ValueError):
    """Raised when a YAML config is missing fields or has invalid values."""


SUPPORTED_ROAD_MODELS = set(ROAD_MODEL_DEFINITIONS)
SUPPORTED_BIOMES = set(BIOME_DEFINITIONS)

SUPPORTED_FOOTPRINT_MODELS = set(FOOTPRINT_DEFINITIONS) | {"mixed"}

SUPPORTED_CONCRETE_FOOTPRINT_MODELS = SUPPORTED_FOOTPRINT_MODELS - {"mixed"}

SUPPORTED_ROOF_MODELS = set(ROOF_DEFINITIONS) | {"mixed"}

SUPPORTED_CONCRETE_ROOF_MODELS = SUPPORTED_ROOF_MODELS - {"mixed"}


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
class RoadProfileConfig:
    carriageway_width_m: float
    sidewalk_width_m: float
    median_width_m: float = 0.0

    @property
    def total_corridor_width_m(self) -> float:
        return self.carriageway_width_m + self.median_width_m + 2.0 * self.sidewalk_width_m

    @property
    def hardscape_half_width_m(self) -> float:
        return self.total_corridor_width_m * 0.5


@dataclass(frozen=True)
class RoadProfilesConfig:
    enabled: bool = False
    default: str = "default"
    definitions: dict[str, RoadProfileConfig] = field(default_factory=dict)
    model_weights: dict[str, dict[str, float]] = field(default_factory=dict)
    biome_weights: dict[str, dict[str, float]] = field(default_factory=dict)


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
    profiles: RoadProfilesConfig = field(default_factory=RoadProfilesConfig)

    @property
    def default_profile(self) -> RoadProfileConfig:
        profile = self.profiles.definitions.get(self.profiles.default)
        if profile is not None:
            return profile
        return RoadProfileConfig(
            carriageway_width_m=self.width_m,
            sidewalk_width_m=self.sidewalk_width_m,
            median_width_m=0.0,
        )


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
class ParcelsConfig:
    enabled: bool = False
    block_size_m: float = 96.0
    block_jitter_m: float = 8.0
    min_block_size_m: float = 32.0
    min_parcel_width_m: float = 14.0
    max_parcel_width_m: float = 42.0
    min_parcel_depth_m: float = 18.0
    max_parcel_depth_m: float = 56.0
    parcel_setback_m: float = 2.0
    split_jitter_ratio: float = 0.18
    max_subdivision_depth: int = 3
    building_alignment: str = "parcel"
    orientation_jitter_degrees: float = 0.0
    max_building_coverage: float = 0.72
    require_building_inside_buildable_area: bool = True
    oriented_blocks: bool = False
    block_orientation_source: str = "road_model"
    block_orientation_jitter_degrees: float = 0.0
    organic_orientation_jitter_degrees: float = 10.0


@dataclass(frozen=True)
class WorldgenConfig:
    catalog_docs: bool = True
    strict_catalog_validation: bool = True


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
    parcels: ParcelsConfig = ParcelsConfig()
    worldgen: WorldgenConfig = WorldgenConfig()
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
        parcels=_parcels_config(_section(raw, "parcels")),
        worldgen=_worldgen_config(_section(raw, "worldgen")),
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
    width_m = _float(raw, "width_m", defaults.width_m)
    sidewalk_width_m = _float(raw, "sidewalk_width_m", defaults.sidewalk_width_m)
    return RoadsConfig(
        model=_str(raw, "model", defaults.model),
        spacing_m=_float(raw, "spacing_m", defaults.spacing_m),
        width_m=width_m,
        sidewalk_width_m=sidewalk_width_m,
        angle_degrees=_float(raw, "angle_degrees", defaults.angle_degrees),
        radial_count=_int(raw, "radial_count", defaults.radial_count),
        ring_spacing_m=_float(raw, "ring_spacing_m", defaults.ring_spacing_m),
        organic_wander_m=_float(raw, "organic_wander_m", defaults.organic_wander_m),
        profiles=_road_profiles_config(raw.get("profiles"), width_m, sidewalk_width_m),
    )


def _road_profiles_config(raw: Any, width_m: float, sidewalk_width_m: float) -> RoadProfilesConfig:
    if raw is None:
        return RoadProfilesConfig(
            enabled=False,
            default="default",
            definitions={
                "default": RoadProfileConfig(
                    carriageway_width_m=width_m,
                    sidewalk_width_m=sidewalk_width_m,
                    median_width_m=0.0,
                )
            },
        )
    if not isinstance(raw, dict):
        raise ConfigError("roads.profiles must be a mapping.")

    supported = {
        "enabled",
        "default",
        "definitions",
        "model_weights",
        "biome_weights",
    }
    for key in raw:
        if key not in supported:
            fields = ", ".join(sorted(supported))
            raise ConfigError(f"Unsupported roads.profiles.{key}. Supported fields: {fields}.")

    enabled = _bool(raw, "enabled", False)
    definitions = _default_road_profile_definitions(width_m, sidewalk_width_m)
    definitions.update(_road_profile_definitions(raw.get("definitions")))
    return RoadProfilesConfig(
        enabled=enabled,
        default=_str(raw, "default", "collector"),
        definitions=definitions,
        model_weights=_road_profile_weight_table(
            raw.get("model_weights"),
            DEFAULT_ROAD_PROFILE_MODEL_WEIGHTS if enabled else {},
            "roads.profiles.model_weights",
        ),
        biome_weights=_road_profile_weight_table(
            raw.get("biome_weights"),
            DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS if enabled else {},
            "roads.profiles.biome_weights",
        ),
    )


def _default_road_profile_definitions(width_m: float, sidewalk_width_m: float) -> dict[str, RoadProfileConfig]:
    local_width = max(4.0, width_m * 0.72)
    arterial_width = max(width_m + 4.0, width_m * 1.35)
    boulevard_width = max(width_m + 6.0, width_m * 1.6)
    return {
        "local": RoadProfileConfig(
            carriageway_width_m=local_width,
            sidewalk_width_m=max(1.5, sidewalk_width_m * 0.72),
            median_width_m=0.0,
        ),
        "collector": RoadProfileConfig(
            carriageway_width_m=width_m,
            sidewalk_width_m=sidewalk_width_m,
            median_width_m=0.0,
        ),
        "arterial": RoadProfileConfig(
            carriageway_width_m=arterial_width,
            sidewalk_width_m=sidewalk_width_m + 1.0,
            median_width_m=1.5,
        ),
        "boulevard": RoadProfileConfig(
            carriageway_width_m=boulevard_width,
            sidewalk_width_m=sidewalk_width_m + 1.0,
            median_width_m=6.0,
        ),
    }


def _road_profile_definitions(raw: Any) -> dict[str, RoadProfileConfig]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("roads.profiles.definitions must be a mapping.")

    definitions: dict[str, RoadProfileConfig] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name:
            raise ConfigError("roads.profiles.definitions keys must be non-empty strings.")
        if not isinstance(value, dict):
            raise ConfigError(f"roads.profiles.definitions.{name} must be a mapping.")
        definitions[name] = RoadProfileConfig(
            carriageway_width_m=_float(value, "carriageway_width_m", 0.0),
            sidewalk_width_m=_float(value, "sidewalk_width_m", 0.0),
            median_width_m=_float(value, "median_width_m", 0.0),
        )
    return definitions


def _road_profile_weight_table(
    raw: Any,
    defaults: dict[str, dict[str, float]],
    label: str,
) -> dict[str, dict[str, float]]:
    if raw is None:
        return {name: dict(weights) for name, weights in defaults.items()}
    if not isinstance(raw, dict):
        raise ConfigError(f"{label} must be a mapping.")

    result: dict[str, dict[str, float]] = {}
    for selector, weights in raw.items():
        if not isinstance(selector, str):
            raise ConfigError(f"{label} keys must be strings.")
        result[selector] = _road_profile_weights(weights, f"{label}.{selector}")
    return result


def _road_profile_weights(raw: Any, label: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ConfigError(f"{label} must be a mapping.")

    weights: dict[str, float] = {}
    for profile_name, value in raw.items():
        if not isinstance(profile_name, str):
            raise ConfigError(f"{label} keys must be strings.")
        if isinstance(value, bool):
            raise ConfigError(f"{label}.{profile_name} must be a number.")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{label}.{profile_name} must be a number.") from exc
        weights[profile_name] = weight
    return weights


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


def _parcels_config(raw: dict[str, Any]) -> ParcelsConfig:
    supported = {
        "enabled",
        "block_size_m",
        "block_jitter_m",
        "min_block_size_m",
        "min_parcel_width_m",
        "max_parcel_width_m",
        "min_parcel_depth_m",
        "max_parcel_depth_m",
        "parcel_setback_m",
        "split_jitter_ratio",
        "max_subdivision_depth",
        "building_alignment",
        "orientation_jitter_degrees",
        "max_building_coverage",
        "require_building_inside_buildable_area",
        "oriented_blocks",
        "block_orientation_source",
        "block_orientation_jitter_degrees",
        "organic_orientation_jitter_degrees",
    }
    for key in raw:
        if key not in supported:
            fields = ", ".join(sorted(supported))
            raise ConfigError(f"Unsupported parcels.{key}. Supported fields: {fields}.")
    defaults = ParcelsConfig()
    return ParcelsConfig(
        enabled=_bool(raw, "enabled", defaults.enabled),
        block_size_m=_float(raw, "block_size_m", defaults.block_size_m),
        block_jitter_m=_float(raw, "block_jitter_m", defaults.block_jitter_m),
        min_block_size_m=_float(raw, "min_block_size_m", defaults.min_block_size_m),
        min_parcel_width_m=_float(raw, "min_parcel_width_m", defaults.min_parcel_width_m),
        max_parcel_width_m=_float(raw, "max_parcel_width_m", defaults.max_parcel_width_m),
        min_parcel_depth_m=_float(raw, "min_parcel_depth_m", defaults.min_parcel_depth_m),
        max_parcel_depth_m=_float(raw, "max_parcel_depth_m", defaults.max_parcel_depth_m),
        parcel_setback_m=_float(raw, "parcel_setback_m", defaults.parcel_setback_m),
        split_jitter_ratio=_float(raw, "split_jitter_ratio", defaults.split_jitter_ratio),
        max_subdivision_depth=_int(raw, "max_subdivision_depth", defaults.max_subdivision_depth),
        building_alignment=_str(raw, "building_alignment", defaults.building_alignment),
        orientation_jitter_degrees=_float(
            raw,
            "orientation_jitter_degrees",
            defaults.orientation_jitter_degrees,
        ),
        max_building_coverage=_float(raw, "max_building_coverage", defaults.max_building_coverage),
        require_building_inside_buildable_area=_bool(
            raw,
            "require_building_inside_buildable_area",
            defaults.require_building_inside_buildable_area,
        ),
        oriented_blocks=_bool(raw, "oriented_blocks", defaults.oriented_blocks),
        block_orientation_source=_str(raw, "block_orientation_source", defaults.block_orientation_source),
        block_orientation_jitter_degrees=_float(
            raw,
            "block_orientation_jitter_degrees",
            defaults.block_orientation_jitter_degrees,
        ),
        organic_orientation_jitter_degrees=_float(
            raw,
            "organic_orientation_jitter_degrees",
            defaults.organic_orientation_jitter_degrees,
        ),
    )


def _worldgen_config(raw: dict[str, Any]) -> WorldgenConfig:
    supported = {
        "catalog_docs",
        "strict_catalog_validation",
    }
    for key in raw:
        if key not in supported:
            fields = ", ".join(sorted(supported))
            raise ConfigError(f"Unsupported worldgen.{key}. Supported fields: {fields}.")
    defaults = WorldgenConfig()
    return WorldgenConfig(
        catalog_docs=_bool(raw, "catalog_docs", defaults.catalog_docs),
        strict_catalog_validation=_bool(raw, "strict_catalog_validation", defaults.strict_catalog_validation),
    )


def _validate(cfg: CityGenConfig) -> None:
    if cfg.worldgen.strict_catalog_validation:
        issues = validate_catalogs()
        if issues:
            raise ConfigError("Invalid worldgen catalogs: " + "; ".join(issues))

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
        ("parcels.block_size_m", cfg.parcels.block_size_m),
        ("parcels.min_block_size_m", cfg.parcels.min_block_size_m),
        ("parcels.min_parcel_width_m", cfg.parcels.min_parcel_width_m),
        ("parcels.max_parcel_width_m", cfg.parcels.max_parcel_width_m),
        ("parcels.min_parcel_depth_m", cfg.parcels.min_parcel_depth_m),
        ("parcels.max_parcel_depth_m", cfg.parcels.max_parcel_depth_m),
    ]
    for name, value in positive_fields:
        if value <= 0:
            raise ConfigError(f"{name} must be positive.")

    if cfg.roads.model not in SUPPORTED_ROAD_MODELS:
        supported = ", ".join(sorted(SUPPORTED_ROAD_MODELS))
        raise ConfigError(f"Unsupported roads.model='{cfg.roads.model}'. Supported models: {supported}.")
    _validate_road_profiles(cfg)
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
    if cfg.parcels.block_jitter_m < 0:
        raise ConfigError("parcels.block_jitter_m must be >= 0.")
    if cfg.parcels.parcel_setback_m < 0:
        raise ConfigError("parcels.parcel_setback_m must be >= 0.")
    if cfg.parcels.building_alignment not in {"parcel", "global"}:
        raise ConfigError("parcels.building_alignment must be one of: global, parcel.")
    if cfg.parcels.orientation_jitter_degrees < 0:
        raise ConfigError("parcels.orientation_jitter_degrees must be >= 0.")
    if not 0 < cfg.parcels.max_building_coverage <= 1:
        raise ConfigError("parcels.max_building_coverage must be between 0 and 1.")
    if cfg.parcels.block_orientation_source not in {"road_model", "config", "none"}:
        raise ConfigError("parcels.block_orientation_source must be one of: config, none, road_model.")
    if cfg.parcels.block_orientation_jitter_degrees < 0:
        raise ConfigError("parcels.block_orientation_jitter_degrees must be >= 0.")
    if cfg.parcels.organic_orientation_jitter_degrees < 0:
        raise ConfigError("parcels.organic_orientation_jitter_degrees must be >= 0.")
    if not 0 <= cfg.parcels.split_jitter_ratio <= 0.45:
        raise ConfigError("parcels.split_jitter_ratio must be between 0 and 0.45.")
    if cfg.parcels.max_subdivision_depth < 0:
        raise ConfigError("parcels.max_subdivision_depth must be >= 0.")
    if cfg.parcels.max_parcel_width_m < cfg.parcels.min_parcel_width_m:
        raise ConfigError("parcels.max_parcel_width_m must be >= parcels.min_parcel_width_m.")
    if cfg.parcels.max_parcel_depth_m < cfg.parcels.min_parcel_depth_m:
        raise ConfigError("parcels.max_parcel_depth_m must be >= parcels.min_parcel_depth_m.")
    if cfg.parcels.block_size_m < cfg.parcels.min_block_size_m:
        raise ConfigError("parcels.block_size_m must be >= parcels.min_block_size_m.")


def _validate_road_profiles(cfg: CityGenConfig) -> None:
    profiles = cfg.roads.profiles
    if not profiles.definitions:
        raise ConfigError("roads.profiles.definitions must contain at least one profile.")
    if profiles.default not in profiles.definitions:
        raise ConfigError(f"roads.profiles.default='{profiles.default}' is not defined.")

    for name, profile in profiles.definitions.items():
        if profile.carriageway_width_m <= 0:
            raise ConfigError(f"roads.profiles.definitions.{name}.carriageway_width_m must be positive.")
        if profile.sidewalk_width_m <= 0:
            raise ConfigError(f"roads.profiles.definitions.{name}.sidewalk_width_m must be positive.")
        if profile.median_width_m < 0:
            raise ConfigError(f"roads.profiles.definitions.{name}.median_width_m must be >= 0.")

    for model, weights in profiles.model_weights.items():
        if model not in SUPPORTED_ROAD_MODELS - {"mixed"}:
            supported = ", ".join(sorted(SUPPORTED_ROAD_MODELS - {"mixed"}))
            raise ConfigError(f"Unsupported roads.profiles.model_weights.{model}. Supported models: {supported}.")
        _validate_road_profile_weights(weights, profiles.definitions, f"roads.profiles.model_weights.{model}")

    for biome, weights in profiles.biome_weights.items():
        if biome not in SUPPORTED_BIOMES:
            supported = ", ".join(sorted(SUPPORTED_BIOMES))
            raise ConfigError(f"Unsupported roads.profiles.biome_weights.{biome}. Supported biomes: {supported}.")
        _validate_road_profile_weights(weights, profiles.definitions, f"roads.profiles.biome_weights.{biome}")

    if profiles.enabled:
        max_width = max(profile.total_corridor_width_m for profile in profiles.definitions.values())
        if max_width >= cfg.roads.spacing_m:
            raise ConfigError(
                "roads.profiles maximum corridor width must be smaller than roads.spacing_m."
            )


def _validate_road_profile_weights(
    weights: dict[str, float],
    definitions: dict[str, RoadProfileConfig],
    label: str,
) -> None:
    if not weights:
        raise ConfigError(f"{label} must contain at least one profile weight.")
    total = 0.0
    for profile_name, weight in weights.items():
        if profile_name not in definitions:
            raise ConfigError(f"{label}.{profile_name} references an undefined road profile.")
        if weight < 0:
            raise ConfigError(f"{label}.{profile_name} must be >= 0.")
        total += weight
    if total <= 0:
        raise ConfigError(f"{label} must have a positive weight sum.")


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
