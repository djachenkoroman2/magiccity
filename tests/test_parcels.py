from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from citygen.cli import main
from citygen.config import ConfigError, load_config
from citygen.export import write_metadata, write_ply
from citygen.generator import generate_scene
from citygen.sampling import sample_scene


class ParcelTests(unittest.TestCase):
    def test_loads_parcel_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
parcels:
  enabled: true
  block_size_m: 80
  min_parcel_width_m: 12
  max_parcel_width_m: 32
"""
        )

        self.assertTrue(config.parcels.enabled)
        self.assertEqual(config.parcels.block_size_m, 80.0)
        self.assertEqual(config.parcels.max_parcel_width_m, 32.0)

    def test_invalid_parcel_config_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  min_parcel_width_m: 40
  max_parcel_width_m: 20
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  block_size: 80
"""
            )

    def test_parcel_generation_is_deterministic(self) -> None:
        config = load_config("configs/demo_parcels.yaml")

        scene_a = generate_scene(config)
        scene_b = generate_scene(config)

        self.assertEqual(scene_a.parcels, scene_b.parcels)
        self.assertEqual(
            [(building.id, building.parcel_id, building.footprint.bbox) for building in scene_a.buildings],
            [(building.id, building.parcel_id, building.footprint.bbox) for building in scene_b.buildings],
        )

    def test_different_seed_changes_parcels_or_buildings(self) -> None:
        config = load_config("configs/demo_parcels.yaml")
        scene_a = generate_scene(config)
        scene_b = generate_scene(replace(config, seed=config.seed + 1))

        self.assertNotEqual(
            [(parcel.id, parcel.bbox) for parcel in scene_a.parcels],
            [(parcel.id, parcel.bbox) for parcel in scene_b.parcels],
        )
        self.assertNotEqual(
            [(building.parcel_id, building.footprint.bbox) for building in scene_a.buildings],
            [(building.parcel_id, building.footprint.bbox) for building in scene_b.buildings],
        )

    def test_buildings_stay_inside_parcels_and_avoid_roads(self) -> None:
        config = load_config("configs/demo_parcels.yaml")
        scene = generate_scene(config)
        parcels = {parcel.id: parcel for parcel in scene.parcels}

        self.assertGreater(len(scene.blocks), 0)
        self.assertGreater(len(scene.parcels), 0)
        self.assertGreater(len(scene.buildings), 0)
        for parcel in scene.parcels:
            self.assertGreater(parcel.width, 0)
            self.assertGreater(parcel.depth, 0)
            self.assertGreater(parcel.area_m2, 0)

        for building in scene.buildings:
            self.assertIsNotNone(building.parcel_id)
            parcel = parcels[building.parcel_id]
            self.assertTrue(_rect_contains(parcel.inner, building.footprint.bbox))
            for x, y in building.footprint.clearance_sample_points():
                self.assertTrue(parcel.inner.contains_xy(x, y))
                self.assertEqual(scene.road_network.surface_kind(config, x, y), "ground")

        for index, building in enumerate(scene.buildings):
            for other in scene.buildings[index + 1 :]:
                self.assertFalse(_rects_overlap(building.footprint.bbox, other.footprint.bbox))

    def test_metadata_contains_parcel_counts(self) -> None:
        config = load_config("configs/demo_parcels.yaml")
        scene = generate_scene(config)
        points = sample_scene(config, scene)
        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "parcels.ply"
            write_ply(ply_path, points, config)
            metadata_path = write_metadata(ply_path, config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        parcel_counts = metadata["parcel_counts"]
        self.assertGreater(parcel_counts["blocks"], 0)
        self.assertGreater(parcel_counts["parcels"], 0)
        self.assertGreater(parcel_counts["buildable_parcels"], 0)
        self.assertGreater(parcel_counts["occupied_parcels"], 0)
        self.assertEqual(parcel_counts["buildings_with_parcel_id"], metadata["building_counts"]["total"])
        self.assertIn("by_parcel_biome", metadata["building_counts"])

    def test_cli_smoke_writes_demo_parcels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "demo_parcels.ply"
            exit_code = main(["--config", "configs/demo_parcels.yaml", "--out", str(out_path)])
            metadata_path = out_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertGreater(metadata["point_count"], 0)
        self.assertGreater(metadata["parcel_counts"]["blocks"], 0)
        self.assertGreater(metadata["parcel_counts"]["occupied_parcels"], 0)


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


def _rect_contains(outer, inner) -> bool:
    return (
        outer.min_x <= inner.min_x
        and outer.max_x >= inner.max_x
        and outer.min_y <= inner.min_y
        and outer.max_y >= inner.max_y
    )


def _rects_overlap(a, b) -> bool:
    return not (a.max_x < b.min_x or a.min_x > b.max_x or a.max_y < b.min_y or a.min_y > b.max_y)


if __name__ == "__main__":
    unittest.main()
