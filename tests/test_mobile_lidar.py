from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from citygen.config import load_config
from citygen.export import write_metadata
from citygen.footprints import BuildingFootprint
from citygen.generator import generate_scene
from citygen.geometry import BBox, Building, Rect
from citygen.mobile_lidar import _ray_direction, _trace_ray
from citygen.sampling import sample_scene


BASE_CONFIG = """
seed: {seed}
tile:
  x: 0
  y: 0
  size_m: 96
  margin_m: 16
roads:
  model: grid
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
  jitter_ratio: 0.1
"""


class MobileLidarTests(unittest.TestCase):
    def test_disabled_mode_keeps_surface_sampling_unchanged(self) -> None:
        plain = _config_from_text(BASE_CONFIG.format(seed=123))
        disabled = _config_from_text(
            BASE_CONFIG.format(seed=123)
            + """
mobile_lidar:
  enabled: false
  output_mode: lidar_only
  trajectory: road
"""
        )

        plain_points = sample_scene(plain, generate_scene(plain))
        disabled_points = sample_scene(disabled, generate_scene(disabled))

        self.assertEqual(plain_points, disabled_points)

    def test_enabled_mode_produces_lidar_points(self) -> None:
        config = _config_from_text(
            BASE_CONFIG.format(seed=321)
            + """
mobile_lidar:
  enabled: true
  output_mode: lidar_only
  trajectory: road
  sensor_height_m: 2.2
  position_step_m: 10
  min_range_m: 1.0
  max_range_m: 80
  horizontal_fov_degrees: 180
  horizontal_step_degrees: 6
  vertical_fov_degrees: 36
  vertical_center_degrees: -10
  vertical_channels: 6
  angle_jitter_degrees: 0
  range_noise_m: 0
  drop_probability: 0
  distance_attenuation: 0
  occlusions_enabled: true
  ray_step_m: 0.75
"""
        )
        points = sample_scene(config, generate_scene(config))

        self.assertGreater(len(points), 0)

    def test_occlusion_returns_nearest_visible_hit(self) -> None:
        config = _config_from_text(
            BASE_CONFIG.format(seed=11)
            + """
mobile_lidar:
  enabled: true
  occlusions_enabled: true
  min_range_m: 1
  max_range_m: 120
  angle_jitter_degrees: 0
  range_noise_m: 0
  drop_probability: 0
  distance_attenuation: 0
"""
        )

        front = Building(
            id="front",
            footprint=BuildingFootprint(kind="rectangle", parts=(Rect(12, -3, 16, 3),)),
            height_m=10.0,
            base_z=0.0,
        )
        back = Building(
            id="back",
            footprint=BuildingFootprint(kind="rectangle", parts=(Rect(30, -4, 36, 4),)),
            height_m=12.0,
            base_z=0.0,
        )

        road_network = SimpleNamespace(surface_kind=lambda _config, _x, _y: "ground")
        scene = SimpleNamespace(
            work_bbox=BBox(-20, -20, 120, 20),
            bbox=BBox(-20, -20, 80, 20),
            buildings=[front, back],
            fences=(),
            road_network=road_network,
        )
        origin = (0.0, 0.0, 2.2)
        direction = _ray_direction(0.0, -1.2)
        hit = _trace_ray(config, scene, origin, direction)

        self.assertIsNotNone(hit)
        if hit is None:
            self.fail("Expected the front facade to occlude farther geometry.")
        self.assertEqual(hit.class_name, "building_facade")
        self.assertLess(hit.distance_m, 20.0)

    def test_metadata_contains_mobile_lidar_statistics(self) -> None:
        config = _config_from_text(
            BASE_CONFIG.format(seed=222)
            + """
mobile_lidar:
  enabled: true
  output_mode: additive
  trajectory: line
  start_x: 0
  start_y: 0
  end_x: 96
  end_y: 0
  position_step_m: 12
  horizontal_step_degrees: 10
  vertical_channels: 4
"""
        )
        scene = generate_scene(config)
        points = sample_scene(config, scene)

        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "lidar.ply"
            metadata_path = write_metadata(ply_path, config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertIn("mobile_lidar", metadata)
        self.assertIn("point_sources", metadata)
        self.assertTrue(metadata["mobile_lidar"]["enabled"])
        self.assertGreater(metadata["mobile_lidar"]["sensor_positions"], 0)
        self.assertGreater(metadata["mobile_lidar"]["emitted_rays"], 0)
        self.assertIn("successful_hits", metadata["mobile_lidar"])
        self.assertIn("max_range_misses", metadata["mobile_lidar"])

    def test_mobile_lidar_is_deterministic_for_same_seed(self) -> None:
        lidar_block = """
mobile_lidar:
  enabled: true
  output_mode: lidar_only
  trajectory: road
  position_step_m: 8
  horizontal_step_degrees: 8
  vertical_channels: 8
  angle_jitter_degrees: 0.35
  range_noise_m: 0.04
  drop_probability: 0.1
  distance_attenuation: 0.2
"""
        config = _config_from_text(BASE_CONFIG.format(seed=404) + lidar_block)
        other_config = _config_from_text(BASE_CONFIG.format(seed=405) + lidar_block)

        first = sample_scene(config, generate_scene(config))
        second = sample_scene(config, generate_scene(config))
        other = sample_scene(other_config, generate_scene(other_config))

        self.assertEqual(len(first), len(second))
        self.assertEqual(first[:200], second[:200])
        self.assertGreater(len(first), 0)
        self.assertGreater(len(other), 0)
        count = min(80, len(first), len(other))
        self.assertNotEqual(first[:count], other[:count])


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
