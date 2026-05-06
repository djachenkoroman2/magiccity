# MagicCity

MagicCity — MVP CLI-генератора синтетической городской застройки в формате облака точек.

Проект строит простой процедурный городской тайл: рельеф, разные модели уличной сети, тротуары, здания с несколькими типами footprint и крыш, глобальные urban fields, городские биомы, точки поверхностей, семантические классы, опциональные RGB-цвета и экспорт в ASCII PLY. Это рабочий MVP пайплайна от YAML-конфига до готового `.ply`, а не полноценный симулятор LiDAR.

## Что Генерируется

Для каждого тайла `citygen` создает детерминированную сцену:

- прямоугольный городской тайл с координатами `tile.x` и `tile.z`;
- процедурный рельеф по `seed`, `terrain.base_height_m` и `terrain.height_noise_m`;
- road network по одной из поддерживаемых моделей: `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free`;
- зоны тротуаров вокруг дорог;
- опциональные здания с footprint-формами `rectangle`, `square`, `circle`, `slab`, `courtyard`, `l_shape`, `u_shape`, `t_shape`;
- roof geometry: `flat`, `shed`, `gable`, `hip`, `half_hip`, `pyramid`, `mansard`, `dome`, `barrel`, `cone`;
- urban fields и biome map, влияющие на дороги и здания;
- точки крыш и фасадов зданий;
- точки земли, дорог и тротуаров;
- `.ply` файл и соседний `.metadata.json`.

Поддерживаемые классы точек:

| ID | Класс | RGB по умолчанию |
| --- | --- | --- |
| 1 | `ground` | `107, 132, 85` |
| 2 | `road` | `47, 50, 54` |
| 3 | `sidewalk` | `174, 174, 166` |
| 4 | `building_facade` | `176, 164, 148` |
| 5 | `building_roof` | `112, 116, 122` |

## Возможности MVP

Сейчас реализовано:

- детерминированная генерация по `seed`;
- тайловая система координат;
- несколько моделей дорог: `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free`;
- road primitives и distance-based классификация `ground` / `road` / `sidewalk`;
- глобальные urban fields в мировых координатах;
- городские биомы `downtown`, `residential`, `industrial`, `suburb`;
- генерация нескольких тайлов из одного конфига;
- классы `ground`, `road`, `sidewalk`, `building_facade`, `building_roof`;
- процедурный шум высоты рельефа;
- процедурные здания с прямоугольными, круговыми, линейными, периметральными и составными footprints;
- процедурные крыши: плоские, скатные, мансардные, купольные, арочные и конические;
- sampling крыш и фасадов;
- surface sampling земли, дорог и тротуаров;
- настройка плотности точек;
- jitter для менее регулярного расположения точек;
- ASCII PLY экспорт;
- включение/отключение RGB-полей;
- включение/отключение поля semantic class;
- metadata JSON с итоговым конфигом, bbox тайла, количеством точек и статистикой классов.

Пока не реализовано:

- полноценный топологический дорожный граф с идеальными кварталами и перекрестками;
- настоящие GIS-ограничения и CRS-aware road layout;
- настоящая LiDAR-симуляция лучей, окклюзий, углов сканирования, intensity и returns;
- деревья, автомобили, столбы, ЛЭП, подстанции, фонари, уличная мебель;
- LAS/LAZ экспорт;
- CRS/georeferencing metadata;
- текстуры и mesh-геометрия.

## Структура Проекта

```text
citygen/
  __main__.py       # запуск через python -m citygen
  cli.py            # CLI entry point
  config.py         # загрузка YAML, defaults, validation
  generator.py      # генерация сцены: тайл, дороги, здания
  roads.py          # road primitives и модели уличной сети
  fields.py         # глобальные urban fields
  biomes.py         # классификация городских биомов
  footprints.py     # геометрия building footprints
  roofs.py          # геометрия и height functions крыш
  sampling.py       # sampling точек поверхностей
  export.py         # запись PLY и metadata JSON
  geometry.py       # геометрические примитивы и deterministic helpers
  classes.py        # semantic class IDs и цвета
configs/
  mvp.yaml
  demo_*.yaml       # демонстрационные конфиги
outputs/
  .gitkeep          # директория вывода по умолчанию
tests/
  test_config.py
  test_determinism.py
  test_export.py
  test_roads_biomes_tiles.py
prompts/
  ...               # продуктовый и архитектурный контекст
pyproject.toml
uv.lock
```

