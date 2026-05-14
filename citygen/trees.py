from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any

from .biomes import classify_biome
from .catalogs import TREE_CROWN_DEFINITIONS
from .classes import POINT_CLASSES
from .config import CityGenConfig, TreesConfig
from .fences import FenceSegment
from .geometry import BBox, Building, Point, stable_rng, terrain_height
from .roads import RoadNetworkLike
from .selectors import select_weighted_id


TREE_CROWN_SHAPES: tuple[str, ...] = tuple(TREE_CROWN_DEFINITIONS)


@dataclass(frozen=True)
class Tree:
    id: str
    x: float
    y: float
    base_z: float
    height_m: float
    trunk_radius_m: float
    trunk_height_m: float
    crown_shape: str
    crown_radius_m: float
    crown_height_m: float
    biome: str

    @property
    def top_z(self) -> float:
        return self.base_z + self.height_m

    @property
    def crown_base_z(self) -> float:
        return max(self.base_z + self.trunk_height_m * 0.75, self.top_z - self.crown_height_m)

    @property
    def crown_center_z(self) -> float:
        rx, _ry, rz = crown_radii(self)
        if self.crown_shape == "umbrella":
            return self.top_z - rz
        if self.crown_shape == "cone":
            return self.crown_base_z + self.crown_height_m * 0.5
        return self.crown_base_z + rz

    @property
    def crown_diameter_m(self) -> float:
        rx, ry, _rz = crown_radii(self)
        return max(rx, ry) * 2.0


def build_trees(
    config: CityGenConfig,
    bbox: BBox,
    road_network: RoadNetworkLike,
    buildings: list[Building],
    fences: tuple[FenceSegment, ...],
) -> tuple[Tree, ...]:
    tree_config = config.trees
    if not tree_config.enabled or tree_config.density_per_ha <= 0:
        return ()

    max_multiplier = max(tree_config.biome_density_multipliers.values(), default=0.0)
    if max_multiplier <= 0:
        return ()

    max_density = tree_config.density_per_ha * max_multiplier
    candidate_step = max(tree_config.min_spacing_m, math.sqrt(10000.0 / max_density))
    start_i = math.floor(bbox.min_x / candidate_step)
    end_i = math.ceil(bbox.max_x / candidate_step)
    start_j = math.floor(bbox.min_y / candidate_step)
    end_j = math.ceil(bbox.max_y / candidate_step)

    trees: list[Tree] = []
    for ix in range(start_i, end_i):
        for iy in range(start_j, end_j):
            rng = stable_rng(config.seed, "tree-candidate", config.tile.x, config.tile.y, ix, iy)
            x = (ix + 0.5) * candidate_step + rng.uniform(-candidate_step * 0.35, candidate_step * 0.35)
            y = (iy + 0.5) * candidate_step + rng.uniform(-candidate_step * 0.35, candidate_step * 0.35)
            if not _inside_tree_bbox(bbox, tree_config, x, y):
                continue

            biome = classify_biome(config.seed, config.urban_fields, x, y)
            multiplier = tree_config.biome_density_multipliers.get(biome, 0.0)
            effective_density = tree_config.density_per_ha * multiplier
            if effective_density <= 0:
                continue
            acceptance_probability = min(0.97, effective_density * candidate_step * candidate_step / 10000.0)
            if rng.random() > acceptance_probability:
                continue
            if not _tree_location_is_clear(config, tree_config, road_network, buildings, fences, trees, x, y):
                continue

            trees.append(_make_tree(config, tree_config, x, y, biome, f"tree_{ix}_{iy}", rng))

    return tuple(sorted(trees, key=lambda item: item.id))


def tree_counts(trees: tuple[Tree, ...]) -> dict[str, Any]:
    if not trees:
        return {
            "total": 0,
            "by_crown_shape": {},
            "by_biome": {},
            "average_height_m": 0.0,
            "min_height_m": 0.0,
            "max_height_m": 0.0,
        }

    heights = [tree.height_m for tree in trees]
    return {
        "total": len(trees),
        "by_crown_shape": dict(sorted(Counter(tree.crown_shape for tree in trees).items())),
        "by_biome": dict(sorted(Counter(tree.biome for tree in trees).items())),
        "average_height_m": round(sum(heights) / len(heights), 3),
        "min_height_m": round(min(heights), 3),
        "max_height_m": round(max(heights), 3),
    }


def sample_tree(config: CityGenConfig, tree: Tree) -> list[Point]:
    spacing = config.trees.sample_spacing_m
    points: list[Point] = []
    points.extend(_sample_trunk(tree, spacing))
    points.extend(_sample_crown(tree, spacing, config.trees.crown_segments))
    return points


