# Справочник по дорогам

`roads` описывает процедурную дорожную сеть, surface-классы для дорог/тротуаров и опциональные road profiles. Все расчеты идут в горизонтальной плоскости `x/y`; высота остается осью `z` и добавляется позже на этапе семплирования.

Это MVP-слой дорог, построенный на простых road primitives и классификации по расстоянию. Он не является GIS-графом дорог, не хранит перекрестки как топологические узлы и не делает polygon clipping дорожных коридоров.

Смежные документы:

- `doc/configuration_reference.md` — YAML-поля, значения по умолчанию и правила валидации;
- `doc/biomes.md` — как биомы выбирают предпочтительную модель дорог и веса road profiles;
- `doc/parcels.md` — как roads ограничивают buildable parcels и задают orientation context;
- `doc/generated_objects.md` — какие road feature ids и semantic classes попадают в catalogs/metadata.

## YAML

Минимальная секция:

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

Если секция отсутствует, используется `grid` с совместимыми значениями по умолчанию.

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `model` | `grid` | Модель дорожной сети: `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free`. |
| `spacing_m` | `64.0` | Основной шаг между дорогами, кольцами или локальными узлами. |
| `width_m` | `10.0` | Ширина проезжей части для совместимого profile по умолчанию. |
| `sidewalk_width_m` | `3.0` | Ширина тротуара с каждой стороны для совместимого profile по умолчанию. |
| `angle_degrees` | `0.0` | Базовый угол для `linear`, `radial`, `radial_ring`, частей `mixed` и oriented parcel blocks. Геометрия `grid` дорог остается axis-aligned. |
| `radial_count` | `12` | Количество лучей для `radial` и `radial_ring`; должно быть `>= 3`. |
| `ring_spacing_m` | `0.0` | Шаг колец для `radial_ring`; `0` означает использовать `spacing_m`. |
| `organic_wander_m` | `0.0` | Амплитуда изгиба дорог модели `organic`; `0` включает авторасчет от `spacing_m` и `terrain.height_noise_m`. |
| `profiles` | выключено | Опциональные profile-aware ширины проезжей части, тротуаров и median. |

Валидатор требует:

```text
roads.width_m + 2 * roads.sidewalk_width_m < roads.spacing_m
```

При включенных road profiles дополнительно проверяется, что максимальная ширина corridor меньше `roads.spacing_m`.

## Модели дорог

| Модель | Что строит | Основные параметры |
| --- | --- | --- |
| `grid` | Ортогональная регулярная сеть infinite lines по глобальным X/Y. | `spacing_m`, `width_m`, `sidewalk_width_m`. |
| `radial_ring` | Лучи от центра плюс концентрические кольца. | `radial_count`, `angle_degrees`, `spacing_m`, `ring_spacing_m`. |
| `radial` | Только лучи от центра, без колец. | `radial_count`, `angle_degrees`, `spacing_m`. |
| `linear` | Параллельные дороги вдоль главной оси и более редкие поперечные дороги. | `angle_degrees`, `spacing_m`. |
| `organic` | Волнистые polyline-дороги в двух направлениях. | `spacing_m`, `organic_wander_m`, `terrain.height_noise_m`, `seed`. |
| `mixed` | Одновременно строит `grid`, `radial_ring`, `linear`, `organic`, а при запросе выбирает network по биому. | `urban_fields`, предпочтительная модель дорог биома. |
| `free` | Нерегулярные segment-дороги между детерминированно смещенными локальными узлами. | `spacing_m`, `seed`. |

Центр для `radial` и `radial_ring` берется из `urban_fields.center_x/center_y`, если `urban_fields.enabled: true`; иначе используется центр рабочего bbox.

`mixed` не выбирает `radial` и `free` как предпочтительные модели биомов. Текущий набор mixed-подсетей: `grid`, `linear`, `organic`, `radial_ring`.

## Дорожные primitives

В коде дорожная сеть хранится как набор простых primitives:

| Primitive | Геометрия | Типичные модели |
| --- | --- | --- |
| `InfiniteLinePrimitive` | Бесконечная линия с точкой и направлением. | `grid`, `linear`. |
| `SegmentPrimitive` | Отрезок между двумя точками. | `radial`, `radial_ring`, `free`. |
| `RingPrimitive` | Окружность вокруг центра. | `radial_ring`. |
| `PolylinePrimitive` | Ломаная из нескольких точек. | `organic`. |

Каждая primitive оборачивается в `RoadPrimitiveInstance`, где хранится:

- `model`;
- стабильный `index`;
- `profile_name`;
- разрешенный `profile`;
- biome в anchor-точке primitive.

Все проверки surface вызывают `distance_to(x, y)` в world-space `x/y`.

## Классы поверхностей

Для каждой семплированной ground-точки вызывается `RoadNetwork.surface_kind(config, x, y)`. Результат:

| Surface kind | Semantic class | Когда выбирается |
| --- | --- | --- |
| `road_median` | class id `6` | Точка попала в центральный median profile. |
| `road` | class id `2` | Точка попала в carriageway. |
| `sidewalk` | class id `3` | Точка попала в sidewalk band. |
| `ground` | class id `1` | Точка вне hardscape corridor. |