## Установка

Требуется Python `>=3.11`.

Рекомендуемый вариант через `uv`:

```bash
uv sync
```

Альтернативный вариант через стандартный virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

После установки доступна CLI-команда `citygen`.

## Быстрый Старт

Сгенерировать базовый MVP-тайл:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
```

Эквивалентный запуск как Python-модуля:

```bash
uv run python -m citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
```

Если используешь локальное виртуальное окружение напрямую:

```bash
.venv/bin/citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
```

После успешного запуска будут созданы два файла:

```text
outputs/mvp_tile.ply
outputs/mvp_tile.metadata.json
```

Пример вывода CLI:

```text
Wrote <N> points to outputs/mvp_tile.ply
Wrote metadata to outputs/mvp_tile.metadata.json
```

Точное количество точек зависит от размера тайла, road/building spacing и настроек sampling.

## Использование CLI

```bash
citygen --config CONFIG_PATH [--out OUTPUT_PATH_OR_DIRECTORY]
```

Аргументы:

| Аргумент | Обязательный | Описание |
| --- | --- | --- |
| `--config` | да | Путь к YAML-конфигу генерации. |
| `--out` | нет | Путь к `.ply` файлу или директории вывода. |

Логика `--out`:

- если `--out` не указан, результат пишется в `outputs/tile_X_Z.ply`;
- если `--out` заканчивается на `.ply`, используется этот точный путь;
- если `--out` не заканчивается на `.ply`, он считается директорией, а файл называется `tile_X_Z.ply`;
- если в конфиге есть несколько тайлов через `tiles`, `--out` должен быть директорией или отсутствовать;
- multi-tile запуск пишет отдельный `tile_X_Z.ply` и `tile_X_Z.metadata.json` для каждого тайла;
- директория вывода создается автоматически;
- metadata всегда пишется рядом с PLY как `<name>.metadata.json`.

Примеры:

```bash
uv run citygen --config configs/mvp.yaml
uv run citygen --config configs/mvp.yaml --out outputs/custom_name.ply
uv run citygen --config configs/mvp.yaml --out outputs/demo_run
uv run citygen --config configs/demo_multi_tile.yaml --out outputs/multi_tile
```

## Демо-Конфиги

В `configs/` есть несколько конфигов, которые демонстрируют разные возможности текущей версии MVP.

| Конфиг | Что показывает |
| --- | --- |
| `configs/mvp.yaml` | Базовый MVP-сценарий: дороги, тротуары, рельеф, здания, RGB и class labels. |
| `configs/demo_dense_downtown.yaml` | Плотный downtown: частая сетка дорог, высокие здания, плотный sampling. |
| `configs/demo_lowrise_suburb.yaml` | Пригород: крупные кварталы, большие отступы, низкая застройка, умеренный рельеф. |
| `configs/demo_roads_and_sidewalks.yaml` | Здания выключены. Удобно для проверки классов `ground`, `road`, `sidewalk`. |
| `configs/demo_terrain_relief.yaml` | Заметный рельеф, поднятая базовая высота, смещенный тайл, увеличенный margin. |
| `configs/demo_export_geometry_only.yaml` | PLY только с `x`, `y`, `z`, без RGB и class fields. |
| `configs/demo_sparse_fast_preview.yaml` | Большой тайл с грубым sampling для быстрого preview. |
| `configs/demo_radial_ring.yaml` | Радиально-кольцевая система: лучи от центра и кольцевые дороги. |
| `configs/demo_radial.yaml` | Лучевая система без колец. |
| `configs/demo_linear.yaml` | Линейная структура города с основной осью и редкими поперечными улицами. |
| `configs/demo_organic.yaml` | Органические wavy streets, зависящие от рельефа. |
| `configs/demo_mixed_biomes.yaml` | `mixed` road model, urban fields и несколько биомов в одном тайле. |
| `configs/demo_building_footprints.yaml` | Несколько типов building footprint в одном тайле. |
| `configs/demo_courtyard_blocks.yaml` | Периметральные здания с внутренними дворами. |
| `configs/demo_building_roofs.yaml` | Все поддержанные типы roof geometry в одном тайле. |
| `configs/demo_pitched_roofs.yaml` | Скатные крыши: shed, gable, hip, half-hip, pyramid, mansard. |
| `configs/demo_curved_roofs.yaml` | Купольные, арочные и конические крыши. |
| `configs/demo_multi_tile.yaml` | Генерация четырех соседних тайлов одним запуском. |

Запуск всех демо-конфигов вручную:

```bash
uv run citygen --config configs/demo_dense_downtown.yaml --out outputs/demo_dense_downtown.ply
uv run citygen --config configs/demo_lowrise_suburb.yaml --out outputs/demo_lowrise_suburb.ply
uv run citygen --config configs/demo_roads_and_sidewalks.yaml --out outputs/demo_roads_and_sidewalks.ply
uv run citygen --config configs/demo_terrain_relief.yaml --out outputs/demo_terrain_relief.ply
uv run citygen --config configs/demo_export_geometry_only.yaml --out outputs/demo_export_geometry_only.ply
uv run citygen --config configs/demo_sparse_fast_preview.yaml --out outputs/demo_sparse_fast_preview.ply
uv run citygen --config configs/demo_radial_ring.yaml --out outputs/demo_radial_ring.ply
uv run citygen --config configs/demo_radial.yaml --out outputs/demo_radial.ply
uv run citygen --config configs/demo_linear.yaml --out outputs/demo_linear.ply
uv run citygen --config configs/demo_organic.yaml --out outputs/demo_organic.ply
uv run citygen --config configs/demo_mixed_biomes.yaml --out outputs/demo_mixed_biomes.ply
uv run citygen --config configs/demo_building_footprints.yaml --out outputs/demo_building_footprints.ply
uv run citygen --config configs/demo_courtyard_blocks.yaml --out outputs/demo_courtyard_blocks.ply
uv run citygen --config configs/demo_building_roofs.yaml --out outputs/demo_building_roofs.ply
uv run citygen --config configs/demo_pitched_roofs.yaml --out outputs/demo_pitched_roofs.ply
uv run citygen --config configs/demo_curved_roofs.yaml --out outputs/demo_curved_roofs.ply
uv run citygen --config configs/demo_multi_tile.yaml --out outputs/multi_tile
```

## Формат Конфига

Конфиг — это YAML mapping. Обязательное поле только одно: `seed`. Остальные секции имеют значения по умолчанию.

Минимальный валидный конфиг:

```yaml
seed: 7
```

Полный базовый пример:

```yaml
seed: 42
tile:
  x: 0
  z: 0
  size_m: 256
  margin_m: 32
