from __future__ import annotations

from dataclasses import dataclass

from .catalogs import SEMANTIC_CLASS_DEFINITIONS


@dataclass(frozen=True)
class PointClass:
    id: int
    name: str
    color: tuple[int, int, int]


POINT_CLASSES: dict[str, PointClass] = {
    name: PointClass(definition.class_id, name, definition.color)
    for name, definition in SEMANTIC_CLASS_DEFINITIONS.items()
}


CLASS_BY_ID: dict[int, PointClass] = {spec.id: spec for spec in POINT_CLASSES.values()}


def class_mapping() -> dict[str, int]:
    return {name: spec.id for name, spec in POINT_CLASSES.items()}
