# Справочник по конфигурации

Этот документ является справочником по YAML-конфигам `citygen`, построенным от исходного кода. Источник истины: `CityGenConfig` и вложенные значения по умолчанию dataclass-ов в `citygen/config.py`, логика валидатора, каталоги в `citygen/catalogs.py`, runtime-код дорог/parcels/ограждений/деревьев/транспорта/зданий и экспорт metadata.

`configs/*.yaml` остаются примерами запуска и проверочными конфигами. Они не являются источником схемы.

Связанные тематические документы:

- `doc/terrain.md` — шум высоты, горы, холмы, овраги и потребители `terrain_height`;
- `doc/roads.md` — модели дорог, primitives, профили и surface-классы;
- `doc/biomes.md` — `urban_fields`, классификация биомов и влияние биомов;
- `doc/parcels.md` — block/parcel subdivision и oriented parcels;
- `doc/fences.md` — ограждения участков, типы заборов, ворота, фундаменты и metadata;
- `doc/trees.md` — деревья, формы крон, biome-aware плотность, placement clearance, sampling и LiDAR;
- `doc/vehicles.md` — транспорт, типы, road/parking/yard placement, sampling, LiDAR и metadata;
- `doc/sampling.md` — стадии sampling pipeline, плотности точек, mobile LiDAR, semantic class/RGB и metadata;
- `doc/building_footprints.md` — идентификаторы footprints, aliases и семплирование;
- `doc/building_roofs.md` — идентификаторы roofs, aliases и функции высоты;
- `doc/generated_objects.md` — feature ids объектов и semantic classes;
- `doc/worldgen_catalogs.md` — каталоги и стадии пайплайна;
- `doc/universal_showcase.md` — справочник по большому интеграционному демонстрационному сценарию.

Запуск одного конфига:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
```

Для multi-tile конфига `--out` должен быть директорией или может быть пропущен:

```bash
uv run citygen --config path/to/multi_tile_config.yaml --out outputs/multi_tile
```

CLI по умолчанию показывает preflight-сводку, progress по стадиям pipeline, внутренний progress стадии `sampling` и итоговый summary. `sampling` печатает line-based диагностику по `tile_surfaces`, `buildings`, `fences`, `trees`, `vehicles` и `mobile LiDAR rays`, если соответствующие подэтапы участвуют в генерации. Для скриптов можно оставить только финальные пути:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply --quiet
```

Для диагностики доступны расширенные counters по стадиям и отдельные `item_done`-строки внутри `sampling`:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply --verbose
```

## Общие правила YAML

- Корневой объект должен быть YAML mapping, то есть словарем ключей и значений.
- Обязательное поле только одно: `seed`.
- Все остальные секции опциональны и получают значения по умолчанию.
- Все размеры и расстояния задаются в метрах.
- Горизонтальные координаты сцены: `x` и `y`; высота: `z`.
- Булевы значения пишутся как `true` или `false`.
- Текущий загрузчик читает описанные ниже поля. Секции `terrain`, `parcels`, `fences`, `trees`, `vehicles`, `mobile_lidar` и `worldgen` валидируют имена параметров строго, чтобы опечатки в новых слоях не проходили молча.

Минимальный валидный конфиг:

```yaml
seed: 7
```

Полный конфиг со всеми значениями по умолчанию:

```yaml
seed: 42
tile:
  x: 0
  y: 0
  size_m: 256
  margin_m: 32
terrain:
  base_height_m: 0
  height_noise_m: 1.5
  mountains: []
  hills: []
  ravines: []
urban_fields:
  enabled: false
  center_x: 0
  center_y: 0
  city_radius_m: 1200
  noise_scale_m: 350
  density_bias: 0
  industrial_bias: 0
  green_bias: 0
roads:
  model: grid
  spacing_m: 64
  width_m: 10
  sidewalk_width_m: 3
  angle_degrees: 0
  radial_count: 12
  ring_spacing_m: 0
  organic_wander_m: 0
  profiles:
    enabled: false
    default: default
    definitions:
      default:
        carriageway_width_m: 10
        sidewalk_width_m: 3
        median_width_m: 0
    model_weights: {}
    biome_weights: {}
buildings:
  enabled: true
  min_height_m: 8
  max_height_m: 60
  setback_m: 6
  footprint_min_m: 12
  footprint_max_m: 36
  footprint:
    model: rectangle
    weights: {}
    circle_segments: 24
    courtyard_ratio: 0.45
    wing_width_ratio: 0.35
    min_part_width_m: 5
    align_to_roads: true
  roof:
    model: flat
    weights: {}
    pitch_degrees: 28
    pitch_jitter_degrees: 8
    flat_slope_degrees: 0
    eave_overhang_m: 0
    ridge_height_ratio: 0.35
    mansard_break_ratio: 0.45
    dome_segments: 16
    align_to_long_axis: true
parcels:
  enabled: false
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
fences:
  enabled: false
  mode: perimeter
  type: mixed
  weights:
    wood_picket: 0.18
    wood_solid: 0.14
    wood_decorative: 0.10
    metal_profile: 0.14
    metal_chain_link: 0.12
    metal_welded: 0.10
    metal_forged: 0.08
    stone: 0.07
    brick: 0.07
  height_m: 1.8
  height_jitter_m: 0.25
  thickness_m: 0.12
  boundary_offset_m: 0.35
  road_clearance_m: 0.5
  coverage_ratio: 0.65
  sides: []
  gate_probability: 0.65
  gate_width_m: 4
  gate_sides:
    - front
  foundation: auto
  foundation_height_m: 0.25
  foundation_width_m: 0.35
  sample_spacing_m: 0.8
  openness: null
  decorative: false
trees:
  enabled: false
  density_per_ha: 18
  min_spacing_m: 8
  height_m: 7
  height_jitter_m: 1.5
  trunk_radius_m: 0.18
  trunk_height_ratio: 0.42
  crown_shape: mixed
  crown_radius_m: 2.4
  crown_height_ratio: 0.58
  crown_segments: 12
  weights:
    round: 0.32
    ellipsoid: 0.24
    cone: 0.18
    columnar: 0.12
    umbrella: 0.14
  biome_density_multipliers:
    downtown: 0.15
    residential: 0.75
    industrial: 0.05
    suburb: 1.25
  road_clearance_m: 3
  building_clearance_m: 2
  fence_clearance_m: 1
  tile_margin_clearance_m: 1
  allow_road_medians: false
  sample_spacing_m: 1
vehicles:
  enabled: false
  density_per_km: 10
  parking_density_per_ha: 12
  min_spacing_m: 8
  placement_modes:
    - road
    - parking
    - industrial_yard
  vehicle_type: mixed
  weights:
    car: 0.55
    truck: 0.18
    bus: 0.10
    emergency: 0.07
    tractor: 0.10
  biome_density_multipliers:
    downtown: 1.25
    residential: 0.85
    industrial: 0.75
    suburb: 0.65
  length_m: null
  width_m: null
  height_m: null
  wheel_radius_m: null
  clearance_m: 0.7
  orientation_jitter_degrees: 3
  building_clearance_m: 1
  fence_clearance_m: 0.6
  tree_clearance_m: 1.5
  tile_margin_clearance_m: 1
  allow_road_medians: false
  allowed_road_profiles: []
  lane_offset_m: null
  parked_ratio: 0.35
  side_of_road: both
  sample_spacing_m: 0.75
  max_points_per_vehicle: 500
mobile_lidar:
  enabled: false
  output_mode: additive
  trajectory: centerline
  sensor_height_m: 2.2
  direction_degrees: 0
  start_x: null
  start_y: null
  end_x: null
  end_y: null
  position_step_m: 8
  min_range_m: 1
  max_range_m: 90
  horizontal_fov_degrees: 180
  horizontal_step_degrees: 3
  vertical_fov_degrees: 50
  vertical_center_degrees: -8
  vertical_channels: 12
  angle_jitter_degrees: 0
  range_noise_m: 0.03
  drop_probability: 0.02
  distance_attenuation: 0.12
  occlusions_enabled: true
  ray_step_m: 1
sampling:
  mode: surface
  ground_spacing_m: 2
  road_spacing_m: 1.5
  building_spacing_m: 2
  jitter_ratio: 0.18
output:
  format: ply
  include_rgb: true
  include_class: true
worldgen:
  catalog_docs: true
  strict_catalog_validation: true
