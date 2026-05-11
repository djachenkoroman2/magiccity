# Справочник по parcels

`parcels` — это опциональный слой кварталов и земельных участков для размещения зданий. Он работает в координатах проекта: горизонтальная плоскость `x/y`, высота `z`.

Главная идея: road network остается источником недоступных зон дорог и тротуаров, а здания в parcel mode больше не ставятся просто по candidate centers. Генератор сначала строит прямоугольные `Block`, делит их на `Parcel`, фильтрует buildable участки и только потом размещает building footprint внутри выбранного parcel.

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
```

Если секция отсутствует, используется `enabled: false`, и генератор сохраняет прежний режим размещения зданий.

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `enabled` | `false` | Включает placement зданий через parcels. |
| `block_size_m` | `96.0` | Размер регулярной ячейки candidate blocks в рабочем bbox. |
| `block_jitter_m` | `8.0` | Детерминированный inset краев block. Делает blocks менее одинаковыми. |
| `min_block_size_m` | `32.0` | Минимальная ширина и глубина block после обрезки по рабочему bbox. |
| `min_parcel_width_m` | `14.0` | Минимальная ширина parcel. |
| `max_parcel_width_m` | `42.0` | Целевая максимальная ширина parcel до остановки subdivision. |
| `min_parcel_depth_m` | `18.0` | Минимальная глубина parcel. |
| `max_parcel_depth_m` | `56.0` | Целевая максимальная глубина parcel до остановки subdivision. |
| `parcel_setback_m` | `2.0` | Внутренний отступ parcel; из него получается `parcel.inner`. |
| `split_jitter_ratio` | `0.18` | Jitter позиции split как доля текущей ширины или глубины. |
| `max_subdivision_depth` | `3` | Максимальная глубина рекурсивного деления block. |
| `building_alignment` | `parcel` | Ориентация зданий в parcel mode. `parcel` выравнивает footprint по локальным осям участка; `global` оставляет глобальные оси `x/y`. |
| `orientation_jitter_degrees` | `0.0` | Детерминированное отклонение от parcel orientation. По умолчанию здания строго параллельны границам участка. |
| `max_building_coverage` | `0.72` | Верхняя доля buildable area, которую может занимать footprint. |
| `require_building_inside_buildable_area` | `true` | Требует, чтобы representative points footprint лежали внутри buildable area. |

Валидатор требует положительные размеры, согласованные min/max-значения, `split_jitter_ratio` в диапазоне `0..0.45`, `orientation_jitter_degrees >= 0`, `max_building_coverage` в диапазоне `0..1` и известные имена параметров в секции `parcels`.

## Как Это Работает

1. Генератор строит `work_bbox`: bbox тайла плюс `tile.margin_m`.
2. По `work_bbox` проходит регулярная сетка с шагом `block_size_m`.
3. Каждая candidate cell превращается в прямоугольный `Block`; края немного inset-ятся через `block_jitter_m`.
4. Слишком маленькие blocks отбрасываются по `min_block_size_m`.
5. Каждый block рекурсивно делится по длинной оси, пока parcel не укладывается в `max_parcel_width_m` и `max_parcel_depth_m` или пока не достигнут `max_subdivision_depth`.
6. Для каждого parcel считается `inner` через `parcel_setback_m`, biome в центре участка, расстояние до ближайшей road primitive и parcel geometry. Сейчас generated parcels остаются axis-aligned, поэтому orientation равен `0`.
7. Parcel считается buildable, если его `inner` достаточно велик и representative points проходят road/sidewalk clearance.
8. Building generation проходит по buildable parcels детерминированно от `seed` и `parcel.id`.
9. Footprint строится в локальной системе участка и получает orientation по `building_alignment`.

Это сознательная MVP-аппроксимация. Текущие дороги представлены primitives и distance-based классификацией, а не полноценным топологическим графом, поэтому `parcels` не обещают идеальную GIS-полигонализацию кварталов для `organic`, `free`, `radial` или `mixed` roads.

## Placement Зданий

При `parcels.enabled: true` каждое принятое здание получает `parcel_id`. Footprint здания должен:

- помещаться в buildable area участка после `parcel_setback_m` и building setback;
- иметь representative points внутри buildable area;
- быть ориентированным параллельно parcel axes при `building_alignment: parcel`;
- быть дальше от road centerline, чем `roads.width_m / 2 + roads.sidewalk_width_m + effective_setback`;
- не пересекаться с уже принятыми зданиями по conservative bbox overlap check.

Старые настройки `buildings.footprint_min_m`, `buildings.footprint_max_m` и `buildings.setback_m` продолжают влиять на размер и отступы здания. Если выбранный footprint type не помещается в участок, генератор пробует deterministic rectangle fallback; если и он не помещается, parcel остается пустым.

Внутри кода для этого используется тонкий geometry layer: axis-aligned `Rect` адаптируется в `OrientedRect`, а `BuildingFootprint` хранит transform. Это позволяет roof sampling и facade boundary segments работать в world-space, но оценивать форму в local-space footprint.

## Metadata

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
    "buildable_area_failures": 96
  }
}
```

## Демо

Базовый demo-конфиг parcels:

```bash
uv run citygen --config configs/demo_parcels.yaml --out outputs/demo_parcels.ply
```

Демо parcel-aware alignment:

```bash
uv run citygen --config configs/demo_parcel_alignment.yaml --out outputs/demo_parcel_alignment.ply
```

Большой showcase с включенными parcels:

```bash
uv run citygen --config configs/demo_universal_showcase.yaml --out outputs/demo_universal_showcase.ply
```

После запуска удобно смотреть:

```bash
jq '{point_count, building_counts, parcel_counts}' outputs/demo_parcels.metadata.json
```

## Практические Подсказки

Если buildings почти не появляются:

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

- Blocks и generated parcels пока прямоугольные и axis-aligned; geometry layer уже хранит orientation для будущих rotated parcels.
- Нет Shapely/GIS stack и нет polygon clipping дорожных коридоров.
- Road/sidewalk avoidance проверяется через representative sample points и distance to road primitives.
- Overlap зданий фильтруется консервативно по bbox.
- Полный список parcel polygons не пишется в metadata, чтобы metadata оставалась компактной.
