# Справочник по Universal Showcase

`configs/demo_universal_showcase.yaml` — большой интеграционный showcase для проверки основных возможностей `citygen` одним запуском. Этот документ описывает не схему YAML, а то, какие участки runtime-кода и диагностические поля metadata удобно проверять этим конфигом.

Полная схема YAML описана в `doc/configuration_reference.md`; отдельные подсистемы — в `doc/roads.md`, `doc/biomes.md`, `doc/parcels.md`, `doc/fences.md`, `doc/trees.md`, `doc/building_footprints.md` и `doc/building_roofs.md`.

Он полезен после изменений в следующих подсистемах:

- модели дорог и `roads.model: mixed`;
- urban fields и выбор биома;
- генерация footprints зданий;
- геометрия крыш;
- разбиение parcels;
- отдельный demo `configs/demo_parcel_fences.yaml` проверяет слой ограждений;
- отдельный demo `configs/demo_trees.yaml` проверяет слой деревьев;
- семплирование поверхностей;
- экспорт PLY и metadata.

## Что демонстрирует

Конфиг включает:

- большой тайл `tile.size_m: 1200`;
- разнообразный рельеф через `terrain.height_noise_m`, `terrain.mountains`, `terrain.hills` и `terrain.ravines`;
- `urban_fields.enabled: true`;
- `roads.model: mixed`;
- `roads.profiles.enabled: true` с `local`, `collector`, `arterial`, `boulevard`;
- широкий `road_median` через `arterial`/`boulevard` и semantic class `road_median`;
- `buildings.footprint.model: mixed` со всеми поддержанными весами footprints;
- `buildings.roof.model: mixed` со всеми поддержанными весами roofs;
- `parcels.enabled: true` с размещением зданий внутри parcels;
- layer `fences` в этом showcase не включен, чтобы не утяжелять большой тайл; для ограждений используется отдельный `configs/demo_parcel_fences.yaml`;
- layer `trees` в этом showcase не включен, чтобы не утяжелять большой тайл; для деревьев используется отдельный `configs/demo_trees.yaml`;
- layer `mobile_lidar` в этом showcase не включен; при необходимости его можно добавить в тот же YAML;
- сводки `worldgen`/catalogs в metadata;
- RGB и поля semantic class в PLY.

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

Если нужен быстрый эксперимент с параметрами, временно уменьши `tile.size_m` или увеличь `sampling.*_spacing_m`. Для финального showcase лучше возвращать большой тайл, потому что он дает больше шансов увидеть разные биомы, модели дорог, footprints, roofs и parcels.

## Быстрая проверка метаданных

