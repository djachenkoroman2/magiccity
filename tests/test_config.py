from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from citygen.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_loads_minimal_config_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("seed: 7\n", encoding="utf-8")

            config = load_config(path)

        self.assertEqual(config.seed, 7)
        self.assertEqual(config.tile.size_m, 256.0)
        self.assertEqual(config.roads.model, "grid")
        self.assertEqual(config.buildings.footprint.model, "rectangle")
        self.assertEqual(config.buildings.roof.model, "flat")

    def test_missing_seed_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("tile:\n  x: 0\n", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_config(path)

    def test_loads_terrain_features(self) -> None:
        config = _config_from_text(
            """
seed: 7
terrain:
  base_height_m: 2
  height_noise_m: 0
  mountains:
    - center_x: 10
      center_y: 20
      height_m: 120
      radius_m: 80
  hills:
    - center_x: 30
      center_y: 40
      height_m: 24
      radius_m: 140
  ravines:
    - center_x: 50
      center_y: 60
      length_m: 300
      width_m: 30
      depth_m: 18
      angle_degrees: 35
"""
        )

        self.assertEqual(config.terrain.base_height_m, 2.0)
        self.assertEqual(config.terrain.mountains[0].height_m, 120.0)
        self.assertEqual(config.terrain.hills[0].radius_m, 140.0)
        self.assertEqual(config.terrain.ravines[0].angle_degrees, 35.0)

    def test_invalid_terrain_features_are_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
terrain:
  mountains:
    - center_x: 0
      center_y: 0
      height_m: 20
      radius_m: 0
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
terrain:
  ravines:
    - center_x: 0
      center_y: 0
      length_m: 100
      width_m: 20
      depth_m: -5
"""
            )

    def test_loads_footprint_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
buildings:
  footprint:
    model: mixed
    weights:
      rectangle: 0.5
      rotunda: 0.5
    circle_segments: 16
"""
        )

        self.assertEqual(config.buildings.footprint.model, "mixed")
        self.assertEqual(config.buildings.footprint.weights["circle"], 0.5)
        self.assertEqual(config.buildings.footprint.circle_segments, 16)

    def test_unknown_footprint_model_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  footprint:
    model: pyramid
"""
            )

    def test_negative_footprint_weight_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  footprint:
    model: mixed
    weights:
      rectangle: 1
      circle: -1
"""
            )

    def test_zero_mixed_footprint_weight_sum_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  footprint:
    model: mixed
    weights:
      rectangle: 0
      circle: 0
"""
            )

    def test_loads_roof_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
buildings:
  roof:
    model: mixed
    weights:
      flat: 0.4
      pitched: 0.6
    pitch_degrees: 34
    dome_segments: 20
"""
        )

        self.assertEqual(config.buildings.roof.model, "mixed")
        self.assertEqual(config.buildings.roof.weights["gable"], 0.6)
        self.assertEqual(config.buildings.roof.pitch_degrees, 34)
        self.assertEqual(config.buildings.roof.dome_segments, 20)

    def test_unknown_roof_model_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  roof:
    model: impossible
"""
            )

    def test_negative_roof_weight_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  roof:
    model: mixed
    weights:
      flat: 1
      dome: -1
"""
            )

    def test_zero_mixed_roof_weight_sum_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
buildings:
  roof:
    model: mixed
    weights:
      flat: 0
      dome: 0
"""
            )

    def test_loads_parcel_alignment_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
parcels:
  enabled: true
  building_alignment: parcel
  orientation_jitter_degrees: 3
  max_building_coverage: 0.65
  require_building_inside_buildable_area: true
  oriented_blocks: true
  block_orientation_source: road_model
  block_orientation_jitter_degrees: 4
  organic_orientation_jitter_degrees: 12
"""
        )

        self.assertEqual(config.parcels.building_alignment, "parcel")
        self.assertEqual(config.parcels.orientation_jitter_degrees, 3.0)
        self.assertEqual(config.parcels.max_building_coverage, 0.65)
        self.assertTrue(config.parcels.require_building_inside_buildable_area)
        self.assertTrue(config.parcels.oriented_blocks)
        self.assertEqual(config.parcels.block_orientation_source, "road_model")
        self.assertEqual(config.parcels.block_orientation_jitter_degrees, 4.0)
        self.assertEqual(config.parcels.organic_orientation_jitter_degrees, 12.0)

    def test_invalid_parcel_alignment_config_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  building_alignment: diagonal
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  orientation_jitter_degrees: -1
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  max_building_coverage: 1.5
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  block_orientation_source: nearest_lane
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
  block_orientation_jitter_degrees: -1