terrain:
  base_height_m: 0
  height_noise_m: 1.5
roads:
  model: grid
  spacing_m: 64
  width_m: 10
  sidewalk_width_m: 3
  angle_degrees: 0
  radial_count: 12
  ring_spacing_m: 0
  organic_wander_m: 0
urban_fields:
  enabled: false
  center_x: 0
  center_z: 0
  city_radius_m: 1200
  noise_scale_m: 350
  density_bias: 0.0
  industrial_bias: 0.0
  green_bias: 0.0
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
sampling:
  mode: surface
  ground_spacing_m: 2.0
  road_spacing_m: 1.5
  building_spacing_m: 2.0
  jitter_ratio: 0.18
output:
  format: ply
  include_rgb: true
  include_class: true
```

### `seed`

```yaml
seed: 42
```

Управляет детерминированной генерацией. Один и тот же конфиг с одним и тем же seed дает одинаковую сцену и одинаковые первые точки. Изменение seed влияет на размещение зданий, размеры footprint, высоты зданий, фазу рельефа и jitter.

### `tile`

```yaml
tile:
  x: 0
  z: 0
  size_m: 256
  margin_m: 32
```

| Поле | Значение по умолчанию | Описание |
| --- | --- | --- |
| `x` | `0` | Целочисленная координата тайла по X. |
| `z` | `0` | Целочисленная координата тайла по Z. |
| `size_m` | `256.0` | Размер тайла в метрах. |
| `margin_m` | `32.0` | Дополнительная зона генерации вокруг тайла. После sampling точки crop-ятся обратно в bbox тайла. |

Итоговый bbox тайла:

```text
min_x = tile.x * tile.size_m
min_z = tile.z * tile.size_m
max_x = min_x + tile.size_m
max_z = min_z + tile.size_m
```

`margin_m` нужен, чтобы здания рядом с границей тайла могли корректно попадать в обрезанный результат, а не исчезали слишком резко на краю.

### `tiles`

`tile` описывает один тайл. Для batch generation можно использовать `tiles`.

```yaml
tiles:
  items:
    - {x: 0, z: 0}
    - {x: 1, z: 0}
  size_m: 256
  margin_m: 48
