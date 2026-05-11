from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CATALOG_SCHEMA_VERSION = 1

WORLDGEN_PIPELINE_VERSION = 1

WORLDGEN_STAGES = (
    "load_config",
    "resolve_catalogs",
    "create_worldgen_context",
    "biome_source",
    "roads",
    "parcels",
    "objects",
    "sampling",
    "export_ply",
    "export_metadata",
)


@dataclass(frozen=True)
class BiomeDefinition:
    id: str
    title: str
    description: str
    tags: tuple[str, ...]
    build_probability: float
    footprint_scale: float
    height_min_multiplier: float
    height_max_multiplier: float
    setback_scale: float
    preferred_road_model: str
    road_profile_weights: dict[str, float]
    object_weights: dict[str, float]


@dataclass(frozen=True)
class RoadModelDefinition:
    id: str
    title: str
    description: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoadProfileDefinition:
    id: str
    title: str
    description: str
    carriageway_width_m: float
    sidewalk_width_m: float
    median_width_m: float = 0.0


@dataclass(frozen=True)
class FootprintDefinition:
    id: str
    title: str
    description: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoofDefinition:
    id: str
    title: str
    description: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticClassDefinition:
    id: str
    class_id: int
    color: tuple[int, int, int]
    description: str


@dataclass(frozen=True)
class ObjectFeatureDefinition:
    id: str
    title: str
    category: str
    description: str
    stage: str
    semantic_classes: tuple[str, ...]
    config_section: str | None
    enabled_by_default: bool
    biome_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldgenCatalogs:
    biomes: dict[str, BiomeDefinition]
    road_models: dict[str, RoadModelDefinition]
    road_profiles: dict[str, RoadProfileDefinition]
    object_features: dict[str, ObjectFeatureDefinition]
    footprint_types: dict[str, FootprintDefinition]
    roof_types: dict[str, RoofDefinition]
    semantic_classes: dict[str, SemanticClassDefinition]


ROAD_MODEL_DEFINITIONS: dict[str, RoadModelDefinition] = {
    "grid": RoadModelDefinition("grid", "Grid", "Regular orthogonal street grid.", ("regular",)),
    "radial_ring": RoadModelDefinition(
        "radial_ring",
        "Radial Ring",
        "Radial spokes with concentric rings around the city center.",
        ("centered", "downtown"),
    ),
    "radial": RoadModelDefinition("radial", "Radial", "Radial spokes without ring roads.", ("centered",)),
    "linear": RoadModelDefinition("linear", "Linear", "Main-axis roads with sparser cross streets.", ("industrial",)),
    "organic": RoadModelDefinition(
        "organic",
        "Organic",
        "Wavy road polylines with terrain-influenced wandering.",
        ("suburb", "irregular"),
    ),
    "mixed": RoadModelDefinition("mixed", "Mixed", "Biome-driven road model selection.", ("biome_driven",)),
    "free": RoadModelDefinition("free", "Free", "Deterministic irregular segment network.", ("irregular",)),
}

ROAD_PROFILE_DEFINITIONS: dict[str, RoadProfileDefinition] = {
    "local": RoadProfileDefinition("local", "Local", "Narrow local street.", 7.0, 2.0, 0.0),
    "collector": RoadProfileDefinition("collector", "Collector", "Medium urban street.", 10.0, 3.0, 0.0),
    "arterial": RoadProfileDefinition("arterial", "Arterial", "Wider arterial road.", 14.0, 4.0, 1.5),
    "boulevard": RoadProfileDefinition(
        "boulevard",
        "Boulevard",
        "Wide road with a visible central median.",
        16.0,
        4.0,
        6.0,
    ),
}

DEFAULT_ROAD_PROFILE_MODEL_WEIGHTS = {
    "grid": {"local": 0.45, "collector": 0.40, "arterial": 0.15},
    "radial_ring": {"collector": 0.20, "arterial": 0.45, "boulevard": 0.35},
    "radial": {"collector": 0.30, "arterial": 0.50, "boulevard": 0.20},
    "linear": {"collector": 0.35, "arterial": 0.50, "boulevard": 0.15},
    "organic": {"local": 0.80, "collector": 0.20},
    "free": {"local": 0.55, "collector": 0.35, "arterial": 0.10},
}

DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS = {
    "downtown": {"collector": 0.15, "arterial": 0.45, "boulevard": 0.40},
    "residential": {"local": 0.55, "collector": 0.35, "arterial": 0.10},
    "industrial": {"collector": 0.30, "arterial": 0.55, "boulevard": 0.15},
    "suburb": {"local": 0.85, "collector": 0.15},
}

BIOME_DEFINITIONS: dict[str, BiomeDefinition] = {
    "downtown": BiomeDefinition(
        id="downtown",
        title="Downtown",
        description="Dense central core with taller buildings and radial-ring roads.",
        tags=("central", "dense", "highrise"),
        build_probability=0.94,
        footprint_scale=1.08,
        height_min_multiplier=1.45,
        height_max_multiplier=1.75,
        setback_scale=0.65,
        preferred_road_model="radial_ring",
        road_profile_weights=DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS["downtown"],
        object_weights={"building": 1.0, "road_network": 1.0, "parcel_blocks": 0.8},
    ),
    "residential": BiomeDefinition(
        id="residential",
        title="Residential",
        description="Balanced urban fabric with grid roads and medium building density.",
        tags=("urban", "regular", "housing"),
        build_probability=0.78,
        footprint_scale=0.92,
        height_min_multiplier=0.85,
        height_max_multiplier=0.82,
        setback_scale=1.0,
        preferred_road_model="grid",
        road_profile_weights=DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS["residential"],
        object_weights={"building": 1.0, "road_network": 1.0, "parcel_blocks": 1.0},
    ),
    "industrial": BiomeDefinition(
        id="industrial",
        title="Industrial",
        description="Larger footprints, lower heights, and linear road structure.",
        tags=("industrial", "large_footprints"),
        build_probability=0.64,
        footprint_scale=1.45,
        height_min_multiplier=0.9,
        height_max_multiplier=0.75,
        setback_scale=0.85,
        preferred_road_model="linear",
        road_profile_weights=DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS["industrial"],
        object_weights={"building": 0.85, "road_network": 1.0, "parcel_blocks": 0.7},
    ),
    "suburb": BiomeDefinition(
        id="suburb",
        title="Suburb",
        description="Lower density areas with organic roads and larger setbacks.",
        tags=("suburban", "green", "lowrise"),
        build_probability=0.38,
        footprint_scale=0.72,
        height_min_multiplier=0.55,
        height_max_multiplier=0.45,
        setback_scale=1.45,
        preferred_road_model="organic",
        road_profile_weights=DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS["suburb"],
        object_weights={"building": 0.55, "road_network": 1.0, "parcel_blocks": 0.9},
    ),
}

FOOTPRINT_DEFINITIONS: dict[str, FootprintDefinition] = {
    "rectangle": FootprintDefinition("rectangle", "Rectangle", "Axis-aligned rectangular building footprint."),
    "square": FootprintDefinition("square", "Square", "Axis-aligned square building footprint."),
    "circle": FootprintDefinition("circle", "Circle", "Circular footprint approximated by sampled boundary segments."),
    "slab": FootprintDefinition("slab", "Slab", "Long narrow slab footprint.", ("linear",)),
    "courtyard": FootprintDefinition("courtyard", "Courtyard", "Perimeter footprint with an inner void."),
    "l_shape": FootprintDefinition("l_shape", "L Shape", "Composite L-shaped footprint."),
    "u_shape": FootprintDefinition("u_shape", "U Shape", "Composite U-shaped footprint."),
    "t_shape": FootprintDefinition("t_shape", "T Shape", "Composite T-shaped footprint."),
}

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

ROOF_DEFINITIONS: dict[str, RoofDefinition] = {
    "flat": RoofDefinition("flat", "Flat", "Flat or very slightly sloped roof."),
    "shed": RoofDefinition("shed", "Shed", "Single-slope roof."),
    "gable": RoofDefinition("gable", "Gable", "Two-slope pitched roof."),
    "hip": RoofDefinition("hip", "Hip", "Four-sided hipped roof."),
    "half_hip": RoofDefinition("half_hip", "Half Hip", "Gable-like roof with clipped ends."),
    "pyramid": RoofDefinition("pyramid", "Pyramid", "Tent-like roof rising to a central peak."),
    "mansard": RoofDefinition("mansard", "Mansard", "Two-slope mansard-style roof."),
    "dome": RoofDefinition("dome", "Dome", "Curved dome height function."),
    "barrel": RoofDefinition("barrel", "Barrel", "Vaulted barrel roof."),
    "cone": RoofDefinition("cone", "Cone", "Conical roof."),
}

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

