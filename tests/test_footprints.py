from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import random
import tempfile
import unittest

from citygen.config import FootprintConfig, load_config
from citygen.export import write_metadata, write_ply
from citygen.footprints import FOOTPRINT_KINDS, build_footprint
from citygen.generator import generate_scene
from citygen.geometry import Building
from citygen.sampling import _sample_facades, _sample_roof, sample_scene


class FootprintTests(unittest.TestCase):
    def test_all_footprint_types_have_geometry(self) -> None:
        cfg = FootprintConfig()
        for kind in FOOTPRINT_KINDS:
            with self.subTest(kind=kind):
                footprint = build_footprint(kind, 0.0, 0.0, 24.0, 36.0, cfg, random.Random(3))

                self.assertEqual(footprint.kind, kind)
                self.assertGreater(footprint.bbox.width, 0)
                self.assertGreater(footprint.bbox.depth, 0)
                self.assertGreater(len(footprint.boundary_segments()), 0)

    def test_circle_roof_points_stay_inside_circle(self) -> None:
        cfg = FootprintConfig(model="circle", circle_segments=24)
        footprint = build_footprint("circle", 0.0, 0.0, 20.0, 20.0, cfg, random.Random(4))
        building = Building("circle", footprint, height_m=12.0, base_y=0.0)
        config = _config_from_text(
            """
seed: 1
buildings:
  footprint:
    model: circle
sampling:
  building_spacing_m: 2
  jitter_ratio: 0
"""
        )

        points = _sample_roof(config, building, 2.0, random.Random(5))

        self.assertGreater(len(points), 0)
        for point in points:
            self.assertTrue(footprint.contains_xy(point.x, point.z))

    def test_courtyard_roof_points_skip_inner_court(self) -> None:
        cfg = FootprintConfig(model="courtyard", courtyard_ratio=0.5, min_part_width_m=4)
        footprint = build_footprint("courtyard", 0.0, 0.0, 28.0, 28.0, cfg, random.Random(6))
        building = Building("courtyard", footprint, height_m=12.0, base_y=0.0)
        config = _config_from_text(
            """
seed: 1
buildings:
  footprint:
    model: courtyard
sampling:
  building_spacing_m: 2
  jitter_ratio: 0
"""
        )

        points = _sample_roof(config, building, 2.0, random.Random(7))
        hole = footprint.holes[0]

        self.assertGreater(len(points), 0)
        self.assertFalse(any(hole.contains_xy(point.x, point.z) for point in points))

    def test_composite_footprints_have_roofs_and_facades(self) -> None:
        config = _config_from_text(
            """
seed: 1
sampling:
  building_spacing_m: 3
  jitter_ratio: 0
"""
        )
        for kind in ("l_shape", "u_shape", "t_shape"):
            with self.subTest(kind=kind):
                footprint = build_footprint(kind, 0.0, 0.0, 30.0, 36.0, FootprintConfig(), random.Random(8))
                building = Building(kind, footprint, height_m=12.0, base_y=0.0)

                self.assertGreater(len(_sample_roof(config, building, 3.0, random.Random(9))), 0)
                self.assertGreater(len(_sample_facades(config, building, 3.0, random.Random(10))), 0)

    def test_mixed_footprints_are_deterministic_and_reach_metadata(self) -> None:
        config = _config_from_text(
            """
seed: 41
tile:
  size_m: 160
  margin_m: 32
roads:
  spacing_m: 80
  width_m: 6
  sidewalk_width_m: 2
buildings:
  min_height_m: 8
  max_height_m: 22
  footprint_min_m: 14
  footprint_max_m: 30
  footprint:
    model: mixed
    weights:
      rectangle: 1
      circle: 1
      courtyard: 1
      l_shape: 1
      u_shape: 1
      t_shape: 1
sampling:
  ground_spacing_m: 8
  road_spacing_m: 6
  building_spacing_m: 5
  jitter_ratio: 0
"""
        )
        scene_a = generate_scene(config)
        scene_b = generate_scene(config)
        points_a = sample_scene(config, scene_a)
        points_b = sample_scene(config, scene_b)
        kinds = Counter(building.footprint.kind for building in scene_a.buildings)

        self.assertEqual([building.footprint.kind for building in scene_a.buildings], [building.footprint.kind for building in scene_b.buildings])
        self.assertEqual(points_a[:100], points_b[:100])
        self.assertGreaterEqual(len(kinds), 2)

        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "mixed.ply"
            write_ply(ply_path, points_a, config)
            metadata_path = write_metadata(ply_path, config, scene_a, points_a)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(metadata["building_counts"]["by_footprint"], dict(sorted(kinds.items())))

    def test_generated_footprints_avoid_road_and_sidewalk_samples(self) -> None:
        config = _config_from_text(
            """
seed: 55
tile:
  size_m: 128
  margin_m: 32
roads:
  spacing_m: 64
  width_m: 6
  sidewalk_width_m: 2
buildings:
  footprint_min_m: 14
  footprint_max_m: 28
  footprint:
    model: mixed
sampling:
  ground_spacing_m: 8
  road_spacing_m: 6
  building_spacing_m: 5
"""
        )
        scene = generate_scene(config)

        for building in scene.buildings:
            for x, z in building.footprint.clearance_sample_points():
                if building.footprint.contains_xy(x, z):
                    self.assertEqual(scene.road_network.surface_kind(config, x, z), "ground")


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
