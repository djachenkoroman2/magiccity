# Справочник по worldgen catalogs citygen

`citygen` использует подход, похожий на Minecraft worldgen, в архитектурном смысле: генерация разбита на явные стадии, а поддержанные биомы, типы объектов, surface-классы, модели дорог, road profiles, footprints, roofs, fences и tree crowns описаны в registry/catalog слое.

Это не voxel/block система и не runtime для data packs. Текущий MVP использует Python dataclass definitions в `citygen/catalogs.py`; они являются единым источником истины для поддержанных ids, сводок metadata и тестов покрытия документации.

Смежные справочники:

- `doc/roads.md` — модели дорог, road primitives, road profiles и surface-классы;
- `doc/configuration_reference.md` — YAML-схема конфигов, значения по умолчанию и правила валидации;
- `doc/parcels.md` — block/parcel subdivision и oriented parcels;
- `doc/fences.md` — fence catalog ids, генерация ограждений, ворота, фундаменты и metadata;
- `doc/trees.md` — tree crown ids, biome-aware density, placement и sampling деревьев;
- `doc/sampling.md` — detailed sampling pipeline, surface sampling, mobile LiDAR и metadata diagnostics;
- `doc/generated_objects.md` — object feature ids и counts в metadata;
- `doc/building_footprints.md` и `doc/building_roofs.md` — каталоги геометрии зданий.

## Стадии пайплайна

Стадии объявлены в `citygen.catalogs.WORLDGEN_STAGES`:

| Stage id | Назначение |
| --- | --- |
| `load_config` | Чтение YAML, значения по умолчанию и валидация. |
| `resolve_catalogs` | Получение активных worldgen catalogs. |
| `create_worldgen_context` | Создание `WorldgenContext` с seed, tile, bbox, work bbox и catalogs. |
| `biome_source` | Классификация биомов через `urban_fields` и catalog definitions. |
| `roads` | Построение road primitives, road models и road profiles. |
| `parcels` | Опциональное block/parcel subdivision. |
| `objects` | Размещение зданий и связанных footprint/roof features. |
| `fences` | Опциональное размещение fence segments и foundations по boundaries parcels. |
| `trees` | Опциональное размещение деревьев на natural ground с учетом биомов, дорог, зданий и fences. |
| `sampling` | Семплирование поверхностей рельефа, roads, sidewalks, medians, facades, roofs, fences и деревьев, плюс опциональный mobile LiDAR ray sampling. |
| `export_ply` | Экспорт ASCII PLY. |
| `export_metadata` | Экспорт JSON metadata. |

`generate_scene(config)` остается совместимой точкой входа. Внутри он создает `WorldgenContext`, но существующие generation functions продолжают принимать привычные `config`, bbox и дорожную сеть. Это осознанный MVP-подход: catalog layer добавлен без полного переписывания placement engine.

## Каталоги

Основной модуль:

```text
citygen/catalogs.py
```

Ключевые definitions:

- `BiomeDefinition`
- `RoadModelDefinition`
- `RoadProfileDefinition`
- `FootprintDefinition`
- `RoofDefinition`
- `FenceDefinition`
- `TreeCrownDefinition`
- `SemanticClassDefinition`
- `ObjectFeatureDefinition`
- `WorldgenCatalogs`

Активный набор возвращает `resolve_catalogs()`. Сейчас он возвращает встроенный `DEFAULT_CATALOGS`; внешние data packs и загрузка plugin-ов намеренно не реализованы.

## Идентификаторы биомов в каталоге

- `downtown`
- `residential`
- `industrial`
- `suburb`

Чтобы добавить новый биом:

1. Добавь `BiomeDefinition` в `BIOME_DEFINITIONS`.
2. Укажи `tags`, building multipliers, `preferred_road_model`, `road_profile_weights` и `object_weights`.
3. Обнови логику biome source в `citygen/biomes.py`, если новый биом требует нового условия выбора.
4. Добавь описание в `doc/biomes.md`.
5. Запусти тесты: documentation coverage проверит, что id описан.

## Идентификаторы object features в каталоге

- `terrain_surface`
- `road_network`
- `road_surface`
- `road_sidewalk`
- `road_median`
- `parcel_blocks`
- `building`
- `building_footprint`
- `building_roof`
- `parcel_fence`
- `fence_foundation`
- `tree`
- `tree_trunk`
- `tree_crown`

Чтобы добавить новый generated object feature:

1. Добавь `ObjectFeatureDefinition` в `OBJECT_FEATURE_DEFINITIONS`.
2. Укажи stable `id`, `category`, `stage`, `semantic_classes`, `config_section` и `enabled_by_default`.
3. Если feature зависит от биома, добавь веса или tags в `BiomeDefinition.object_weights`.
4. Реализуй generation или sampling в соответствующей стадии.
5. Опиши feature в `doc/generated_objects.md`.
6. Добавь тесты для валидации catalogs, покрытия документации и metadata.

## Идентификаторы форм крон

Tree crown catalog ids:

- `round`
- `ellipsoid`
- `cone`
- `columnar`
- `umbrella`

Формы используются секцией `trees`: `crown_shape` может указывать конкретный id или `mixed`, а `trees.weights` задает weighted selector для смешанной посадки. Alias-значения (`sphere`, `oval`, `conical`, `narrow`, `wide` и другие) нормализуются на уровне загрузки YAML, но canonical ids в catalogs остаются стабильными.

## Взвешенные селекторы

Общий helper находится в:

```text
citygen/selectors.py
```

`select_weighted_id()` принимает weights mapping, детерминированный RNG и fallback. Если explicit order не передан, keys сортируются, чтобы результат не зависел от порядка dict. Для selectors footprints и roofs используется catalog order, чтобы сохранить базовое распределение.

Правила:

- веса должны быть `>= 0`;
- сумма для активного selector должна быть положительной;
- unknown ids проверяются при валидации config/catalog;
- RNG namespace должен быть локальным и стабильным: seed + tile coords + stage/feature id + object id.

## Метаданные

Metadata теперь содержит дополнительные разделы:

- `worldgen`: `pipeline_version` и список stages;
- `catalogs`: сводка поддержанных ids;
- `biome_catalog`: tags, preferred road model и road profile weights;
- `object_feature_counts`: простые агрегаты по feature ids.

Старые поля сохранены: `road_models`, `biome_counts`, `building_counts`, `parcel_counts`, `supported_footprint_types`, `supported_roof_types`, `config`. Fence layer добавляет `fence_counts` и `supported_fence_types`; tree layer добавляет `tree_counts` и `supported_tree_crown_shapes`. Road/profile metadata (`road_profile_counts`, `road_widths`, `road_median`), parcel geometry metadata (`parcel_building_alignment`, `building_orientations`, `block_geometry`, `parcel_geometry`), fence metadata и tree metadata остаются отдельными runtime-агрегатами, а не catalog definitions.

Mobile LiDAR добавляет runtime-агрегаты `mobile_lidar` и `point_sources`. Они не являются catalog definitions и не добавляют новых object feature ids.

## Ограничения MVP

- Catalogs пока встроены в Python-код, без внешних data packs.
- Существующие generation functions не заменены универсальным placement engine.
- Biome source остается текущим `urban_fields` + thresholds.
- Object features описывают текущие runtime-сущности; новые слои должны добавляться отдельной стадией или понятным sampling feature id.