```

## Корневые параметры

| Параметр | Тип | Обязателен | Значение по умолчанию | Действие |
| --- | --- | --- | --- | --- |
| `seed` | integer | да | нет | Управляет всей детерминированной генерацией: рельефом, размещением зданий, размерами footprints, высотами, изгибами некоторых дорог и jitter. Один и тот же конфиг с тем же seed дает тот же результат. |
| `tile` | mapping | нет | см. секцию `tile` | Описывает один тайл. Используется, когда секция `tiles` отсутствует. |
| `tiles` | mapping | нет | отсутствует | Описывает пакет из нескольких тайлов. Если задана эта секция, CLI генерирует несколько PLY-файлов. |
| `terrain` | mapping | нет | см. секцию `terrain` | Настраивает высоту поверхности. |
| `urban_fields` | mapping | нет | см. секцию `urban_fields` | Включает процедурные городские поля и биомы. |
| `roads` | mapping | нет | см. секцию `roads` | Настраивает модель дорог, ширину дорог и тротуары. |
| `buildings` | mapping | нет | см. секцию `buildings` | Настраивает генерацию зданий. |
| `parcels` | mapping | нет | см. секцию `parcels` | Включает прямоугольное разбиение blocks/parcels и размещение зданий внутри участков. |
| `fences` | mapping | нет | см. секцию `fences` | Опционально добавляет заборы и ограждения по границам parcels. |
| `trees` | mapping | нет | см. секцию `trees` | Опционально добавляет деревья на естественном грунте. |
| `vehicles` | mapping | нет | см. секцию `vehicles` | Опционально добавляет транспорт на проезжей части, parking pockets и industrial yards. |
| `mobile_lidar` | mapping | нет | см. секцию `mobile_lidar` | Опционально включает трассировку лучей мобильного LiDAR-сенсора. |
| `sampling` | mapping | нет | см. секцию `sampling` | Настраивает плотность и регулярность точек. |
| `output` | mapping | нет | см. секцию `output` | Настраивает PLY-поля. |
| `worldgen` | mapping | нет | см. секцию `worldgen` | Настраивает флаги валидации catalogs/worldgen. |

## `tile`

Секция `tile` описывает один квадратный тайл в мировой сетке.

```yaml
tile:
  x: 0
  y: 0
  size_m: 256
  margin_m: 32
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `x` | integer | `0` | любое целое число | Индекс тайла по мировой оси X. Может быть отрицательным. |
| `y` | integer | `0` | любое целое число | Индекс тайла по мировой оси Y. Может быть отрицательным. |
| `size_m` | number | `256.0` | `> 0` | Размер стороны тайла в метрах. Чем больше значение, тем больше площадь и обычно больше точек. |
| `margin_m` | number | `32.0` | `> 0` | Рабочий запас вокруг тайла. Дороги и здания строятся в расширенной области, затем точки обрезаются обратно до bbox тайла. |

BBox тайла считается так:

```text
min_x = tile.x * tile.size_m
min_y = tile.y * tile.size_m
max_x = min_x + tile.size_m
max_y = min_y + tile.size_m
```

`margin_m` помогает получить более естественные края: здания и дороги могут быть рассчитаны за пределами тайла, но в итоговый PLY попадут только точки внутри исходного bbox.

## `tiles`

Секция `tiles` включает генерацию нескольких тайлов за один запуск. Она заменяет одиночный режим `tile`.

Вариант с явным списком:

```yaml
tiles:
  items:
    - {x: 0, y: 0}
    - {x: 1, y: 0}
    - {x: 0, y: 1, size_m: 192, margin_m: 48}
  size_m: 128
  margin_m: 40
```

Вариант с диапазонами:

```yaml
tiles:
  x_range: [0, 2]
  y_range: [0, 2]
  size_m: 128
  margin_m: 40
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `items` | list of mappings | нет | непустой список тайлов | Явно перечисляет тайлы. Каждый элемент обязан иметь `x` и `y`; `size_m` и `margin_m` можно задать на элементе. |
| `items[].x` | integer | нет | любое целое число | Индекс конкретного тайла по X. |
| `items[].y` | integer | нет | любое целое число | Индекс конкретного тайла по Y. |
| `items[].size_m` | number | `tiles.size_m`, затем `tile.size_m`, затем `256.0` | `> 0` | Размер конкретного тайла. |
| `items[].margin_m` | number | `tiles.margin_m`, затем `tile.margin_m`, затем `32.0` | `> 0` | Margin конкретного тайла. |
| `x_range` | two-item integer list | нет | `[start, stop]`, где `stop > start` | Диапазон индексов X по правилу Python `range(start, stop)`: stop не включается. |
| `y_range` | two-item integer list | нет | `[start, stop]`, где `stop > start` | Диапазон индексов Y по правилу Python `range(start, stop)`: stop не включается. |
| `size_m` | number | `tile.size_m`, затем `256.0` | `> 0` | Общий размер тайлов в `items` или range-режиме. |
| `margin_m` | number | `tile.margin_m`, затем `32.0` | `> 0` | Общий margin тайлов в `items` или range-режиме. |

Правила:

- Нужно задать либо `items`, либо обе секции `x_range` и `y_range`.
- Если есть `items`, диапазоны не используются.
- `x_range: [0, 2]` и `y_range: [0, 2]` создают четыре тайла: `(0,0)`, `(0,1)`, `(1,0)`, `(1,1)`.
- Для нескольких тайлов CLI пишет файлы вида `tile_X_Y.ply` и `tile_X_Y.metadata.json`.
- Если multi-tile конфигу передать `--out something.ply`, это ошибка: нужен путь к директории.

## `terrain`

Секция `terrain` описывает процедурную высоту поверхности.

```yaml
terrain:
  base_height_m: 0
  height_noise_m: 1.5
  mountains:
    - center_x: 120
      center_y: 160
      height_m: 140
      radius_m: 220
  hills:
    - center_x: 420
      center_y: 320
      height_m: 28
      radius_m: 180
  ravines:
    - center_x: 260
      center_y: 300
      length_m: 360
      width_m: 55
      depth_m: 18
      angle_degrees: 25
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `base_height_m` | number | `0.0` | любое число | Базовая высота поверхности по оси Z. Поднимает или опускает весь рельеф. |
| `height_noise_m` | number | `1.5` | `>= 0` | Амплитуда процедурного шума высоты. `0` отключает шум, но не отключает `mountains`, `hills` и `ravines`. |
| `mountains` | list | `[]` | элементы с `center_x`, `center_y`, `height_m > 0`, `radius_m > 0` | Высокие радиальные поднятия рельефа с более резким профилем. |
| `hills` | list | `[]` | элементы с `center_x`, `center_y`, `height_m > 0`, `radius_m > 0` | Более мягкие радиальные поднятия рельефа. |
| `ravines` | list | `[]` | элементы с `center_x`, `center_y`, `length_m > 0`, `width_m > 0`, `depth_m > 0`, опционально `angle_degrees` | Линейные понижения рельефа, повернутые на `angle_degrees`. |

Высота рельефа зависит от `seed`, координат `x/y` и настроек `terrain`. Она используется для точек земли, дорог, тротуаров и базовой высоты зданий.

Подробное описание форм рельефа и вложенных полей см. в `doc/terrain.md`.

## `urban_fields`

Секция `urban_fields` включает плавные городские поля и выбор биома в каждой точке мира.