```

Также поддерживается half-open range:

```yaml
tiles:
  x_range: [0, 2]
  z_range: [0, 2]
  size_m: 256
  margin_m: 48
```

`x_range: [0, 2]` означает тайлы `0` и `1`, по аналогии с Python `range(0, 2)`. Multi-tile конфиг нужно запускать с `--out` директорией:

```bash
uv run citygen --config configs/demo_multi_tile.yaml --out outputs/multi_tile
```

### `terrain`

```yaml
terrain:
  base_height_m: 0
  height_noise_m: 1.5
```

| Поле | Значение по умолчанию | Описание |
| --- | --- | --- |
| `base_height_m` | `0.0` | Базовая высота рельефа. |
| `height_noise_m` | `1.5` | Амплитуда процедурного шума высоты. `0` дает плоскую поверхность. |

Высота рельефа детерминирована и зависит от seed, координат `x/z` и настроек terrain.

### `urban_fields`

```yaml
urban_fields:
  enabled: true
  center_x: 128
  center_z: 128
  city_radius_m: 500
  noise_scale_m: 180
  density_bias: 0.0
  industrial_bias: 0.0
  green_bias: 0.0
```

Urban fields вычисляются в мировых координатах и задают плавные поля:

- `centrality`: близость к городскому центру;
- `density`: плотность застройки;
- `height_potential`: потенциал высотности;
- `green_index`: открытость/озелененность;
- `industrialness`: промышленный характер района;
- `orderliness`: регулярность планировки.

Когда `enabled: false`, используется нейтральный residential-like режим для обратной совместимости. Когда `enabled: true`, поля влияют на biome selection, высоты зданий, вероятность зданий, footprint scale и `mixed` road model.

Поддерживаемые биомы:

| Биом | Эффект |
| --- | --- |
| `downtown` | Более высокая плотность и высотность, `radial_ring` как preferred road model. |
| `residential` | Средняя плотность, нейтральные здания, `grid` как preferred road model. |
| `industrial` | Крупнее footprints, ниже высотность, `linear` как preferred road model. |
| `suburb` | Ниже здания, реже застройка, `organic` как preferred road model. |

### `roads`

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

| Поле | Значение по умолчанию | Описание |
| --- | --- | --- |
| `model` | `grid` | Модель дорог: `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free`. |
| `spacing_m` | `64.0` | Расстояние между осями параллельных дорог. |
| `width_m` | `10.0` | Ширина проезжей части. |
| `sidewalk_width_m` | `3.0` | Ширина тротуара с каждой стороны дороги. |
| `angle_degrees` | `0.0` | Поворот для `linear`, `radial`, `radial_ring`. |
| `radial_count` | `12` | Количество лучей для radial models. |
| `ring_spacing_m` | `0.0` | Шаг кольцевых дорог для `radial_ring`; `0` означает использовать `spacing_m`. |
| `organic_wander_m` | `0.0` | Амплитуда изгиба organic roads; `0` включает auto-значение. |

Road model кратко:

- `grid`: регулярная сетка.
- `radial_ring`: лучи от центра плюс кольцевые дороги.
- `radial`: лучи от центра без колец.
- `linear`: улицы вдоль главной оси и более редкие поперечные улицы.
- `organic`: wavy polylines; изгиб зависит от `terrain.height_noise_m` и `organic_wander_m`.
- `mixed`: выбирает preferred road model по биому в каждой точке.
- `free`: хаотичная сеть из детерминированных сегментов между локальными узлами.

Валидатор требует:

```text
roads.width_m + 2 * roads.sidewalk_width_m < roads.spacing_m
```

Иначе дороги и тротуары занимают весь квартал, и для земли/зданий не остается корректного пространства.

### `buildings`

```yaml
buildings:
  enabled: true
  min_height_m: 8
  max_height_m: 60
  setback_m: 6
  footprint_min_m: 12
  footprint_max_m: 36
  footprint:
    model: rectangle
  roof:
    model: flat
