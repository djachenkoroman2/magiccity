from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from citygen.config import load_config
from citygen.export import write_metadata, write_ply
from citygen.generator import generate_scene
from citygen.sampling import sample_scene


class ExportTests(unittest.TestCase):
    def test_ply_and_metadata_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                """
seed: 5
tile:
  size_m: 64
roads:
  spacing_m: 32
  width_m: 8
  sidewalk_width_m: 2
buildings:
  min_height_m: 8
  max_height_m: 12
sampling:
  ground_spacing_m: 4
  road_spacing_m: 4
  building_spacing_m: 4
""",
                encoding="utf-8",
            )
            config = load_config(config_path)
            scene = generate_scene(config)
            points = sample_scene(config, scene)
            ply_path = Path(tmp) / "out.ply"

            write_ply(ply_path, points, config)
            metadata_path = write_metadata(ply_path, config, scene, points)

            header = ply_path.read_text(encoding="utf-8").split("end_header", 1)[0]
            self.assertIn("format ascii 1.0", header)
            self.assertIn("property int class", header)
            self.assertIn(f"element vertex {len(points)}", header)

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["seed"], 5)
            self.assertEqual(metadata["point_count"], len(points))
            self.assertIn("ground", metadata["class_mapping"])
            self.assertIn("building_counts", metadata)
            self.assertIsInstance(metadata["building_counts"]["by_footprint"], dict)


if __name__ == "__main__":
    unittest.main()