```yaml
urban_fields:
  enabled: true
  center_x: 128
  center_y: 128
  city_radius_m: 460
  noise_scale_m: 180
  density_bias: 0.04
  industrial_bias: 0.08
  green_bias: 0.02
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | `false` | `true`, `false` | Включает urban fields. При `false` используется нейтральный режим, близкий к `residential`. |
| `center_x` | number | `0.0` | любое число | X-координата городского центра. Влияет на `centrality`, биомы и центр radial/ring дорог при включенных fields. |
| `center_y` | number | `0.0` | любое число | Y-координата городского центра. |
| `city_radius_m` | number | `1200.0` | `> 0` | Радиус влияния городского центра. Большое значение растягивает downtown/residential переходы. |
| `noise_scale_m` | number | `350.0` | `> 0` | Масштаб плавного шума. Больше значение дает более крупные и медленные изменения районов. |
| `density_bias` | number | `0.0` | любое число; практически полезно около `-1..1` | Смещает поле плотности. Положительное значение повышает шанс плотных и высотных районов. Итоговое поле clamp-ится в `0..1`. |
| `industrial_bias` | number | `0.0` | любое число; практически полезно около `-1..1` | Смещает поле промышленности. Положительное значение повышает вероятность industrial-биома. |
| `green_bias` | number | `0.0` | любое число; практически полезно около `-1..1` | Смещает green/open-space поле. Положительное значение повышает вероятность suburb-биома. |

Внутри считаются поля:

| Поле | Смысл | Где используется |
| --- | --- | --- |
| `centrality` | близость к городскому центру | выбор биома, потенциал высоты |
| `density` | плотность городской ткани | выбор биома, вероятность зданий, высотность |
| `height_potential` | потенциал высотности | множитель максимальной высоты зданий |
| `green_index` | зеленость или открытость района | выбор suburb-биома |
| `industrialness` | промышленный характер района | выбор industrial-биома |
| `orderliness` | регулярность планировки | сейчас вычисляется, но напрямую дорогами не используется |

Поддерживаемые биомы:

| Биом | Когда выбирается | Эффект на здания | Предпочтительная модель дорог для `roads.model: mixed` |
| --- | --- | --- | --- |
| `downtown` | высокая centrality и высокая density | больше шанс здания, выше высоты, чуть крупнее footprint, меньше setback | `radial_ring` |
| `residential` | запасной вариант для обычной городской ткани | средние параметры | `grid` |
| `industrial` | высокая industrialness вне самого центра | крупнее footprints, ниже высотность, умеренный setback | `linear` |
| `suburb` | низкая density или высокая green_index вне центра | реже здания, ниже высоты, меньше footprints, больше setback | `organic` |

При `enabled: false` классификация всегда возвращает `residential`. Поэтому `roads.model: mixed` без включенных `urban_fields` фактически будет использовать поведение `grid` в каждой точке.

## `roads`

Секция `roads` описывает осевые линии дорог, ширину проезжей части и тротуары.

```yaml
roads:
  model: grid
  spacing_m: 64
  width_m: 10
  sidewalk_width_m: 3
  angle_degrees: 0
  radial_count: 12
  ring_spacing_m: 0
  organic_wander_m: 0
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `model` | string | `grid` | `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free` | Выбирает алгоритм построения дорожной сети. |
| `spacing_m` | number | `64.0` | `> 0` | Основной шаг между дорогами или узлами сети. Чем меньше значение, тем плотнее дорожная сеть. |
| `width_m` | number | `10.0` | `> 0` | Полная ширина проезжей части. Точка считается `road`, если расстояние до оси дороги не больше `width_m / 2`. |
| `sidewalk_width_m` | number | `3.0` | `> 0` | Ширина тротуара с каждой стороны дороги. Точка считается `sidewalk`, если она за пределами дороги, но в пределах `width_m / 2 + sidewalk_width_m`. |
| `profiles` | mapping | выключено | mapping | Опциональные road profiles с разной шириной проезжей части, тротуаров и центрального разделителя. |
| `angle_degrees` | number | `0.0` | любое число | Поворот в градусах. Используется в `radial`, `radial_ring` и `linear`; в `mixed` влияет на соответствующие подмодели. |
| `radial_count` | integer | `12` | `>= 3` | Количество лучей в моделях `radial` и `radial_ring`. |
| `ring_spacing_m` | number | `0.0` | `>= 0` | Шаг кольцевых дорог для `radial_ring`. `0` означает использовать `spacing_m`. |
| `organic_wander_m` | number | `0.0` | `>= 0` | Амплитуда изгиба дорог модели `organic`. `0` включает авторасчет от `spacing_m` и `terrain.height_noise_m`. |

Валидатор требует:

```text
roads.width_m + 2 * roads.sidewalk_width_m < roads.spacing_m
```

Если условие нарушено, дороги с тротуарами занимают весь квартал и конфиг считается ошибочным.

### Значения `roads.model`

| Значение | Что генерирует | На что реагирует |
| --- | --- | --- |
| `grid` | Регулярную ортогональную сетку бесконечных линий по X и Y. | `spacing_m`, `width_m`, `sidewalk_width_m`. `angle_degrees` не используется. |
| `radial_ring` | Лучи из центра и концентрические кольца. | `radial_count`, `angle_degrees`, `spacing_m`, `ring_spacing_m`. Центр берется из `urban_fields.center_x/center_y`, если fields включены; иначе из центра рабочего bbox. |
| `radial` | Только лучи из центра, без колец. | `radial_count`, `angle_degrees`, `spacing_m`. Центр выбирается так же, как у `radial_ring`. |
| `linear` | Параллельные дороги вдоль главной оси и более редкие поперечные дороги. | `angle_degrees`, `spacing_m`. Поперечный шаг равен `spacing_m * 2.5`. |
| `organic` | Волнистые polyline-дороги в двух направлениях. | `spacing_m`, `organic_wander_m`, `terrain.height_noise_m`, `seed`. |
| `mixed` | Набор подмоделей `grid`, `radial_ring`, `linear`, `organic` и выбор модели по биому в каждой точке. | Требует осмысленных `urban_fields` для разнообразия. Не выбирает `radial` и `free` как предпочтительные модели биомов. |
| `free` | Нерегулярную сеть сегментов между детерминированно смещенными локальными узлами. | `spacing_m`, `seed`. Создает более хаотичную сеть, чем `organic`. |

Surface-класс точки определяется по расстоянию до ближайшей дорожной primitive:

```text
distance <= width_m / 2                         -> road
distance <= width_m / 2 + sidewalk_width_m      -> sidewalk
иначе                                           -> ground
```

### `roads.profiles`

Если `roads.profiles.enabled: true`, каждая дорожная primitive получает детерминированно выбранный profile. Profile задает поперечное сечение дороги:

```yaml
roads:
  profiles:
    enabled: true
    default: collector
    definitions:
      local:
        carriageway_width_m: 7
        sidewalk_width_m: 2
        median_width_m: 0
      collector:
        carriageway_width_m: 10
        sidewalk_width_m: 3
        median_width_m: 0
      arterial:
        carriageway_width_m: 14
        sidewalk_width_m: 4
        median_width_m: 1.5
      boulevard:
        carriageway_width_m: 16
        sidewalk_width_m: 4
        median_width_m: 6
    model_weights:
      grid: {local: 0.45, collector: 0.40, arterial: 0.15}
      radial_ring: {collector: 0.20, arterial: 0.45, boulevard: 0.35}
      linear: {collector: 0.35, arterial: 0.50, boulevard: 0.15}
      organic: {local: 0.80, collector: 0.20}
    biome_weights:
      downtown: {collector: 0.15, arterial: 0.45, boulevard: 0.40}
      residential: {local: 0.55, collector: 0.35, arterial: 0.10}
      industrial: {collector: 0.30, arterial: 0.55, boulevard: 0.15}
      suburb: {local: 0.85, collector: 0.15}
```

| Параметр | Тип | Действие |
| --- | --- | --- |
| `enabled` | boolean | Включает ширины из road profiles. При `false` используется совместимое поведение через `roads.width_m` и `roads.sidewalk_width_m`. |
| `default` | string | Profile для запасного выбора; должен быть описан в `definitions`. |
| `definitions.*.carriageway_width_m` | number | Суммарная ширина проезжей части без `road_median`. |
| `definitions.*.sidewalk_width_m` | number | Ширина тротуара с каждой стороны. |
| `definitions.*.median_width_m` | number | Ширина центрального разделителя; при `> 0` генерирует class `road_median`. |
| `model_weights` | mapping | Веса profiles по модели дорог. |
| `biome_weights` | mapping | Веса profiles по биому anchor-точки дорожной primitive. |

Для profile с `road_median` классификация идет от оси дороги наружу: `road_median`, затем `road`, затем `sidewalk`, затем `ground`. На перекрытиях дорог `road` имеет приоритет над `road_median`, чтобы пересечения не превращались в сплошной разделитель.

Валидатор требует положительные `carriageway_width_m`/`sidewalk_width_m`, `median_width_m >= 0`, существующие имена profiles в weights, положительные суммы весов и:

```text
max(carriageway_width_m + median_width_m + 2 * sidewalk_width_m) < roads.spacing_m
```

## `buildings`

Секция `buildings` управляет генерацией зданий, формой footprint и геометрией крыши.