```

| Поле | Значение по умолчанию | Описание |
| --- | --- | --- |
| `enabled` | `true` | Включает или выключает генерацию зданий. |
| `min_height_m` | `8.0` | Минимальная высота здания. |
| `max_height_m` | `60.0` | Максимальная высота здания. |
| `setback_m` | `6.0` | Отступ от защищенной зоны дороги и тротуара. |
| `footprint_min_m` | `12.0` | Минимальный размер footprint по ширине/глубине. |
| `footprint_max_m` | `36.0` | Максимальный размер footprint по ширине/глубине. |
| `footprint.model` | `rectangle` | Тип контура здания: `rectangle`, `square`, `circle`, `slab`, `courtyard`, `l_shape`, `u_shape`, `t_shape`, `mixed`. |
| `roof.model` | `flat` | Тип крыши: `flat`, `shed`, `gable`, `hip`, `half_hip`, `pyramid`, `mansard`, `dome`, `barrel`, `cone`, `mixed`. |

Здания размещаются по детерминированным candidate centers и отбрасываются, если footprint попадает в road/sidewalk clearance или пересекается с другим зданием. Каждое здание имеет:

- footprint выбранного типа;
- base height по рельефу в центре footprint;
- крышу;
- фасады по реальной границе footprint, включая внутренний двор у `courtyard`.

Для `footprint.model: mixed` тип выбирается по `footprint.weights`. Подробный справочник по форме зданий находится в `doc/building_footprints.md`.

Для `roof.model: mixed` тип крыши выбирается по `roof.weights`. Подробный справочник по крышам находится в `doc/building_roofs.md`.

Валидатор требует:

```text
buildings.max_height_m >= buildings.min_height_m
buildings.footprint_max_m >= buildings.footprint_min_m
```

Если здания не появляются, чаще всего не хватает buildable area между дорогами. Увеличь `roads.spacing_m` или уменьши `roads.width_m`, `roads.sidewalk_width_m`, `buildings.setback_m`, `buildings.footprint_min_m`.

### `sampling`

```yaml
sampling:
  mode: surface
  ground_spacing_m: 2.0
  road_spacing_m: 1.5
  building_spacing_m: 2.0
  jitter_ratio: 0.18
```

| Поле | Значение по умолчанию | Описание |
| --- | --- | --- |
| `mode` | `surface` | Режим sampling. В MVP поддерживается только `surface`. |
| `ground_spacing_m` | `2.0` | Примерный шаг точек земли. Чем больше значение, тем меньше точек. |
| `road_spacing_m` | `1.5` | Примерный шаг точек дорог и тротуаров. |
| `building_spacing_m` | `2.0` | Примерный шаг точек крыш и фасадов. |
| `jitter_ratio` | `0.18` | Случайное смещение как доля spacing. Допустимый диапазон: `0` .. `0.45`. |

Практические ориентиры:

- для быстрого preview увеличивай spacing;
- для плотного облака уменьшай spacing;
- `jitter_ratio: 0` дает регулярную сетку;
- высокий jitter делает точки менее регулярными, но слишком большой jitter запрещен валидатором.

### `output`

```yaml
output:
  format: ply
  include_rgb: true
  include_class: true
