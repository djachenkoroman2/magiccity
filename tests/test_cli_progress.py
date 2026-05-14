from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
import warnings

from citygen.cli import main
from citygen.config import load_config
from citygen.generator import generate_scene
from citygen.sampling import sample_scene


BASE_CONFIG = """
seed: 701
tile:
  x: 0
  y: 0
  size_m: 48
  margin_m: 8
roads:
  model: grid
  spacing_m: 24
  width_m: 5
  sidewalk_width_m: 2
buildings:
  enabled: false
sampling:
  ground_spacing_m: 8
  road_spacing_m: 6
  building_spacing_m: 8
  jitter_ratio: 0
"""


LIDAR_CONFIG = (
    BASE_CONFIG
    + """
mobile_lidar:
  enabled: true
  output_mode: lidar_only
  trajectory: line
  start_x: 0
  start_y: 0
  end_x: 48
  end_y: 0
  position_step_m: 24
  min_range_m: 1
  max_range_m: 30
  horizontal_fov_degrees: 180
  horizontal_step_degrees: 60
  vertical_fov_degrees: 30
  vertical_center_degrees: -10
  vertical_channels: 2
  angle_jitter_degrees: 0
  range_noise_m: 0
  drop_probability: 0
  distance_attenuation: 0
  occlusions_enabled: true
  ray_step_m: 2
"""
)


