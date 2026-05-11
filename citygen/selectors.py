from __future__ import annotations

from collections.abc import Iterable, Mapping
from random import Random


def validate_weight_mapping(
    weights: Mapping[str, float],
    supported_ids: Iterable[str],
    label: str,
) -> None:
    supported = set(supported_ids)
    if not weights:
        raise ValueError(f"{label} must contain at least one weight.")
    total = 0.0
    for key, weight in weights.items():
        if key not in supported:
            raise ValueError(f"{label}.{key} references an unknown id.")
        if weight < 0:
            raise ValueError(f"{label}.{key} must be >= 0.")
        total += weight
    if total <= 0:
        raise ValueError(f"{label} must have a positive weight sum.")


def select_weighted_id(
    weights: Mapping[str, float],
    rng: Random,
    fallback: str,
    ordered_ids: Iterable[str] | None = None,
    supported_ids: Iterable[str] | None = None,
    require_positive: bool = False,
) -> str:
    if supported_ids is not None:
        validate_weight_mapping(weights, supported_ids, "weights")

    total = sum(weights.values())
    if total <= 0:
        if require_positive:
            raise ValueError("weights must have a positive sum.")
        return fallback

    order = tuple(ordered_ids) if ordered_ids is not None else tuple(sorted(weights))
    pick = rng.random() * total
    cursor = 0.0
    for item_id in order:
        weight = weights.get(item_id, 0.0)
        if weight < 0:
            if require_positive:
                raise ValueError(f"weights.{item_id} must be >= 0.")
            continue
        cursor += weight
        if pick <= cursor:
            return item_id
    return fallback
