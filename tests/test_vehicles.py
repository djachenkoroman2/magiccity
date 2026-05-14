from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from citygen.classes import CLASS_BY_ID, POINT_CLASSES
from citygen.config import load_config
from citygen.export import write_metadata
from citygen.generator import generate_scene
from citygen.geometry import BBox, angle_delta_degrees
from citygen.mobile_lidar import _trace_ray
from citygen.sampling import sample_scene
from citygen.vehicles import Vehicle


ROAD_VEHICLE_CONFIG = """
seed: 905
tile:
  size_m: 96
  margin_m: 8
roads:
  model: grid
  spacing_m: 48
  width_m: 8
  sidewalk_width_m: 1
buildings:
  enabled: false
vehicles:
  enabled: true
  density_per_km: 80
  parking_density_per_ha: 0
  min_spacing_m: 6
  placement_modes:
    - road
  orientation_jitter_degrees: 0
  sample_spacing_m: 1.5
sampling:
  ground_spacing_m: 16
  road_spacing_m: 8
  building_spacing_m: 8
  jitter_ratio: 0
"""


PARKING_VEHICLE_CONFIG = """
seed: 907
tile:
  size_m: 128
  margin_m: 8
roads:
  model: grid
  spacing_m: 128
  width_m: 6
  sidewalk_width_m: 1
buildings:
  enabled: false
parcels:
  enabled: true
  block_size_m: 64
  block_jitter_m: 0
  min_block_size_m: 24
  min_parcel_width_m: 12
  max_parcel_width_m: 30
  min_parcel_depth_m: 12
  max_parcel_depth_m: 30
  parcel_setback_m: 1
  max_subdivision_depth: 3
vehicles:
  enabled: true
  density_per_km: 0
  parking_density_per_ha: 120
  min_spacing_m: 5
  placement_modes:
    - parking
  vehicle_type: car
  sample_spacing_m: 2
sampling:
  ground_spacing_m: 16
  road_spacing_m: 8
  jitter_ratio: 0
"""


