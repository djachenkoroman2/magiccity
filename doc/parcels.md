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

Валидатор требует положительные размеры, согласованные min/max-значения, `split_jitter_ratio` в диапазоне `0..0.45` и известные имена параметров в секции `parcels`.

## Как Это Работает

1. Генератор строит `work_bbox`: bbox тайла плюс `tile.margin_m`.
2. По `work_bbox` проходит регулярная сетка с шагом `block_size_m`.
3. Каждая candidate cell превращается в прямоугольный `Block`; края немного inset-ятся через `block_jitter_m`.
4. Слишком маленькие blocks отбрасываются по `min_block_size_m`.
5. Каждый block рекурсивно делится по длинной оси, пока parcel не укладывается в `max_parcel_width_m` и `max_parcel_depth_m` или пока не достигнут `max_subdivision_depth`.
6. Для каждого parcel считается `inner` через `parcel_setback_m`, biome в центре участка и расстояние до ближайшей road primitive.
7. Parcel считается buildable, если его `inner` достаточно велик и representative points проходят road/sidewalk clearance.
8. Building generation проходит по buildable parcels детерминированно от `seed` и `parcel.id`.

Это сознательная MVP-аппроксимация. Текущие дороги представлены primitives и distance-based классификацией, а не полноценным топологическим графом, поэтому `parcels` не обещают идеальную GIS-полигонализацию кварталов для `organic`, `free`, `radial` или `mixed` roads.

## Placement Зданий

При `parcels.enabled: true` каждое принятое здание получает `parcel_id`. Footprint здания должен:

- помещаться в `parcel.inner`;
- иметь representative points внутри `parcel.inner`;
- быть дальше от road centerline, чем `roads.width_m / 2 + roads.sidewalk_width_m + effective_setback`;
- не пересекаться с уже принятыми зданиями по conservative bbox overlap check.

Старые настройки `buildings.footprint_min_m`, `buildings.footprint_max_m` и `buildings.setback_m` продолжают влиять на размер и отступы здания. Если выбранный footprint type не помещается в участок, здание детерминированно пропускается.

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

## Демо

Базовый demo-конфиг parcels:

```bash
uv run citygen --config configs/demo_parcels.yaml --out outputs/demo_parcels.ply
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

- Blocks и parcels прямоугольные и axis-aligned.
- Нет Shapely/GIS stack и нет polygon clipping дорожных коридоров.
- Road/sidewalk avoidance проверяется через representative sample points и distance to road primitives.
- Overlap зданий фильтруется консервативно по bbox.
- Полный список parcel polygons не пишется в metadata, чтобы metadata оставалась компактной.