def tree_ray_hits(
    config: CityGenConfig,
    tree: Tree,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> tuple[tuple[float, str], ...]:
    hits: list[tuple[float, str]] = []
    trunk_distance = _intersect_trunk(config, tree, origin, direction)
    if trunk_distance is not None:
        hits.append((trunk_distance, "tree_trunk"))
    crown_distance = _intersect_crown(config, tree, origin, direction)
    if crown_distance is not None:
        hits.append((crown_distance, "tree_crown"))
    return tuple(sorted(hits, key=lambda item: item[0]))


def crown_radii(tree: Tree) -> tuple[float, float, float]:
    radius = tree.crown_radius_m
    height_radius = max(0.35, tree.crown_height_m * 0.5)
    if tree.crown_shape == "ellipsoid":
        return radius * 1.15, radius * 0.85, height_radius
    if tree.crown_shape == "columnar":
        return radius * 0.55, radius * 0.55, height_radius * 1.12
    if tree.crown_shape == "umbrella":
        return radius * 1.45, radius * 1.20, max(0.30, tree.crown_height_m * 0.35)
    return radius, radius, height_radius


def _make_tree(
    config: CityGenConfig,
    tree_config: TreesConfig,
    x: float,
    y: float,
    biome: str,
    tree_id: str,
    rng,
) -> Tree:
    height = max(1.5, tree_config.height_m + rng.uniform(-tree_config.height_jitter_m, tree_config.height_jitter_m))
    trunk_height = max(0.7, min(height * 0.88, height * tree_config.trunk_height_ratio))
    crown_height = max(0.8, min(height * 0.95, height * tree_config.crown_height_ratio))
    radius = max(0.4, tree_config.crown_radius_m * rng.uniform(0.82, 1.18))
    trunk_radius = max(0.06, tree_config.trunk_radius_m * rng.uniform(0.82, 1.18))
    return Tree(
        id=tree_id,
        x=x,
        y=y,
        base_z=terrain_height(config.seed, config.terrain, x, y),
        height_m=height,
        trunk_radius_m=trunk_radius,
        trunk_height_m=trunk_height,
        crown_shape=_select_crown_shape(tree_config, rng),
        crown_radius_m=radius,
        crown_height_m=crown_height,
        biome=biome,
    )


def _select_crown_shape(config: TreesConfig, rng) -> str:
    if config.crown_shape != "mixed":
        return config.crown_shape
    return select_weighted_id(config.weights, rng, fallback="round", ordered_ids=TREE_CROWN_SHAPES)


def _inside_tree_bbox(bbox: BBox, config: TreesConfig, x: float, y: float) -> bool:
    clearance = config.tile_margin_clearance_m
    return (
        bbox.min_x + clearance <= x <= bbox.max_x - clearance
        and bbox.min_y + clearance <= y <= bbox.max_y - clearance
    )


def _tree_location_is_clear(
    config: CityGenConfig,
    tree_config: TreesConfig,
    road_network: RoadNetworkLike,
    buildings: list[Building],
    fences: tuple[FenceSegment, ...],
    trees: list[Tree],
    x: float,
    y: float,
) -> bool:
    kind = road_network.surface_kind(config, x, y)
    if kind != "ground" and not (tree_config.allow_road_medians and kind == "road_median"):
        return False
    if kind == "ground" and road_network.nearest_hardscape_distance(x, y) <= tree_config.road_clearance_m:
        return False
    if _near_building(buildings, x, y, tree_config.building_clearance_m):
        return False
    if _near_fence(fences, x, y, tree_config.fence_clearance_m):
        return False
    return not _near_existing_tree(trees, x, y, tree_config.min_spacing_m)


def _near_building(buildings: list[Building], x: float, y: float, clearance: float) -> bool:
    for building in buildings:
        if building.footprint.contains_xy(x, y):
            return True
        if _distance_to_rect(x, y, building.footprint.bbox) <= clearance:
            return True
    return False


def _near_fence(fences: tuple[FenceSegment, ...], x: float, y: float, clearance: float) -> bool:
    return any(_distance_to_segment(x, y, fence.x0, fence.y0, fence.x1, fence.y1) <= clearance for fence in fences)


def _near_existing_tree(trees: list[Tree], x: float, y: float, min_spacing: float) -> bool:
    return any(math.hypot(tree.x - x, tree.y - y) < min_spacing for tree in trees)


def _sample_trunk(tree: Tree, spacing: float) -> list[Point]:
    cls = POINT_CLASSES["tree_trunk"]
    points: list[Point] = []
    circumference = max(0.1, 2.0 * math.pi * tree.trunk_radius_m)
    radial_count = max(8, int(math.ceil(circumference / max(0.25, spacing * 0.65))))
    for z in _grid_values(tree.base_z, tree.base_z + tree.trunk_height_m, max(0.25, spacing * 0.55)):
        for index in range(radial_count):
            angle = 2.0 * math.pi * index / radial_count
            x = tree.x + math.cos(angle) * tree.trunk_radius_m
            y = tree.y + math.sin(angle) * tree.trunk_radius_m
            points.append(Point(x, y, z, *cls.color, cls.id))
    return points


def _sample_crown(tree: Tree, spacing: float, segments: int) -> list[Point]:
    if tree.crown_shape == "cone":
        return _sample_cone_crown(tree, spacing, segments)
    return _sample_ellipsoid_crown(tree, spacing, segments)


def _sample_ellipsoid_crown(tree: Tree, spacing: float, segments: int) -> list[Point]:
    cls = POINT_CLASSES["tree_crown"]
    rx, ry, rz = crown_radii(tree)
    center_z = tree.crown_center_z
    vertical_count = max(4, int(math.ceil((rz * 2.0) / max(0.25, spacing))))
    angle_count = max(segments, int(math.ceil((2.0 * math.pi * max(rx, ry)) / max(0.25, spacing))))
    points: list[Point] = []
    for level in range(vertical_count + 1):
        phi = -math.pi * 0.5 + math.pi * level / vertical_count
        ring_scale = math.cos(phi)
        z = center_z + math.sin(phi) * rz
        ring_rx = rx * ring_scale
        ring_ry = ry * ring_scale
        ring_count = max(1, int(math.ceil(angle_count * max(0.18, abs(ring_scale)))))
        for index in range(ring_count):
            theta = 2.0 * math.pi * index / ring_count
            x = tree.x + math.cos(theta) * ring_rx
            y = tree.y + math.sin(theta) * ring_ry
            points.append(Point(x, y, z, *cls.color, cls.id))
    return points


def _sample_cone_crown(tree: Tree, spacing: float, segments: int) -> list[Point]:
    cls = POINT_CLASSES["tree_crown"]
    points: list[Point] = []
    base_z = tree.crown_base_z
    top_z = tree.top_z
    vertical_count = max(4, int(math.ceil((top_z - base_z) / max(0.25, spacing))))
    for level in range(vertical_count + 1):
        ratio = level / vertical_count
        z = base_z + (top_z - base_z) * ratio
        radius = tree.crown_radius_m * (1.0 - ratio)
        ring_count = max(1, int(math.ceil(segments * max(0.18, radius / max(0.01, tree.crown_radius_m)))))
        for index in range(ring_count):
            theta = 2.0 * math.pi * index / ring_count
            x = tree.x + math.cos(theta) * radius
            y = tree.y + math.sin(theta) * radius
            points.append(Point(x, y, z, *cls.color, cls.id))
    return points


def _intersect_trunk(
    config: CityGenConfig,
    tree: Tree,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> float | None:
    dx = origin[0] - tree.x
    dy = origin[1] - tree.y
    a = direction[0] * direction[0] + direction[1] * direction[1]
    if a <= 1e-12:
        return None
    b = 2.0 * (dx * direction[0] + dy * direction[1])
    c = dx * dx + dy * dy - tree.trunk_radius_m * tree.trunk_radius_m
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0:
        return None
    sqrt_disc = math.sqrt(discriminant)
    for distance in sorted(((-b - sqrt_disc) / (2.0 * a), (-b + sqrt_disc) / (2.0 * a))):
        if not _lidar_distance_in_range(config, distance):
            continue
        z = origin[2] + direction[2] * distance
        if tree.base_z - 1e-6 <= z <= tree.base_z + tree.trunk_height_m + 1e-6:
            return distance
    return None


def _intersect_crown(
    config: CityGenConfig,
    tree: Tree,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> float | None:
    rx, ry, rz = crown_radii(tree)
    if tree.crown_shape == "cone":
        rx = ry = tree.crown_radius_m * 0.78
        rz = max(0.35, tree.crown_height_m * 0.5)
    center = (tree.x, tree.y, tree.crown_center_z)
    ox = (origin[0] - center[0]) / rx
    oy = (origin[1] - center[1]) / ry
    oz = (origin[2] - center[2]) / rz
    dx = direction[0] / rx
    dy = direction[1] / ry
    dz = direction[2] / rz
    a = dx * dx + dy * dy + dz * dz
    if a <= 1e-12:
        return None
    b = 2.0 * (ox * dx + oy * dy + oz * dz)
    c = ox * ox + oy * oy + oz * oz - 1.0
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0:
        return None
    sqrt_disc = math.sqrt(discriminant)
    for distance in sorted(((-b - sqrt_disc) / (2.0 * a), (-b + sqrt_disc) / (2.0 * a))):
        if _lidar_distance_in_range(config, distance):
            return distance
    return None


def _lidar_distance_in_range(config: CityGenConfig, distance: float) -> bool:
    return config.mobile_lidar.min_range_m <= distance <= config.mobile_lidar.max_range_m


def _grid_values(start: float, stop: float, spacing: float):
    count = max(1, int(math.floor((stop - start) / spacing)) + 1)
    for index in range(count):
        value = start + index * spacing
        yield min(value, stop)


def _distance_to_rect(x: float, y: float, rect) -> float:
    dx = max(rect.min_x - x, 0.0, x - rect.max_x)
    dy = max(rect.min_y - y, 0.0, y - rect.max_y)
    return math.hypot(dx, dy)


def _distance_to_segment(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = x1 - x0
    dy = y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.hypot(x - x0, y - y0)
    t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / length_sq))
    px = x0 + dx * t
    py = y0 + dy * t
    return math.hypot(x - px, y - py)
