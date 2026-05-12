# Generated objects citygen

Этот документ перечисляет generated object / feature ids из `citygen.catalogs.OBJECT_FEATURE_DEFINITIONS`. Он нужен как расширяемый справочник: при добавлении нового feature id тесты требуют обновить этот файл.

## Сводная таблица

| Feature id | Stage | Config section | Semantic classes | Назначение |
| --- | --- | --- | --- | --- |
| `terrain_surface` | `sampling` | `terrain` | `ground` | Процедурная поверхность земли внутри tile bbox. |
| `road_network` | `roads` | `roads` | `road`, `sidewalk`, `road_median` | Road primitives, road models и road profiles. |
| `road_surface` | `sampling` | `roads` | `road` | Точки проезжей части. |
| `road_sidewalk` | `sampling` | `roads` | `sidewalk` | Точки тротуаров вокруг дорог. |
| `road_median` | `sampling` | `roads.profiles` | `road_median` | Центральный разделитель для road profiles с `median_width_m > 0`. |
| `parcel_blocks` | `parcels` | `parcels` | none | Прямоугольные blocks/parcels для parcel-mode размещения зданий. |
| `building` | `objects` | `buildings` | `building_facade`, `building_roof` | Здание как процедурный объект с footprint, facade и roof. |
| `building_footprint` | `objects` | `buildings.footprint` | none | Геометрия плана здания и clearance checks. |
| `building_roof` | `objects` | `buildings.roof` | `building_roof` | Roof geometry и roof surface sampling. |

## Terrain

`terrain_surface` создается на стадии `sampling` по `terrain.base_height_m`, `terrain.height_noise_m` и deterministic terrain height function. Точки получают semantic class `ground`.

Metadata:

- `class_counts.ground`;
- `object_feature_counts.terrain_surface`.

Ограничение MVP: terrain является height function, а не mesh/voxel terrain.

## Roads

`road_network` строится на стадии `roads`. Он выбирает road model из `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free`; при `roads.profiles.enabled: true` road primitives также получают road profile.

Связанные sampled features:

- `road_surface` -> semantic class `road`;
- `road_sidewalk` -> semantic class `sidewalk`;
- `road_median` -> semantic class `road_median`.

Biome interaction:

- `roads.model: mixed` выбирает preferred road model текущего биома;
- road profiles могут выбирать веса по биому через `roads.profiles.biome_weights`;
- catalog biomes также хранят default road profile preferences.

Metadata:

- `road_models`;
- `road_profile_counts`;
- `road_profile_counts_by_biome`;
- `road_widths`;
- `road_median`;
- `object_feature_counts.road_network`;
- `object_feature_counts.road_surface`;
- `object_feature_counts.road_sidewalk`;
- `object_feature_counts.road_median`.

Ограничение MVP: road graph остается набором primitives и distance-based classification, без полной topology/GIS polygonization.

## Parcels

`parcel_blocks` включается через `parcels.enabled: true`. Генератор создает прямоугольные candidate blocks, subdivides them into parcels и использует buildable geometry parcel для buildings. При `parcels.oriented_blocks: true` block получает orientation, subdivision идет в block local-space, а каждый parcel хранит world-space `OrientedRect`.

Biome interaction:

- parcel получает biome по центру;
- building placement внутри parcel использует biome building multipliers.

Metadata:

- `parcel_counts`;
- `parcel_building_alignment`;
- `block_geometry`;
- `parcel_geometry`;
- `building_counts.by_parcel_biome`;
- `object_feature_counts.parcel_blocks`.

Ограничение MVP: parcels являются прямоугольной аппроксимацией поверх road primitives, не cadastral/GIS layer. Поддерживаются oriented rectangles, но не arbitrary polygon parcels и не exact road polygon clipping.

## Buildings

`building` включается через `buildings.enabled: true`. На стадии `objects` generator выбирает candidate или parcel, применяет biome probability, строит footprint и roof, затем surface sampling создает facade/roof points.

Связанные features:

- `building_footprint`;
- `building_roof`.

Biome interaction:

- `build_probability`;
- `footprint_scale`;
- `height_min_multiplier`;
- `height_max_multiplier`;
- `setback_scale`;
- optional object weights in biome catalog for future placement engines.

Metadata:

- `building_counts.total`;
- `building_counts.by_biome`;
- `building_counts.by_footprint`;
- `building_counts.by_roof`;
- `building_orientations`;
- `object_feature_counts.building`;
- `object_feature_counts.building_footprint`;
- `object_feature_counts.building_roof`.

Ограничение MVP: buildings are analytic surfaces sampled to point cloud, not full solid meshes.

## Footprints

`building_footprint` поддерживает:

- `rectangle`;
- `square`;
- `circle`;
- `slab`;
- `courtyard`;
- `l_shape`;
- `u_shape`;
- `t_shape`.

Footprint ids описаны в catalog `FOOTPRINT_DEFINITIONS`; старое metadata поле `supported_footprint_types` сохранено. Footprint geometry может хранить orientation transform: `contains_xy`, roof sampling и facade boundary segments работают в world-space, но форма оценивается в local-space.

## Roofs

`building_roof` поддерживает:

- `flat`;
- `shed`;
- `gable`;
- `hip`;
- `half_hip`;
- `pyramid`;
- `mansard`;
- `dome`;
- `barrel`;
- `cone`.

Roof ids описаны в catalog `ROOF_DEFINITIONS`; старое metadata поле `supported_roof_types` сохранено.

## Semantic classes

Semantic class ids стабильны и описаны в catalog `SEMANTIC_CLASS_DEFINITIONS`:

- `ground`: id `1`;
- `road`: id `2`;
- `sidewalk`: id `3`;
- `building_facade`: id `4`;
- `building_roof`: id `5`;
- `road_median`: id `6`.

Новые semantic classes можно добавлять только с новым id; существующие id менять нельзя.
