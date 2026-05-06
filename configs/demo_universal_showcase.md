# Применение demo_universal_showcase.yaml

`configs/demo_universal_showcase.yaml` — большой интеграционный showcase-конфиг для проверки основных возможностей `citygen` одним запуском.

Он полезен после изменений в:

- road models и `roads.model: mixed`;
- urban fields и biome selection;
- building footprint generation;
- roof geometry;
- parcel subdivision;
- surface sampling;
- PLY/metadata export.

## Что Демонстрирует

Конфиг включает:

- большой тайл `tile.size_m: 2000`;
- заметный, но умеренный рельеф через `terrain.height_noise_m`;
- `urban_fields.enabled: true`;
- `roads.model: mixed`;
- mixed building footprints со всеми supported footprint weights;
- mixed roofs со всеми supported roof weights;
- `parcels.enabled: true`;
- RGB и semantic class fields в PLY.

Горизонтальная плоскость остается `x/y`, высота остается `z`.

## Запуск

Из корня репозитория:

```bash
uv run citygen --config configs/demo_universal_showcase.yaml --out outputs/demo_universal_showcase.ply
```

Рядом будет создан metadata-файл:

```text
outputs/demo_universal_showcase.metadata.json
```

Если нужен быстрый эксперимент с параметрами, временно уменьши `tile.size_m` или увеличь `sampling.*_spacing_m`. Для финального showcase лучше возвращать большой тайл, потому что он дает больше шансов увидеть разные биомы, road models, footprints, roofs и parcels.

## Быстрая Проверка Metadata

```bash
jq '{
  point_count,
  class_counts,
  road_models,
  biome_counts,
  building_counts: {
    total: .building_counts.total,
    by_footprint: .building_counts.by_footprint,
    by_roof: .building_counts.by_roof,
    by_parcel_biome: .building_counts.by_parcel_biome
  },
  parcel_counts
}' outputs/demo_universal_showcase.metadata.json
```

Хороший результат для этого конфига:

- `point_count > 0`;
- `class_counts` содержит `ground`, `road`, `sidewalk`, `building_facade`, `building_roof`;
- `road_models` содержит несколько effective models для `mixed`;
- `biome_counts` содержит несколько биомов, желательно все четыре;
- `building_counts.total > 0`;
- `building_counts.by_footprint` содержит разные footprint types;
- `building_counts.by_roof` содержит разные roof types;
- `parcel_counts.blocks > 0`;
- `parcel_counts.parcels > 0`;
- `parcel_counts.buildable_parcels > 0`;
- `parcel_counts.occupied_parcels > 0`;
- `parcel_counts.buildings_with_parcel_id == building_counts.total`.

## Что Означают Важные Секции

`urban_fields` задает плавные поля города. В этом showcase центр смещен относительно тайла, чтобы получить неоднородную карту биомов.

`roads.model: mixed` выбирает effective road model по биому. Текущий mixed-режим демонстрирует biome-preferred модели вроде `grid`, `radial_ring`, `linear` и `organic`. Отдельные `radial` и `free` проверяются отдельными demo-конфигами.

`buildings.footprint.model: mixed` выбирает форму здания по weights. Конфиг задает положительные веса для всех поддержанных footprint types.

`buildings.roof.model: mixed` выбирает roof geometry по weights. Конфиг задает положительные веса для всех поддержанных roof types.

`parcels.enabled: true` включает прямоугольное block/parcel subdivision. Здания размещаются внутри `parcel.inner`, получают `parcel_id` и учитываются в `parcel_counts`.

## Ограничения

Showcase не добавляет сущности, которых нет в текущем генераторе: машины, деревья, фонари, материалы, LAS/LAZ или настоящий LiDAR.

Parcel subdivision в текущем MVP — прямоугольная road-aware аппроксимация поверх road primitives. Это не полноценная GIS-полигонализация кварталов из дорожного графа.

Mixed footprints и roofs выбираются детерминированно, но все равно через weighted sampling. Если после изменений генератора какой-то тип исчез из metadata, сначала проверь `seed`, размеры тайла, parcel sizes, `footprint_min_m`, `footprint_max_m` и weights.

## Полезные Команды

Проверить PLY header:

```bash
head -n 20 outputs/demo_universal_showcase.ply
```

Посмотреть только parcel stats:

```bash
jq '.parcel_counts' outputs/demo_universal_showcase.metadata.json
```

Посмотреть разнообразие зданий:

```bash
jq '.building_counts | {total, by_footprint, by_roof, by_parcel_biome}' outputs/demo_universal_showcase.metadata.json
```

Запустить полный test suite перед сравнением showcase-вывода:

```bash
uv run python -m unittest discover -s tests
```