"""
            )

    def test_loads_fence_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  mode: partial
  type: chain_link
  height_m: 2.2
  height_jitter_m: 0.1
  sides:
    - front
    - right
  gate_sides:
    - front
  foundation: always
  openness: 0.7
  decorative: true
"""
        )

        self.assertTrue(config.fences.enabled)
        self.assertEqual(config.fences.mode, "partial")
        self.assertEqual(config.fences.type, "metal_chain_link")
        self.assertEqual(config.fences.height_m, 2.2)
        self.assertEqual(config.fences.sides, ("front", "right"))
        self.assertEqual(config.fences.gate_sides, ("front",))
        self.assertEqual(config.fences.foundation, "always")
        self.assertEqual(config.fences.openness, 0.7)
        self.assertTrue(config.fences.decorative)

    def test_invalid_fence_config_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
fences:
  enabled: true
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  type: hedge
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  sides:
    - diagonal
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  openness: 1.2
"""
            )

    def test_loads_tree_config_with_defaults_and_aliases(self) -> None:
        config = _config_from_text(
            """
seed: 7
trees:
  enabled: true
  density_per_ha: 22
  min_spacing_m: 6
  height_m: 9
  height_jitter_m: 0.5
  trunk_radius_m: 0.25
  trunk_height_ratio: 0.4
  crown_shape: sphere
  crown_radius_m: 3
  crown_height_ratio: 0.6
  crown_segments: 10
  weights:
    round: 1
    conical: 2
  biome_density_multipliers:
    residential: 0
    suburb: 2
  road_clearance_m: 1
  building_clearance_m: 2
  fence_clearance_m: 0.5
  tile_margin_clearance_m: 1
  allow_road_medians: true
  sample_spacing_m: 0.8
"""
        )

        self.assertTrue(config.trees.enabled)
        self.assertEqual(config.trees.crown_shape, "round")
        self.assertEqual(config.trees.weights["cone"], 2.0)
        self.assertEqual(config.trees.biome_density_multipliers["residential"], 0.0)
        self.assertEqual(config.trees.biome_density_multipliers["suburb"], 2.0)
        self.assertTrue(config.trees.allow_road_medians)

    def test_invalid_tree_config_is_error(self) -> None:
        invalid_configs = [
            """
seed: 7
trees:
  density_per_ha: -1
""",
            """
seed: 7
trees:
  min_spacing_m: 0
""",
            """
seed: 7
trees:
  crown_shape: impossible
""",
            """
seed: 7
trees:
  crown_shape: mixed
  weights:
    round: 0
    cone: 0
""",
            """
seed: 7
trees:
  weights:
    round: -1
""",
            """
seed: 7
trees:
  biome_density_multipliers:
    tundra: 1
""",
            """
seed: 7
trees:
  unknown_field: true
""",
        ]
        for text in invalid_configs:
            with self.subTest(text=text):
                with self.assertRaises(ConfigError):
                    _config_from_text(text)

    def test_loads_vehicle_config_with_defaults_and_aliases(self) -> None:
        config = _config_from_text(
            """
seed: 7
vehicles:
  enabled: true
  density_per_km: 30
  parking_density_per_ha: 18
  min_spacing_m: 5
  placement_modes: mixed
  vehicle_type: sedan
  weights:
    sedan: 1
    lorry: 2
    firetruck: 3
    farm_tractor: 4
  biome_density_multipliers:
    residential: 0
    industrial: 2
  length_m: 4.8
  width_m: 1.9
  height_m: 1.6
  wheel_radius_m: 0.36
  clearance_m: 0.5
  orientation_jitter_degrees: 2
  building_clearance_m: 1
  fence_clearance_m: 0.5
  tree_clearance_m: 1.2
  tile_margin_clearance_m: 1
  allowed_road_profiles:
    - default
  lane_offset_m: 2
  parked_ratio: 0.4
  side_of_road: left
  sample_spacing_m: 0.9
  max_points_per_vehicle: 320