SEMANTIC_CLASS_DEFINITIONS: dict[str, SemanticClassDefinition] = {
    "ground": SemanticClassDefinition("ground", 1, (107, 132, 85), "Terrain surface."),
    "road": SemanticClassDefinition("road", 2, (47, 50, 54), "Road carriageway surface."),
    "sidewalk": SemanticClassDefinition("sidewalk", 3, (174, 174, 166), "Sidewalk surface."),
    "building_facade": SemanticClassDefinition("building_facade", 4, (176, 164, 148), "Building facade points."),
    "building_roof": SemanticClassDefinition("building_roof", 5, (112, 116, 122), "Building roof points."),
    "road_median": SemanticClassDefinition("road_median", 6, (118, 128, 84), "Central road median."),
}

OBJECT_FEATURE_DEFINITIONS: dict[str, ObjectFeatureDefinition] = {
    "terrain_surface": ObjectFeatureDefinition(
        "terrain_surface",
        "Terrain Surface",
        "surface",
        "Procedural ground surface sampled inside the tile bbox.",
        "sampling",
        ("ground",),
        "terrain",
        True,
    ),
    "road_network": ObjectFeatureDefinition(
        "road_network",
        "Road Network",
        "network",
        "Road primitives generated by the configured road model.",
        "roads",
        ("road", "sidewalk", "road_median"),
        "roads",
        True,
    ),
    "road_surface": ObjectFeatureDefinition(
        "road_surface",
        "Road Surface",
        "surface",
        "Sampled road carriageway points.",
        "sampling",
        ("road",),
        "roads",
        True,
    ),
    "road_sidewalk": ObjectFeatureDefinition(
        "road_sidewalk",
        "Road Sidewalk",
        "surface",
        "Sampled sidewalk points around roads.",
        "sampling",
        ("sidewalk",),
        "roads",
        True,
    ),
    "road_median": ObjectFeatureDefinition(
        "road_median",
        "Road Median",
        "surface",
        "Sampled central median for profiles with median_width_m > 0.",
        "sampling",
        ("road_median",),
        "roads.profiles",
        False,
    ),
    "parcel_blocks": ObjectFeatureDefinition(
        "parcel_blocks",
        "Parcel Blocks",
        "placement",
        "Rectangular block and parcel subdivision used by parcel-mode buildings.",
        "parcels",
        (),
        "parcels",
        False,
    ),
    "building": ObjectFeatureDefinition(
        "building",
        "Building",
        "object",
        "Procedural building composed of footprint, facade, and roof surfaces.",
        "objects",
        ("building_facade", "building_roof"),
        "buildings",
        True,
        ("urban", "central", "industrial", "suburban"),
    ),
    "building_footprint": ObjectFeatureDefinition(
        "building_footprint",
        "Building Footprint",
        "geometry",
        "Plan-shape geometry used to place and sample a building.",
        "objects",
        (),
        "buildings.footprint",
        True,
    ),
    "building_roof": ObjectFeatureDefinition(
        "building_roof",
        "Building Roof",
        "geometry",
        "Roof height function and sampled roof points.",
        "objects",
        ("building_roof",),
        "buildings.roof",
        True,
    ),
}

DEFAULT_CATALOGS = WorldgenCatalogs(
    biomes=BIOME_DEFINITIONS,
    road_models=ROAD_MODEL_DEFINITIONS,
    road_profiles=ROAD_PROFILE_DEFINITIONS,
    object_features=OBJECT_FEATURE_DEFINITIONS,
    footprint_types=FOOTPRINT_DEFINITIONS,
    roof_types=ROOF_DEFINITIONS,
    semantic_classes=SEMANTIC_CLASS_DEFINITIONS,
)


def resolve_catalogs() -> WorldgenCatalogs:
    return DEFAULT_CATALOGS


def catalog_summary(catalogs: WorldgenCatalogs = DEFAULT_CATALOGS) -> dict[str, Any]:
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "biomes": sorted(catalogs.biomes),
        "object_features": sorted(catalogs.object_features),
        "road_models": sorted(catalogs.road_models),
        "road_profiles": sorted(catalogs.road_profiles),
        "footprint_types": sorted(catalogs.footprint_types),
        "roof_types": sorted(catalogs.roof_types),
        "semantic_classes": sorted(catalogs.semantic_classes),
    }


