# Транспорт

Слой `vehicles` добавляет в `citygen` опциональные generated objects: легковые автомобили, грузовики, автобусы, спецтехнику и тракторы/utility vehicles. Слой выключен по умолчанию (`vehicles.enabled: false`) и не меняет старые сцены, пока явно не включен.

Координатная конвенция та же, что во всем проекте: горизонтальная плоскость `x/y`, высота `z`. Базовая высота каждого транспортного средства берется через `terrain_height(seed, terrain, x, y)`.

## Pipeline

Транспорт строится отдельной стадией `vehicles` после `trees` и до `sampling`:

```text
roads -> parcels -> objects -> fences -> trees -> vehicles -> sampling
```

В `Scene` транспорт хранится отдельно от зданий, fences и trees. Surface sampling только превращает готовые `Vehicle` instances в точки; placement не скрыт внутри sampling.

## Типы транспорта

Catalog ids:

- `car` — легковой автомобиль, taxi/sedan-sized;
- `truck` — грузовик, фургон или delivery vehicle;
- `bus` — городской/пригородный автобус;
- `emergency` — пожарная, ambulance или служебная машина;
- `tractor` — трактор или utility vehicle.

Aliases нормализуются при загрузке YAML:

| Alias | Canonical |
| --- | --- |
| `sedan`, `hatchback`, `taxi` | `car` |
| `van`, `lorry`, `delivery` | `truck` |
| `coach` | `bus` |
| `firetruck`, `ambulance`, `service` | `emergency` |
| `utility`, `farm_tractor` | `tractor` |

Каждый catalog type задает габариты, радиус колеса, базовый цвет корпуса, допустимые placement modes и tags. При необходимости `vehicles.length_m`, `width_m`, `height_m`, `wheel_radius_m` могут глобально переопределить catalog defaults.

## Placement

Поддерживаемые режимы:

- `road` — транспорт на проезжей части road primitive;
- `parking` — стоящий транспорт внутри buildable parcels, только на `ground`;
- `industrial_yard` — двор/площадка industrial parcels для trucks, emergency и tractors;
- `mixed` — shorthand для всех режимов.

Road placement выбирает точки вдоль road primitives, проверяет ширину carriageway и ставит объект со смещением от оси/median. Orientation идет вдоль road primitive, с опциональным `orientation_jitter_degrees`.

Parking и industrial yard placement используют `Parcel.buildable_geometry`: это простая MVP-аппроксимация parking/yard surface внутри участка. Такой транспорт не ставится на произвольный natural ground вне parcel.

Транспорт запрещен:

- на `sidewalk`;
- на `road_median`, если `allow_road_medians: false`;
- внутри building footprint и building clearance;
- рядом с fences/foundations;
- рядом с деревьями;
- за пределами crop bbox тайла;
- на слишком узкой дороге.

## Биомы

Итоговая плотность умножается на `vehicles.biome_density_multipliers`. Значение `0` полностью отключает транспорт в биоме.

Defaults:

| Биом | Множитель | Характер |
| --- | --- | --- |
| `downtown` | `1.25` | больше road vehicles, buses и служебной техники |
| `residential` | `0.85` | средняя плотность легковых |
| `suburb` | `0.65` | меньше движения, больше parked/utility |
| `industrial` | `0.75` | больше trucks, emergency/utility и tractors |

При `vehicle_type: mixed` веса типов дополнительно корректируются по биому: downtown поднимает `bus`/`car`, industrial поднимает `truck`/`tractor`, suburb повышает utility-like vehicles. Явный вес `0` остается нулем.

## YAML

Минимальный пример:

```yaml
vehicles:
  enabled: true
  density_per_km: 30
  parking_density_per_ha: 20
  min_spacing_m: 7
  placement_modes: mixed
  vehicle_type: mixed
  sample_spacing_m: 1
```

Ключевые поля:

| Поле | Назначение |
| --- | --- |
| `density_per_km` | плотность road vehicles вдоль дорожных primitives |
| `parking_density_per_ha` | плотность стоящих машин на parcel parking/yard |
| `placement_modes` | `road`, `parking`, `industrial_yard` или `mixed` |
| `vehicle_type` | конкретный тип или `mixed` |
| `weights` | веса типов при `mixed` |
| `biome_density_multipliers` | множители плотности по биомам |
| `allowed_road_profiles` | whitelist profiles для road placement |
| `side_of_road` | `left`, `right` или `both` |
| `parked_ratio` | доля parking-кандидатов в industrial parcels, если включены и `parking`, и `industrial_yard` |
| `sample_spacing_m` | плотность точек транспорта |
| `max_points_per_vehicle` | cap, который защищает большие тайлы от слишком большого числа точек |

Полный список полей и строгие правила валидации описаны в `doc/configuration_reference.md`.

## Geometry and Sampling

MVP использует аналитические формы:

- корпус — oriented box в world-space;
- колеса — упрощенные диски/кольца на боковых сторонах;
- окна — patches на боках и торцах корпуса.

Surface sampling создает semantic classes:

| Class | Id | RGB | Что семплируется |
| --- | --- | --- | --- |
| `vehicle_body` | `11` | `52, 93, 142` | корпус |
| `vehicle_wheel` | `12` | `28, 30, 33` | колеса |
| `vehicle_window` | `13` | `98, 148, 172` | окна |

Существующие class ids не изменены.

## Mobile LiDAR

Mobile LiDAR учитывает транспорт вместе с terrain, roads, buildings, fences и trees. Корпус трассируется как oriented box obstacle; при включенных occlusions он может закрывать объекты позади.

Ограничение MVP: wheels/windows пока не являются отдельными LiDAR-примитивами. Луч возвращает `vehicle_body` для попадания в oriented box, а детализация колес и окон видна через surface sampling.

## Metadata

Metadata получает:

- `vehicle_counts.total`;
- `vehicle_counts.by_type`;
- `vehicle_counts.by_placement_mode`;
- `vehicle_counts.by_biome`;
- `vehicle_counts.dimensions_m`;
- `vehicle_counts.body_points`, `wheel_points`, `window_points`;
- `supported_vehicle_types`;
- `vehicle_catalog`;
- `vehicle_aliases`;
- `object_feature_counts.vehicle`;
- `object_feature_counts.vehicle_body`;
- `object_feature_counts.vehicle_wheel`;
- `object_feature_counts.vehicle_window`;
- resolved `config.vehicles`.

## Demo

Запуск:

```bash
uv run citygen --config configs/demo_vehicles.yaml --out outputs/demo_vehicles.ply
```

Демо включает road vehicles, parcel parking/yard placement, mixed vehicle types, trees, road profiles и additive mobile LiDAR; fences в нем выключены, чтобы не сжимать площадки для parked/yard vehicles.
