from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from citygen.config import load_config
from citygen.generator import generate_scene
from citygen.sampling import sample_scene


CONFIG_TEXT = """
seed: {seed}
tile:
  x: 0
  y: 0
  size_m: 96
roads:
  spacing_m: 48
  width_m: 8
  sidewalk_width_m: 2
buildings:
  min_height_m: 8
  max_height_m: 20
  footprint_min_m: 10
  footprint_max_m: 18
sampling:
  ground_spacing_m: 4
  road_spacing_m: 3
  building_spacing_m: 4
"""


class DeterminismTests(unittest.TestCase):
    def test_same_seed_produces_same_points(self) -> None:
        config = _config_from_text(CONFIG_TEXT.format(seed=123))

        first = sample_scene(config, generate_scene(config))
        second = sample_scene(config, generate_scene(config))

        self.assertEqual(len(first), len(second))
        self.assertEqual(first[:100], second[:100])

    def test_different_seed_changes_scene(self) -> None:
        config_a = _config_from_text(CONFIG_TEXT.format(seed=123))
        config_b = _config_from_text(CONFIG_TEXT.format(seed=124))

        points_a = sample_scene(config_a, generate_scene(config_a))
        points_b = sample_scene(config_b, generate_scene(config_b))

        self.assertNotEqual(points_a[:50], points_b[:50])


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
