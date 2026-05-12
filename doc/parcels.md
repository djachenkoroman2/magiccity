# Справочник по участкам (parcels)

`parcels` — это опциональный слой кварталов и земельных участков для размещения зданий. Он работает в координатах проекта: горизонтальная плоскость `x/y`, высота `z`.

Главная идея: дорожная сеть остается источником недоступных зон дорог, median и тротуаров, а здания в режиме parcels больше не ставятся просто по центрам-кандидатам. Генератор сначала строит прямоугольные `Block`, делит их на `Parcel`, фильтрует пригодные для застройки участки и только потом размещает footprint здания внутри выбранного parcel.

Значения YAML по умолчанию и правила валидации описаны в `doc/configuration_reference.md`. Road primitives, road profiles и hardscape distance подробно описаны в `doc/roads.md`.

## YAML

Секция находится на верхнем уровне конфига:

```yaml
parcels:
  enabled: true
  block_size_m: 96
  block_jitter_m: 8
  min_block_size_m: 32
  min_parcel_width_m: 14
  max_parcel_width_m: 42
  min_parcel_depth_m: 18
  max_parcel_depth_m: 56
  parcel_setback_m: 2
  split_jitter_ratio: 0.18
  max_subdivision_depth: 3
  building_alignment: parcel
  orientation_jitter_degrees: 0
  max_building_coverage: 0.72
  require_building_inside_buildable_area: true
  oriented_blocks: false
  block_orientation_source: road_model
  block_orientation_jitter_degrees: 0
  organic_orientation_jitter_degrees: 10
```

Если секция отсутствует, используется `enabled: false`, и генератор сохраняет прежний режим размещения зданий.

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `enabled` | `false` | Включает размещение зданий через parcels. |
| `block_size_m` | `96.0` | Размер регулярной ячейки для blocks-кандидатов в рабочем bbox. |
| `block_jitter_m` | `8.0` | Детерминированный inset краев block. Делает blocks менее одинаковыми. |
| `min_block_size_m` | `32.0` | Минимальная ширина и глубина block после обрезки по рабочему bbox. |
| `min_parcel_width_m` | `14.0` | Минимальная ширина parcel. |
| `max_parcel_width_m` | `42.0` | Целевая максимальная ширина parcel до остановки subdivision. |
| `min_parcel_depth_m` | `18.0` | Минимальная глубина parcel. |
| `max_parcel_depth_m` | `56.0` | Целевая максимальная глубина parcel до остановки subdivision. |
| `parcel_setback_m` | `2.0` | Внутренний отступ parcel; из него получается `parcel.inner`. |
| `split_jitter_ratio` | `0.18` | Jitter позиции split как доля текущей ширины или глубины. |
| `max_subdivision_depth` | `3` | Максимальная глубина рекурсивного деления block. |
| `building_alignment` | `parcel` | Ориентация зданий в режиме parcels. `parcel` выравнивает footprint по локальным осям участка; `global` оставляет глобальные оси `x/y`. |
| `orientation_jitter_degrees` | `0.0` | Детерминированное отклонение от parcel orientation. По умолчанию здания строго параллельны границам участка. |
| `max_building_coverage` | `0.72` | Верхняя доля buildable area, которую может занимать footprint. |
| `require_building_inside_buildable_area` | `true` | Требует, чтобы representative points footprint лежали внутри buildable area. |
| `oriented_blocks` | `false` | Включает oriented block/parcel subdivision. При `false` blocks/parcels остаются axis-aligned. |
| `block_orientation_source` | `road_model` | Источник ориентации block: `road_model`, `config` или `none`. |
| `block_orientation_jitter_degrees` | `0.0` | Детерминированный jitter ориентации block. |
| `organic_orientation_jitter_degrees` | `10.0` | Минимальный jitter для organic blocks при `block_orientation_source: road_model`. |

Валидатор требует положительные размеры, согласованные min/max-значения, `split_jitter_ratio` в диапазоне `0..0.45`, `orientation_jitter_degrees >= 0`, значения block orientation jitter `>= 0`, `max_building_coverage` в диапазоне `0..1` и известные имена параметров в секции `parcels`.

## Как это работает

1. Генератор строит `work_bbox`: bbox тайла плюс `tile.margin_m`.
2. По `work_bbox` проходит регулярная сетка с шагом `block_size_m`.
3. Каждая cell-кандидат превращается в прямоугольный `Block`; края немного inset-ятся через `block_jitter_m`.
4. Слишком маленькие blocks отбрасываются по `min_block_size_m`.
5. Если `oriented_blocks: true`, block получает orientation. При `block_orientation_source: road_model` используются effective road model/biome около центра block; `config` берет `roads.angle_degrees`, а `none` оставляет `0`.
6. Каждый block рекурсивно делится в local-space по длинной оси, пока parcel не укладывается в `max_parcel_width_m` и `max_parcel_depth_m` или пока не достигнут `max_subdivision_depth`.
7. Каждый local parcel rect преобразуется в world-space `OrientedRect`. `parcel.bbox` остается axis-aligned bbox для broad phase, а точные проверки используют `parcel.geometry`.
8. Для каждого parcel считается buildable area через local-space inset `parcel_setback_m`, biome в центре участка, расстояние до ближайшей road primitive и parcel geometry.
9. Parcel считается buildable, если его buildable geometry достаточно велика и representative points проходят clearance от road/sidewalk/median.
10. Генерация зданий проходит по buildable parcels детерминированно от `seed` и `parcel.id`.
11. Footprint строится в локальной системе участка и получает orientation по `building_alignment`.

