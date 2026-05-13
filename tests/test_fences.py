from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from citygen.classes import POINT_CLASSES
from citygen.config import load_config
from citygen.export import write_metadata
from citygen.generator import generate_scene
from citygen.sampling import sample_scene


class FenceTests(unittest.TestCase):
    def test_generates_and_samples_parcel_fences(self) -> None:
        config = _config_from_text(
            """
seed: 31
tile:
  size_m: 128
  margin_m: 16
roads:
  model: grid
  spacing_m: 80
  width_m: 6
  sidewalk_width_m: 1.5
buildings:
  enabled: false
parcels:
  enabled: true
  block_size_m: 64
  block_jitter_m: 0
  min_block_size_m: 24
  min_parcel_width_m: 12
  max_parcel_width_m: 36
  min_parcel_depth_m: 12
  max_parcel_depth_m: 36
  parcel_setback_m: 1
  max_subdivision_depth: 3
fences:
  enabled: true
  mode: perimeter
  type: brick
  height_m: 2.1
  height_jitter_m: 0
  foundation: auto
  gate_probability: 1
  gate_width_m: 3
  road_clearance_m: 0
  sample_spacing_m: 1
sampling:
  ground_spacing_m: 8
  road_spacing_m: 4
  building_spacing_m: 4
  jitter_ratio: 0
"""
        )

        scene = generate_scene(config)
        points = sample_scene(config, scene)
        fence_class_id = POINT_CLASSES["fence"].id
        foundation_class_id = POINT_CLASSES["fence_foundation"].id

        self.assertGreater(scene.fence_counts["segments"], 0)
        self.assertGreater(scene.fence_counts["foundation_segments"], 0)
        self.assertGreater(scene.fence_counts["gate_openings"], 0)
        self.assertGreater(sum(1 for point in points if point.class_id == fence_class_id), 0)
        self.assertGreater(sum(1 for point in points if point.class_id == foundation_class_id), 0)
        self.assertEqual(scene.fence_counts["by_type"], {"brick": scene.fence_counts["segments"]})

        for segment in scene.fences:
            for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
                x = segment.x0 + (segment.x1 - segment.x0) * ratio
                y = segment.y0 + (segment.y1 - segment.y0) * ratio
                self.assertGreater(scene.road_network.nearest_hardscape_distance(x, y), config.fences.road_clearance_m)

    def test_metadata_contains_fence_counts(self) -> None:
        config = _config_from_text(
            """
seed: 41
tile:
  size_m: 128
  margin_m: 16
roads:
  spacing_m: 80
  width_m: 6
  sidewalk_width_m: 1.5
buildings:
  enabled: false
parcels:
  enabled: true
  block_size_m: 64
  block_jitter_m: 0
  min_block_size_m: 24
  min_parcel_width_m: 12
  max_parcel_width_m: 36
  min_parcel_depth_m: 12
  max_parcel_depth_m: 36
  parcel_setback_m: 1
fences:
  enabled: true
  mode: partial
  sides:
    - left
    - right
  type: metal_welded
  foundation: never
  gate_probability: 0
  road_clearance_m: 0
sampling:
  ground_spacing_m: 8
  road_spacing_m: 4
"""
        )
        scene = generate_scene(config)
        points = sample_scene(config, scene)

        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "fences.ply"
            metadata_path = write_metadata(ply_path, config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertIn("fence_counts", metadata)
        self.assertIn("supported_fence_types", metadata)
        self.assertEqual(metadata["fence_counts"]["segments"], scene.fence_counts["segments"])
        self.assertEqual(metadata["fence_counts"]["foundation_segments"], 0)
        self.assertGreater(metadata["object_feature_counts"]["parcel_fence"], 0)
        self.assertIn("fence", metadata["class_mapping"])


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
