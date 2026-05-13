from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from citygen.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_loads_minimal_config_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("seed: 7\n", encoding="utf-8")

            config = load_config(path)

        self.assertEqual(config.seed, 7)
        self.assertEqual(config.tile.size_m, 256.0)
        self.assertEqual(config.roads.model, "grid")
        self.assertEqual(config.buildings.footprint.model, "rectangle")
        self.assertEqual(config.buildings.roof.model, "flat")

    def test_missing_seed_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("tile:\n  x: 0\n", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_config(path)

    def test_loads_footprint_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
buildings:
  footprint:
    model: mixed
    weights:
      rectangle: 0.5
      rotunda: 0.5
    circle_segments: 16
"""
        )

        self.assertEqual(config.buildings.footprint.model, "mixed")
        self.assertEqual(config.buildings.footprint.weights["circle"], 0.5)
        self.assertEqual(config.buildings.footprint.circle_segments, 16)

    def test_unknown_footprint_model_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  footprint:
    model: pyramid
"""
            )

    def test_negative_footprint_weight_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  footprint:
    model: mixed
    weights:
      rectangle: 1
      circle: -1
"""
            )

    def test_zero_mixed_footprint_weight_sum_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  footprint:
    model: mixed
    weights:
      rectangle: 0
      circle: 0
"""
            )

    def test_loads_roof_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
buildings:
  roof:
    model: mixed
    weights:
      flat: 0.4
      pitched: 0.6
    pitch_degrees: 34
    dome_segments: 20
"""
        )

        self.assertEqual(config.buildings.roof.model, "mixed")
        self.assertEqual(config.buildings.roof.weights["gable"], 0.6)
        self.assertEqual(config.buildings.roof.pitch_degrees, 34)
        self.assertEqual(config.buildings.roof.dome_segments, 20)

    def test_unknown_roof_model_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  roof:
    model: impossible
"""
            )

    def test_negative_roof_weight_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  roof:
    model: mixed
    weights:
      flat: 1
      dome: -1
"""
            )

    def test_zero_mixed_roof_weight_sum_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  roof:
    model: mixed
    weights:
      flat: 0
      dome: 0
"""
            )

    def test_loads_parcel_alignment_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
parcels:
  enabled: true
  building_alignment: parcel
  orientation_jitter_degrees: 3
  max_building_coverage: 0.65
  require_building_inside_buildable_area: true
  oriented_blocks: true
  block_orientation_source: road_model
  block_orientation_jitter_degrees: 4
  organic_orientation_jitter_degrees: 12
"""
        )

        self.assertEqual(config.parcels.building_alignment, "parcel")
        self.assertEqual(config.parcels.orientation_jitter_degrees, 3.0)
        self.assertEqual(config.parcels.max_building_coverage, 0.65)
        self.assertTrue(config.parcels.require_building_inside_buildable_area)
        self.assertTrue(config.parcels.oriented_blocks)
        self.assertEqual(config.parcels.block_orientation_source, "road_model")
        self.assertEqual(config.parcels.block_orientation_jitter_degrees, 4.0)
        self.assertEqual(config.parcels.organic_orientation_jitter_degrees, 12.0)

    def test_invalid_parcel_alignment_config_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  building_alignment: diagonal
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  orientation_jitter_degrees: -1
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  max_building_coverage: 1.5
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  block_orientation_source: nearest_lane
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  block_orientation_jitter_degrees: -1
"""
            )

    def test_loads_fence_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  mode: partial
  type: chain_link
  height_m: 2.2
  height_jitter_m: 0.1
  sides:
    - front
    - right
  gate_sides:
    - front
  foundation: always
  openness: 0.7
  decorative: true
"""
        )

        self.assertTrue(config.fences.enabled)
        self.assertEqual(config.fences.mode, "partial")
        self.assertEqual(config.fences.type, "metal_chain_link")
        self.assertEqual(config.fences.height_m, 2.2)
        self.assertEqual(config.fences.sides, ("front", "right"))
        self.assertEqual(config.fences.gate_sides, ("front",))
        self.assertEqual(config.fences.foundation, "always")
        self.assertEqual(config.fences.openness, 0.7)
        self.assertTrue(config.fences.decorative)

    def test_invalid_fence_config_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
fences:
  enabled: true
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  type: hedge
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  sides:
    - diagonal
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  openness: 1.2
"""
            )


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