Это сознательная MVP-аппроксимация. Текущие дороги представлены primitives и классификацией по расстоянию, а не полноценным топологическим графом, поэтому `parcels` не обещают идеальную GIS-полигонализацию кварталов для `organic`, `free`, `radial` или `mixed` roads.

Для `mixed` road model orientation выбирается практично: residential/grid использует `roads.angle_degrees` (по умолчанию `0`), industrial/linear следует `roads.angle_degrees`, downtown/radial_ring использует tangent вокруг city center, suburb/organic получает base angle с детерминированным jitter. Это не road-tangent solver, а легкая MVP-связь parcels с road context.

## Размещение зданий

При `parcels.enabled: true` каждое принятое здание получает `parcel_id`. Footprint здания должен:

- помещаться в buildable area участка после `parcel_setback_m` и building setback;
- иметь representative points внутри buildable area;
- быть ориентированным параллельно parcel axes при `building_alignment: parcel`;
- быть вне effective road hardscape corridor с учетом road profiles, median, sidewalks и building setback;
- не пересекаться с уже принятыми зданиями по консервативной bbox overlap check.

Старые настройки `buildings.footprint_min_m`, `buildings.footprint_max_m` и `buildings.setback_m` продолжают влиять на размер и отступы здания. Если выбранный тип footprint не помещается в участок, генератор пробует детерминированный fallback к `rectangle`; если и он не помещается, parcel остается пустым.

Внутри кода для этого используется тонкий geometry layer: axis-aligned `Rect` адаптируется в `OrientedRect`, а `BuildingFootprint` хранит transform. Это позволяет roof sampling и facade boundary segments работать в world-space, но оценивать форму в local-space footprint.

## Метаданные

Metadata получает агрегированную секцию `parcel_counts`:

```json
{
  "parcel_counts": {
    "blocks": 24,
    "parcels": 134,
    "buildable_parcels": 38,
    "occupied_parcels": 27,
    "buildings_with_parcel_id": 27,
    "by_biome": {
      "downtown": 20,
      "industrial": 36,
      "residential": 64,
      "suburb": 14
    },
    "average_parcel_area_m2": 702.34,
    "average_parcel_width_m": 22.235,
    "average_parcel_depth_m": 31.458
  }
}
```

`building_counts.by_parcel_biome` дополнительно показывает распределение зданий, которые были размещены через parcels.

Для parcel-aware placement добавляются агрегаты:

```json
{
  "parcel_building_alignment": {
    "mode": "parcel",
    "buildings_with_parcel_id": 27,
    "aligned_buildings": 27,
    "skipped_too_small_parcels": 0,
    "orientation_jitter_degrees": 0.0,
    "require_building_inside_buildable_area": true,
    "max_building_coverage": 0.72
  },
  "building_orientations": {
    "min_degrees": 0.0,
    "max_degrees": 0.0,
    "unique_bucket_count": 1
  },
  "parcel_geometry": {
    "oriented_parcels": 0,
    "axis_aligned_parcels": 134,
    "buildable_area_failures": 96,
    "orientation_bucket_degrees": {
      "0": 134
    }
  },
  "block_geometry": {
    "oriented_blocks": 0,
    "axis_aligned_blocks": 24,
    "orientation_source": "road_model",
    "oriented_blocks_enabled": false,
    "orientation_bucket_degrees": {
      "0": 24
    }
  }
}
```

## Демо

Базовый demo-конфиг parcels:

```bash
uv run citygen --config configs/demo_parcels.yaml --out outputs/demo_parcels.ply
```

Демо выравнивания зданий по parcels:

```bash
uv run citygen --config configs/demo_parcel_alignment.yaml --out outputs/demo_parcel_alignment.ply
```

Демо oriented parcels:

```bash
uv run citygen --config configs/demo_oriented_parcels.yaml --out outputs/demo_oriented_parcels.ply
```

Большой showcase с включенными parcels:

```bash
uv run citygen --config configs/demo_universal_showcase.yaml --out outputs/demo_universal_showcase.ply
```

После запуска удобно смотреть:

```bash
jq '{point_count, building_counts, parcel_counts}' outputs/demo_parcels.metadata.json
jq '{block_geometry, parcel_geometry, parcel_building_alignment}' outputs/demo_oriented_parcels.metadata.json
```

## Практические подсказки

Если здания почти не появляются:

- увеличь `roads.spacing_m`;
- уменьши `roads.width_m` или `roads.sidewalk_width_m`;
- уменьши `buildings.setback_m`;
- уменьши `buildings.footprint_min_m`;
- увеличь `parcels.block_size_m`, `max_parcel_width_m` или `max_parcel_depth_m`;
- уменьши `parcel_setback_m`.

Если parcels слишком крупные и однообразные:

- уменьши `max_parcel_width_m` и `max_parcel_depth_m`;
- увеличь `max_subdivision_depth`;
- немного увеличь `block_jitter_m` или `split_jitter_ratio`.

Если parcels слишком мелкие и здания часто пропускаются:

- увеличь `min_parcel_width_m`, `min_parcel_depth_m`;
- увеличь `max_parcel_width_m`, `max_parcel_depth_m`;
- уменьши `buildings.footprint_min_m`.

## Ограничения MVP

- Blocks и generated parcels остаются прямоугольными, но могут быть oriented. Полноценные произвольные polygon parcels не поддерживаются.
- Нет Shapely/GIS stack и нет polygon clipping дорожных коридоров.
- Orientation для blocks берется эвристикой из road model/config, без вычисления точного nearest road tangent.
- Road/sidewalk avoidance проверяется через representative sample points и расстояние до road primitives.
- Overlap зданий фильтруется консервативно по bbox.
- Полный список parcel polygons не пишется в metadata, чтобы metadata оставалась компактной.