```yaml
buildings:
  enabled: true
  min_height_m: 8
  max_height_m: 60
  setback_m: 6
  footprint_min_m: 12
  footprint_max_m: 36
  footprint:
    model: mixed
    weights:
      rectangle: 0.30
      square: 0.10
      circle: 0.08
      slab: 0.12
      courtyard: 0.12
      l_shape: 0.10
      u_shape: 0.10
      t_shape: 0.08
    circle_segments: 24
    courtyard_ratio: 0.45
    wing_width_ratio: 0.35
    min_part_width_m: 5
    align_to_roads: true
  roof:
    model: mixed
    weights:
      flat: 0.22
      shed: 0.10
      gable: 0.16
      hip: 0.14
      half_hip: 0.08
      pyramid: 0.08
      mansard: 0.08
      dome: 0.06
      barrel: 0.04
      cone: 0.04
    pitch_degrees: 28
    pitch_jitter_degrees: 8
    flat_slope_degrees: 0
    eave_overhang_m: 0
    ridge_height_ratio: 0.35
    mansard_break_ratio: 0.45
    dome_segments: 16
    align_to_long_axis: true
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | `true` | `true`, `false` | Включает или выключает генерацию зданий. При `false` остаются только точки `ground`/`road`/`sidewalk`. |
| `min_height_m` | number | `8.0` | `> 0`, `<= max_height_m` | Базовая минимальная высота здания. Биомы могут умножать ее. |
| `max_height_m` | number | `60.0` | `> 0`, `>= min_height_m` | Базовая максимальная высота здания. Биомы и `height_potential` могут умножать ее. |
| `setback_m` | number | `6.0` | `> 0` | Дополнительный отступ здания от защищенной зоны дороги и тротуара. Больше setback дает меньше зданий и больше свободного места у дорог. |
| `footprint_min_m` | number | `12.0` | `> 0`, `<= footprint_max_m` | Минимальный размер footprint по ширине и глубине до biome-множителя. |
| `footprint_max_m` | number | `36.0` | `> 0`, `>= footprint_min_m` | Максимальный размер footprint по ширине и глубине до biome-множителя. |
| `footprint` | mapping | см. ниже | mapping | Настраивает тип контура здания на земле. Если отсутствует, используется `rectangle`. |
| `roof` | mapping | см. ниже | mapping | Настраивает геометрию крыши. Если отсутствует, используется `flat`. |

### `buildings.footprint`

`buildings.footprint` описывает форму здания в плане.

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `model` | string | `rectangle` | `rectangle`, `square`, `circle`, `slab`, `courtyard`, `l_shape`, `u_shape`, `t_shape`, `mixed` | Выбирает тип footprint. |
| `weights` | mapping | `{}` для `rectangle`; стандартная смесь для `mixed` без weights | ключи типов footprint, значения `>= 0` | Веса выбора формы при `model: mixed`. Сумма должна быть положительной. |
| `circle_segments` | integer | `24` | `>= 8` | Количество сегментов для аппроксимации кругового фасада. |
| `courtyard_ratio` | number | `0.45` | `0 < value < 0.8` | Доля внешнего размера, занимаемая внутренним двором у `courtyard`. |
| `wing_width_ratio` | number | `0.35` | `0 < value < 0.8` | Базовая относительная ширина крыла для `l_shape`, `u_shape`, `t_shape`. |
| `min_part_width_m` | number | `5.0` | `> 0` | Минимальная ширина крыла или периметральной части. Если форма слишком мала, генератор детерминированно возвращается к `rectangle`. |
| `align_to_roads` | boolean | `true` | `true`, `false` | Зарезервировано для будущей ориентации вытянутых форм по дорогам. В parcel mode orientation приходит от parcel geometry. |

Поддерживаемые канонические типы footprints:

| Тип | Действие |
| --- | --- |
| `rectangle` | Базовый прямоугольник, совместимый со старым поведением. |
| `square` | Квадратный footprint с равными шириной и глубиной. |
| `circle` | Круговая/ротондная форма, фасад аппроксимируется `circle_segments`. |
| `slab` | Вытянутая полоса или пластина. |
| `courtyard` | Периметральный блок с пустым внутренним двором; roof points во двор не попадают. |
| `l_shape` | Г-образная форма из двух крыльев. |
| `u_shape` | П-образная форма с полузакрытым двором. |
| `t_shape` | Т-образная форма из пересекающихся крыльев. |
| `mixed` | Детерминированно выбирает один из конкретных типов по `weights`. |

Alias-значения в YAML нормализуются:

| Alias | Каноническое значение |
| --- | --- |
| `rotunda` | `circle` |
| `perimeter` | `courtyard` |
| `strip` | `slab` |
| `plate` | `slab` |
| `g_shape` | `l_shape` |
| `p_shape` | `u_shape` |

### `buildings.roof`

`buildings.roof` описывает форму крыши и функцию высоты для семплирования крыши.

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `model` | string | `flat` | `flat`, `shed`, `gable`, `hip`, `half_hip`, `pyramid`, `mansard`, `dome`, `barrel`, `cone`, `mixed` | Выбирает тип крыши. |
| `weights` | mapping | `{}` для `flat`; стандартная смесь для `mixed` без weights | ключи типов roof, значения `>= 0` | Веса выбора крыши при `model: mixed`. Сумма должна быть положительной. |
| `pitch_degrees` | number | `28.0` | `0..75` | Базовый угол скатной крыши. |
| `pitch_jitter_degrees` | number | `8.0` | `>= 0` | Детерминированное случайное отклонение угла. |
| `flat_slope_degrees` | number | `0.0` | `0..15` | Малый уклон для `flat`. `0` сохраняет старое плоское поведение. |
| `eave_overhang_m` | number | `0.0` | `>= 0` | Зарезервировано для будущего выноса карниза; текущий MVP не расширяет footprint. |
| `ridge_height_ratio` | number | `0.35` | `0 < value <= 0.8` | Верхняя граница подъема крыши как доля высоты здания. |
| `mansard_break_ratio` | number | `0.45` | `0.1..0.9` | Положение перелома мансардной крыши. |
| `dome_segments` | integer | `16` | `>= 8` | Зарезервировано для детализации криволинейных крыш и metadata; функция высоты аналитическая. |
| `align_to_long_axis` | boolean | `true` | `true`, `false` | Ориентирует конек или арку относительно длинной оси локального bbox footprint. |

Поддерживаемые канонические типы roofs:

| Тип | Действие |
| --- | --- |
| `flat` | Плоская крыша, дефолт обратной совместимости. |
| `shed` | Односкатная крыша с монотонным уклоном. |
| `gable` | Двускатная крыша с коньком вдоль длинной оси. |
| `hip` | Четырехскатная вальмовая крыша. |
| `half_hip` | Полувальмовая крыша, промежуточная между gable и hip. |
| `pyramid` | Шатровая крыша с максимумом в центре. |
| `mansard` | Ломаная мансардная крыша с переломом ската. |
| `dome` | Купольная крыша с плавным подъемом к центру. |
| `barrel` | Арочная/сводчатая крыша по одной оси. |
| `cone` | Коническая крыша с линейным снижением к краю. |
| `mixed` | Детерминированно выбирает один из конкретных типов по `weights`. |

Alias-значения `roof.model`:

| Alias | Каноническое значение |
| --- | --- |
| `single_slope` | `shed` |
| `mono_pitch` | `shed` |
| `dual_pitch` | `gable` |
| `pitched` | `gable` |
| `hipped` | `hip` |
| `half_hipped` | `half_hip` |
| `tent` | `pyramid` |
| `vault` | `barrel` |
| `arched` | `barrel` |
| `conical` | `cone` |

Даже если `enabled: false`, числовые поля секции все равно проходят валидацию.

Как это влияет на сцену:

- Центры-кандидаты создаются детерминированно от `seed`; при `parcels.enabled: true` здания создаются из buildable parcels.
- Типы footprint/roof, размеры footprint и высоты выбираются детерминированным случайным выбором от `seed`.
- Здание отбрасывается, если его footprint слишком близко к дороге или тротуару.
- Здание отбрасывается, если пересекается с уже принятым зданием.
- `base_z` здания берется из высоты рельефа в центре footprint.
- В облако точек попадают roof-точки с высотой по `roof.model` и facade-точки по реальной границе footprint до линии карниза.

Clearance от дорог считается так:

```text
roads.width_m / 2 + roads.sidewalk_width_m + effective_setback
```

Где `effective_setback` может быть изменен биомом.

Если здания почти не появляются, обычно нужно увеличить `roads.spacing_m` или уменьшить `roads.width_m`, `roads.sidewalk_width_m`, `buildings.setback_m`, `buildings.footprint_min_m`.

## `parcels`

Секция `parcels` включает явный слой прямоугольных кварталов и земельных участков. При `enabled: false` генератор использует прежнее размещение зданий по центрам-кандидатам.

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

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | `false` | `true`, `false` | Включает размещение зданий через parcels. |
| `block_size_m` | number | `96.0` | `> 0`, `>= min_block_size_m` | Шаг прямоугольной сетки candidate blocks в рабочем bbox. |
| `block_jitter_m` | number | `8.0` | `>= 0` | Детерминированный inset краев block, чтобы участки не выглядели идеально одинаковыми. |
| `min_block_size_m` | number | `32.0` | `> 0` | Минимальная ширина и глубина block после обрезки по рабочему bbox. |
| `min_parcel_width_m` | number | `14.0` | `> 0`, `<= max_parcel_width_m` | Минимальная ширина parcel. |
| `max_parcel_width_m` | number | `42.0` | `> 0`, `>= min_parcel_width_m` | Целевая максимальная ширина parcel до остановки subdivision. |
| `min_parcel_depth_m` | number | `18.0` | `> 0`, `<= max_parcel_depth_m` | Минимальная глубина parcel. |
| `max_parcel_depth_m` | number | `56.0` | `> 0`, `>= min_parcel_depth_m` | Целевая максимальная глубина parcel до остановки subdivision. |
| `parcel_setback_m` | number | `2.0` | `>= 0` | Внутренний отступ parcel для получения `parcel.inner`. |
| `split_jitter_ratio` | number | `0.18` | `0..0.45` | Детерминированный jitter позиции split как доля текущего размера. |
| `max_subdivision_depth` | integer | `3` | `>= 0` | Максимальная глубина рекурсивного деления block. |
| `building_alignment` | string | `parcel` | `parcel`, `global` | При `parcel` footprint здания выравнивается по локальным осям участка; `global` оставляет глобальные оси. |
| `orientation_jitter_degrees` | number | `0.0` | `>= 0` | Детерминированное отклонение orientation здания от parcel orientation. |
| `max_building_coverage` | number | `0.72` | `> 0`, `<= 1` | Максимальная доля buildable area, которую может занять footprint. |
| `require_building_inside_buildable_area` | boolean | `true` | `true`, `false` | Требует, чтобы representative points footprint лежали внутри buildable area parcel. |
| `oriented_blocks` | boolean | `false` | `true`, `false` | Включает local-space subdivision повернутых blocks. |
| `block_orientation_source` | string | `road_model` | `road_model`, `config`, `none` | Источник orientation для blocks. |
| `block_orientation_jitter_degrees` | number | `0.0` | `>= 0` | Детерминированный jitter orientation block. |
| `organic_orientation_jitter_degrees` | number | `10.0` | `>= 0` | Минимальный jitter для organic blocks при источнике `road_model`. |

MVP не строит полноценные GIS-полигоны кварталов из дорожного графа. Вместо этого он создает road-aware прямоугольные blocks/parcels, отбрасывает участки без достаточного clearance от `road`/`sidewalk` и размещает здания только внутри buildable area parcel. При `oriented_blocks: true` subdivision идет в local-space block, а `bbox` остается только axis-aligned envelope для broad phase. Для `block_orientation_source: road_model` модели `grid`, `linear`, `free` и `organic` используют `roads.angle_degrees` как базовую orientation; `radial` и `radial_ring` вычисляют направление от центра.

Metadata получает агрегированные секции `parcel_counts`, `parcel_building_alignment`, `building_orientations`, `block_geometry` и `parcel_geometry`: количество blocks/parcels, buildable и occupied parcels, распределение parcels по биомам, число зданий с `parcel_id`, режим alignment и сводку orientation.

Подробный архитектурный справочник по этому слою находится в `doc/parcels.md`.

## `fences`

Секция `fences` включает опциональные заборы и ограждения для земельных участков. Заборы строятся только при `parcels.enabled: true`, потому что их геометрия идет по `Parcel.geometry`.

```yaml
fences:
  enabled: true
  mode: perimeter
  type: mixed
  height_m: 1.8
  foundation: auto
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | `false` | `true`, `false` | Включает генерацию ограждений. При `false` сцена полностью сохраняет прежнее поведение. |
| `mode` | string | `perimeter` | `none`, `partial`, `perimeter` | `none` отключает сегменты, `partial` строит выбранные или случайные стороны, `perimeter` пытается оградить весь участок. |
| `type` | string | `mixed` | тип забора или `mixed` | Выбирает материал/конструкцию. |
| `weights` | mapping | стандартная смесь для `mixed` | ключи типов, значения `>= 0` | Веса выбора типа при `type: mixed`. |
| `height_m` | number | `1.8` | `> 0` | Базовая высота ограждения. |
| `height_jitter_m` | number | `0.25` | `>= 0` | Детерминированное отклонение высоты по участкам. |
| `thickness_m` | number | `0.12` | `> 0` | Толщина ограждения для offset и metadata. |
| `boundary_offset_m` | number | `0.35` | `>= 0` | Смещение внутрь участка от границы parcel, чтобы ограждение не лежало прямо на дороге или соседнем объекте. |
| `road_clearance_m` | number | `0.5` | `>= 0` | Минимальный clearance от road/sidewalk/median; сегменты, нарушающие clearance, пропускаются. |
| `coverage_ratio` | number | `0.65` | `0..1` | Доля сторон для случайного выбора в режиме `partial`, если `sides` не задан. |
| `sides` | list | `[]` | `front`, `back`, `left`, `right` | Явные стороны для `mode: partial`. |
| `gate_probability` | number | `0.65` | `0..1` | Вероятность оставить разрыв под ворота/калитку на разрешенной стороне. |
| `gate_width_m` | number | `4.0` | `> 0` | Ширина разрыва под ворота. |
| `gate_sides` | list | `[front]` | `front`, `back`, `left`, `right` | Стороны, на которых разрешены воротные разрывы. |
| `foundation` | string | `auto` | `auto`, `always`, `never` | Фундамент включается автоматически для `stone` и `brick`, либо принудительно/запрещается. |
| `foundation_height_m` | number | `0.25` | `> 0` | Высота семплируемого фундамента. |
| `foundation_width_m` | number | `0.35` | `> 0` | Ширина фундамента, учитываемая при offset. |
| `sample_spacing_m` | number | `0.8` | `> 0` | Шаг точек для забора и фундамента. |
| `openness` | number или null | `null` | `0..1` | Переопределяет прозрачность: `0` почти сплошной забор, `1` максимально открытая решетка. `null` берет значение типа. |
| `decorative` | boolean | `false` | `true`, `false` | Добавляет декоративные верхние элементы для совместимых типов. |

