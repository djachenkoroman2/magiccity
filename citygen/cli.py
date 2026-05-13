from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time
from typing import Any

from tqdm import tqdm

from .config import CityGenConfig, ConfigError, iter_tile_configs, load_config
from .export import write_metadata, write_ply
from .generator import generate_scene
from .sampling import sample_scene


STAGE_LABELS = {
    "worldgen_context": "resolving catalogs/worldgen context",
    "roads": "roads",
    "parcels": "parcels",
    "objects": "buildings/objects",
    "fences": "fences",
    "sampling": "sampling",
    "mobile_lidar": "mobile LiDAR",
    "writing_ply": "writing PLY",
    "writing_metadata": "writing metadata",
}

PROGRESS_SUBSTAGE_LABELS = {
    "mobile_lidar_rays": "mobile LiDAR rays",
}

_TQDM_SUBSTAGES = {"tile_surfaces", "buildings", "fences", "mobile_lidar_rays"}


@dataclass
class RunContext:
    stage: str = "startup"
    tile_label: str | None = None
    target: Path | None = None

    def describe(self) -> str:
        parts = [self.stage]
        if self.tile_label is not None:
            parts.append(self.tile_label)
        if self.target is not None:
            parts.append(f"target={self.target}")
        return ", ".join(parts)


@dataclass
class TileRunResult:
    tile_index: int
    tile_total: int
    tile_x: int
    tile_y: int
    point_count: int
    ply_path: Path
    metadata_path: Path
    metadata: dict[str, Any]
    elapsed_s: float