FENCE_CONFIG = """
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


class CliProgressTests(unittest.TestCase):
    def test_default_output_contains_preflight_stages_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, BASE_CONFIG)
            out_path = Path(tmp) / "normal.ply"

            exit_code, stdout = _run_cli(["--config", str(config_path), "--out", str(out_path)])

        self.assertEqual(exit_code, 0)
        self.assertIn("loading config started", stdout)
        self.assertIn("citygen preflight", stdout)
        self.assertIn("seed: 701", stdout)
        self.assertIn("stage 1/9 resolving catalogs/worldgen context started", stdout)
        self.assertIn("sampling tile_surfaces started", stdout)
        self.assertIn("sampling tile_surfaces progress", stdout)
        self.assertIn("ground_points=", stdout)
        self.assertIn("hardscape_points=", stdout)
        self.assertIn("sampling buildings done", stdout)
        self.assertIn("sampling surface_total done", stdout)
        self.assertIn("stage 6/9 trees started", stdout)
        self.assertIn("stage 7/9 sampling done", stdout)
        self.assertIn("citygen: tile 1/1 summary", stdout)
        self.assertIn("classes:", stdout)
        self.assertIn("point_sources:", stdout)
        self.assertIn("Wrote metadata to", stdout)
        self.assertIn("citygen: run summary", stdout)

    def test_quiet_and_verbose_modes_adjust_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, BASE_CONFIG)
            quiet_path = Path(tmp) / "quiet.ply"
            verbose_path = Path(tmp) / "verbose.ply"

            quiet_code, quiet_stdout = _run_cli(
                ["--config", str(config_path), "--out", str(quiet_path), "--quiet"]
            )
            verbose_code, verbose_stdout = _run_cli(
                ["--config", str(config_path), "--out", str(verbose_path), "--verbose"]
            )

        self.assertEqual(quiet_code, 0)
        self.assertEqual(verbose_code, 0)
        self.assertNotIn("citygen preflight", quiet_stdout)
        self.assertNotIn("stage 1/9", quiet_stdout)
        self.assertNotIn("sampling tile_surfaces", quiet_stdout)
        self.assertIn("Wrote ", quiet_stdout)
        self.assertIn("citygen preflight", verbose_stdout)
        self.assertIn("sampling tile_surfaces started", verbose_stdout)
        self.assertIn("class_counts=", verbose_stdout)
        self.assertIn("road_models:", verbose_stdout)
        self.assertIn("buildings:", verbose_stdout)

    def test_interactive_tty_uses_tqdm_for_sampling_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, BASE_CONFIG)
            out_path = Path(tmp) / "tty.ply"

            exit_code, stdout, stderr = _run_cli_capture(
                ["--config", str(config_path), "--out", str(out_path)],
                stdout_tty=True,
                stderr_tty=True,
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("stage 7/9 sampling started", stdout)
        self.assertNotIn("sampling tile_surfaces progress", stdout)
        self.assertIn("tile 1/1 (x=0, y=0) sampling tile_surfaces", stderr)
        self.assertIn("%|", stderr)
        self.assertIn("ground", stderr)
        self.assertIn("hardscape", stderr)

    def test_interactive_quiet_hides_tqdm_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, BASE_CONFIG)
            out_path = Path(tmp) / "quiet_tty.ply"

            exit_code, stdout, stderr = _run_cli_capture(
                ["--config", str(config_path), "--out", str(out_path), "--quiet"],
                stdout_tty=True,
                stderr_tty=True,
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("Wrote ", stdout)
        self.assertEqual(stderr, "")

    def test_non_tty_uses_stable_progress_lines_without_tqdm_control_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, BASE_CONFIG)
            out_path = Path(tmp) / "non_tty.ply"

            exit_code, stdout, stderr = _run_cli_capture(
                ["--config", str(config_path), "--out", str(out_path)]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("sampling tile_surfaces progress", stdout)
        self.assertEqual(stderr, "")
        self.assertNotIn("%|", stdout)
        self.assertNotIn("\r", stdout)

    def test_mobile_lidar_stage_reports_ray_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, LIDAR_CONFIG)
            out_path = Path(tmp) / "lidar.ply"

            exit_code, stdout = _run_cli(["--config", str(config_path), "--out", str(out_path)])

        self.assertEqual(exit_code, 0)
        self.assertIn("stage 8/10 mobile LiDAR started", stdout)
        self.assertIn("sampling mobile LiDAR rays started", stdout)
        self.assertIn("sampling mobile LiDAR rays progress", stdout)
        self.assertIn("sampling mobile LiDAR rays done", stdout)
        self.assertIn("mobile LiDAR rays started", stdout)
        self.assertIn("mobile LiDAR rays progress", stdout)
        self.assertIn("mobile LiDAR rays done", stdout)
        self.assertIn("processed_rays=", stdout)
        self.assertIn("emitted_rays=", stdout)
        self.assertIn("successful_hits=", stdout)
        self.assertIn("point_sources: lidar_only", stdout)

    def test_interactive_tty_uses_tqdm_for_mobile_lidar_rays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, LIDAR_CONFIG)
            out_path = Path(tmp) / "lidar_tty.ply"

            exit_code, stdout, stderr = _run_cli_capture(
                ["--config", str(config_path), "--out", str(out_path)],
                stdout_tty=True,
                stderr_tty=True,
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("stage 8/10 mobile LiDAR started", stdout)
        self.assertIn("sampling mobile LiDAR rays", stderr)
        self.assertIn("ray", stderr)
        self.assertIn("hits", stderr)
        self.assertNotIn("sampling mobile LiDAR rays progress", stdout)

    def test_verbose_sampling_reports_fence_segment_counters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, FENCE_CONFIG)
            out_path = Path(tmp) / "fences.ply"

            exit_code, stdout = _run_cli(["--config", str(config_path), "--out", str(out_path), "--verbose"])

        self.assertEqual(exit_code, 0)
        self.assertIn("sampling fences started", stdout)
        self.assertIn("sampling fences item_done", stdout)
        self.assertIn("fence_segments=", stdout)
        self.assertIn("foundation_points=", stdout)
        self.assertIn("total_foundation_points=", stdout)

    def test_multi_tile_progress_reports_each_tile_and_overall_summary(self) -> None:
        config_text = """
seed: 702
tiles:
  items:
    - {x: 0, y: 0}
    - {x: 1, y: 0}
  size_m: 32
  margin_m: 8
roads:
  model: grid
  spacing_m: 24
  width_m: 5
  sidewalk_width_m: 2
buildings:
  enabled: false
sampling:
  ground_spacing_m: 8
  road_spacing_m: 8
  building_spacing_m: 8
  jitter_ratio: 0
"""
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, config_text)
            out_dir = Path(tmp) / "tiles"

            exit_code, stdout = _run_cli(["--config", str(config_path), "--out", str(out_dir)])

            self.assertTrue((out_dir / "tile_0_0.ply").exists())
            self.assertTrue((out_dir / "tile_1_0.ply").exists())

        self.assertEqual(exit_code, 0)
        self.assertIn("mode: multi-tile", stdout)
        self.assertIn("tile 1/2", stdout)
        self.assertIn("tile 2/2", stdout)
        self.assertGreaterEqual(stdout.count("sampling tile_surfaces started"), 2)
        self.assertIn("outputs:", stdout)

    def test_interactive_multi_tile_tqdm_progress_reports_each_tile(self) -> None:
        config_text = """
