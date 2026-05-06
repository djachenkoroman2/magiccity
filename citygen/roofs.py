from __future__ import annotations

from dataclasses import dataclass
import math
from random import Random

from .config import RoofConfig
from .footprints import BuildingFootprint


ROOF_KINDS = (
    "flat",
    "shed",
    "gable",
    "hip",
    "half_hip",
    "pyramid",
    "mansard",
    "dome",
    "barrel",
    "cone",
)


@dataclass(frozen=True)
class RoofSpec:
    kind: str
    requested_kind: str
    eave_z: float
    max_z: float
    rise_m: float
    axis: str = "x"
    mansard_break_ratio: float = 0.45
    flat_slope_degrees: float = 0.0

    def height_at(self, x: float, y: float, footprint: BuildingFootprint) -> float:
        bbox = footprint.bbox
        ux = _normalized_axis(x, bbox.center_x, bbox.width)
        uy = _normalized_axis(y, bbox.center_y, bbox.depth)

        if self.kind == "flat":
            factor = self._flat_factor(ux, uy)
        elif self.kind == "shed":
            coord = ux if self.axis == "x" else uy
            factor = (coord + 1.0) * 0.5
        elif self.kind == "gable":
            coord = uy if self.axis == "x" else ux
            factor = 1.0 - abs(coord)
        elif self.kind == "hip":
            factor = _hip_factor(ux, uy, bbox.width, bbox.depth)
        elif self.kind == "half_hip":
            factor = _half_hip_factor(ux, uy, self.axis)
        elif self.kind == "pyramid":
            factor = 1.0 - max(abs(ux), abs(uy))
        elif self.kind == "mansard":
            factor = _mansard_factor(ux, uy, self.mansard_break_ratio)
        elif self.kind == "dome":
            r = math.hypot(ux, uy)
            factor = math.sqrt(max(0.0, 1.0 - r * r))
        elif self.kind == "barrel":
            coord = uy if self.axis == "x" else ux
            factor = math.sqrt(max(0.0, 1.0 - coord * coord))
        elif self.kind == "cone":
            factor = 1.0 - math.hypot(ux, uy)
        else:
            factor = 1.0

        factor = _clamp(factor)
        return self.eave_z + self.rise_m * factor

    def _flat_factor(self, ux: float, uy: float) -> float:
        if self.rise_m <= 0:
            return 1.0
        coord = ux if self.axis == "x" else uy
        return (coord + 1.0) * 0.5


def select_roof_kind(config: RoofConfig, rng: Random) -> str:
    if config.model != "mixed":
        return config.model
    total = sum(config.weights.values())
    pick = rng.random() * total
    cursor = 0.0
    for kind in ROOF_KINDS:
        weight = config.weights.get(kind, 0.0)
        cursor += weight
        if pick <= cursor:
            return kind
    return "flat"


def build_roof(
    kind: str,
    footprint: BuildingFootprint,
    base_z: float,
    max_z: float,
    config: RoofConfig,
    rng: Random,
) -> RoofSpec:
    axis = _long_axis(footprint)
    height_m = max(0.0, max_z - base_z)
    rise_m = _roof_rise(kind, footprint, height_m, config, rng)
    eave_z = max_z - rise_m
    return RoofSpec(
        kind=kind,
        requested_kind=kind,
        eave_z=eave_z,
        max_z=max_z,
        rise_m=rise_m,
        axis=axis,
        mansard_break_ratio=config.mansard_break_ratio,
        flat_slope_degrees=config.flat_slope_degrees,
    )


def default_flat_roof(footprint: BuildingFootprint, max_z: float) -> RoofSpec:
    return RoofSpec(
        kind="flat",
        requested_kind="flat",
        eave_z=max_z,
        max_z=max_z,
        rise_m=0.0,
        axis=_long_axis(footprint),
    )


def _roof_rise(
    kind: str,
    footprint: BuildingFootprint,
    height_m: float,
    config: RoofConfig,
    rng: Random,
) -> float:
    if height_m <= 0:
        return 0.0

    bbox = footprint.bbox
    min_dim = max(1.0, min(bbox.width, bbox.depth))
    max_dim = max(1.0, max(bbox.width, bbox.depth))
    if kind == "flat":
        if config.flat_slope_degrees <= 0:
            return 0.0
        slope_rise = math.tan(math.radians(config.flat_slope_degrees)) * max_dim
        return min(slope_rise, height_m * 0.08)

    pitch = config.pitch_degrees
    if config.pitch_jitter_degrees > 0:
        pitch += rng.uniform(-config.pitch_jitter_degrees, config.pitch_jitter_degrees)
    pitch = max(0.0, min(75.0, pitch))
    pitch_rise = math.tan(math.radians(pitch)) * min_dim * 0.5
    ratio_rise = height_m * config.ridge_height_ratio

    if kind in {"dome", "barrel", "cone"}:
        shape_rise = min_dim * 0.45
    elif kind == "mansard":
        shape_rise = min_dim * 0.38
    elif kind == "shed":
        shape_rise = min_dim * 0.35
    else:
        shape_rise = min_dim * 0.42

    return max(0.0, min(pitch_rise, ratio_rise, shape_rise, height_m * 0.5))


def _long_axis(footprint: BuildingFootprint) -> str:
    bbox = footprint.bbox
    return "x" if bbox.width >= bbox.depth else "y"


def _normalized_axis(value: float, center: float, span: float) -> float:
    if span <= 0:
        return 0.0
    return _clamp((value - center) / (span * 0.5), -1.0, 1.0)


def _hip_factor(ux: float, uy: float, width: float, depth: float) -> float:
    if width >= depth:
        long = abs(ux)
        short = abs(uy)
        ratio = width / max(depth, 1e-6)
    else:
        long = abs(uy)
        short = abs(ux)
        ratio = depth / max(width, 1e-6)
    return min(1.0 - short, (1.0 - long) * ratio)


def _half_hip_factor(ux: float, uy: float, axis: str) -> float:
    long = abs(ux) if axis == "x" else abs(uy)
    short = abs(uy) if axis == "x" else abs(ux)
    gable = 1.0 - short
    end_clip = 1.0 - max(0.0, long - 0.58) / 0.42 * 0.55
    return min(gable, end_clip)


def _mansard_factor(ux: float, uy: float, break_ratio: float) -> float:
    edge_distance = 1.0 - max(abs(ux), abs(uy))
    edge_distance = _clamp(edge_distance)
    if edge_distance <= break_ratio:
        return 0.72 * edge_distance / break_ratio
    upper = (edge_distance - break_ratio) / max(1e-6, 1.0 - break_ratio)
    return 0.72 + 0.28 * upper


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(value, upper))