def biome_catalog_summary(catalogs: WorldgenCatalogs = DEFAULT_CATALOGS) -> dict[str, Any]:
    return {
        biome_id: {
            "title": biome.title,
            "tags": list(biome.tags),
            "preferred_road_model": biome.preferred_road_model,
            "road_profile_weights": dict(sorted(biome.road_profile_weights.items())),
        }
        for biome_id, biome in sorted(catalogs.biomes.items())
    }


def worldgen_summary() -> dict[str, Any]:
    return {
        "pipeline_version": WORLDGEN_PIPELINE_VERSION,
        "stages": list(WORLDGEN_STAGES),
    }


def validate_catalogs(catalogs: WorldgenCatalogs = DEFAULT_CATALOGS) -> list[str]:
    issues: list[str] = []
    _validate_key_matches(catalogs.biomes, "biome", issues)
    _validate_key_matches(catalogs.road_models, "road model", issues)
    _validate_key_matches(catalogs.road_profiles, "road profile", issues)
    _validate_key_matches(catalogs.object_features, "object feature", issues)
    _validate_key_matches(catalogs.footprint_types, "footprint type", issues)
    _validate_key_matches(catalogs.roof_types, "roof type", issues)
    _validate_key_matches(catalogs.semantic_classes, "semantic class", issues)

    for biome in catalogs.biomes.values():
        if biome.preferred_road_model not in catalogs.road_models:
            issues.append(f"Biome '{biome.id}' references unknown road model '{biome.preferred_road_model}'.")
        _validate_weights(
            biome.road_profile_weights,
            catalogs.road_profiles,
            f"Biome '{biome.id}' road_profile_weights",
            issues,
        )
        _validate_weights(
            biome.object_weights,
            catalogs.object_features,
            f"Biome '{biome.id}' object_weights",
            issues,
        )

    for label, table in (
        ("DEFAULT_ROAD_PROFILE_MODEL_WEIGHTS", DEFAULT_ROAD_PROFILE_MODEL_WEIGHTS),
        ("DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS", DEFAULT_ROAD_PROFILE_BIOME_WEIGHTS),
    ):
        for selector, weights in table.items():
            if label.endswith("MODEL_WEIGHTS") and selector not in catalogs.road_models:
                issues.append(f"{label}.{selector} references unknown road model.")
            if label.endswith("BIOME_WEIGHTS") and selector not in catalogs.biomes:
                issues.append(f"{label}.{selector} references unknown biome.")
            _validate_weights(weights, catalogs.road_profiles, f"{label}.{selector}", issues)

    _validate_weights(DEFAULT_MIXED_FOOTPRINT_WEIGHTS, catalogs.footprint_types, "DEFAULT_MIXED_FOOTPRINT_WEIGHTS", issues)
    _validate_weights(DEFAULT_MIXED_ROOF_WEIGHTS, catalogs.roof_types, "DEFAULT_MIXED_ROOF_WEIGHTS", issues)

    for feature in catalogs.object_features.values():
        if feature.stage not in WORLDGEN_STAGES:
            issues.append(f"Object feature '{feature.id}' references unknown stage '{feature.stage}'.")
        for class_name in feature.semantic_classes:
            if class_name not in catalogs.semantic_classes:
                issues.append(f"Object feature '{feature.id}' references unknown semantic class '{class_name}'.")

    return issues


def _validate_key_matches(items: dict[str, Any], label: str, issues: list[str]) -> None:
    seen: set[str] = set()
    for key, definition in items.items():
        if key in seen:
            issues.append(f"Duplicate {label} id '{key}'.")
        seen.add(key)
        if key != definition.id:
            issues.append(f"{label.title()} key '{key}' does not match definition id '{definition.id}'.")


def _validate_weights(weights: dict[str, float], supported: dict[str, Any], label: str, issues: list[str]) -> None:
    if not weights:
        issues.append(f"{label} must contain at least one weight.")
        return
    total = 0.0
    for key, weight in weights.items():
        if key not in supported:
            issues.append(f"{label}.{key} references an unknown id.")
        if weight < 0:
            issues.append(f"{label}.{key} must be >= 0.")
        total += weight
    if total <= 0:
        issues.append(f"{label} must have a positive weight sum.")
