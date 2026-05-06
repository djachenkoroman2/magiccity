from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import ConfigError, iter_tile_configs, load_config
from .export import write_metadata, write_ply
from .generator import generate_scene
from .sampling import sample_scene


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        tile_configs = iter_tile_configs(config)
        output_paths = _resolve_output_paths(args.out, tile_configs)
        written: list[tuple[int, Path, Path]] = []

        for tile_config, output_path in zip(tile_configs, output_paths):
            scene = generate_scene(tile_config)
            points = sample_scene(tile_config, scene)
            if not points:
                raise ConfigError("Generation produced zero points; check spacing and tile size.")
            ply_path = write_ply(output_path, points, tile_config)
            metadata_path = write_metadata(ply_path, tile_config, scene, points)
            written.append((len(points), ply_path, metadata_path))
    except ConfigError as exc:
        print(f"citygen: config error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"citygen: file error: {exc}", file=sys.stderr)
        return 3

    for point_count, ply_path, metadata_path in written:
        print(f"Wrote {point_count} points to {ply_path}")
        print(f"Wrote metadata to {metadata_path}")
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