class VehicleGenerationTests(unittest.TestCase):
    def test_enabled_vehicles_create_instances_and_points(self) -> None:
        config = _config_from_text(ROAD_VEHICLE_CONFIG)
        scene = generate_scene(config)
        points = sample_scene(config, scene)
        class_counts = _class_counts(points)

        self.assertGreater(len(scene.vehicles), 0)
        self.assertEqual(scene.vehicle_counts["total"], len(scene.vehicles))
        self.assertGreater(class_counts["vehicle_body"], 0)
        self.assertGreater(class_counts["vehicle_wheel"], 0)
        self.assertGreater(class_counts["vehicle_window"], 0)
        self.assertEqual(POINT_CLASSES["vehicle_body"].id, 11)
        self.assertEqual(POINT_CLASSES["vehicle_wheel"].id, 12)
        self.assertEqual(POINT_CLASSES["vehicle_window"].id, 13)

    def test_disabled_vehicles_do_not_change_surface_points(self) -> None:
        base = _config_from_text(_without_vehicle_section(ROAD_VEHICLE_CONFIG))
        disabled = _config_from_text(
            _without_vehicle_section(ROAD_VEHICLE_CONFIG)
            + """
vehicles:
  enabled: false
"""
        )

        base_scene = generate_scene(base)
        disabled_scene = generate_scene(disabled)

        self.assertEqual(base_scene.vehicles, ())
        self.assertEqual(disabled_scene.vehicles, ())
        self.assertEqual(sample_scene(base, base_scene), sample_scene(disabled, disabled_scene))

    def test_road_vehicles_stay_on_carriageway_and_keep_road_orientation(self) -> None:
        config = _config_from_text(ROAD_VEHICLE_CONFIG)
        scene = generate_scene(config)

        self.assertGreater(len(scene.vehicles), 0)
        for vehicle in scene.vehicles:
            with self.subTest(vehicle=vehicle.id):
                self.assertEqual(vehicle.placement_mode, "road")
                self.assertEqual(scene.road_network.surface_kind(config, vehicle.x, vehicle.y), "road")
                self.assertLessEqual(
                    min(angle_delta_degrees(vehicle.orientation_degrees, target) for target in (0, 90, 180, 270)),
                    1e-6,
                )

    def test_parking_vehicles_stay_on_ground_inside_parcels(self) -> None:
        config = _config_from_text(PARKING_VEHICLE_CONFIG)
        scene = generate_scene(config)

        self.assertGreater(len(scene.vehicles), 0)
        self.assertGreater(scene.parcel_counts["buildable_parcels"], 0)
        for vehicle in scene.vehicles:
            with self.subTest(vehicle=vehicle.id):
                self.assertEqual(vehicle.placement_mode, "parking")
                self.assertEqual(scene.road_network.surface_kind(config, vehicle.x, vehicle.y), "ground")
                self.assertIsNotNone(vehicle.parcel_id)

    def test_vehicles_avoid_trees(self) -> None:
        config = _config_from_text(
            ROAD_VEHICLE_CONFIG.replace(
                "vehicles:\n",
                """
trees:
  enabled: true
  density_per_ha: 80
  min_spacing_m: 6
  road_clearance_m: 1
  building_clearance_m: 1
  fence_clearance_m: 0.5
vehicles:
""",
            )
        )
        scene = generate_scene(config)

        self.assertGreater(len(scene.vehicles), 0)
        self.assertGreater(len(scene.trees), 0)
        for vehicle in scene.vehicles:
            for tree in scene.trees:
                distance = math.hypot(vehicle.x - tree.x, vehicle.y - tree.y)
                self.assertGreater(distance, config.vehicles.tree_clearance_m)

    def test_biome_density_multipliers_control_vehicle_count(self) -> None:
        zero_config = _config_from_text(
            _vehicle_density_config(
                """
  biome_density_multipliers:
    residential: 0
    downtown: 0
    industrial: 0
    suburb: 0
"""
            )
        )
        high_config = _config_from_text(
            _vehicle_density_config(
                """
  biome_density_multipliers:
    residential: 2
    downtown: 0
    industrial: 0
    suburb: 0
"""
            )
        )

        self.assertEqual(len(generate_scene(zero_config).vehicles), 0)
        self.assertGreater(len(generate_scene(high_config).vehicles), 0)

    def test_vehicle_weights_control_mixed_types(self) -> None:
        config = _config_from_text(
            ROAD_VEHICLE_CONFIG.replace(
                "sample_spacing_m: 1.5",
                """
  weights:
    car: 0
    truck: 1
    bus: 0
    emergency: 0
    tractor: 0
  sample_spacing_m: 1.5
""",
            )
        )
        scene = generate_scene(config)

        self.assertGreater(len(scene.vehicles), 0)
        self.assertEqual({vehicle.vehicle_type for vehicle in scene.vehicles}, {"truck"})

    def test_same_seed_produces_same_vehicles_and_points(self) -> None:
        config_a = _config_from_text(ROAD_VEHICLE_CONFIG)
        config_b = _config_from_text(ROAD_VEHICLE_CONFIG)

        scene_a = generate_scene(config_a)
        scene_b = generate_scene(config_b)

        self.assertEqual(scene_a.vehicles, scene_b.vehicles)
        self.assertEqual(sample_scene(config_a, scene_a), sample_scene(config_b, scene_b))

    def test_metadata_contains_vehicle_counts_and_class_mapping(self) -> None:
        config = _config_from_text(ROAD_VEHICLE_CONFIG)
        scene = generate_scene(config)
        points = sample_scene(config, scene)

        with tempfile.TemporaryDirectory() as tmp:
            metadata_path = write_metadata(Path(tmp) / "vehicles.ply", config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        class_counts = _class_counts(points)
        self.assertEqual(metadata["vehicle_counts"]["total"], len(scene.vehicles))
        self.assertEqual(metadata["vehicle_counts"]["body_points"], class_counts["vehicle_body"])
        self.assertEqual(metadata["vehicle_counts"]["wheel_points"], class_counts["vehicle_wheel"])
        self.assertEqual(metadata["vehicle_counts"]["window_points"], class_counts["vehicle_window"])
        self.assertEqual(metadata["object_feature_counts"]["vehicle"], len(scene.vehicles))
        self.assertEqual(metadata["object_feature_counts"]["vehicle_body"], class_counts["vehicle_body"])
        self.assertEqual(metadata["object_feature_counts"]["vehicle_wheel"], class_counts["vehicle_wheel"])
        self.assertEqual(metadata["object_feature_counts"]["vehicle_window"], class_counts["vehicle_window"])
        self.assertEqual(metadata["class_mapping"]["vehicle_body"], 11)
        self.assertEqual(metadata["class_mapping"]["vehicle_wheel"], 12)
        self.assertEqual(metadata["class_mapping"]["vehicle_window"], 13)
        self.assertEqual(metadata["class_colors"]["vehicle_body"], [52, 93, 142])
        self.assertEqual(metadata["class_colors"]["vehicle_wheel"], [28, 30, 33])
        self.assertEqual(metadata["class_colors"]["vehicle_window"], [98, 148, 172])
        self.assertIn("truck", metadata["supported_vehicle_types"])
        self.assertEqual(metadata["vehicle_aliases"]["sedan"], "car")
        self.assertIn("truck", metadata["vehicle_catalog"])
        self.assertIn("vehicles", metadata["worldgen"]["stages"])

    def test_mobile_lidar_ray_can_hit_vehicle_body(self) -> None:
        config = _config_from_text(
            """
seed: 1
mobile_lidar:
  enabled: true
  min_range_m: 0.1
  max_range_m: 50
  occlusions_enabled: true
"""
        )
        vehicle = Vehicle(
            id="manual_vehicle",
            vehicle_type="car",
            x=10,
            y=0,
            base_z=0,
            length_m=4.5,
            width_m=1.8,
            height_m=1.5,
            wheel_radius_m=0.34,
            orientation_degrees=0,
            biome="residential",
            placement_mode="road",
            body_color=(52, 93, 142),
        )
        scene = SimpleNamespace(
            bbox=BBox(0, -5, 20, 5),
            buildings=(),
            fences=(),
            trees=(),
            vehicles=(vehicle,),
        )

        hit = _trace_ray(config, scene, origin=(0, 0, 0.8), direction=(1, 0, 0))

        self.assertIsNotNone(hit)
        self.assertEqual(hit.class_name, "vehicle_body")


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


def _class_counts(points) -> Counter[str]:
    return Counter(CLASS_BY_ID[point.class_id].name for point in points)


def _without_vehicle_section(text: str) -> str:
    return text.split("vehicles:\n", 1)[0] + "sampling:\n" + text.split("sampling:\n", 1)[1]


def _vehicle_density_config(extra: str) -> str:
    return (
        """
seed: 41
tile:
  size_m: 96
roads:
  model: grid
  spacing_m: 48
  width_m: 8
  sidewalk_width_m: 1
buildings:
  enabled: false
vehicles:
  enabled: true
  density_per_km: 100
  parking_density_per_ha: 0
  min_spacing_m: 5
  placement_modes:
    - road
  vehicle_type: car
  sample_spacing_m: 2
"""
        + extra
        + """
sampling:
  ground_spacing_m: 12
  road_spacing_m: 8
  jitter_ratio: 0
"""
    )


if __name__ == "__main__":
    unittest.main()
