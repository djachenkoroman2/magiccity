from __future__ import annotations

import json
from pathlib import Path
import random
import tempfile
import unittest

from citygen.biomes import biome_definition, biome_params, classify_biome, preferred_road_model_for_biome
from citygen.catalogs import DEFAULT_CATALOGS, WORLDGEN_STAGES, catalog_summary, validate_catalogs
from citygen.classes import POINT_CLASSES
from citygen.cli import main
from citygen.config import load_config
from citygen.export import write_metadata, write_ply
from citygen.generator import generate_scene
from citygen.sampling import sample_scene
from citygen.selectors import select_weighted_id


class CatalogTests(unittest.TestCase):
    def test_builtin_catalogs_are_valid(self) -> None:
        self.assertEqual(validate_catalogs(), [])
        self.assertEqual(set(POINT_CLASSES), set(DEFAULT_CATALOGS.semantic_classes))

    def test_backward_compatible_biome_facades_still_work(self) -> None:
        config = load_config("configs/mvp.yaml")

        self.assertEqual(classify_biome(config.seed, config.urban_fields, 0, 0), "residential")
        self.assertEqual(biome_params("downtown").preferred_road_model, "radial_ring")
        self.assertEqual(preferred_road_model_for_biome("industrial"), "linear")
        self.assertEqual(biome_definition("suburb").preferred_road_model, "organic")

    def test_existing_demo_configs_load(self) -> None:
        for path in sorted(Path("configs").glob("demo_*.yaml")):
            with self.subTest(path=path):
                load_config(path)

    def test_weighted_selector_is_stable_for_dict_order(self) -> None:
        weights_a = {"collector": 1.0, "local": 2.0, "boulevard": 3.0}
        weights_b = {"boulevard": 3.0, "local": 2.0, "collector": 1.0}

        self.assertEqual(
            select_weighted_id(weights_a, random.Random(42), fallback="collector"),
            select_weighted_id(weights_b, random.Random(42), fallback="collector"),
        )

    def test_documentation_mentions_all_catalog_ids(self) -> None:
        biome_doc = Path("doc/biomes.md").read_text(encoding="utf-8")
        objects_doc = Path("doc/generated_objects.md").read_text(encoding="utf-8")
        worldgen_doc = Path("doc/worldgen_catalogs.md").read_text(encoding="utf-8")

        for biome_id in DEFAULT_CATALOGS.biomes:
            self.assertIn(f"`{biome_id}`", biome_doc)
        for feature_id in DEFAULT_CATALOGS.object_features:
            self.assertIn(f"`{feature_id}`", objects_doc)
        for stage_id in WORLDGEN_STAGES:
            self.assertIn(f"`{stage_id}`", worldgen_doc)

    def test_metadata_contains_worldgen_and_catalog_summary(self) -> None:
        config = _config_from_text(
            """
seed: 101
tile:
  size_m: 64
roads:
  spacing_m: 32
  width_m: 6
  sidewalk_width_m: 2
buildings:
  enabled: false
sampling:
  ground_spacing_m: 8
  road_spacing_m: 4
  jitter_ratio: 0
"""
        )
        scene = generate_scene(config)
        points = sample_scene(config, scene)
        with tempfile.TemporaryDirectory() as tmp:
            ply_path = Path(tmp) / "catalogs.ply"
            write_ply(ply_path, points, config)
            metadata_path = write_metadata(ply_path, config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertIn("worldgen", metadata)
        self.assertIn("catalogs", metadata)
        self.assertIn("biome_catalog", metadata)
        self.assertIn("object_feature_counts", metadata)
        self.assertEqual(metadata["catalogs"]["biomes"], catalog_summary()["biomes"])
        self.assertIn("supported_footprint_types", metadata)
        self.assertIn("supported_roof_types", metadata)

    def test_mvp_cli_smoke_with_catalog_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "mvp_catalogs_check.ply"
            exit_code = main(["--config", "configs/mvp.yaml", "--out", str(out_path)])
            metadata = json.loads(out_path.with_suffix(".metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertGreater(metadata["point_count"], 0)
        self.assertIn("worldgen", metadata)
        self.assertIn("catalogs", metadata)


def _config_from_text(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)


if __name__ == "__main__":
    unittest.main()