"""
        )

        self.assertTrue(config.vehicles.enabled)
        self.assertEqual(config.vehicles.vehicle_type, "car")
        self.assertEqual(config.vehicles.placement_modes, ("road", "parking", "industrial_yard"))
        self.assertEqual(config.vehicles.weights["truck"], 2.0)
        self.assertEqual(config.vehicles.weights["emergency"], 3.0)
        self.assertEqual(config.vehicles.weights["tractor"], 4.0)
        self.assertEqual(config.vehicles.biome_density_multipliers["residential"], 0.0)
        self.assertEqual(config.vehicles.biome_density_multipliers["industrial"], 2.0)
        self.assertEqual(config.vehicles.allowed_road_profiles, ("default",))
        self.assertEqual(config.vehicles.side_of_road, "left")

    def test_invalid_vehicle_config_is_error(self) -> None:
        invalid_configs = [
            """
seed: 7
vehicles:
  unknown_field: true
""",
            """
seed: 7
vehicles:
  density_per_km: -1
""",
            """
seed: 7
vehicles:
  parking_density_per_ha: -1
""",
            """
seed: 7
vehicles:
  min_spacing_m: 0
""",
            """
seed: 7
vehicles:
  vehicle_type: hovercraft
""",
            """
seed: 7
vehicles:
  placement_modes:
    - sidewalk
""",
            """
seed: 7
vehicles:
  vehicle_type: mixed
  weights:
    car: 0
    truck: 0
""",
            """
seed: 7
vehicles:
  weights:
    car: -1
""",
            """
seed: 7
vehicles:
  biome_density_multipliers:
    tundra: 1
""",
            """
seed: 7
vehicles:
  building_clearance_m: -1
""",
            """
seed: 7
vehicles:
  side_of_road: center
""",
            """
seed: 7
vehicles:
  parked_ratio: 1.2
""",
            """
seed: 7
vehicles:
  length_m: 0
""",
        ]
        for text in invalid_configs:
            with self.subTest(text=text):
                with self.assertRaises(ConfigError):
                    _config_from_text(text)

    def test_loads_mobile_lidar_config(self) -> None:
        config = _config_from_text(
            """
seed: 7
mobile_lidar:
  enabled: true
  output_mode: lidar_only
  trajectory: road
  sensor_height_m: 2.4
  direction_degrees: 25
  position_step_m: 5
  min_range_m: 1.5
  max_range_m: 80
  horizontal_fov_degrees: 220
  horizontal_step_degrees: 2
  vertical_fov_degrees: 42
  vertical_center_degrees: -6
  vertical_channels: 16
  angle_jitter_degrees: 0.4
  range_noise_m: 0.02
  drop_probability: 0.1
  distance_attenuation: 0.3
  occlusions_enabled: true
  ray_step_m: 0.5
"""
        )
        self.assertTrue(config.mobile_lidar.enabled)
        self.assertEqual(config.mobile_lidar.output_mode, "lidar_only")
        self.assertEqual(config.mobile_lidar.trajectory, "road")
        self.assertEqual(config.mobile_lidar.vertical_channels, 16)
        self.assertAlmostEqual(config.mobile_lidar.position_step_m, 5.0)

    def test_invalid_mobile_lidar_config_is_error(self) -> None:
        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
mobile_lidar:
  trajectory: arc
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
mobile_lidar:
  min_range_m: 10
  max_range_m: 10
"""
            )

        with self.assertRaises(ConfigError):
            _config_from_text(
                """
seed: 7
mobile_lidar:
  trajectory: line
  start_x: 0
  start_y: 0
  end_x: 10
"""
            )


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