Поддерживаемые типы: `wood_picket`, `wood_solid`, `wood_decorative`, `metal_profile`, `metal_chain_link`, `metal_welded`, `metal_forged`, `stone`, `brick`, а также `mixed`.

Alias-значения нормализуются: `wood`/`wooden` -> `wood_picket`, `wood_board`/`timber` -> `wood_solid`, `profile`/`corrugated` -> `metal_profile`, `chain_link`/`rabitz`/`mesh` -> `metal_chain_link`, `welded` -> `metal_welded`, `forged` -> `metal_forged`, `masonry` -> `stone`, `brick_wall` -> `brick`.

Генератор делит периметр участка на стороны, оставляет разрывы под ворота, пропускает сегменты с конфликтом с road hardscape или footprint здания и семплирует точки классов `fence` и, при наличии основания, `fence_foundation`. Metadata получает `fence_counts`, а `object_feature_counts` — `parcel_fence` и `fence_foundation`.

Подробный тематический справочник по ограждениям находится в `doc/fences.md`.

## `trees`

Секция `trees` включает независимый слой деревьев. По умолчанию он выключен, поэтому существующие конфиги не меняют PLY-результат, пока не задано `trees.enabled: true`.

```yaml
trees:
  enabled: true
  density_per_ha: 28
  min_spacing_m: 7
  crown_shape: mixed
  biome_density_multipliers:
    downtown: 0.12
    residential: 0.8
    industrial: 0
    suburb: 1.75
  sample_spacing_m: 1.8
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | `false` | `true`, `false` | Включает генерацию деревьев. |
| `density_per_ha` | number | `18.0` | `>= 0` | Базовая плотность деревьев на гектар до biome multiplier. |
| `min_spacing_m` | number | `8.0` | `> 0` | Минимальная дистанция между принятыми деревьями. |
| `height_m` | number | `7.0` | `> 0` | Базовая высота дерева. |
| `height_jitter_m` | number | `1.5` | `>= 0` | Детерминированное отклонение высоты. |
| `trunk_radius_m` | number | `0.18` | `> 0` | Радиус цилиндрического ствола. |
| `trunk_height_ratio` | number | `0.42` | `0..1`, не включая границы | Доля высоты, занятая стволом. |
| `crown_shape` | string | `mixed` | `round`, `ellipsoid`, `cone`, `columnar`, `umbrella`, `mixed` | Форма кроны или weighted selector. |
| `crown_radius_m` | number | `2.4` | `> 0` | Базовый радиус кроны. |
| `crown_height_ratio` | number | `0.58` | `0 < value <= 1` | Доля высоты, занятая кроной. |
| `crown_segments` | integer | `12` | `>= 6` | Минимальная угловая детализация sampling кроны. |
| `weights` | mapping | встроенная смесь | формы крон, значения `>= 0` | Веса выбора формы при `crown_shape: mixed`. |
| `biome_density_multipliers` | mapping | `downtown: 0.15`, `residential: 0.75`, `industrial: 0.05`, `suburb: 1.25` | known biome ids, значения `>= 0` | Множители плотности. Значение `0` запрещает деревья в биоме. |
| `road_clearance_m` | number | `3.0` | `>= 0` | Минимальный отступ от road/sidewalk/median. |
| `building_clearance_m` | number | `2.0` | `>= 0` | Минимальный отступ от footprints зданий. |
| `fence_clearance_m` | number | `1.0` | `>= 0` | Минимальный отступ от fence segments. |
| `tile_margin_clearance_m` | number | `1.0` | `>= 0` | Отступ от границы crop bbox тайла. |
| `allow_road_medians` | boolean | `false` | `true`, `false` | Разрешает посадку на `road_median`; без этого medians считаются hardscape. |
| `sample_spacing_m` | number | `1.0` | `> 0` | Шаг точек ствола и кроны. |

Alias-значения форм крон: `sphere`/`spherical` -> `round`, `oval` -> `ellipsoid`, `conical`/`evergreen` -> `cone`, `narrow`/`poplar` -> `columnar`, `wide`/`canopy` -> `umbrella`.

Деревья ставятся только на natural ground: не на дорогах, не на тротуарах, не на medians без явного `allow_road_medians`, не внутри зданий, не в clearance вокруг зданий и fences, и не за границами crop bbox. Основание берет `z` из `terrain_height`. Sampling добавляет semantic classes `tree_trunk` и `tree_crown`, а metadata получает `tree_counts`, `supported_tree_crown_shapes` и counters в `object_feature_counts`.

Подробный тематический справочник по деревьям находится в `doc/trees.md`.

## `vehicles`

Секция `vehicles` включает независимый слой транспорта. По умолчанию он выключен, поэтому старые конфиги и PLY-результаты не меняются, пока не задано `vehicles.enabled: true`.

```yaml
vehicles:
  enabled: true
  density_per_km: 32
  parking_density_per_ha: 24
  min_spacing_m: 7
  placement_modes: mixed
  vehicle_type: mixed
  weights:
    car: 0.55
    truck: 0.18
    bus: 0.10
    emergency: 0.07
    tractor: 0.10
  sample_spacing_m: 1
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | `false` | `true`, `false` | Включает генерацию транспорта. |
| `density_per_km` | number | `10.0` | `>= 0` | Базовая плотность road vehicles на километр дорожных primitives до biome multiplier. |
| `parking_density_per_ha` | number | `12.0` | `>= 0` | Базовая плотность стоящего транспорта в parking/yard зонах внутри buildable parcels. |
| `min_spacing_m` | number | `8.0` | `> 0` | Минимальная дистанция между принятыми транспортными средствами. |
| `placement_modes` | string или list | `road`, `parking`, `industrial_yard` | `road`, `parking`, `industrial_yard`, `mixed` | Где разрешено размещать транспорт. `mixed` раскрывается во все поддержанные режимы. |
| `vehicle_type` | string | `mixed` | `car`, `truck`, `bus`, `emergency`, `tractor`, `mixed` | Конкретный тип или weighted selector. |
| `weights` | mapping | встроенная смесь | типы транспорта, значения `>= 0` | Веса выбора типа при `vehicle_type: mixed`. |
| `biome_density_multipliers` | mapping | `downtown: 1.25`, `residential: 0.85`, `industrial: 0.75`, `suburb: 0.65` | known biome ids, значения `>= 0` | Множители плотности; `0` отключает транспорт в биоме. |
| `length_m`, `width_m`, `height_m`, `wheel_radius_m` | number или null | `null` | `null` или `> 0` | Глобальное переопределение габаритов catalog default для выбранных типов. |
| `clearance_m` | number | `0.7` | `> 0` | Базовый зазор для road lane offset и placement-проверок. |
| `orientation_jitter_degrees` | number | `3.0` | `>= 0` | Детерминированное отклонение orientation от оси дороги или участка. |
| `building_clearance_m` | number | `1.0` | `>= 0` | Отступ от footprints зданий. |
| `fence_clearance_m` | number | `0.6` | `>= 0` | Отступ от fence segments/foundations. |
| `tree_clearance_m` | number | `1.5` | `>= 0` | Отступ от деревьев. |
| `tile_margin_clearance_m` | number | `1.0` | `>= 0` | Отступ от crop bbox тайла. |
| `allow_road_medians` | boolean | `false` | `true`, `false` | Разрешает размещение на `road_median`; по умолчанию medians запрещены. |
| `allowed_road_profiles` | list | `[]` | имена profiles | Если список непустой, road placement работает только на этих road profiles. |
| `lane_offset_m` | number или null | `null` | `null` или `>= 0` | Явный боковой offset от median/оси; `null` выбирает допустимый offset внутри carriageway. |
| `parked_ratio` | number | `0.35` | `0..1` | Доля parking-кандидатов внутри industrial parcels, когда одновременно включены `parking` и `industrial_yard`. |
| `side_of_road` | string | `both` | `left`, `right`, `both` | Сторона дороги для road placement. |
| `sample_spacing_m` | number | `0.75` | `> 0` | Шаг точек корпуса, колес и окон. |
| `max_points_per_vehicle` | integer | `500` | `> 0` | Верхний предел surface points на одно транспортное средство. |

