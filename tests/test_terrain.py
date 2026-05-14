from __future__ import annotations

import unittest

from citygen.config import TerrainConfig, TerrainPeakConfig, TerrainRavineConfig
from citygen.geometry import terrain_height


class TerrainHeightTests(unittest.TestCase):
    def test_mountains_and_hills_raise_terrain(self) -> None:
        terrain = TerrainConfig(
            height_noise_m=0,
            mountains=(TerrainPeakConfig(center_x=0, center_y=0, height_m=100, radius_m=50),),
            hills=(TerrainPeakConfig(center_x=120, center_y=0, height_m=20, radius_m=80),),
        )

        self.assertAlmostEqual(terrain_height(1, terrain, 0, 0), 100.0)
        self.assertGreater(terrain_height(1, terrain, 120, 0), 19.0)
        self.assertAlmostEqual(terrain_height(1, terrain, 300, 0), 0.0)

    def test_ravines_lower_terrain(self) -> None:
        terrain = TerrainConfig(
            base_height_m=30,
            height_noise_m=0,
            ravines=(
                TerrainRavineConfig(
                    center_x=0,
                    center_y=0,
                    length_m=100,
                    width_m=20,
                    depth_m=12,
                ),
            ),
        )

        self.assertAlmostEqual(terrain_height(1, terrain, 0, 0), 18.0)
        self.assertAlmostEqual(terrain_height(1, terrain, 0, 15), 30.0)
        self.assertAlmostEqual(terrain_height(1, terrain, 70, 0), 30.0)


if __name__ == "__main__":
    unittest.main()
