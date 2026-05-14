# Деревья

Слой `trees` добавляет опциональные generated objects: одиночные деревья с цилиндрическим стволом и аналитической кроной. По умолчанию слой выключен, поэтому старые YAML-конфиги и PLY-outputs не получают новых объектов, пока явно не задано `trees.enabled: true`.

Источник истины по реализации:

- `citygen/trees.py` — размещение, dataclass `Tree`, sampling ствола/кроны и пересечения LiDAR-лучей;
- `citygen/config.py` — секция `TreesConfig`, defaults и строгая валидация `trees`;
- `citygen/generator.py` — отдельная стадия pipeline `trees` между `objects`/`fences` и `sampling`;
- `citygen/sampling.py` — добавление точек `tree_trunk` и `tree_crown`;
- `citygen/mobile_lidar.py` — попадания лучей в стволы и кроны;
- `citygen/export.py` — `tree_counts`, class mapping и `object_feature_counts`.

Координатная конвенция та же, что в проекте: горизонтальная плоскость `x/y`, высота `z`. Основание дерева ставится на `terrain_height(seed, terrain, x, y)`.

## Конфигурация

Минимальное включение:

```yaml
trees:
  enabled: true
```

Практический пример:

```yaml
trees:
  enabled: true
  density_per_ha: 28
  min_spacing_m: 7
  height_m: 7.5
  height_jitter_m: 1.8
  trunk_radius_m: 0.18
  trunk_height_ratio: 0.42
  crown_shape: mixed
  crown_radius_m: 2.5
  crown_height_ratio: 0.62
  crown_segments: 12
  weights:
    round: 0.28
    ellipsoid: 0.22
    cone: 0.20
    columnar: 0.12
    umbrella: 0.18
  biome_density_multipliers:
    downtown: 0.12
    residential: 0.80
    industrial: 0.0
    suburb: 1.75
  road_clearance_m: 3
  building_clearance_m: 2.5
  fence_clearance_m: 1
  tile_margin_clearance_m: 1.5
  sample_spacing_m: 1.8
```

Основные параметры:

| Параметр | По умолчанию | Смысл |
| --- | --- | --- |
| `enabled` | `false` | Включает слой деревьев. |
| `density_per_ha` | `18.0` | Базовая плотность кандидатов на гектар до biome multiplier. |
| `min_spacing_m` | `8.0` | Минимальная дистанция между принятыми деревьями. |
| `height_m`, `height_jitter_m` | `7.0`, `1.5` | Базовая высота и детерминированное отклонение. |
| `trunk_radius_m` | `0.18` | Радиус цилиндрического ствола. |
| `trunk_height_ratio` | `0.42` | Доля высоты дерева, занятая стволом. |
| `crown_shape` | `mixed` | Форма кроны или mixed selector. |
| `crown_radius_m` | `2.4` | Базовый радиус кроны в плане. |
| `crown_height_ratio` | `0.58` | Доля высоты дерева, занятая кроной. |
| `crown_segments` | `12` | Минимальная угловая детализация sampling кроны. |
| `weights` | built-in mix | Веса форм при `crown_shape: mixed`. |
| `biome_density_multipliers` | built-in multipliers | Множители плотности по биомам; `0` полностью запрещает деревья в биоме. |
| `road_clearance_m` | `3.0` | Минимальный отступ от road/sidewalk/median. |
| `building_clearance_m` | `2.0` | Отступ от footprints зданий. |
| `fence_clearance_m` | `1.0` | Отступ от fence segments и foundations. |
| `tile_margin_clearance_m` | `1.0` | Отступ от границы crop bbox тайла. |
| `allow_road_medians` | `false` | Разрешает посадку на `road_median`; по умолчанию medians запрещены. |
| `sample_spacing_m` | `1.0` | Шаг точек ствола и кроны. |

Секция `trees` валидируется строго: неизвестное поле вызывает `ConfigError` с перечнем поддержанных ключей. Плотности, размеры, spacing и clearances должны быть неотрицательными или положительными по смыслу поля; неизвестные формы крон и биомы в multipliers также запрещены.

## Формы крон

Поддержанные формы:

| Форма | Геометрия sampling | Типичный вид |
| --- | --- | --- |
| `round` | эллипсоид с равными радиусами | округлая лиственная крона |
| `ellipsoid` | вытянутый эллипсоид | овальная крона |
| `cone` | коническая поверхность | хвойная крона |
| `columnar` | узкий вертикальный эллипсоид | колонновидная посадка |
| `umbrella` | широкий приплюснутый эллипсоид | зонтичная крона |

Aliases нормализуются при загрузке YAML:

