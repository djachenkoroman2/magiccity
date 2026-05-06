from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from citygen.cli import main
from citygen.config import ConfigError, load_config
from citygen.generator import generate_scene
from citygen.sampling import sample_scene


ROAD_CONFIG = """
seed: 17
tile:
  x: 0
  y: 0
  size_m: 96
  margin_m: 32
terrain:
  height_noise_m: 1.0
urban_fields:
  enabled: true
  center_x: 48
  center_y: 48
  city_radius_m: 180
  noise_scale_m: 90
roads:
  model: {model}
  spacing_m: 32
  width_m: 6
  sidewalk_width_m: 2
  angle_degrees: 18
  radial_count: 8
buildings:
  enabled: false
sampling:
  ground_spacing_m: 4
  road_spacing_m: 3
  building_spacing_m: 4
  jitter_ratio: 0
"""


class RoadBiomeTileTests(unittest.TestCase):
    def test_baseline_mvp_still_contains_building_classes(self) -> None:
        config = load_config("configs/mvp.yaml")
        scene = generate_scene(config)
        points = sample_scene(config, scene)
        counts = Counter(point.class_id for point in points)

        self.assertGreater(counts[4], 0)
        self.assertGreater(counts[5], 0)

    def test_supported_road_models_generate_roads_and_sidewalks(self) -> None:
        for model in ("grid", "radial_ring", "radial", "linear", "organic", "mixed"):
            with self.subTest(model=model):
                config = _config_from_text(ROAD_CONFIG.format(model=model))
                scene = generate_scene(config)
                points = sample_scene(config, scene)
                counts = Counter(point.class_id for point in points)

                self.assertGreater(counts[2], 0)
                self.assertGreater(counts[3], 0)

    def test_unknown_road_model_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 1
roads:
  model: impossible
"""
            )

    def test_mixed_model_samples_multiple_biomes(self) -> None:
        config = _config_from_text(
            """
seed: 23
tile:
  size_m: 192
  margin_m: 32
urban_fields:
  enabled: true
  center_x: 96
  center_y: 96
  city_radius_m: 145
  noise_scale_m: 80
roads:
  model: mixed
  spacing_m: 40
  width_m: 8
  sidewalk_width_m: 3
  radial_count: 10
buildings:
  enabled: false
sampling:
  ground_spacing_m: 6
  road_spacing_m: 4
  building_spacing_m: 6
"""
        )
        scene = generate_scene(config)

        self.assertGreaterEqual(len(scene.biome_counts), 2)
        self.assertIn("radial_ring", scene.road_models)
        self.assertIn("organic", scene.road_models)

    def test_multi_tile_config_writes_multiple_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "multi.yaml"
            out_dir = Path(tmp) / "tiles"
            config_path.write_text(
                """
seed: 31
tiles:
  items:
    - {x: 0, y: 0}
    - {x: 1, y: 0}
  size_m: 64
  margin_m: 16
roads:
  model: grid
  spacing_m: 32
  width_m: 6
  sidewalk_width_m: 2
buildings:
  enabled: false
sampling:
  ground_spacing_m: 8
  road_spacing_m: 6
  building_spacing_m: 8
""",
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                exit_code = main(["--config", str(config_path), "--out", str(out_dir)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((out_dir / "tile_0_0.ply").exists())
            self.assertTrue((out_dir / "tile_0_0.metadata.json").exists())
            self.assertTrue((out_dir / "tile_1_0.ply").exists())
            self.assertTrue((out_dir / "tile_1_0.metadata.json").exists())


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
