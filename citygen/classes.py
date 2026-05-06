from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PointClass:
    id: int
    name: str
    color: tuple[int, int, int]


POINT_CLASSES: dict[str, PointClass] = {
    "ground": PointClass(1, "ground", (107, 132, 85)),
    "road": PointClass(2, "road", (47, 50, 54)),
    "sidewalk": PointClass(3, "sidewalk", (174, 174, 166)),
    "building_facade": PointClass(4, "building_facade", (176, 164, 148)),
    "building_roof": PointClass(5, "building_roof", (112, 116, 122)),
}


CLASS_BY_ID: dict[int, PointClass] = {spec.id: spec for spec in POINT_CLASSES.values()}


def class_mapping() -> dict[str, int]:
    return {name: spec.id for name, spec in POINT_CLASSES.items()}