Catalog types: `car`, `truck`, `bus`, `emergency`, `tractor`. Aliases: `sedan`, `hatchback`, `taxi` -> `car`; `van`, `lorry`, `delivery` -> `truck`; `coach` -> `bus`; `firetruck`, `ambulance`, `service` -> `emergency`; `utility`, `farm_tractor` -> `tractor`.

Road vehicles размещаются только на `road`/carriageway и получают orientation вдоль road primitive. Parking и industrial yard vehicles размещаются внутри buildable parcels только на `ground`, то есть не на sidewalks, medians или обычном natural ground вне явной parking/yard зоны. Все типы проверяют здания, fences, trees, соседний транспорт и границу crop bbox. Sampling добавляет semantic classes `vehicle_body`, `vehicle_wheel`, `vehicle_window`; mobile LiDAR трассирует корпус как oriented box obstacle.

Подробный тематический справочник по транспорту находится в `doc/vehicles.md`.

## `mobile_lidar`

Секция `mobile_lidar` включает опциональный режим мобильного LiDAR-сканирования. В этом режиме точки создаются не по регулярному surface sampling, а по фактическим попаданиям лучей из движущегося сенсора.

```yaml
mobile_lidar:
  enabled: true
  output_mode: additive
  trajectory: road
  sensor_height_m: 2.2
  direction_degrees: 0
  position_step_m: 8
  min_range_m: 1
  max_range_m: 90
  horizontal_fov_degrees: 180
  horizontal_step_degrees: 3
  vertical_fov_degrees: 50
  vertical_center_degrees: -8
  vertical_channels: 12
  angle_jitter_degrees: 0
  range_noise_m: 0.03
  drop_probability: 0.02
  distance_attenuation: 0.12
  occlusions_enabled: true
  ray_step_m: 1
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | `false` | `true`, `false` | Включает mobile LiDAR-режим. При `false` поведение остается поверхностным, как в старых версиях. |
| `output_mode` | string | `additive` | `additive`, `lidar_only` | Режим вывода: добавить LiDAR к surface sampling или оставить только LiDAR-точки. |
| `trajectory` | string | `centerline` | `centerline`, `line`, `road` | Тип траектории сенсора: по центру тайла, по явно заданной линии или по road primitives. |
| `sensor_height_m` | number | `2.2` | `> 0` | Высота установки сенсора над поверхностью рельефа. |
| `direction_degrees` | number | `0.0` | любое число | Базовое направление движения для `centerline` и fallback-направление. |
| `start_x`, `start_y`, `end_x`, `end_y` | number или null | `null` | числа или `null` | Явная линия траектории для `trajectory: line`; должны быть заданы все четыре значения одновременно. |
| `position_step_m` | number | `8.0` | `> 0` | Шаг между позициями сенсора вдоль траектории. |
| `min_range_m` | number | `1.0` | `> 0`, `< max_range_m` | Минимальная дальность луча. |
| `max_range_m` | number | `90.0` | `> 0`, `> min_range_m` | Максимальная дальность луча. |
| `horizontal_fov_degrees` | number | `180.0` | `0 < value <= 360` | Горизонтальный угол обзора. |
| `horizontal_step_degrees` | number | `3.0` | `> 0` | Шаг горизонтального сканирования. |
| `vertical_fov_degrees` | number | `50.0` | `0 < value <= 180` | Вертикальный угол обзора. |
| `vertical_center_degrees` | number | `-8.0` | любое число | Центральный вертикальный угол (обычно отрицательный, чтобы смотреть вниз). |
| `vertical_channels` | integer | `12` | `> 0` | Количество вертикальных каналов (слоев). |
| `angle_jitter_degrees` | number | `0.0` | `>= 0` | Угловой jitter лучей. |
| `range_noise_m` | number | `0.03` | `>= 0` | Шум дальности попадания. |
| `drop_probability` | number | `0.02` | `0..1` | Вероятность пропуска луча. |
| `distance_attenuation` | number | `0.12` | `0..1` | Вероятность отбросить дальние попадания для имитации потери плотности по дистанции. |
| `occlusions_enabled` | boolean | `true` | `true`, `false` | Включает режим ближайшего пересечения и окклюзий. |
| `ray_step_m` | number | `1.0` | `> 0` | Шаг трассировки луча при поиске пересечений с height field. |

Поведение:

- Лучи взаимодействуют с рельефом, дорогами, тротуарами, median, фасадами, крышами, ограждениями и деревьями.
- При `occlusions_enabled: true` сохраняется ближайшее пересечение луча; объекты за преградой не попадают в облако точек.
- При `occlusions_enabled: false` используется дальнее пересечение по лучу, что может визуально уменьшать окклюзии.
- Все лучи, jitter и пропуски полностью детерминированы от `seed`, координат тайла, индекса позиции и индексов углов.

Взаимодействие с `sampling`:

- `sampling.mode` по-прежнему должен быть `surface`.
- Если `mobile_lidar.enabled: false`, используется только surface sampling.
- Если `mobile_lidar.enabled: true` и `output_mode: additive`, итоговый PLY содержит surface + LiDAR точки.
- Если `mobile_lidar.enabled: true` и `output_mode: lidar_only`, итоговый PLY содержит только LiDAR точки.

Подробное описание порядка ray sampling, окклюзий, статистики и взаимодействия с surface sampling находится в `doc/sampling.md`.

## `sampling`

Секция `sampling` управляет плотностью точек и случайным смещением samples.

```yaml
sampling:
  mode: surface
  ground_spacing_m: 2
  road_spacing_m: 1.5
  building_spacing_m: 2
  jitter_ratio: 0.18
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `mode` | string | `surface` | только `surface` | Режим семплирования. В текущем MVP другие значения запрещены. |
| `ground_spacing_m` | number | `2.0` | `> 0` | Примерный шаг точек земли. Больше значение дает меньше ground-точек. |
| `road_spacing_m` | number | `1.5` | `> 0` | Примерный шаг точек дорог и тротуаров. Больше значение дает меньше road/sidewalk-точек. |
| `building_spacing_m` | number | `2.0` | `> 0` | Шаг точек крыш и фасадов. Больше значение дает меньше building-точек. |
| `jitter_ratio` | number | `0.18` | `0 <= value <= 0.45` | Случайное смещение точки как доля текущего spacing. `0` дает регулярную сетку. |

