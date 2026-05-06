# Справочник по конфигурациям citygen

Этот каталог содержит YAML-конфиги для `citygen`. Конфиг описывает seed, тайл или набор тайлов, рельеф, дорожную сеть, застройку, sampling и формат вывода.

Запуск одного конфига:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
```

Для multi-tile конфига `--out` должен быть директорией или может быть пропущен:

```bash
uv run citygen --config configs/demo_multi_tile.yaml --out outputs/multi_tile
```

## Общие правила YAML

- Корневой объект должен быть YAML mapping.
- Обязательное поле только одно: `seed`.
- Все остальные секции опциональны и получают значения по умолчанию.
- Все размеры и расстояния задаются в метрах.
- Горизонтальные координаты сцены: `x` и `y`; высота: `z`.
- Булевы значения пишутся как `true` или `false`.
- Текущий загрузчик читает описанные ниже поля. Секция `parcels` валидирует имена параметров строго, чтобы опечатки в новом слое участков не проходили молча.

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
```

## Корневые параметры

| Параметр | Тип | Обязателен | Значение по умолчанию | Действие |
| --- | --- | --- | --- | --- |
| `seed` | integer | да | нет | Управляет всей детерминированной генерацией: рельефом, размещением зданий, размерами footprints, высотами, изгибами некоторых дорог и jitter. Один и тот же конфиг с тем же seed дает тот же результат. |
| `tile` | mapping | нет | см. секцию `tile` | Описывает один тайл. Используется, когда секция `tiles` отсутствует. |
| `tiles` | mapping | нет | отсутствует | Описывает batch из нескольких тайлов. Если задана эта секция, CLI генерирует несколько PLY-файлов. |
| `terrain` | mapping | нет | см. секцию `terrain` | Настраивает высоту поверхности. |
| `urban_fields` | mapping | нет | см. секцию `urban_fields` | Включает процедурные городские поля и биомы. |
| `roads` | mapping | нет | см. секцию `roads` | Настраивает модель дорог, ширину дорог и тротуары. |
| `buildings` | mapping | нет | см. секцию `buildings` | Настраивает генерацию зданий. |
| `parcels` | mapping | нет | см. секцию `parcels` | Включает прямоугольное block/parcel subdivision и размещение зданий внутри участков. |
| `sampling` | mapping | нет | см. секцию `sampling` | Настраивает плотность и регулярность точек. |
| `output` | mapping | нет | см. секцию `output` | Настраивает PLY-поля. |

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
```

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `base_height_m` | number | `0.0` | любое число | Базовая высота поверхности по оси Z. Поднимает или опускает весь рельеф. |
| `height_noise_m` | number | `1.5` | любое число; обычно `>= 0` | Амплитуда процедурного шума высоты. `0` дает плоскую поверхность на `base_height_m`. |

Высота рельефа зависит от `seed`, координат `x/y` и настроек `terrain`. Она используется для точек земли, дорог, тротуаров и базовой высоты зданий.

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
| `enabled` | boolean | `false` | `true`, `false` | Включает urban fields. При `false` используется нейтральный residential-like режим. |
| `center_x` | number | `0.0` | любое число | X-координата городского центра. Влияет на centrality, биомы и центр radial/ring дорог при включенных fields. |
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

| Биом | Когда выбирается | Эффект на здания | Preferred road model для `roads.model: mixed` |
| --- | --- | --- | --- |
| `downtown` | высокая centrality и высокая density | больше шанс здания, выше высоты, чуть крупнее footprint, меньше setback | `radial_ring` |
| `residential` | fallback для обычной городской ткани | средние параметры | `grid` |
| `industrial` | высокая industrialness вне самого центра | крупнее footprints, ниже высотность, умеренный setback | `linear` |
| `suburb` | низкая density или высокая green_index вне центра | реже здания, ниже высоты, меньше footprints, больше setback | `organic` |

При `enabled: false` классификация всегда возвращает `residential`. Поэтому `roads.model: mixed` без включенных `urban_fields` фактически будет использовать grid-поведение в каждой точке.

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
| `angle_degrees` | number | `0.0` | любое число | Поворот в градусах. Используется в `radial`, `radial_ring` и `linear`; в `mixed` влияет на соответствующие подмодели. |
| `radial_count` | integer | `12` | `>= 3` | Количество лучей в моделях `radial` и `radial_ring`. |
| `ring_spacing_m` | number | `0.0` | `>= 0` | Шаг кольцевых дорог для `radial_ring`. `0` означает использовать `spacing_m`. |
| `organic_wander_m` | number | `0.0` | `>= 0` | Амплитуда изгиба organic-дорог. `0` включает авторасчет от `spacing_m` и `terrain.height_noise_m`. |

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
| `mixed` | Набор подмоделей `grid`, `radial_ring`, `linear`, `organic` и выбор модели по биому в каждой точке. | Требует осмысленных `urban_fields` для разнообразия. Не выбирает `radial` и `free` как biome-preferred модели. |
| `free` | Нерегулярную сеть сегментов между детерминированно смещенными локальными узлами. | `spacing_m`, `seed`. Создает более хаотичную сеть, чем `organic`. |

Surface-класс точки определяется по расстоянию до ближайшей дорожной примитивы:

```text
distance <= width_m / 2                         -> road
distance <= width_m / 2 + sidewalk_width_m      -> sidewalk
иначе                                           -> ground
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
| `enabled` | boolean | `true` | `true`, `false` | Включает или выключает генерацию зданий. При `false` остаются только ground/road/sidewalk точки. |
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
| `weights` | mapping | `{}` для `rectangle`; стандартная смесь для `mixed` без weights | ключи footprint types, значения `>= 0` | Веса выбора формы при `model: mixed`. Сумма должна быть положительной. |
| `circle_segments` | integer | `24` | `>= 8` | Количество сегментов для аппроксимации кругового фасада. |
| `courtyard_ratio` | number | `0.45` | `0 < value < 0.8` | Доля внешнего размера, занимаемая внутренним двором у `courtyard`. |
| `wing_width_ratio` | number | `0.35` | `0 < value < 0.8` | Базовая относительная ширина крыла для `l_shape`, `u_shape`, `t_shape`. |
| `min_part_width_m` | number | `5.0` | `> 0` | Минимальная ширина крыла или периметральной части. Если форма слишком мала, генератор детерминированно fallback-ится к `rectangle`. |
| `align_to_roads` | boolean | `true` | `true`, `false` | Зарезервировано для ориентации вытянутых форм относительно дорог; текущая MVP-геометрия остается axis-aligned. |

