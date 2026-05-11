from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from citygen.config import ConfigError, load_config
from citygen.export import write_metadata, write_ply
from citygen.generator import generate_scene
from citygen.sampling import sample_scene


class RoadProfileTests(unittest.TestCase):
    def test_loads_road_profiles_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
roads:
  spacing_m: 48
  profiles:
    enabled: true
    default: boulevard
    definitions:
      boulevard:
        carriageway_width_m: 16
        sidewalk_width_m: 4
        median_width_m: 6
    model_weights:
      grid:
        boulevard: 1
    biome_weights:
      residential:
        boulevard: 1
"""
        )

        self.assertTrue(config.roads.profiles.enabled)
        self.assertEqual(config.roads.profiles.default, "boulevard")
        self.assertEqual(config.roads.profiles.definitions["boulevard"].median_width_m, 6.0)

    def test_invalid_road_profiles_are_errors(self) -> None:
        invalid_configs = [
            """
seed: 7
roads:
  spacing_m: 48
  profiles:
    enabled: true
    default: missing
""",
            """
seed: 7
roads:
  spacing_m: 48
  profiles:
    enabled: true
    definitions:
      bad:
        carriageway_width_m: -1
        sidewalk_width_m: 2
""",
            """
seed: 7
roads:
  spacing_m: 48
  profiles:
    enabled: true
    model_weights:
      impossible:
        local: 1
""",
            """
seed: 7
roads:
  spacing_m: 48
  profiles:
    enabled: true
    model_weights:
      grid:
        missing: 1
""",
            """
seed: 7
roads:
  spacing_m: 48
  profiles:
    enabled: true
    model_weights:
      grid:
        local: 0
        collector: 0
""",
            """
seed: 7
roads:
  spacing_m: 20
  profiles:
    enabled: true
""",
        ]

        for text in invalid_configs:
            with self.subTest(text=text):
                with self.assertRaises(ConfigError):
                    _config_from_text(text)

    def test_surface_classification_uses_plain_profile_widths(self) -> None:
        config = _config_from_text(
            """
seed: 11
tile:
  size_m: 96
  margin_m: 32
roads:
  model: grid
  spacing_m: 48
  profiles:
    enabled: true
    default: collector
    definitions:
      collector:
        carriageway_width_m: 10
        sidewalk_width_m: 3
        median_width_m: 0
    model_weights:
      grid:
        collector: 1
    biome_weights:
      residential:
        collector: 1
buildings:
  enabled: false
"""
        )
        scene = generate_scene(config)

        self.assertEqual(scene.road_network.surface_kind(config, 0, 20), "road")
        self.assertEqual(scene.road_network.surface_kind(config, 6, 20), "sidewalk")
        self.assertEqual(scene.road_network.surface_kind(config, 9, 20), "ground")

    def test_surface_classification_uses_wide_median_profile(self) -> None:
        config = _wide_median_config(seed=12)
        scene = generate_scene(config)

        self.assertEqual(scene.road_network.surface_kind(config, 0, 17), "road_median")
        self.assertEqual(scene.road_network.surface_kind(config, 4, 17), "road")
        self.assertEqual(scene.road_network.surface_kind(config, 13, 17), "sidewalk")
        self.assertEqual(scene.road_network.surface_kind(config, 18, 17), "ground")
        self.assertEqual(scene.road_network.surface_kind(config, 0, 0), "road")

    def test_road_profile_assignment_is_deterministic(self) -> None:
        config = _weighted_profiles_config(seed=41)

        first = generate_scene(config)
        second = generate_scene(config)
        other_seed = generate_scene(_weighted_profiles_config(seed=42))

        self.assertEqual(_profile_sequence(first), _profile_sequence(second))
        self.assertNotEqual(_profile_sequence(first), _profile_sequence(other_seed))

    def test_metadata_contains_profiles_widths_and_median_class(self) -> None:
        config = _wide_median_config(seed=12)
        scene = generate_scene(config)
        points = sample_scene(config, scene)
        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "profiles.ply"
            write_ply(ply_path, points, config)
            metadata_path = write_metadata(ply_path, config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertIn("boulevard", metadata["road_profile_counts"])
        self.assertEqual(metadata["road_widths"]["max_median_width_m"], 6.0)
        self.assertTrue(metadata["road_median"]["enabled"])
        self.assertIn("road_median", metadata["class_counts"])
        self.assertIn("road_profile_counts_by_biome", metadata)


def _wide_median_config(seed: int):
    return _config_from_text(
        f"""
seed: {seed}
tile:
  size_m: 96
  margin_m: 32
roads:
  model: grid
  spacing_m: 48
  profiles:
    enabled: true
    default: boulevard
    definitions:
      boulevard:
        carriageway_width_m: 16
        sidewalk_width_m: 4
        median_width_m: 6
    model_weights:
      grid:
        boulevard: 1
    biome_weights:
      residential:
        boulevard: 1
buildings:
  enabled: false
sampling:
  ground_spacing_m: 4
  road_spacing_m: 2
  jitter_ratio: 0
"""
    )


def _weighted_profiles_config(seed: int):
    return _config_from_text(
        f"""
seed: {seed}
tile:
  size_m: 160
  margin_m: 32
roads:
  model: grid
  spacing_m: 48
  profiles:
    enabled: true
    default: collector
    model_weights:
      grid:
        local: 1
        collector: 1
        boulevard: 1
    biome_weights:
      residential:
        local: 1
        collector: 1
        boulevard: 1
buildings:
  enabled: false
"""
    )


def _profile_sequence(scene) -> list[tuple[int, str, str]]:
    return [
        (instance.index, instance.profile_name, instance.biome)
        for instance in scene.road_network.instances
    ]


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