| Alias | Каноническая форма |
| --- | --- |
| `sphere`, `spherical` | `round` |
| `oval` | `ellipsoid` |
| `conical`, `evergreen` | `cone` |
| `narrow`, `poplar` | `columnar` |
| `wide`, `canopy` | `umbrella` |

При `crown_shape: mixed` форма выбирается детерминированно через `weights`. Если `weights` не заданы, используется встроенная смесь: `round`, `ellipsoid`, `cone`, `columnar`, `umbrella`.

## Размещение

Деревья размещаются отдельной стадией `trees` после зданий, parcels и fences. Алгоритм строит deterministic candidate grid по плотности, затем для каждой точки проверяет:

- точка лежит внутри crop bbox тайла с учетом `tile_margin_clearance_m`;
- текущий surface kind равен `ground`;
- точка не попадает на `road`, `sidewalk` или `road_median`, если `allow_road_medians: false`;
- расстояние до hardscape больше `road_clearance_m`;
- точка не лежит внутри footprint здания и находится дальше `building_clearance_m`;
- точка не ближе `fence_clearance_m` к fence segment;
- расстояние до уже принятых деревьев не меньше `min_spacing_m`;
- biome multiplier для найденного биома больше нуля.

Все случайные решения берут namespace от `seed`, координат тайла, индексов candidate grid и локального id дерева. Один и тот же config дает одинаковые деревья, их формы и surface points.

## Биомы

Плотность вычисляется как:

```text
effective_density = trees.density_per_ha * trees.biome_density_multipliers[biome]
```

Значения по умолчанию делают пригород самым зеленым, жилую ткань умеренно зеленой, центр редким, а industrial почти без деревьев:

| Биом | Multiplier по умолчанию |
| --- | --- |
| `suburb` | `1.25` |
| `residential` | `0.75` |
| `downtown` | `0.15` |
| `industrial` | `0.05` |

Можно явно поставить `0`, например для `industrial`, чтобы полностью запретить деревья в этом биоме.

## Sampling

Surface sampling добавляет два semantic class:

| Class id | Имя | RGB | Источник |
| --- | --- | --- | --- |
| `9` | `tree_trunk` | `111, 78, 46` | цилиндрическая поверхность ствола |
| `10` | `tree_crown` | `54, 128, 70` | поверхность кроны |

`trees.sample_spacing_m` управляет плотностью точек деревьев отдельно от `sampling.ground_spacing_m`, `sampling.road_spacing_m` и `sampling.building_spacing_m`. Чтобы большие тайлы не взрывали число точек, defaults держат умеренную плотность деревьев и шаг sampling `1.0` м; для быстрых previews лучше поднимать `sample_spacing_m` до `1.5..2.5`.

## Mobile LiDAR

Mobile LiDAR учитывает деревья вместе с terrain, roads, buildings и fences:

- ствол трассируется как цилиндр;
- крона трассируется как эллипсоидная аппроксимация формы;
- при `occlusions_enabled: true` ближайшее попадание может быть `tree_trunk` или `tree_crown` и закрывать объекты за деревом;
- при `occlusions_enabled: false` сохраняется существующее поведение дальнего пересечения.

Ограничение MVP: для `cone` LiDAR использует эллипсоидную аппроксимацию конической кроны, а не точное аналитическое пересечение с конусом. Surface sampling при этом остается коническим.

## Metadata

Metadata получает:

- `tree_counts.total`;
- `tree_counts.by_crown_shape`;
- `tree_counts.by_biome`;
- `tree_counts.average_height_m`, `min_height_m`, `max_height_m`;
- `tree_counts.trunk_points`, `crown_points`;
- `supported_tree_crown_shapes`;
- `class_mapping.tree_trunk`, `class_mapping.tree_crown`;
- `class_colors.tree_trunk`, `class_colors.tree_crown`;
- `class_counts.tree_trunk`, `class_counts.tree_crown`;
- `object_feature_counts.tree`, `object_feature_counts.tree_trunk`, `object_feature_counts.tree_crown`;
- resolved `config.trees` после defaults.

Пример проверки:

```bash
jq '{tree_counts, class_counts, object_feature_counts, supported_tree_crown_shapes}' outputs/demo_trees.metadata.json
```

## Demo

Запуск демонстрационного конфига:

```bash
uv run citygen --config configs/demo_trees.yaml --out outputs/demo_trees.ply
```

`configs/demo_trees.yaml` включает mixed формы крон, разные biome multipliers, легкий рельеф, road profiles, parcels и здания. Это быстрый сценарий для проверки, что деревья стоят только на естественном грунте и добавляют точки `tree_trunk`/`tree_crown`.