Без `roads.profiles.enabled` используется profile по умолчанию из `roads.width_m` и `roads.sidewalk_width_m`.

С profile-aware дорогами поперечное сечение считается так:

```text
median_half        = median_width_m / 2
road_outer_half    = median_half + carriageway_width_m / 2
sidewalk_outer_half = road_outer_half + sidewalk_width_m
```

Классификация по расстоянию до primitive:

```text
distance <= median_half          -> road_median
distance <= road_outer_half      -> road
distance <= sidewalk_outer_half  -> sidewalk
otherwise                        -> ground
```

Если несколько primitives одновременно покрывают точку, выбирается детерминированное попадание с приоритетом: `road` выше `road_median`, `road_median` выше `sidewalk`. Пересечение двух median-like попаданий намеренно приводится к `road`, чтобы перекрестки boulevard не превращались в широкие median-пятна.

## Дорожные профили

Дорожные профили позволяют разным road primitives иметь разные ширины:

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

| Поле | Описание |
| --- | --- |
| `enabled` | Включает ширины из road profiles. |
| `default` | Profile для запасного выбора; должен существовать в `definitions`. |
| `definitions` | Описания profiles: `carriageway_width_m`, `sidewalk_width_m`, `median_width_m`. |
| `model_weights` | Веса выбора profile по модели дорог. |
| `biome_weights` | Веса выбора profile по биому. |

Если одновременно заданы `model_weights` и `biome_weights`, генератор сначала пробует пересечение весов, перемножая значения. Если пересечение пустое, использует сумму доступных весов. Если весов нет, выбирается `default`.

Выбор profile детерминирован: RNG seed включает глобальный `seed`, координаты тайла, модель дорог, index primitive, biome и stable primitive key.

## Смешанные дороги и биомы

При `roads.model: mixed` строятся несколько подсетей, но в каждой точке используется только сеть предпочтительной модели для текущего биома:

| Биом | Предпочтительная модель дорог |
| --- | --- |
| `downtown` | `radial_ring` |
| `residential` | `grid` |
| `industrial` | `linear` |
| `suburb` | `organic` |

Если `urban_fields.enabled: false`, классификация biome всегда близка к `residential`, поэтому mixed roads фактически используют поведение `grid` в каждой точке.

## Взаимодействие с parcels и зданиями

Parcels и buildings используют дорожный слой как hardscape-ограничение:

- `nearest_distance(x, y)` дает расстояние до ближайшей оси или кривой road primitive;
- `nearest_hardscape_distance(x, y)` вычитает half-width effective corridor;
- parcel buildability проверяет center, corners, edge midpoints и interior sample points oriented buildable area;
- building placement проверяет representative footprint points через `nearest_hardscape_distance`;
- при `parcels.oriented_blocks: true` block orientation может брать road context через `parcels.block_orientation_source: road_model`.

Важно: `roads.angle_degrees` не поворачивает geometry `grid` road network, но может быть использован как base orientation для oriented parcels. Для фактически повернутых параллельных дорог используй `roads.model: linear`.

## Метаданные

Metadata содержит дорожные агрегаты:

```json
{
  "road_models": ["grid", "linear", "organic", "radial_ring"],
  "road_profile_counts": {
    "arterial": 16,
    "boulevard": 8,
    "collector": 10,
    "local": 22
  },
  "road_profile_counts_by_biome": {
    "downtown": {
      "arterial": 3,
      "boulevard": 6
    }
  },
  "road_widths": {
    "min_carriageway_width_m": 7.0,
    "max_carriageway_width_m": 16.0,
    "max_median_width_m": 6.0,
    "max_total_corridor_width_m": 30.0
  },
  "road_median": {
    "enabled": true,
    "profiles": ["arterial", "boulevard"]
  }
}
```

`class_counts` дополнительно показывает, сколько семплированных точек попало в `road`, `sidewalk` и `road_median`.

## Полезные демо-конфиги

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_roads.ply
uv run citygen --config configs/demo_road_profiles.yaml --out outputs/demo_road_profiles.ply
uv run citygen --config configs/demo_universal_showcase.yaml --out outputs/demo_universal_showcase.ply
uv run citygen --config configs/demo_oriented_parcels.yaml --out outputs/demo_oriented_parcels.ply
```

Полезные проверки metadata:

```bash
jq '{road_models, road_profile_counts, road_widths, road_median, class_counts}' outputs/demo_road_profiles.metadata.json
jq '{road_models, block_geometry, parcel_geometry}' outputs/demo_oriented_parcels.metadata.json
```

## Ограничения MVP

- Нет топологического road graph, lane graph, junction graph и turn restrictions.
- Нет CRS/georeferencing, speed limits, lane counts или semantic road names.
- Нет точного polygon clipping дорожных коридоров.
- Road profiles задают только width bands, а не подробную геометрию curb/marking.
- `mixed` выбирает сеть по biome в query point, а не смешивает primitives через настоящую boundary topology.
- Organic roads являются deterministic polylines, но не гарантируют связность как транспортная сеть.
- Road clearance для parcels/buildings остается консервативной проверкой sample points.