Практические эффекты:

- Уменьшение spacing увеличивает плотность и размер PLY.
- Увеличение spacing ускоряет предварительный просмотр и уменьшает файлы.
- Для ground/road/road_median/sidewalk сначала берется минимальный шаг из `ground_spacing_m` и `road_spacing_m`, затем лишние точки прореживаются под нужный класс.
- `building_spacing_m` отдельно применяется к крышам и фасадам.
- `trees.sample_spacing_m` отдельно применяется к стволам и кронам деревьев.
- Jitter детерминирован от `seed`, поэтому не ломает воспроизводимость.

Подробный справочник по стадиям `sampling`, входным/выходным структурам, влиянию настроек, примерам и диагностике находится в `doc/sampling.md`.

## `output`

Секция `output` управляет форматом PLY.

```yaml
output:
  format: ply
  include_rgb: true
  include_class: true
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `format` | string | `ply` | только `ply` | Формат вывода. Сейчас поддерживается только ASCII PLY. |
| `include_rgb` | boolean | `true` | `true`, `false` | Добавляет в PLY vertex-поля `red`, `green`, `blue`. |
| `include_class` | boolean | `true` | `true`, `false` | Добавляет в PLY vertex-поле `class`. |

При `include_rgb: true` и `include_class: true` каждая строка vertex содержит:

```text
x y z red green blue class
```

При `include_rgb: false` и `include_class: false` каждая строка содержит только:

```text
x y z
```

Классы точек:

| Class id | Имя | RGB |
| --- | --- | --- |
| `1` | `ground` | `107, 132, 85` |
| `2` | `road` | `47, 50, 54` |
| `3` | `sidewalk` | `174, 174, 166` |
| `4` | `building_facade` | `176, 164, 148` |
| `5` | `building_roof` | `112, 116, 122` |
| `6` | `road_median` | `118, 128, 84` |
| `7` | `fence` | `130, 101, 72` |
| `8` | `fence_foundation` | `118, 112, 103` |
| `9` | `tree_trunk` | `111, 78, 46` |
| `10` | `tree_crown` | `54, 128, 70` |
| `11` | `vehicle_body` | `52, 93, 142` |
| `12` | `vehicle_wheel` | `28, 30, 33` |
| `13` | `vehicle_window` | `98, 148, 172` |

Для каждого PLY также пишется metadata-файл рядом с ним:

```text
outputs/example.ply
outputs/example.metadata.json
```

Metadata содержит `seed`, bbox тайла, количество точек, распределение классов, mapping классов, RGB-палитру `class_colors`, использованные модели дорог, `road_profile_counts`, `road_profile_counts_by_biome`, `road_widths`, `road_median`, counts по биомам, `building_counts`, `parcel_counts`, `fence_counts`, `tree_counts`, `vehicle_counts`, `mobile_lidar`, `point_sources`, `parcel_building_alignment`, `building_orientations`, `block_geometry`, `parcel_geometry`, списки поддержанных типов footprint/roof/fence/tree crowns/vehicle types и полный конфиг после применения значений по умолчанию.

## `worldgen`

Секция `worldgen` опциональна и управляет флагами валидации catalogs/worldgen. Она не меняет runtime-распределение сцены.

```yaml
worldgen:
  catalog_docs: true
  strict_catalog_validation: true
