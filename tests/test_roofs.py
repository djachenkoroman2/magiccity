from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import random
import tempfile
import unittest

from citygen.config import RoofConfig, load_config
from citygen.export import write_metadata, write_ply
from citygen.footprints import BuildingFootprint
from citygen.generator import generate_scene
from citygen.geometry import Building, Rect
from citygen.roofs import ROOF_KINDS, build_roof
from citygen.sampling import _sample_facades, _sample_roof, sample_scene


class RoofTests(unittest.TestCase):
    def test_roof_height_functions_are_distinct(self) -> None:
        footprint = _rect_footprint()
        cfg = RoofConfig(pitch_degrees=30, pitch_jitter_degrees=0, flat_slope_degrees=0)

        flat = build_roof("flat", footprint, 0.0, 20.0, cfg, random.Random(1))
        self.assertEqual(flat.height_at(0, 0, footprint), 20.0)
        self.assertEqual(flat.height_at(-10, 0, footprint), 20.0)

        shed = build_roof("shed", footprint, 0.0, 20.0, cfg, random.Random(1))
        self.assertLess(shed.height_at(-10, 0, footprint), shed.height_at(10, 0, footprint))

        for kind in ("gable", "hip", "half_hip", "pyramid", "mansard", "dome", "barrel", "cone"):
            with self.subTest(kind=kind):
                roof = build_roof(kind, footprint, 0.0, 20.0, cfg, random.Random(1))
                self.assertGreater(roof.height_at(0, 0, footprint), roof.height_at(-10, -10, footprint))

    def test_all_roof_types_sample_nonempty_roofs(self) -> None:
        config = _config_from_text(
            """
seed: 1
sampling:
  building_spacing_m: 3
  jitter_ratio: 0
"""
        )
        footprint = _rect_footprint()
        cfg = RoofConfig(pitch_degrees=30, pitch_jitter_degrees=0)

        for kind in ROOF_KINDS:
            with self.subTest(kind=kind):
                roof = build_roof(kind, footprint, 0.0, 20.0, cfg, random.Random(2))
                building = Building(kind, footprint, height_m=20.0, base_y=0.0, roof=roof)
                points = _sample_roof(config, building, 3.0, random.Random(3))

                self.assertGreater(len(points), 0)
                for point in points:
                    self.assertTrue(footprint.contains_xy(point.x, point.z))

    def test_roof_sampling_skips_courtyard_hole(self) -> None:
        footprint = BuildingFootprint(
            kind="courtyard",
            parts=(Rect(-12, -12, 12, 12),),
            holes=(Rect(-4, -4, 4, 4),),
        )
        roof = build_roof("dome", footprint, 0.0, 20.0, RoofConfig(pitch_jitter_degrees=0), random.Random(4))
        building = Building("courtyard", footprint, height_m=20.0, base_y=0.0, roof=roof)
        config = _config_from_text(
            """
seed: 1
sampling:
  building_spacing_m: 2
  jitter_ratio: 0
"""
        )

        points = _sample_roof(config, building, 2.0, random.Random(5))

        self.assertGreater(len(points), 0)
        self.assertFalse(any(footprint.holes[0].contains_xy(point.x, point.z) for point in points))

    def test_facades_stop_at_eave_height(self) -> None:
        footprint = _rect_footprint()
        roof = build_roof("gable", footprint, 0.0, 20.0, RoofConfig(pitch_jitter_degrees=0), random.Random(6))
        building = Building("gable", footprint, height_m=20.0, base_y=0.0, roof=roof)
        config = _config_from_text(
            """
seed: 1
sampling:
  building_spacing_m: 3
  jitter_ratio: 0
"""
        )

        points = _sample_facades(config, building, 3.0, random.Random(7))

        self.assertGreater(len(points), 0)
        self.assertLessEqual(max(point.y for point in points), roof.eave_y)

    def test_mixed_roofs_are_deterministic_and_reach_metadata(self) -> None:
        config = _config_from_text(
            """
seed: 77
tile:
  size_m: 192
  margin_m: 32
roads:
  spacing_m: 96
  width_m: 6
  sidewalk_width_m: 2
buildings:
  min_height_m: 12
  max_height_m: 30
  footprint_min_m: 14
  footprint_max_m: 30
  roof:
    model: mixed
    weights:
      flat: 1
      shed: 1
      gable: 1
      hip: 1
      half_hip: 1
      pyramid: 1
      mansard: 1
      dome: 1
      barrel: 1
      cone: 1
    pitch_jitter_degrees: 0
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
        roofs = Counter(building.roof.kind for building in scene_a.buildings if building.roof is not None)

        self.assertEqual([building.roof.kind for building in scene_a.buildings], [building.roof.kind for building in scene_b.buildings])
        self.assertEqual(points_a[:100], points_b[:100])
        self.assertGreaterEqual(len(roofs), 2)

        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "roofs.ply"
            write_ply(ply_path, points_a, config)
            metadata_path = write_metadata(ply_path, config, scene_a, points_a)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(metadata["building_counts"]["by_roof"], dict(sorted(roofs.items())))
        self.assertIn("supported_roof_types", metadata)


def _rect_footprint() -> BuildingFootprint:
    return BuildingFootprint(kind="rectangle", parts=(Rect(-10.0, -10.0, 10.0, 10.0),))


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