Поддерживаемые canonical footprint types:

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
| `mixed` | Детерминированно выбирает один из concrete types по `weights`. |

Alias-значения в YAML нормализуются:

| Alias | Canonical |
| --- | --- |
| `rotunda` | `circle` |
| `perimeter` | `courtyard` |
| `strip` | `slab` |
| `plate` | `slab` |
| `g_shape` | `l_shape` |
| `p_shape` | `u_shape` |

### `buildings.roof`

`buildings.roof` описывает форму крыши и height function для roof sampling.

| Параметр | Тип | По умолчанию | Возможные значения | Действие |
| --- | --- | --- | --- | --- |
| `model` | string | `flat` | `flat`, `shed`, `gable`, `hip`, `half_hip`, `pyramid`, `mansard`, `dome`, `barrel`, `cone`, `mixed` | Выбирает тип крыши. |
| `weights` | mapping | `{}` для `flat`; стандартная смесь для `mixed` без weights | ключи roof types, значения `>= 0` | Веса выбора крыши при `model: mixed`. Сумма должна быть положительной. |
| `pitch_degrees` | number | `28.0` | `0..75` | Базовый угол скатной крыши. |
| `pitch_jitter_degrees` | number | `8.0` | `>= 0` | Детерминированное случайное отклонение угла. |
| `flat_slope_degrees` | number | `0.0` | `0..15` | Малый уклон для `flat`. `0` сохраняет старое плоское поведение. |
| `eave_overhang_m` | number | `0.0` | `>= 0` | Зарезервировано для будущего выноса карниза; текущий MVP не расширяет footprint. |
| `ridge_height_ratio` | number | `0.35` | `0 < value <= 0.8` | Верхняя граница rise крыши как доля высоты здания. |
| `mansard_break_ratio` | number | `0.45` | `0.1..0.9` | Положение перелома мансардной крыши. |
| `dome_segments` | integer | `16` | `>= 8` | Зарезервировано для детализации curved roofs и metadata; height function аналитическая. |
| `align_to_long_axis` | boolean | `true` | `true`, `false` | Ориентирует ridge/arch относительно длинной оси bbox. |