```

| Поле | Значение по умолчанию | Описание |
| --- | --- | --- |
| `format` | `ply` | Формат вывода. В MVP поддерживается только `ply`. |
| `include_rgb` | `true` | Добавляет поля `red`, `green`, `blue` в PLY. |
| `include_class` | `true` | Добавляет поле `class` в PLY. |

Если `include_rgb: true` и `include_class: true`, каждая строка вершины содержит:

```text
x y z red green blue class
```

Если оба поля отключены:

```text
x y z
```

## Выходные Файлы

### PLY

PLY записывается в ASCII-формате:

```text
ply
format ascii 1.0
comment generated by citygen
element vertex <point_count>
property float x
property float y
property float z
...
end_header
```

Координаты:

- `x`: горизонтальная координата в метрах;
- `y`: высота в метрах;
- `z`: горизонтальная координата в метрах.

Опциональные поля:

- `red`, `green`, `blue`: RGB-цвет semantic class;
- `class`: integer ID semantic class.

### Metadata JSON

Для каждого `.ply` рядом создается `.metadata.json`:

```text
outputs/mvp_tile.ply
outputs/mvp_tile.metadata.json
```

Metadata содержит:

- `seed`;
- координаты тайла;
- bbox тайла;
- `point_count`;
- `class_counts`;
- `class_mapping`;
- `road_models`;
- `biome_counts`;
- `building_counts` с распределением по footprint type и биомам;
- `supported_footprint_types`;
- `building_counts.by_roof` с распределением зданий по roof type;
- `supported_roof_types`;
- полный resolved config с defaults.

Перед открытием большого PLY удобно сначала посмотреть metadata и проверить, что классы и количество точек выглядят ожидаемо.

## Просмотр Результатов

Сгенерированные `.ply` можно открыть в инструментах, которые поддерживают ASCII PLY:

- CloudCompare;
- MeshLab;
- Open3D;
- PyntCloud;
- другие point cloud / mesh viewers.

Для быстрой проверки без viewer открой `.metadata.json` и посмотри `point_count` и `class_counts`.

## Тесты

Запуск тестов через `uv`:

```bash
uv run python -m unittest discover -s tests
```

Запуск через локальное виртуальное окружение:

```bash
.venv/bin/python -m unittest discover -s tests
```

Текущие тесты проверяют:

- загрузку конфига и обязательное поле `seed`;
- детерминизм при одинаковом seed;
- отличие результата при разном seed;
- запись PLY;
- запись metadata JSON;
- поддержку новых road models;
- ошибку для неизвестного `roads.model`;
- mixed-biome metadata;
- запись нескольких тайлов из одного конфига.

## Типовые Сценарии

### Плотный Downtown

```bash
uv run citygen --config configs/demo_dense_downtown.yaml --out outputs/downtown.ply
```

Подходит для проверки плотной застройки, высоких зданий, фасадов и крыш.

### Быстрый Preview

```bash
uv run citygen --config configs/demo_sparse_fast_preview.yaml --out outputs/preview.ply
```

Подходит для быстрой генерации крупного тайла с небольшим количеством точек.

### Только Дороги, Тротуары И Земля

```bash
uv run citygen --config configs/demo_roads_and_sidewalks.yaml --out outputs/roads_only.ply
```

Полезно для проверки road/sidewalk classification без влияния building classes.

### Только XYZ Геометрия

```bash
uv run citygen --config configs/demo_export_geometry_only.yaml --out outputs/xyz_only.ply
```

Полезно для потребителей данных, которым нужен только набор координат без цветов и классов.

### Радиально-Кольцевой Центр

```bash
uv run citygen --config configs/demo_radial_ring.yaml --out outputs/radial_ring.ply
```

Полезно для проверки лучей, кольцевых дорог и более центральной downtown-структуры.

### Mixed Biomes

```bash
uv run citygen --config configs/demo_mixed_biomes.yaml --out outputs/mixed_biomes.ply
```

Полезно для проверки `urban_fields`, распределения `biome_counts` и переключения road model по биомам.

### Mixed Building Footprints

```bash
uv run citygen --config configs/demo_building_footprints.yaml --out outputs/building_footprints.ply
```

Полезно для проверки `rectangle`, `circle`, `slab`, `courtyard`, `l_shape`, `u_shape`, `t_shape` и metadata `building_counts.by_footprint`.

### Courtyard Blocks

```bash
uv run citygen --config configs/demo_courtyard_blocks.yaml --out outputs/courtyard_blocks.ply
```

Полезно для проверки периметральной застройки: крыши не семплируются во внутреннем дворе, а фасады идут по внешнему и внутреннему контуру.

### Building Roofs

```bash
uv run citygen --config configs/demo_building_roofs.yaml --out outputs/building_roofs.ply
```

Полезно для проверки всех roof types и metadata `building_counts.by_roof`.

### Pitched Roofs

```bash
uv run citygen --config configs/demo_pitched_roofs.yaml --out outputs/pitched_roofs.ply
```

Полезно для проверки односкатных, двускатных, вальмовых, полувальмовых, шатровых и мансардных крыш.

### Curved Roofs

```bash
uv run citygen --config configs/demo_curved_roofs.yaml --out outputs/curved_roofs.ply
```

Полезно для проверки купольных, арочных и конических крыш.

### Multi-Tile

```bash
uv run citygen --config configs/demo_multi_tile.yaml --out outputs/multi_tile
```

Создает несколько соседних тайлов в одной директории.

## Troubleshooting

### `citygen: config error: Missing required field: seed`

В конфиге обязательно должно быть top-level поле:

```yaml
seed: 42
```

### `Unsupported roads.model='...'`

Проверь, что `roads.model` входит в список:

```yaml
roads:
  model: grid  # grid, radial_ring, radial, linear, organic, mixed, free
