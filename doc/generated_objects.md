# Генерируемые объекты citygen

Этот документ перечисляет generated object / feature ids из `citygen.catalogs.OBJECT_FEATURE_DEFINITIONS`. Он нужен как расширяемый справочник: при добавлении нового feature id тесты требуют обновить этот файл.

Подробные справочники по связанным слоям: `doc/configuration_reference.md`, `doc/roads.md`, `doc/parcels.md`, `doc/fences.md`, `doc/building_footprints.md`, `doc/building_roofs.md`, `doc/biomes.md`.

## Сводная таблица

| Feature id | Стадия | Секция конфига | Semantic classes | Назначение |
| --- | --- | --- | --- | --- |
| `terrain_surface` | `sampling` | `terrain` | `ground` | Процедурная поверхность земли внутри bbox тайла. |
| `road_network` | `roads` | `roads` | `road`, `sidewalk`, `road_median` | Road primitives, модели дорог и road profiles. |
| `road_surface` | `sampling` | `roads` | `road` | Точки проезжей части. |
| `road_sidewalk` | `sampling` | `roads` | `sidewalk` | Точки тротуаров вокруг дорог. |
| `road_median` | `sampling` | `roads.profiles` | `road_median` | Центральный разделитель для road profiles с `median_width_m > 0`. |
| `parcel_blocks` | `parcels` | `parcels` | none | Прямоугольные blocks/parcels для parcel-mode размещения зданий. |
| `building` | `objects` | `buildings` | `building_facade`, `building_roof` | Здание как процедурный объект с footprint, фасадом и roof. |
| `building_footprint` | `objects` | `buildings.footprint` | none | Геометрия плана здания и проверки clearance. |
| `building_roof` | `objects` | `buildings.roof` | `building_roof` | Геометрия крыши и семплирование roof surface. |
| `parcel_fence` | `objects` | `fences` | `fence` | Опциональные ограждения по границам parcels. |
| `fence_foundation` | `objects` | `fences` | `fence_foundation` | Низкое основание под массивными или явно настроенными ограждениями. |

## Рельеф

`terrain_surface` создается на стадии `sampling` по `terrain.base_height_m`, `terrain.height_noise_m` и детерминированной функции высоты рельефа. Точки получают semantic class `ground`.

Metadata:

- `class_counts.ground`;
- `object_feature_counts.terrain_surface`.

Ограничение MVP: рельеф является height function, а не mesh/voxel terrain.

## Дороги

`road_network` строится на стадии `roads`. Он выбирает модель дорог из `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free`; при `roads.profiles.enabled: true` road primitives также получают road profile. Подробности road primitives, приоритета surface-классов и profiles описаны в `doc/roads.md`.

Связанные семплируемые features:

- `road_surface` -> semantic class `road`;
- `road_sidewalk` -> semantic class `sidewalk`;
- `road_median` -> semantic class `road_median`.

Взаимодействие с биомами:

- `roads.model: mixed` выбирает предпочтительную модель дорог текущего биома;
- road profiles могут выбирать веса по биому через `roads.profiles.biome_weights`;
- биомы в catalog также хранят предпочтения road profiles по умолчанию.

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

Ограничение MVP: road graph остается набором primitives и классификацией по расстоянию, без полной topology/GIS-полигонализации.

## Участки и кварталы

`parcel_blocks` включается через `parcels.enabled: true`. Генератор создает прямоугольные blocks-кандидаты, делит их на parcels и использует buildable geometry parcel для зданий. При `parcels.oriented_blocks: true` block получает orientation, subdivision идет в local-space block, а каждый parcel хранит world-space `OrientedRect`, oriented buildable area и axis-aligned bbox для broad phase.

Взаимодействие с биомами:

- parcel получает biome по центру;
- размещение здания внутри parcel использует building multipliers выбранного биома.

Metadata:

- `parcel_counts`;
- `parcel_building_alignment`;
- `building_orientations`;
- `block_geometry`;
- `parcel_geometry`;
- `building_counts.by_parcel_biome`;
- `object_feature_counts.parcel_blocks`.

Ограничение MVP: parcels являются прямоугольной аппроксимацией поверх road primitives, а не cadastral/GIS layer. Поддерживаются oriented rectangles, но не произвольные polygon parcels и не точный road polygon clipping.

## Здания

`building` включается через `buildings.enabled: true`. На стадии `objects` генератор выбирает candidate или parcel, применяет probability из биома, строит footprint и roof, затем семплирование поверхности создает facade/roof points.

Связанные features:

- `building_footprint`;
- `building_roof`.

Взаимодействие с биомами:

- `build_probability`;
- `footprint_scale`;
- `height_min_multiplier`;
- `height_max_multiplier`;
- `setback_scale`;
- опциональные веса объектов в biome catalog для будущих placement engines.

Metadata:

- `building_counts.total`;
- `building_counts.by_biome`;
- `building_counts.by_footprint`;
- `building_counts.by_roof`;
- `building_orientations`;
- `object_feature_counts.building`;
- `object_feature_counts.building_footprint`;
- `object_feature_counts.building_roof`.

Ограничение MVP: здания являются аналитическими поверхностями, которые семплируются в облако точек, а не полноценными объемными meshes.

## Ограждения

`parcel_fence` включается через `fences.enabled: true` совместно с `parcels.enabled: true`. Генератор строит сегменты по сторонам `Parcel.geometry`, может оставлять разрывы под ворота, выбирает тип ограждения и высоту, а также пропускает сегменты, которые конфликтуют с road hardscape или footprint здания.

Поддерживаемые типы fence:

- `wood_picket`;
- `wood_solid`;
- `wood_decorative`;
- `metal_profile`;
- `metal_chain_link`;
- `metal_welded`;
- `metal_forged`;
- `stone`;
- `brick`.

Связанные features:

- `fence_foundation` появляется для `stone` и `brick` при `fences.foundation: auto`, либо для любого типа при `foundation: always`;
- `foundation: never` полностью убирает основание.

Metadata:

- `fence_counts`;
- `supported_fence_types`;
- `object_feature_counts.parcel_fence`;
- `object_feature_counts.fence_foundation`;
- `class_counts.fence`;
- `class_counts.fence_foundation`.

Ограничение MVP: fence layer работает по прямоугольным или oriented-rect parcels и не выполняет точное polygon clipping произвольных кадастровых границ.

## Footprints зданий

`building_footprint` поддерживает:

- `rectangle`;
- `square`;
- `circle`;
- `slab`;
- `courtyard`;
- `l_shape`;
- `u_shape`;
- `t_shape`.

Footprint ids описаны в catalog `FOOTPRINT_DEFINITIONS`; старое metadata поле `supported_footprint_types` сохранено. Геометрия footprint может хранить orientation transform: `contains_xy`, roof sampling и facade boundary segments работают в world-space, но форма оценивается в local-space.

## Крыши зданий

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

## Семантические классы

Semantic class ids стабильны и описаны в catalog `SEMANTIC_CLASS_DEFINITIONS`:

- `ground`: id `1`;
- `road`: id `2`;
- `sidewalk`: id `3`;
- `building_facade`: id `4`;
- `building_roof`: id `5`;
- `road_median`: id `6`;
- `fence`: id `7`;
- `fence_foundation`: id `8`.

Новые semantic classes можно добавлять только с новым id; существующие id менять нельзя.