class TileProgress:
    def __init__(
        self,
        verbosity: int,
        context: RunContext,
        tile_index: int,
        tile_total: int,
        tile_config: CityGenConfig,
        stage_total: int,
        progress_stream: Any | None = None,
    ) -> None:
        self.verbosity = verbosity
        self.context = context
        self.tile_index = tile_index
        self.tile_total = tile_total
        self.tile_config = tile_config
        self.stage_total = stage_total
        self.stage_index = 0
        self.started_at: dict[str, float] = {}
        self.progress_stream = progress_stream if progress_stream is not None else sys.stderr
        self.use_tqdm = (
            verbosity > 0
            and _is_tty(sys.stdout)
            and _is_tty(self.progress_stream)
        )
        self._bars: dict[tuple[str, str], Any] = {}
        self._line_progress_buckets: dict[tuple[str, str], int] = {}

    def __call__(self, stage: str, status: str, details: dict[str, Any] | None = None) -> None:
        label = STAGE_LABELS.get(stage, stage)

        if status == "progress":
            substage = str((details or {}).get("substage", "")).strip()
            event = str((details or {}).get("event", "progress")).strip() or "progress"
            substage_label = PROGRESS_SUBSTAGE_LABELS.get(substage, substage)
            progress_label = f"{label} {substage_label}" if substage_label else label
            self.context.stage = progress_label
            if self.verbosity == 0:
                return
            if self.use_tqdm and self._handle_tqdm_progress(stage, substage, progress_label, event, details or {}):
                return
            if event == "item_done" and self.verbosity < 2:
                return
            if event == "progress" and not self._should_print_line_progress(stage, substage, details or {}):
                return
            print(
                "citygen: "
                f"tile {self.tile_index}/{self.tile_total} "
                f"(x={self.tile_config.tile.x}, y={self.tile_config.tile.y}) "
                f"{progress_label} {event}"
                f"{_format_progress_details(details, self.verbosity)}"
            )
            return

        self.context.stage = label

        if status in {"done", "failed"}:
            self._close_bars_for_stage(stage)

        if status == "started":
            self.stage_index += 1
            self.started_at[stage] = time.perf_counter()
            if self.verbosity > 0:
                print(
                    "citygen: "
                    f"tile {self.tile_index}/{self.tile_total} "
                    f"(x={self.tile_config.tile.x}, y={self.tile_config.tile.y}) "
                    f"stage {self.stage_index}/{self.stage_total} {label} started"
                )
            return

        if status == "done":
            elapsed = time.perf_counter() - self.started_at.get(stage, time.perf_counter())
            if self.verbosity > 0:
                print(
                    "citygen: "
                    f"tile {self.tile_index}/{self.tile_total} "
                    f"(x={self.tile_config.tile.x}, y={self.tile_config.tile.y}) "
                    f"stage {self.stage_index}/{self.stage_total} {label} done "
                    f"in {_format_duration(elapsed)}"
                    f"{_format_details(details, self.verbosity)}"
                )
            return

        if self.verbosity > 0:
            print(
                "citygen: "
                f"tile {self.tile_index}/{self.tile_total} "
                f"(x={self.tile_config.tile.x}, y={self.tile_config.tile.y}) "
                f"{label} {status}"
                f"{_format_details(details, self.verbosity)}"
            )

    def _handle_tqdm_progress(
        self,
        stage: str,
        substage: str,
        progress_label: str,
        event: str,
        details: dict[str, Any],
    ) -> bool:
        total = _progress_total(substage, details)
        if total <= 0:
            return substage in _TQDM_SUBSTAGES
        if substage not in _TQDM_SUBSTAGES:
            return False

        key = (stage, substage)
        bar = self._bars.get(key)
        if bar is None and event in {"started", "progress", "item_done"}:
            bar = tqdm(
                total=total,
                desc=self._tqdm_description(progress_label),
                unit=_progress_unit(substage),
                file=self.progress_stream,
                leave=True,
                dynamic_ncols=True,
                mininterval=0.1,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit}{postfix}",
                disable=False,
            )
            self._bars[key] = bar

        if bar is None:
            return True

        current = _progress_current(substage, event, details, total)
        if current > bar.n:
            bar.update(current - bar.n)
        elif event == "done" and bar.n < total:
            bar.update(total - bar.n)
        bar.set_postfix(_tqdm_postfix(substage, details, self.verbosity), refresh=True)

        if event == "done":
            bar.close()
            self._bars.pop(key, None)
        return True

    def _tqdm_description(self, progress_label: str) -> str:
        return (
            f"tile {self.tile_index}/{self.tile_total} "
            f"(x={self.tile_config.tile.x}, y={self.tile_config.tile.y}) "
            f"{progress_label}"
        )

    def _should_print_line_progress(self, stage: str, substage: str, details: dict[str, Any]) -> bool:
        current, total = _line_progress_position(substage, details)
        if total <= 0 or current <= 0:
            return True
        buckets = 10 if self.verbosity > 1 else 4
        bucket = min(buckets, int(current * buckets / total))
        if bucket <= 0:
            return False
        key = (stage, substage)
        if self._line_progress_buckets.get(key) == bucket:
            return False
        self._line_progress_buckets[key] = bucket
        return True

    def _close_bars_for_stage(self, stage: str) -> None:
        for key, bar in list(self._bars.items()):
            if key[0] != stage:
                continue
            bar.close()
            self._bars.pop(key, None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="citygen",
        description="Generate an MVP synthetic urban point cloud as ASCII PLY.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to YAML generation config.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output .ply path or directory. Defaults to outputs/tile_X_Y.ply.",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--quiet",
        action="store_true",
        help="Only print final output paths.",
    )
    verbosity.add_argument(
        "--verbose",
        action="store_true",
        help="Print extended preflight, stage and summary diagnostics.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    verbosity = 0 if args.quiet else 2 if args.verbose else 1
    context = RunContext(stage="loading config", target=Path(args.config))
    run_started_at = time.perf_counter()

    try:
        _print_loading_started(args.config, verbosity)
        config_started_at = time.perf_counter()
        config = load_config(args.config)
        _print_loading_done(config_started_at, verbosity)

        context.stage = "resolving output paths"
        context.target = Path(args.out) if args.out is not None else None
        tile_configs = iter_tile_configs(config)
        output_paths = _resolve_output_paths(args.out, tile_configs)
        _print_preflight(args.config, args.out, config, tile_configs, output_paths, verbosity)

        results: list[TileRunResult] = []
        for index, (tile_config, output_path) in enumerate(zip(tile_configs, output_paths), start=1):
            context.tile_label = _tile_label(index, len(tile_configs), tile_config)
            context.target = None
            tile_started_at = time.perf_counter()
            if verbosity > 0:
                print(f"citygen: {context.tile_label} started")

            reporter = TileProgress(
                verbosity,
                context,
                index,
                len(tile_configs),
                tile_config,
                _stage_total(tile_config),
            )
            scene = generate_scene(tile_config, progress=reporter)
            points = sample_scene(tile_config, scene, progress=reporter)
            if not points:
                raise ConfigError("Generation produced zero points; check spacing and tile size.")

            context.target = output_path
            reporter("writing_ply", "started", {"path": output_path})
            ply_path = write_ply(output_path, points, tile_config)
            reporter("writing_ply", "done", {"path": ply_path, "points": len(points)})

            context.target = ply_path.with_suffix(".metadata.json")
            reporter("writing_metadata", "started", {"path": context.target})
            metadata_path = write_metadata(ply_path, tile_config, scene, points)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            reporter("writing_metadata", "done", {"path": metadata_path})

            result = TileRunResult(
                tile_index=index,
                tile_total=len(tile_configs),
                tile_x=tile_config.tile.x,
                tile_y=tile_config.tile.y,
                point_count=len(points),
                ply_path=ply_path,
                metadata_path=metadata_path,
                metadata=metadata,
                elapsed_s=time.perf_counter() - tile_started_at,
            )
            results.append(result)
            _print_tile_summary(result, verbosity)

        _print_run_summary(results, time.perf_counter() - run_started_at, verbosity)
    except ConfigError as exc:
        if context.stage == "loading config":
            print(f"citygen: config error in {args.config}: {exc}", file=sys.stderr)
        else:
            print(f"citygen: config error during {context.describe()}: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"citygen: file error during {context.describe()}: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(
            f"citygen: runtime error during {context.describe()}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        if args.verbose:
            raise
        return 1

    return 0


def _resolve_output_paths(out: str | None, configs) -> list[Path]:
    configs = tuple(configs)
    if len(configs) == 1:
        config = configs[0]
        return [_resolve_single_output_path(out, config.tile.x, config.tile.y)]

    if out is not None and Path(out).suffix.lower() == ".ply":
        raise ConfigError("Multi-tile configs require --out to be omitted or point to a directory.")

    output_dir = Path(out) if out is not None else Path("outputs")
    return [output_dir / f"tile_{config.tile.x}_{config.tile.y}.ply" for config in configs]


def _resolve_single_output_path(out: str | None, tile_x: int, tile_y: int) -> Path:
    default_name = f"tile_{tile_x}_{tile_y}.ply"
    if out is None:
        return Path("outputs") / default_name

    path = Path(out)
    if path.suffix.lower() == ".ply":
        return path
    return path / default_name


def _stage_total(config: CityGenConfig) -> int:
    total = 8
    if config.mobile_lidar.enabled:
        total += 1
    return total


def _print_loading_started(config_path: str, verbosity: int) -> None:
    if verbosity > 0:
        print(f"citygen: stage 1/1 loading config started - path={config_path}")


def _print_loading_done(started_at: float, verbosity: int) -> None:
    if verbosity > 0:
        print(f"citygen: stage 1/1 loading config done in {_format_duration(time.perf_counter() - started_at)}")


def _print_preflight(
    config_path: str,
    out_arg: str | None,
    config: CityGenConfig,
    tile_configs: tuple[CityGenConfig, ...],
    output_paths: list[Path],
    verbosity: int,
) -> None:
    if verbosity == 0:
        return

    print("citygen preflight")
    print(f"  config: {config_path}")
    print(f"  seed: {config.seed}")
    print(f"  mode: {'multi-tile' if len(tile_configs) > 1 else 'single-tile'}")
    print(f"  tiles: {_tiles_summary(tile_configs, verbosity)}")
    print(f"  output: {_output_summary(out_arg, output_paths, verbosity)}")
    print(f"  subsystems: {_subsystem_summary(config)}")
    print(f"  sampling: {_sampling_summary(config)}")
    print(f"  cost drivers: {_cost_driver_summary(config, tile_configs)}")


def _print_tile_summary(result: TileRunResult, verbosity: int) -> None:
    if verbosity == 0:
        _print_written_lines(result)
        return

    metadata = result.metadata
    print(f"citygen: tile {result.tile_index}/{result.tile_total} summary")
    print(f"  status: done in {_format_duration(result.elapsed_s)}")
    print(f"  points: {result.point_count}")
    print(f"  classes: {_format_counts(metadata.get('class_counts', {}))}")
    print(f"  point_sources: {_format_source_mode(metadata.get('point_sources', {}))}")
    if verbosity > 1:
        print(f"  road_models: {', '.join(metadata.get('road_models', [])) or 'none'}")
        print(f"  buildings: {_building_summary(metadata.get('building_counts', {}))}")
        print(f"  parcels: {_small_mapping(metadata.get('parcel_counts', {}))}")
        print(f"  fences: {_small_mapping(metadata.get('fence_counts', {}))}")
        print(f"  mobile_lidar: {_lidar_summary(metadata.get('mobile_lidar', {}))}")
    _print_written_lines(result)


def _print_run_summary(results: list[TileRunResult], elapsed_s: float, verbosity: int) -> None:
    if verbosity == 0:
        return
    total_points = sum(result.point_count for result in results)
    print("citygen: run summary")
    print("  status: done")
    print(f"  tiles: {len(results)}")
    print(f"  total_points: {total_points}")
    print(f"  total_time: {_format_duration(elapsed_s)}")
    if len(results) > 1:
        outputs = ", ".join(str(result.ply_path) for result in results[:3])
        if len(results) > 3:
            outputs += f", ... (+{len(results) - 3})"
        print(f"  outputs: {outputs}")


def _print_written_lines(result: TileRunResult) -> None:
    print(f"Wrote {result.point_count} points to {result.ply_path}")
    print(f"Wrote metadata to {result.metadata_path}")


def _tile_label(index: int, total: int, config: CityGenConfig) -> str:
    tile = config.tile
    return f"tile {index}/{total} (x={tile.x}, y={tile.y}, size_m={_format_number(tile.size_m)})"


def _tiles_summary(tile_configs: tuple[CityGenConfig, ...], verbosity: int) -> str:
    parts = [
        f"(x={cfg.tile.x}, y={cfg.tile.y}, size_m={_format_number(cfg.tile.size_m)}, "
        f"margin_m={_format_number(cfg.tile.margin_m)})"
        for cfg in tile_configs
    ]
    if verbosity > 1 or len(parts) <= 3:
        return "; ".join(parts)
    return "; ".join(parts[:3]) + f"; ... (+{len(parts) - 3})"


def _output_summary(out_arg: str | None, output_paths: list[Path], verbosity: int) -> str:
    if len(output_paths) == 1:
        return str(output_paths[0])
    if verbosity > 1:
        return "; ".join(str(path) for path in output_paths)
    target = out_arg if out_arg is not None else "outputs"
    return f"{len(output_paths)} files under {target}"


def _subsystem_summary(config: CityGenConfig) -> str:
    return ", ".join(
        (
            f"roads={config.roads.model}",
            f"buildings={_on_off(config.buildings.enabled)}",
            f"parcels={_on_off(config.parcels.enabled)}",
            f"fences={_on_off(config.fences.enabled)}:{config.fences.mode}",
            f"mobile_lidar={_on_off(config.mobile_lidar.enabled)}:{config.mobile_lidar.output_mode}",
            f"sampling={config.sampling.mode}",
            f"output={config.output.format}/rgb={_on_off(config.output.include_rgb)}/class={_on_off(config.output.include_class)}",
        )
    )


def _sampling_summary(config: CityGenConfig) -> str:
    sampling = config.sampling
    return (
        f"ground_spacing_m={_format_number(sampling.ground_spacing_m)}, "
        f"road_spacing_m={_format_number(sampling.road_spacing_m)}, "
        f"building_spacing_m={_format_number(sampling.building_spacing_m)}, "
        f"jitter_ratio={_format_number(sampling.jitter_ratio)}"
    )


def _cost_driver_summary(config: CityGenConfig, tile_configs: tuple[CityGenConfig, ...]) -> str:
    lidar = config.mobile_lidar
    lidar_summary = "mobile_lidar=off"
    if lidar.enabled:
        lidar_summary = (
            "mobile_lidar="
            f"h_step={_format_number(lidar.horizontal_step_degrees)}deg/"
            f"channels={lidar.vertical_channels}/"
            f"position_step_m={_format_number(lidar.position_step_m)}/"
            f"ray_step_m={_format_number(lidar.ray_step_m)}"
        )
    return (
        f"tiles={len(tile_configs)}, "
        f"tile_size_m={_format_number(config.tile.size_m)}, "
        f"margin_m={_format_number(config.tile.margin_m)}, "
        f"min_surface_spacing_m={_format_number(min(config.sampling.ground_spacing_m, config.sampling.road_spacing_m))}, "
        f"{lidar_summary}"
    )


def _format_details(details: dict[str, Any] | None, verbosity: int) -> str:
    if not details:
        return ""
    items: list[str] = []
    for key, value in details.items():
        if value is None:
            continue
        if verbosity < 2 and key in {"bbox"}:
            continue
        items.append(f"{key}={_format_value(value, verbosity)}")
    return " - " + ", ".join(items) if items else ""


def _format_progress_details(details: dict[str, Any] | None, verbosity: int) -> str:
    if not details:
        return ""
    hidden = {"substage", "event"}
    if verbosity < 2:
        hidden.update({"building_id", "segment_id", "hit_counts_by_class"})
    visible = {key: value for key, value in details.items() if key not in hidden}
    return _format_details(visible, verbosity)


def _is_tty(stream: Any) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty()) if callable(isatty) else False


def _progress_total(substage: str, details: dict[str, Any]) -> int:
    if substage == "tile_surfaces":
        return _int_detail(details, "total_rows", "grid_rows")
    if substage == "buildings":
        return _int_detail(details, "buildings")
    if substage == "fences":
        return _int_detail(details, "fence_segments")
    if substage == "mobile_lidar_rays":
        return _int_detail(details, "total_rays")
    return 0


def _progress_current(substage: str, event: str, details: dict[str, Any], total: int) -> int:
    if event == "started":
        return 0
    if event == "done":
        return total
    if substage == "tile_surfaces":
        return _int_detail(details, "rows", default=0)
    if substage == "buildings":
        return _int_detail(details, "building", default=0)
    if substage == "fences":
        return _int_detail(details, "segment", default=0)
    if substage == "mobile_lidar_rays":
        return _int_detail(details, "processed_rays", "emitted_rays", default=0)
    return 0


def _line_progress_position(substage: str, details: dict[str, Any]) -> tuple[int, int]:
    total = _progress_total(substage, details)
    current = _progress_current(substage, "progress", details, total)
    return current, total


def _progress_unit(substage: str) -> str:
    if substage == "tile_surfaces":
        return "row"
    if substage == "buildings":
        return "building"
    if substage == "fences":
        return "segment"
    if substage == "mobile_lidar_rays":
        return "ray"
    return "item"


def _tqdm_postfix(substage: str, details: dict[str, Any], verbosity: int) -> dict[str, Any]:
    if substage == "tile_surfaces":
        keys = ("points", "ground_points", "hardscape_points")
        if verbosity > 1:
            keys += ("road_points", "sidewalk_points", "road_median_points")
        return _postfix(details, keys)
    if substage == "buildings":
        return _postfix(details, ("total_building_points", "total_roof_points", "total_facade_points"))
    if substage == "fences":
        return _postfix(details, ("total_fence_points", "total_fence_body_points", "total_foundation_points"))
    if substage == "mobile_lidar_rays":
        keys = ("successful_hits", "dropped_rays", "missed_rays", "attenuated_rays", "lidar_points")
        return _postfix(details, keys)
    return {}


def _postfix(details: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {
        _short_counter_name(key): value
        for key in keys
        if (value := details.get(key)) is not None
    }


def _short_counter_name(key: str) -> str:
    return {
        "points": "pts",
        "ground_points": "ground",
        "hardscape_points": "hardscape",
        "road_points": "road",
        "sidewalk_points": "sidewalk",
        "road_median_points": "median",
        "total_building_points": "pts",
        "roof_points": "roof",
        "facade_points": "facade",
        "total_roof_points": "roof",
        "total_facade_points": "facade",
        "total_fence_points": "pts",
        "fence_points": "fence",
        "foundation_points": "foundation",
        "total_fence_body_points": "fence",
        "total_foundation_points": "foundation",
        "successful_hits": "hits",
        "dropped_rays": "dropped",
        "missed_rays": "missed",
        "attenuated_rays": "attenuated",
        "lidar_points": "pts",
    }.get(key, key)


def _int_detail(details: dict[str, Any], *keys: str, default: int = 0) -> int:
    for key in keys:
        value = details.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return default


def _format_value(value: Any, verbosity: int) -> str:
    if isinstance(value, bool):
        return _on_off(value)
    if isinstance(value, float):
        return _format_number(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return _small_mapping(value, max_items=8 if verbosity > 1 else 4)
    if isinstance(value, (list, tuple)):
        return _small_sequence(value, max_items=8 if verbosity > 1 else 4)
    return str(value)


def _format_counts(counts: dict[str, Any]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def _format_source_mode(point_sources: dict[str, Any]) -> str:
    if not point_sources:
        return "unknown"
    mode = point_sources.get("mode", "unknown")
    surface = point_sources.get("surface_sampling", 0)
    lidar = point_sources.get("mobile_lidar", 0)
    return f"{mode} (surface_sampling={surface}, mobile_lidar={lidar})"


def _building_summary(building_counts: dict[str, Any]) -> str:
    if not building_counts:
        return "none"
    return (
        f"total={building_counts.get('total', 0)}, "
        f"by_footprint={_small_mapping(building_counts.get('by_footprint', {}))}, "
        f"by_roof={_small_mapping(building_counts.get('by_roof', {}))}"
    )


def _lidar_summary(metadata: dict[str, Any]) -> str:
    if not metadata or not metadata.get("enabled", False):
        return "off"
    return (
        f"positions={metadata.get('sensor_positions', 0)}, "
        f"rays={metadata.get('emitted_rays', 0)}, "
        f"hits={metadata.get('successful_hits', 0)}, "
        f"missed={metadata.get('missed_rays', 0)}, "
        f"dropped={metadata.get('dropped_rays', 0)}, "
        f"attenuated={metadata.get('attenuated_rays', 0)}"
    )


def _small_mapping(mapping: dict[str, Any], max_items: int = 5) -> str:
    if not mapping:
        return "{}"
    items = list(mapping.items())
    rendered = ", ".join(f"{key}={value}" for key, value in items[:max_items])
    if len(items) > max_items:
        rendered += f", ...(+{len(items) - max_items})"
    return "{" + rendered + "}"


def _small_sequence(values, max_items: int = 5) -> str:
    values = list(values)
    rendered = ", ".join(str(value) for value in values[:max_items])
    if len(values) > max_items:
        rendered += f", ...(+{len(values) - max_items})"
    return "[" + rendered + "]"


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}m{remainder:04.1f}s"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _on_off(value: bool) -> str:
    return "on" if value else "off"