Поддерживаемые canonical roof types:

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
| `mixed` | Детерминированно выбирает один из concrete types по `weights`. |

Alias-значения roof model:

| Alias | Canonical |
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

- Candidate centers создаются детерминированно от `seed`; при `parcels.enabled: true` здания создаются из buildable parcels.
- Типы footprint/roof, размеры footprint и высоты выбираются детерминированным random от `seed`.
- Здание отбрасывается, если его footprint слишком близко к дороге или тротуару.
- Здание отбрасывается, если пересекается с уже принятым зданием.
- `base_z` здания берется из высоты рельефа в центре footprint.
- В point cloud попадают roof-точки с высотой по roof model и facade-точки по реальной границе footprint до eave-line.

Clearance от дорог считается так:

```text
roads.width_m / 2 + roads.sidewalk_width_m + effective_setback
```

Где `effective_setback` может быть изменен биомом.

Если здания почти не появляются, обычно нужно увеличить `roads.spacing_m` или уменьшить `roads.width_m`, `roads.sidewalk_width_m`, `buildings.setback_m`, `buildings.footprint_min_m`.

## `parcels`

Секция `parcels` включает явный слой прямоугольных кварталов и земельных участков. При `enabled: false` генератор использует прежнее размещение зданий по candidate centers.

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

MVP не строит полноценные GIS-полигоны кварталов из дорожного графа. Вместо этого он создает road-aware прямоугольные blocks/parcels, отбрасывает участки без достаточного road/sidewalk clearance и размещает здания только внутри `parcel.inner`.

Metadata получает агрегированную секцию `parcel_counts`: количество blocks/parcels, buildable и occupied parcels, распределение parcels по биомам, средние размеры участков и число зданий с `parcel_id`.

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
| `mode` | string | `surface` | только `surface` | Режим sampling. В текущем MVP другие значения запрещены. |
| `ground_spacing_m` | number | `2.0` | `> 0` | Примерный шаг точек земли. Больше значение дает меньше ground-точек. |
| `road_spacing_m` | number | `1.5` | `> 0` | Примерный шаг точек дорог и тротуаров. Больше значение дает меньше road/sidewalk-точек. |
| `building_spacing_m` | number | `2.0` | `> 0` | Шаг точек крыш и фасадов. Больше значение дает меньше building-точек. |
| `jitter_ratio` | number | `0.18` | `0 <= value <= 0.45` | Случайное смещение точки как доля текущего spacing. `0` дает регулярную сетку. |

Практические эффекты:

- Уменьшение spacing увеличивает плотность и размер PLY.
- Увеличение spacing ускоряет preview и уменьшает файлы.
- Для ground/road/sidewalk сначала берется минимальный шаг из `ground_spacing_m` и `road_spacing_m`, затем лишние точки прореживаются под нужный класс.
- `building_spacing_m` отдельно применяется к крышам и фасадам.
- Jitter детерминирован от `seed`, поэтому не ломает воспроизводимость.

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

| class id | name | RGB |
| --- | --- | --- |
| `1` | `ground` | `107, 132, 85` |
| `2` | `road` | `47, 50, 54` |
| `3` | `sidewalk` | `174, 174, 166` |
| `4` | `building_facade` | `176, 164, 148` |
| `5` | `building_roof` | `112, 116, 122` |

Для каждого PLY также пишется metadata-файл рядом с ним:

```text
outputs/example.ply
outputs/example.metadata.json
```