```bash
jq '{
  point_count,
  class_counts,
  road_models,
  road_profile_counts,
  road_widths,
  road_median,
  biome_counts,
  object_feature_counts,
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
- `point_count` достаточно большой для showcase, ориентировочно `> 100000`;
- `class_counts` содержит `ground`, `road`, `road_median`, `sidewalk`, `building_facade`, `building_roof`;
- `road_models` содержит несколько effective models для `mixed`;
- `road_profile_counts` содержит `local`, `collector`, `arterial`, `boulevard`;
- `road_widths.max_median_width_m > 0`;
- `biome_counts` содержит несколько биомов, желательно все четыре;
- `object_feature_counts` содержит terrain, roads, parcels и buildings;
- `building_counts.total > 0`;
- `building_counts.by_footprint` содержит разные типы footprints;
- `building_counts.by_roof` содержит разные типы roofs;
- `parcel_counts.blocks > 0`;
- `parcel_counts.parcels > 0`;
- `parcel_counts.buildable_parcels > 0`;
- `parcel_counts.occupied_parcels > 0`;
- `parcel_counts.buildings_with_parcel_id == building_counts.total`.
- `mobile_lidar.enabled == false` для этого конкретного showcase-конфига.

## Что означают важные секции

`urban_fields` задает плавные поля города. В этом showcase центр смещен относительно тайла, чтобы получить неоднородную карту биомов.

`terrain` сочетает базовый шум поверхности с двумя высокими горными поднятиями, несколькими мягкими холмами и двумя диагональными оврагами. Эти формы влияют на землю, дороги, тротуары, основания зданий и лучи mobile LiDAR при его включении.

`roads.model: mixed` выбирает effective road network по биому. Текущий mixed-режим строит подсети `grid`, `radial_ring`, `linear` и `organic`; `radial` и `free` остаются поддержанными моделями дорог, но не входят в набор предпочтительных моделей для биомов.

`roads.profiles.enabled: true` назначает road primitives разные поперечные профили. В showcase включены узкие локальные улицы, collector roads, arterial roads и boulevards с широким median.

`buildings.footprint.model: mixed` выбирает форму здания по weights. Конфиг задает положительные веса для всех поддержанных типов footprints.

`buildings.roof.model: mixed` выбирает геометрию крыши по weights. Конфиг задает положительные веса для всех поддержанных типов roofs.

`parcels.enabled: true` включает block/parcel subdivision. Этот showcase проверяет размещение с учетом parcels, `parcel_id`, проверки buildable area и `parcel_counts`. Для визуально повернутых blocks/parcels используй `configs/demo_oriented_parcels.yaml`; в showcase `oriented_blocks` не включен, чтобы сохранить более предсказуемую базовую плотность на большом тайле.

`fences` вынесен в отдельный demo `configs/demo_parcel_fences.yaml`. Этот слой строит заборы по границам parcels, добавляет воротные разрывы, фундаменты для кирпичных/каменных стен и metadata `fence_counts`.

`trees` вынесен в отдельный demo `configs/demo_trees.yaml`. Этот слой строит деревья только на natural ground, смешивает формы крон по weights, учитывает biome density multipliers и добавляет metadata `tree_counts`.

`worldgen` оставлен явно включенным, чтобы metadata показывала сводки catalogs/worldgen: `worldgen`, `catalogs`, `biome_catalog` и `object_feature_counts`.

## Ограничения

Showcase не включает все опциональные слои сразу: fences, trees и mobile LiDAR проверяются отдельными или добавляемыми конфигами ради времени генерации. Машины, фонари, материалы и LAS/LAZ в текущем MVP не реализованы.

Parcel subdivision в текущем MVP — прямоугольная road-aware аппроксимация поверх road primitives. Это не полноценная GIS-полигонализация кварталов из дорожного графа.

Showcase тяжелее обычных проверочных конфигов. Для быстрых итераций уменьши `tile.size_m` или увеличь `sampling.ground_spacing_m`, `sampling.road_spacing_m`, `sampling.building_spacing_m`.

Mixed footprints и roofs выбираются детерминированно, но все равно через weighted sampling. Если после изменений генератора какой-то тип исчез из metadata, сначала проверь `seed`, размеры тайла, размеры parcels, `footprint_min_m`, `footprint_max_m` и weights.

## Полезные команды

Проверить заголовок PLY:

```bash
head -n 20 outputs/demo_universal_showcase.ply
```

Посмотреть только статистику parcels:

```bash
jq '.parcel_counts' outputs/demo_universal_showcase.metadata.json
```

Посмотреть статистику ограждений в отдельном demo:

```bash
jq '.fence_counts' outputs/demo_parcel_fences.metadata.json
```

Посмотреть статистику деревьев в отдельном demo:

```bash
jq '.tree_counts' outputs/demo_trees.metadata.json
```

Посмотреть разнообразие зданий:

```bash
jq '.building_counts | {total, by_footprint, by_roof, by_parcel_biome}' outputs/demo_universal_showcase.metadata.json
```

Запустить полный набор тестов перед сравнением showcase-вывода:

```bash
uv run python -m unittest discover -s tests
```