```

| Параметр | Тип | По умолчанию | Действие |
| --- | --- | --- | --- |
| `catalog_docs` | boolean | `true` | Документирует намерение держать docs, основанные на catalogs, включенными; сейчас используется как флаг resolved config. |
| `strict_catalog_validation` | boolean | `true` | При загрузке конфига проверяет встроенные catalogs на неизвестные ids, некорректные weights и битые ссылки. |

Слой дорог подробно описан в `doc/roads.md`. Архитектура catalogs описана в `doc/worldgen_catalogs.md`, а список feature ids генерируемых объектов — в `doc/generated_objects.md`.

## Ограничения валидатора

Конфиг считается ошибочным, если нарушено любое из условий:

| Условие | Сообщение или смысл |
| --- | --- |
| Нет `seed` | `Missing required field: seed` |
| Корневой YAML не mapping | конфиг должен быть YAML mapping |
| Секция вроде `tile`, `roads`, `sampling` не mapping | секция должна быть mapping |
| `tile.size_m <= 0` | размер тайла должен быть положительным |
| `tile.margin_m <= 0` | margin должен быть положительным |
| `tiles` не mapping | секция `tiles` должна быть mapping |
| `tiles.items` не list | список тайлов должен быть list |
| `tiles.items` пустой | должен быть хотя бы один тайл |
| `tiles.x_range` или `tiles.y_range` не `[int, int]` | диапазон должен быть списком из двух целых |
| `range.stop <= range.start` | конец диапазона должен быть больше начала |
| `roads.model` не из списка поддерживаемых | поддерживаются `free`, `grid`, `linear`, `mixed`, `organic`, `radial`, `radial_ring` |
| `roads.radial_count < 3` | нужно хотя бы три луча |
| `roads.ring_spacing_m < 0` | ring spacing не может быть отрицательным |
| `roads.organic_wander_m < 0` | organic wander не может быть отрицательным |
| `roads.width_m + 2 * roads.sidewalk_width_m >= roads.spacing_m` | дорога с тротуарами должна быть уже квартального шага |
| `roads.profiles.default` не описан в `definitions` | default profile должен существовать |
| `roads.profiles.*_weights` содержит неизвестную модель дорог, biome или profile | веса должны ссылаться на поддержанные сущности |
| `roads.profiles.*_weights` имеет сумму `<= 0` | для выбора profile нужна положительная сумма весов |
| `max(profile corridor width) >= roads.spacing_m` | самый широкий road profile должен помещаться в квартальный шаг |
| Любой обязательный positive spacing/size/height `<= 0` | значение должно быть положительным |
| `buildings.max_height_m < buildings.min_height_m` | максимум высоты должен быть не меньше минимума |
| `buildings.footprint_max_m < buildings.footprint_min_m` | максимум footprint должен быть не меньше минимума |
| `buildings.footprint.model` не из списка поддерживаемых | поддерживаются `rectangle`, `square`, `circle`, `slab`, `courtyard`, `l_shape`, `u_shape`, `t_shape`, `mixed` |
| `buildings.footprint.weights` содержит неизвестный ключ | ключи должны быть конкретными footprint types, без `mixed` |
| `buildings.footprint.weights.* < 0` | веса не могут быть отрицательными |
| `buildings.footprint.model: mixed` и сумма weights `<= 0` | для mixed нужна положительная сумма весов |
| `buildings.footprint.circle_segments < 8` | круг должен иметь хотя бы 8 сегментов |
| `buildings.footprint.courtyard_ratio` вне `0..0.8` | доля двора должна быть в допустимом диапазоне |
| `buildings.footprint.wing_width_ratio` вне `0..0.8` | доля крыла должна быть в допустимом диапазоне |
| `buildings.roof.model` не из списка поддерживаемых | поддерживаются `flat`, `shed`, `gable`, `hip`, `half_hip`, `pyramid`, `mansard`, `dome`, `barrel`, `cone`, `mixed` |
| `buildings.roof.weights` содержит неизвестный ключ | ключи должны быть конкретными roof types, без `mixed` |
| `buildings.roof.weights.* < 0` | веса не могут быть отрицательными |
| `buildings.roof.model: mixed` и сумма weights `<= 0` | для mixed нужна положительная сумма весов |
| `buildings.roof.pitch_degrees` вне `0..75` | базовый угол ската должен быть в допустимом диапазоне |
| `buildings.roof.pitch_jitter_degrees < 0` | jitter угла не может быть отрицательным |
| `buildings.roof.flat_slope_degrees` вне `0..15` | уклон плоской крыши должен быть малым |
| `buildings.roof.eave_overhang_m < 0` | вынос карниза не может быть отрицательным |
| `buildings.roof.ridge_height_ratio` вне `0..0.8` | rise крыши должен быть ограничен |
| `buildings.roof.mansard_break_ratio` вне `0.1..0.9` | перелом мансарды должен быть внутри ската |
| `buildings.roof.dome_segments < 8` | купольная детализация должна иметь хотя бы 8 сегментов |
| Неизвестный ключ в `parcels` | имена параметров `parcels` валидируются строго |
| `parcels.block_jitter_m < 0` | jitter block не может быть отрицательным |
| `parcels.parcel_setback_m < 0` | parcel setback не может быть отрицательным |
| `parcels.building_alignment` неизвестен | поддерживаются `parcel` и `global` |
| `parcels.orientation_jitter_degrees < 0` | orientation jitter не может быть отрицательным |
| `parcels.max_building_coverage` вне `0..1` | coverage должен быть положительным и не больше `1` |
| `parcels.block_orientation_source` неизвестен | поддерживаются `road_model`, `config`, `none` |
| `parcels.block_orientation_jitter_degrees < 0` | block orientation jitter не может быть отрицательным |
| `parcels.organic_orientation_jitter_degrees < 0` | organic orientation jitter не может быть отрицательным |
| `parcels.split_jitter_ratio` вне `0..0.45` | split jitter должен быть в допустимом диапазоне |
| `parcels.max_subdivision_depth < 0` | глубина subdivision не может быть отрицательной |
| `parcels.max_parcel_width_m < parcels.min_parcel_width_m` | максимум ширины parcel должен быть не меньше минимума |
| `parcels.max_parcel_depth_m < parcels.min_parcel_depth_m` | максимум глубины parcel должен быть не меньше минимума |
| `parcels.block_size_m < parcels.min_block_size_m` | размер block должен быть не меньше минимального block |
| Неизвестный ключ в `fences` | имена параметров `fences` валидируются строго |
| `fences.enabled: true` без `parcels.enabled: true` | fences строятся только по границам parcels |
| `fences.mode` неизвестен | поддерживаются `none`, `partial`, `perimeter` |
| `fences.type` или `fences.weights.*` неизвестны | поддерживаются только catalog fence types и `mixed` |
| `fences.weights.* < 0` или сумма weights для `mixed` `<= 0` | веса должны быть неотрицательными, а сумма положительной |
| `fences.sides` или `fences.gate_sides` содержит неизвестную сторону | поддерживаются `front`, `back`, `left`, `right` |
| `fences.foundation` неизвестен | поддерживаются `auto`, `always`, `never` |
| `fences.height_jitter_m`, `boundary_offset_m` или `road_clearance_m < 0` | значения не могут быть отрицательными |
| `fences.coverage_ratio`, `gate_probability` или `openness` вне `0..1` | доли должны быть в допустимом диапазоне |
| Неизвестный ключ в `trees` | имена параметров `trees` валидируются строго |
| `trees.density_per_ha < 0` | плотность не может быть отрицательной |
| `trees.min_spacing_m`, `height_m`, `trunk_radius_m`, `crown_radius_m` или `sample_spacing_m <= 0` | размеры и spacing должны быть положительными |
| `trees.height_jitter_m` или clearance-поля `< 0` | jitter и clearances не могут быть отрицательными |
| `trees.trunk_height_ratio` или `crown_height_ratio` вне допустимого диапазона | ratios должны задавать осмысленную долю высоты дерева |
| `trees.crown_segments < 6` | крона должна иметь минимальную угловую детализацию |
| `trees.crown_shape` неизвестен | поддерживаются `round`, `ellipsoid`, `cone`, `columnar`, `umbrella`, `mixed` и aliases |
| `trees.weights.*` содержит неизвестную форму или отрицательный вес | веса должны ссылаться на поддержанные формы крон |
| `trees.crown_shape: mixed` и сумма weights `<= 0` | для mixed нужна положительная сумма весов |
| `trees.biome_density_multipliers.*` содержит неизвестный биом или отрицательное значение | multipliers должны ссылаться на поддержанные биомы |
| Неизвестный ключ в `vehicles` | имена параметров `vehicles` валидируются строго |
| `vehicles.density_per_km` или `parking_density_per_ha < 0` | плотности не могут быть отрицательными |
| `vehicles.min_spacing_m`, `clearance_m`, `sample_spacing_m` или `max_points_per_vehicle <= 0` | spacing, clearance и point cap должны быть положительными |
| `vehicles.length_m`, `width_m`, `height_m`, `wheel_radius_m <= 0` | габариты при явном переопределении должны быть положительными |
| `vehicles.vehicle_type` неизвестен | поддерживаются `car`, `truck`, `bus`, `emergency`, `tractor`, `mixed` и aliases |
| `vehicles.placement_modes` содержит неизвестный режим | поддерживаются `road`, `parking`, `industrial_yard`, `mixed` |
| `vehicles.side_of_road` неизвестен | поддерживаются `left`, `right`, `both` |
| `vehicles.parked_ratio` вне `0..1` | доля стоящего транспорта должна быть в допустимом диапазоне |
| `vehicles.allowed_road_profiles` содержит неизвестный profile | profiles должны существовать в `roads.profiles.definitions` |
| `vehicles.weights.*` содержит неизвестный тип или отрицательный вес | веса должны ссылаться на поддержанные типы транспорта |
| `vehicles.vehicle_type: mixed` и сумма weights `<= 0` | для mixed нужна положительная сумма весов |
| `vehicles.biome_density_multipliers.*` содержит неизвестный биом или отрицательное значение | multipliers должны ссылаться на поддержанные биомы |
| Неизвестный ключ в `mobile_lidar` | имена параметров `mobile_lidar` валидируются строго |
| `mobile_lidar.output_mode` неизвестен | поддерживаются `additive`, `lidar_only` |
| `mobile_lidar.trajectory` неизвестен | поддерживаются `centerline`, `line`, `road` |
| Для `mobile_lidar.trajectory: line` заданы не все `start_x/start_y/end_x/end_y` | явная line-траектория требует все четыре значения |
| `mobile_lidar.min_range_m >= mobile_lidar.max_range_m` | минимальная дальность должна быть меньше максимальной |
| `mobile_lidar.horizontal_fov_degrees` вне `0..360` | горизонтальный FOV должен быть в допустимом диапазоне |
| `mobile_lidar.vertical_fov_degrees` вне `0..180` | вертикальный FOV должен быть в допустимом диапазоне |
| `mobile_lidar.angle_jitter_degrees < 0` | угловой jitter не может быть отрицательным |
| `mobile_lidar.range_noise_m < 0` | шум дальности не может быть отрицательным |
| `mobile_lidar.drop_probability` вне `0..1` | вероятность пропуска луча должна быть в допустимом диапазоне |
| `mobile_lidar.distance_attenuation` вне `0..1` | ослабление по расстоянию должно быть в допустимом диапазоне |
| `sampling.mode != surface` | поддерживается только `surface` |
| `sampling.jitter_ratio` вне `0..0.45` | jitter должен быть в допустимом диапазоне |
| `output.format != ply` | поддерживается только `ply` |
| Неизвестный ключ в `worldgen` | поддерживаются `catalog_docs`, `strict_catalog_validation` |
| встроенные catalogs не проходят строгую валидацию | определения catalogs должны ссылаться только на известные ids и иметь валидные weights |

## Примеры конфигов

| Файл | Что демонстрирует |
| --- | --- |
| `configs/mvp.yaml` | Базовый MVP: дороги `grid`, sidewalks, terrain, buildings, RGB и class labels. |
| `configs/demo_road_profiles.yaml` | `roads.model: mixed`, road profiles, `road_median`, веса profiles по биомам; здания выключены. |
| `configs/demo_parcels.yaml` | Parcel subdivision и здания, привязанные к parcels, на легком тайле. |
| `configs/demo_parcel_fences.yaml` | Parcel subdivision с разными ограждениями, воротными разрывами и фундаментами. |
| `configs/demo_trees.yaml` | Опциональный слой деревьев: mixed кроны, biome-aware density, natural-ground placement и tree classes. |
| `configs/demo_vehicles.yaml` | Опциональный слой транспорта: road vehicles, parking/yard placement, mixed vehicle types и vehicle classes. |
| `configs/demo_parcel_alignment.yaml` | Выравнивание зданий по parcels, mixed roads, profiles, footprints и roofs. |
| `configs/demo_oriented_parcels.yaml` | Oriented block/parcel subdivision, orientation context от road model и выровненные здания. |
| `configs/demo_universal_showcase.yaml` | Большой интеграционный демонстрационный сценарий: mixed roads, profiles, биомы, parcels, mixed footprints, mixed roofs. См. `doc/universal_showcase.md`. |

Список намеренно отражает только YAML-файлы, которые реально есть в текущем `configs/`. Тематические документы выше описывают возможности шире, чем отдельные demos.
