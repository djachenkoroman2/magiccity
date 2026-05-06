from __future__ import annotations

from dataclasses import dataclass
import math

from .config import UrbanFieldsConfig


@dataclass(frozen=True)
class UrbanFieldSample:
    centrality: float
    density: float
    height_potential: float
    green_index: float
    industrialness: float
    orderliness: float


def sample_urban_fields(seed: int, config: UrbanFieldsConfig, x: float, z: float) -> UrbanFieldSample:
    if not config.enabled:
        return UrbanFieldSample(
            centrality=0.5,
            density=0.5,
            height_potential=0.5,
            green_index=0.35,
            industrialness=0.12,
            orderliness=0.65,
        )

    dx = x - config.center_x
    dz = z - config.center_z
    distance = math.hypot(dx, dz)
    radial = _clamp(1.0 - distance / config.city_radius_m)
    broad_noise = _smooth_noise(seed, x, z, config.noise_scale_m, "broad") - 0.5
    density_noise = _smooth_noise(seed, x, z, config.noise_scale_m * 0.75, "density")
    industrial_noise = _smooth_noise(seed, x + 733.0, z - 419.0, config.noise_scale_m * 1.2, "industrial")
    green_noise = _smooth_noise(seed, x - 137.0, z + 281.0, config.noise_scale_m * 0.9, "green")
    order_noise = _smooth_noise(seed, x + z, z - x, config.noise_scale_m * 1.5, "order")

    centrality = _clamp(radial + broad_noise * 0.18)
    density = _clamp(0.64 * centrality + 0.36 * density_noise + config.density_bias)
    industrial_ring = _clamp(1.0 - abs(distance / config.city_radius_m - 0.65) * 2.0)
    industrialness = _clamp(
        0.16 * (1.0 - centrality)
        + 0.44 * industrial_noise
        + 0.28 * industrial_ring
        + config.industrial_bias
    )
    green_index = _clamp(0.55 * (1.0 - density) + 0.45 * green_noise + config.green_bias)
    height_potential = _clamp(0.62 * density + 0.28 * centrality + 0.10 * density_noise)
    orderliness = _clamp(0.42 * centrality + 0.34 * (1.0 - green_index) + 0.24 * order_noise)

    return UrbanFieldSample(
        centrality=centrality,
        density=density,
        height_potential=height_potential,
        green_index=green_index,
        industrialness=industrialness,
        orderliness=orderliness,
    )


def _smooth_noise(seed: int, x: float, z: float, scale: float, salt: str) -> float:
    phase = ((seed * 37 + sum(ord(ch) for ch in salt) * 97) % 1009) / 1009.0
    sx = x / scale
    sz = z / scale
    value = (
        math.sin(sx * 1.71 + phase * math.tau) * math.cos(sz * 1.37 - phase * 3.1) * 0.55
        + math.sin((sx + sz) * 1.03 + phase * 5.7) * 0.30
        + math.cos((sx - sz) * 0.83 - phase * 4.3) * 0.15
    )
    return _clamp(value * 0.5 + 0.5)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(value, upper))
