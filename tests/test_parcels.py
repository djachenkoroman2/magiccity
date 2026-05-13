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
from citygen.geometry import OrientedRect, rect_to_oriented
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

    def test_oriented_rect_geometry_round_trips(self) -> None:
        rect = OrientedRect(center_x=10.0, center_y=20.0, width=30.0, depth=12.0, angle_degrees=30.0)
        world = rect.local_to_world(8.0, -3.0)
        local = rect.world_to_local(*world)

        self.assertAlmostEqual(local[0], 8.0, places=6)
        self.assertAlmostEqual(local[1], -3.0, places=6)
        self.assertTrue(rect.contains_xy(*world))
        self.assertFalse(rect.contains_xy(*rect.local_to_world(16.0, 0.0)))
        self.assertEqual(len(rect.corners()), 4)

    def test_rect_to_oriented_adapter_keeps_axis_aligned_geometry(self) -> None:
        config = load_config("configs/demo_parcels.yaml")
        scene = generate_scene(config)
        parcel = next(parcel for parcel in scene.parcels if parcel.buildable)
        oriented = rect_to_oriented(parcel.inner)

        self.assertEqual(oriented.angle_degrees, 0.0)
        self.assertEqual(oriented.width, parcel.inner.width)
        self.assertEqual(oriented.depth, parcel.inner.depth)
        self.assertTrue(oriented.contains_xy(parcel.inner.center_x, parcel.inner.center_y))

    def test_oriented_blocks_subdivide_parcels_in_local_space(self) -> None:
        config = load_config("configs/demo_oriented_parcels.yaml")
        scene = generate_scene(config)

        self.assertTrue(config.parcels.oriented_blocks)
        self.assertGreater(len(scene.blocks), 0)
        self.assertGreater(len(scene.parcels), 0)
        self.assertTrue(any(not _is_axis_aligned(block.orientation_degrees) for block in scene.blocks))
        self.assertTrue(any(not _is_axis_aligned(parcel.orientation_degrees) for parcel in scene.parcels))

        blocks = {block.id: block for block in scene.blocks}
        parcel = next(parcel for parcel in scene.parcels if not _is_axis_aligned(parcel.orientation_degrees))
        block = blocks[parcel.block_id]

        self.assertAlmostEqual(parcel.orientation_degrees, block.orientation_degrees, places=6)
        self.assertLessEqual(parcel.width, config.parcels.max_parcel_width_m + 1e-6)
        self.assertLessEqual(parcel.depth, config.parcels.max_parcel_depth_m + 1e-6)
        for x, y in parcel.geometry.corners():
            self.assertTrue(parcel.bbox.contains_xy(x, y))
            local = parcel.geometry.world_to_local(x, y)
            round_trip = parcel.geometry.local_to_world(*local)
            self.assertAlmostEqual(round_trip[0], x, places=6)
            self.assertAlmostEqual(round_trip[1], y, places=6)

    def test_grid_block_orientation_uses_configured_road_angle(self) -> None:
        config = _config_from_text(
            """
seed: 23
tile:
  size_m: 128
  margin_m: 24
roads:
  model: grid
  spacing_m: 80
  width_m: 6
  sidewalk_width_m: 2
  angle_degrees: 33
buildings:
  enabled: false
parcels:
  enabled: true
  oriented_blocks: true
  block_orientation_source: road_model
  block_orientation_jitter_degrees: 0
  block_size_m: 72
  block_jitter_m: 0
  min_block_size_m: 24
  min_parcel_width_m: 12
  max_parcel_width_m: 36
  min_parcel_depth_m: 12
  max_parcel_depth_m: 36
"""
        )
        scene = generate_scene(config)

        self.assertGreater(len(scene.blocks), 0)
        self.assertTrue(all(abs(block.orientation_degrees - 33.0) < 1e-6 for block in scene.blocks))
        self.assertTrue(all(abs(parcel.orientation_degrees - 33.0) < 1e-6 for parcel in scene.parcels))

    def test_buildings_align_to_oriented_parcels_and_avoid_hardscape(self) -> None:
        config = load_config("configs/demo_oriented_parcels.yaml")
        scene = generate_scene(config)
        parcels = {parcel.id: parcel for parcel in scene.parcels}
        oriented_buildings = [
            building
            for building in scene.buildings
            if building.parcel_id is not None and not _is_axis_aligned(parcels[building.parcel_id].orientation_degrees)
        ]

        self.assertGreater(len(oriented_buildings), 0)
        for building in oriented_buildings:
            parcel = parcels[building.parcel_id]
            self.assertAlmostEqual(building.orientation_degrees, parcel.orientation_degrees, places=6)
            for x, y in building.footprint.clearance_sample_points():
                self.assertTrue(parcel.buildable_geometry.contains_xy(x, y))
                self.assertEqual(scene.road_network.surface_kind(config, x, y), "ground")

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
            self.assertAlmostEqual(building.orientation_degrees, parcel.orientation_degrees, places=6)
            self.assertTrue(_rect_contains(parcel.inner, building.footprint.bbox))
            for x, y in building.footprint.clearance_sample_points():
                self.assertTrue(parcel.buildable_geometry.contains_xy(x, y))
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
        self.assertIn("parcel_building_alignment", metadata)
        self.assertIn("building_orientations", metadata)
        self.assertIn("block_geometry", metadata)
        self.assertIn("parcel_geometry", metadata)
        self.assertEqual(
            metadata["parcel_building_alignment"]["buildings_with_parcel_id"],
            metadata["building_counts"]["total"],
        )
        self.assertEqual(
            metadata["parcel_building_alignment"]["aligned_buildings"],
            metadata["building_counts"]["total"],
        )
        self.assertIn("orientation_bucket_degrees", metadata["block_geometry"])
        self.assertIn("orientation_bucket_degrees", metadata["parcel_geometry"])

    def test_cli_smoke_writes_demo_parcels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "demo_parcels.ply"
            exit_code = main(["--config", "configs/demo_parcels.yaml", "--out", str(out_path), "--quiet"])
            metadata_path = out_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertGreater(metadata["point_count"], 0)
        self.assertGreater(metadata["parcel_counts"]["blocks"], 0)
        self.assertGreater(metadata["parcel_counts"]["occupied_parcels"], 0)

    def test_cli_smoke_writes_demo_parcel_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "demo_parcel_alignment.ply"
            exit_code = main(
                ["--config", "configs/demo_parcel_alignment.yaml", "--out", str(out_path), "--quiet"]
            )
            metadata_path = out_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertGreater(metadata["point_count"], 0)
        self.assertGreater(metadata["parcel_counts"]["occupied_parcels"], 0)
        self.assertEqual(metadata["parcel_building_alignment"]["mode"], "parcel")
        self.assertEqual(
            metadata["parcel_building_alignment"]["aligned_buildings"],
            metadata["parcel_building_alignment"]["buildings_with_parcel_id"],
        )

    def test_cli_smoke_writes_demo_oriented_parcels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "demo_oriented_parcels.ply"
            exit_code = main(
                ["--config", "configs/demo_oriented_parcels.yaml", "--out", str(out_path), "--quiet"]
            )
            metadata_path = out_path.with_suffix(".metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertGreater(metadata["point_count"], 0)
        self.assertGreater(metadata["block_geometry"]["oriented_blocks"], 0)
        self.assertGreater(metadata["parcel_geometry"]["oriented_parcels"], 0)
        self.assertEqual(
            metadata["parcel_building_alignment"]["aligned_buildings"],
            metadata["parcel_building_alignment"]["buildings_with_parcel_id"],
        )


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


def _is_axis_aligned(angle_degrees: float) -> bool:
    angle = angle_degrees % 90.0
    return min(angle, 90.0 - angle) <= 1e-6


if __name__ == "__main__":
    unittest.main()
