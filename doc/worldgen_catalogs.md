# Worldgen catalogs citygen

`citygen` использует Minecraft-like подход к worldgen в архитектурном смысле: генерация разбита на явные stages, а поддержанные биомы, типы объектов, surface classes, road models, road profiles, footprints и roofs описаны в registry/catalog слое.

Это не voxel/block система и не data pack runtime. Текущий MVP использует Python dataclass definitions в `citygen/catalogs.py`; они являются единым source of truth для supported ids, metadata summary и тестов покрытия документации.

## Pipeline stages

Стадии объявлены в `citygen.catalogs.WORLDGEN_STAGES`:

| Stage id | Назначение |
| --- | --- |
| `load_config` | Чтение YAML, defaults и validation. |
| `resolve_catalogs` | Получение активных worldgen catalogs. |
| `create_worldgen_context` | Создание `WorldgenContext` с seed, tile, bbox, work bbox и catalogs. |
| `biome_source` | Классификация биомов через `urban_fields` и catalog definitions. |
| `roads` | Построение road primitives, road models и road profiles. |
| `parcels` | Опциональное block/parcel subdivision. |
| `objects` | Размещение зданий и связанных footprint/roof features. |
| `sampling` | Surface sampling terrain, roads, sidewalks, medians, facades и roofs. |
| `export_ply` | ASCII PLY export. |
| `export_metadata` | JSON metadata export. |

`generate_scene(config)` остается совместимым entry point. Внутри он создает `WorldgenContext`, но existing generation functions продолжают принимать привычные `config`, bbox и road network. Это осознанный MVP-подход: catalog layer добавлен без полного rewrite placement engine.

## Catalogs

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
- `SemanticClassDefinition`
- `ObjectFeatureDefinition`
- `WorldgenCatalogs`

Активный набор возвращает `resolve_catalogs()`. Сейчас он возвращает встроенный `DEFAULT_CATALOGS`; внешние data packs и plugin loading намеренно не реализованы.

## Biome catalog ids

- `downtown`
- `residential`
- `industrial`
- `suburb`

Чтобы добавить новый биом:

1. Добавь `BiomeDefinition` в `BIOME_DEFINITIONS`.
2. Укажи `tags`, building multipliers, `preferred_road_model`, `road_profile_weights` и `object_weights`.
3. Обнови biome source logic в `citygen/biomes.py`, если новый биом требует нового условия выбора.
4. Добавь описание в `doc/biomes.md`.
5. Запусти tests: documentation coverage проверит, что id описан.

## Object feature catalog ids

- `terrain_surface`
- `road_network`
- `road_surface`
- `road_sidewalk`
- `road_median`
- `parcel_blocks`
- `building`
- `building_footprint`
- `building_roof`

Чтобы добавить новый generated object feature:

1. Добавь `ObjectFeatureDefinition` в `OBJECT_FEATURE_DEFINITIONS`.
2. Укажи stable `id`, `category`, `stage`, `semantic_classes`, `config_section` и `enabled_by_default`.
3. Если feature зависит от биома, добавь веса или tags в `BiomeDefinition.object_weights`.
4. Реализуй generation или sampling в соответствующем stage.
5. Опиши feature в `doc/generated_objects.md`.
6. Добавь tests для catalog validation, docs coverage и metadata.

## Weighted selectors

Общий helper находится в:

```text
citygen/selectors.py
```

`select_weighted_id()` принимает weights mapping, deterministic RNG и fallback. Если explicit order не передан, keys сортируются, чтобы результат не зависел от порядка dict. Для footprint и roof selectors используется catalog order, чтобы сохранить baseline distribution.

Правила:

- веса должны быть `>= 0`;
- сумма для активного selector должна быть положительной;
- unknown ids проверяются при config/catalog validation;
- RNG namespace должен быть локальным и стабильным: seed + tile coords + stage/feature id + object id.

## Metadata

Metadata теперь содержит дополнительные разделы:

- `worldgen`: `pipeline_version` и список stages;
- `catalogs`: summary supported ids;
- `biome_catalog`: tags, preferred road model и road profile weights;
- `object_feature_counts`: простые агрегаты по feature ids.

Старые поля сохранены: `road_models`, `biome_counts`, `building_counts`, `parcel_counts`, `supported_footprint_types`, `supported_roof_types`, `config`.

## MVP limits

- Catalogs пока встроены в Python-код, без внешних data packs.
- Existing generation functions не заменены универсальным placement engine.
- Biome source остается текущим `urban_fields` + thresholds.
- Object features описывают уже существующие сущности; новые визуальные сущности на этом этапе не добавляются.