Metadata содержит seed, bbox тайла, количество точек, распределение классов, mapping классов, использованные road models, biome counts, `building_counts`, списки поддержанных footprint/roof types и полный конфиг после применения defaults.

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
| Любой обязательный positive spacing/size/height `<= 0` | значение должно быть положительным |
| `buildings.max_height_m < buildings.min_height_m` | максимум высоты должен быть не меньше минимума |
| `buildings.footprint_max_m < buildings.footprint_min_m` | максимум footprint должен быть не меньше минимума |
| `buildings.footprint.model` не из списка поддерживаемых | поддерживаются `rectangle`, `square`, `circle`, `slab`, `courtyard`, `l_shape`, `u_shape`, `t_shape`, `mixed` |
| `buildings.footprint.weights` содержит неизвестный ключ | ключи должны быть concrete footprint types, без `mixed` |
| `buildings.footprint.weights.* < 0` | веса не могут быть отрицательными |
| `buildings.footprint.model: mixed` и сумма weights `<= 0` | для mixed нужна положительная сумма весов |
| `buildings.footprint.circle_segments < 8` | круг должен иметь хотя бы 8 сегментов |
| `buildings.footprint.courtyard_ratio` вне `0..0.8` | доля двора должна быть в допустимом диапазоне |
| `buildings.footprint.wing_width_ratio` вне `0..0.8` | доля крыла должна быть в допустимом диапазоне |
| `buildings.roof.model` не из списка поддерживаемых | поддерживаются `flat`, `shed`, `gable`, `hip`, `half_hip`, `pyramid`, `mansard`, `dome`, `barrel`, `cone`, `mixed` |
| `buildings.roof.weights` содержит неизвестный ключ | ключи должны быть concrete roof types, без `mixed` |
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
| `parcels.split_jitter_ratio` вне `0..0.45` | split jitter должен быть в допустимом диапазоне |
| `parcels.max_subdivision_depth < 0` | глубина subdivision не может быть отрицательной |
| `parcels.max_parcel_width_m < parcels.min_parcel_width_m` | максимум ширины parcel должен быть не меньше минимума |
| `parcels.max_parcel_depth_m < parcels.min_parcel_depth_m` | максимум глубины parcel должен быть не меньше минимума |
| `parcels.block_size_m < parcels.min_block_size_m` | размер block должен быть не меньше минимального block |
| `sampling.mode != surface` | поддерживается только `surface` |
| `sampling.jitter_ratio` вне `0..0.45` | jitter должен быть в допустимом диапазоне |
| `output.format != ply` | поддерживается только `ply` |

## Демо-конфиги в этом каталоге

| Файл | Что демонстрирует |
| --- | --- |
| `mvp.yaml` | Базовый MVP: сетка дорог, тротуары, рельеф, здания, RGB и class labels. |
| `demo_dense_downtown.yaml` | Плотный downtown: частая сетка, высокие здания, более плотный sampling. |
| `demo_lowrise_suburb.yaml` | Пригород: крупные кварталы, большие setback, низкая застройка, умеренный рельеф. |
| `demo_roads_and_sidewalks.yaml` | Здания выключены; удобно проверять `ground`, `road`, `sidewalk`. |
| `demo_terrain_relief.yaml` | Более заметный рельеф, поднятый `base_height_m`, смещенный тайл и больший margin. |
| `demo_export_geometry_only.yaml` | PLY только с `x`, `y`, `z`, без RGB и class fields. |
| `demo_sparse_fast_preview.yaml` | Большой тайл с грубым sampling для быстрого preview. |
| `demo_radial_ring.yaml` | Лучи и кольцевые дороги вокруг центра. |
| `demo_radial.yaml` | Лучевая структура без кольцевых дорог. |
| `demo_linear.yaml` | Линейная городская структура с основной осью и редкими поперечными улицами. |
| `demo_organic.yaml` | Волнистые organic streets, связанные с рельефом. |
| `demo_mixed_biomes.yaml` | `mixed` road model, urban fields и несколько биомов в одном тайле. |
| `demo_universal_showcase.yaml` | Большой showcase-тайл: mixed roads, urban fields, биомы, mixed footprints и mixed roofs. |
| `demo_parcels.yaml` | Parcel subdivision: прямоугольные blocks/parcels и здания, привязанные к участкам. |
| `demo_building_footprints.yaml` | Несколько типов building footprint в одном тайле. |
| `demo_courtyard_blocks.yaml` | Периметральные здания с внутренними дворами. |
| `demo_building_roofs.yaml` | Все поддержанные roof types в одном тайле. |
| `demo_pitched_roofs.yaml` | Скатные крыши: shed, gable, hip, half-hip, pyramid, mansard. |
| `demo_curved_roofs.yaml` | Купольные, арочные и конические крыши. |
| `demo_multi_tile.yaml` | Генерация нескольких соседних тайлов одним запуском. |
