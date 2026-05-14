from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from citygen.classes import CLASS_BY_ID, POINT_CLASSES
from citygen.config import load_config
from citygen.export import write_metadata
from citygen.generator import generate_scene
from citygen.geometry import BBox
from citygen.mobile_lidar import _trace_ray
from citygen.sampling import sample_scene
from citygen.trees import Tree


TREE_CONFIG = """
seed: 812
tile:
  size_m: 96
  margin_m: 8
roads:
  model: grid
  spacing_m: 96
  width_m: 4
  sidewalk_width_m: 1
buildings:
  enabled: true
  min_height_m: 6
  max_height_m: 10
  setback_m: 1
  footprint_min_m: 6
  footprint_max_m: 10
trees:
  enabled: true
  density_per_ha: 120
  min_spacing_m: 7
  height_m: 7
  height_jitter_m: 0.3
  crown_shape: mixed
  crown_radius_m: 2
  crown_segments: 8
  road_clearance_m: 1
  building_clearance_m: 2
  fence_clearance_m: 0.5
  tile_margin_clearance_m: 1
  sample_spacing_m: 2
sampling:
  ground_spacing_m: 12
  road_spacing_m: 8
  building_spacing_m: 6
  jitter_ratio: 0
"""


class TreeGenerationTests(unittest.TestCase):
    def test_enabled_trees_create_instances_and_points(self) -> None:
        config = _config_from_text(TREE_CONFIG)
        scene = generate_scene(config)
        points = sample_scene(config, scene)
        class_counts = _class_counts(points)

        self.assertGreater(len(scene.trees), 0)
        self.assertEqual(scene.tree_counts["total"], len(scene.trees))
        self.assertGreater(class_counts["tree_trunk"], 0)
        self.assertGreater(class_counts["tree_crown"], 0)
        self.assertEqual(POINT_CLASSES["tree_trunk"].id, 9)
        self.assertEqual(POINT_CLASSES["tree_crown"].id, 10)

    def test_disabled_trees_do_not_change_surface_points(self) -> None:
        base = _config_from_text(_without_tree_section(TREE_CONFIG))
        disabled = _config_from_text(
            _without_tree_section(TREE_CONFIG)
            + """
trees:
  enabled: false
"""
        )

        base_scene = generate_scene(base)
        disabled_scene = generate_scene(disabled)

        self.assertEqual(base_scene.trees, ())
        self.assertEqual(disabled_scene.trees, ())
        self.assertEqual(sample_scene(base, base_scene), sample_scene(disabled, disabled_scene))

    def test_trees_stay_on_natural_ground_and_outside_buildings(self) -> None:
        config = _config_from_text(TREE_CONFIG)
        scene = generate_scene(config)

        self.assertGreater(len(scene.trees), 0)
        self.assertGreater(len(scene.buildings), 0)
        for tree in scene.trees:
            with self.subTest(tree=tree.id):
                self.assertEqual(scene.road_network.surface_kind(config, tree.x, tree.y), "ground")
                self.assertGreater(
                    scene.road_network.nearest_hardscape_distance(tree.x, tree.y),
                    config.trees.road_clearance_m,
                )
                self.assertFalse(any(building.footprint.contains_xy(tree.x, tree.y) for building in scene.buildings))

    def test_biome_density_multipliers_control_tree_count(self) -> None:
        zero_config = _config_from_text(
            _tree_density_config(
                """
  biome_density_multipliers:
    residential: 0
    downtown: 0
    industrial: 0
    suburb: 0
"""
            )
        )
        high_config = _config_from_text(
            _tree_density_config(
                """
  biome_density_multipliers:
    residential: 2
    downtown: 0
    industrial: 0
    suburb: 0
"""
            )
        )

        self.assertEqual(len(generate_scene(zero_config).trees), 0)
        self.assertGreater(len(generate_scene(high_config).trees), 0)

    def test_same_seed_produces_same_trees_and_points(self) -> None:
        config_a = _config_from_text(TREE_CONFIG)
        config_b = _config_from_text(TREE_CONFIG)

        scene_a = generate_scene(config_a)
        scene_b = generate_scene(config_b)

        self.assertEqual(scene_a.trees, scene_b.trees)
        self.assertEqual(sample_scene(config_a, scene_a), sample_scene(config_b, scene_b))

    def test_metadata_contains_tree_counts_and_class_mapping(self) -> None:
        config = _config_from_text(TREE_CONFIG)
        scene = generate_scene(config)
        points = sample_scene(config, scene)

        with tempfile.TemporaryDirectory() as tmp:
            metadata_path = write_metadata(Path(tmp) / "trees.ply", config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        class_counts = _class_counts(points)
        self.assertEqual(metadata["tree_counts"]["total"], len(scene.trees))
        self.assertEqual(metadata["tree_counts"]["trunk_points"], class_counts["tree_trunk"])
        self.assertEqual(metadata["tree_counts"]["crown_points"], class_counts["tree_crown"])
        self.assertEqual(metadata["object_feature_counts"]["tree"], len(scene.trees))
        self.assertEqual(metadata["object_feature_counts"]["tree_trunk"], class_counts["tree_trunk"])
        self.assertEqual(metadata["object_feature_counts"]["tree_crown"], class_counts["tree_crown"])
        self.assertEqual(metadata["class_mapping"]["tree_trunk"], 9)
        self.assertEqual(metadata["class_mapping"]["tree_crown"], 10)
        self.assertEqual(metadata["class_colors"]["tree_trunk"], [111, 78, 46])
        self.assertEqual(metadata["class_colors"]["tree_crown"], [54, 128, 70])
        self.assertIn("cone", metadata["supported_tree_crown_shapes"])

    def test_mobile_lidar_ray_can_hit_tree_trunk_and_crown(self) -> None:
        config = _config_from_text(
            """
seed: 1
mobile_lidar:
  enabled: true
  min_range_m: 0.1
  max_range_m: 50
  occlusions_enabled: true
"""
        )
        tree = Tree(
            id="manual_tree",
            x=10,
            y=0,
            base_z=0,
            height_m=7,
            trunk_radius_m=0.4,
            trunk_height_m=3,
            crown_shape="round",
            crown_radius_m=2,
            crown_height_m=3,
            biome="residential",
        )
        scene = SimpleNamespace(
            bbox=BBox(0, -5, 20, 5),
            buildings=(),
            fences=(),
            trees=(tree,),
        )

        trunk_hit = _trace_ray(config, scene, origin=(0, 0, 1.5), direction=(1, 0, 0))
        crown_hit = _trace_ray(config, scene, origin=(0, 0, 5), direction=(1, 0, 0))

        self.assertIsNotNone(trunk_hit)
        self.assertEqual(trunk_hit.class_name, "tree_trunk")
        self.assertIsNotNone(crown_hit)
        self.assertEqual(crown_hit.class_name, "tree_crown")


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


def _class_counts(points) -> Counter[str]:
    return Counter(CLASS_BY_ID[point.class_id].name for point in points)


def _without_tree_section(text: str) -> str:
    return text.split("trees:\n", 1)[0] + "sampling:\n" + text.split("sampling:\n", 1)[1]


def _tree_density_config(extra: str) -> str:
    return (
        """
seed: 41
tile:
  size_m: 80
roads:
  model: grid
  spacing_m: 80
  width_m: 4
  sidewalk_width_m: 1
buildings:
  enabled: false
trees:
  enabled: true
  density_per_ha: 100
  min_spacing_m: 6
  height_m: 6
  height_jitter_m: 0
  crown_shape: round
  crown_radius_m: 1.8
  road_clearance_m: 1
  sample_spacing_m: 2
"""
        + extra
        + """
sampling:
  ground_spacing_m: 12
  road_spacing_m: 8
  jitter_ratio: 0
"""
    )


if __name__ == "__main__":
    unittest.main()