seed: 703
tiles:
  items:
    - {x: 0, y: 0}
    - {x: 1, y: 0}
  size_m: 32
  margin_m: 8
roads:
  model: grid
  spacing_m: 24
  width_m: 5
  sidewalk_width_m: 2
buildings:
  enabled: false
sampling:
  ground_spacing_m: 8
  road_spacing_m: 8
  building_spacing_m: 8
  jitter_ratio: 0
"""
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, config_text)
            out_dir = Path(tmp) / "tiles_tty"

            exit_code, stdout, stderr = _run_cli_capture(
                ["--config", str(config_path), "--out", str(out_dir)],
                stdout_tty=True,
                stderr_tty=True,
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("tile 1/2", stdout)
        self.assertIn("tile 2/2", stdout)
        self.assertIn("tile 1/2 (x=0, y=0) sampling tile_surfaces", stderr)
        self.assertIn("tile 2/2 (x=1, y=0) sampling tile_surfaces", stderr)

    def test_progress_output_does_not_change_ply_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, BASE_CONFIG)
            normal_path = Path(tmp) / "normal.ply"
            quiet_path = Path(tmp) / "quiet.ply"
            tty_path = Path(tmp) / "tty.ply"

            normal_code, _normal_stdout = _run_cli(["--config", str(config_path), "--out", str(normal_path)])
            quiet_code, _quiet_stdout = _run_cli(
                ["--config", str(config_path), "--out", str(quiet_path), "--quiet"]
            )
            tty_code, _tty_stdout, _tty_stderr = _run_cli_capture(
                ["--config", str(config_path), "--out", str(tty_path)],
                stdout_tty=True,
                stderr_tty=True,
            )

            normal_ply = normal_path.read_bytes()
            quiet_ply = quiet_path.read_bytes()
            tty_ply = tty_path.read_bytes()
            normal_metadata = normal_path.with_suffix(".metadata.json").read_bytes()
            quiet_metadata = quiet_path.with_suffix(".metadata.json").read_bytes()
            tty_metadata = tty_path.with_suffix(".metadata.json").read_bytes()

        self.assertEqual(normal_code, 0)
        self.assertEqual(quiet_code, 0)
        self.assertEqual(tty_code, 0)
        self.assertEqual(normal_ply, quiet_ply)
        self.assertEqual(normal_ply, tty_ply)
        self.assertEqual(normal_metadata, quiet_metadata)
        self.assertEqual(normal_metadata, tty_metadata)

    def test_sampling_progress_callback_reports_lidar_rays_inside_sampling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, LIDAR_CONFIG)
            config = load_config(config_path)
            scene = generate_scene(config)
            events: list[tuple[str, str, dict | None]] = []

            points = sample_scene(
                config,
                scene,
                progress=lambda stage, status, details: events.append((stage, status, details)),
            )
            plain_points = sample_scene(config, scene)

        self.assertGreater(len(points), 0)
        self.assertEqual(points, plain_points)
        self.assertTrue(any(stage == "mobile_lidar" and status == "started" for stage, status, _details in events))
        self.assertTrue(any(stage == "mobile_lidar" and status == "done" for stage, status, _details in events))
        self.assertTrue(
            any(
                stage == "sampling"
                and status == "progress"
                and (details or {}).get("substage") == "mobile_lidar_rays"
                and (details or {}).get("event") == "progress"
                for stage, status, details in events
            )
        )

    def test_config_error_mentions_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_config(tmp, "roads:\n  model: grid\n")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["--config", str(config_path), "--quiet"])

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(f"config error in {config_path}", stderr.getvalue())


def _write_config(directory: str, text: str) -> Path:
    path = Path(directory) / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _run_cli(args: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = main(args)
    return exit_code, stdout.getvalue()


def _run_cli_capture(
    args: list[str],
    stdout_tty: bool = False,
    stderr_tty: bool = False,
) -> tuple[int, str, str]:
    stdout = _TtyStringIO(stdout_tty)
    stderr = _TtyStringIO(stderr_tty)
    with redirect_stdout(stdout), redirect_stderr(stderr):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="datetime.datetime.utcfromtimestamp\\(\\) is deprecated",
                category=DeprecationWarning,
                module="tqdm.std",
            )
            exit_code = main(args)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class _TtyStringIO(io.StringIO):
    def __init__(self, tty: bool) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


if __name__ == "__main__":
    unittest.main()