```

### `Only sampling.mode='surface' is supported in the MVP.`

Сейчас поддерживается только:

```yaml
sampling:
  mode: surface
```

### `Only output.format='ply' is supported in the MVP.`

Сейчас поддерживается только:

```yaml
output:
  format: ply
```

### `Road width plus sidewalks must be smaller than road spacing.`

У дорог и тротуаров слишком большая суммарная ширина относительно расстояния между дорогами.

Исправления:

- увеличь `roads.spacing_m`;
- уменьши `roads.width_m`;
- уменьши `roads.sidewalk_width_m`.

### Генерация Медленная Или Слишком Много Точек

Увеличь spacing:

```yaml
sampling:
  ground_spacing_m: 4
  road_spacing_m: 3
  building_spacing_m: 4
```

Также можно уменьшить:

```yaml
tile:
  size_m: 128
```

### Нет Точек Зданий

Проверь, что здания включены:

```yaml
buildings:
  enabled: true
```

Если здания включены, но не появляются, возможно, в кварталах мало места. Попробуй:

- увеличить `roads.spacing_m`;
- уменьшить `roads.width_m`;
- уменьшить `roads.sidewalk_width_m`;
- уменьшить `buildings.setback_m`;
- уменьшить `buildings.footprint_min_m`.

## Как Работает Пайплайн

Высокоуровневый flow:

```text
YAML config
  -> load_config()
  -> build_road_network()
  -> sample_urban_fields() / classify_biome()
  -> generate_scene()
  -> sample_scene()
  -> write_ply()
  -> write_metadata()
```

Основные этапы:

1. `load_config()` читает YAML, применяет defaults и валидирует значения.
2. `build_road_network()` создает road primitives для выбранной модели дорог.
3. `sample_urban_fields()` и `classify_biome()` вычисляют поля и биомы в мировых координатах.
4. `generate_scene()` строит bbox тайла, work bbox с margin и список зданий.
5. `sample_scene()` генерирует точки земли, дорог, тротуаров, крыш и фасадов.
6. Точки crop-ятся по bbox тайла.
7. `write_ply()` записывает ASCII PLY с нужным набором свойств.
8. `write_metadata()` пишет JSON-описание результата.

Генерация специально сделана детерминированной: случайность получается из стабильных hash-based seed parts. Это позволяет воспроизводить одинаковые результаты при повторном запуске с тем же конфигом.

## Идеи Для Следующих Версий

Логичные следующие шаги развития проекта:

- добавить полноценный топологический road graph и parcel subdivision;
- добавить больше semantic classes;
- добавить деревья, машины, столбы, фонари, ЛЭП;
- добавить LAS/LAZ экспорт;
- добавить настоящую LiDAR-симуляцию;
- добавить intensity / return number / scan angle;
- добавить CRS/georeferencing metadata;
- расширить тесты на новые config fields;
- держать демо-конфиги в `configs/` синхронизированными с возможностями MVP.
