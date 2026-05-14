# Sampling pipeline

`sampling` превращает уже построенную сцену `Scene` в список точек `Point`, которые затем экспортируются в PLY и агрегируются в metadata. Это последняя runtime-стадия генерации перед `export_ply` и `export_metadata`.

Источник истины по реализации:

- `citygen/sampling.py` - surface sampling рельефа, дорог, зданий, деревьев, транспорта и объединение с mobile LiDAR;
- `citygen/fences.py` - sampling ограждений и фундаментов;
- `citygen/trees.py` - sampling стволов/крон и helper-ы для LiDAR-пересечений;
- `citygen/vehicles.py` - sampling корпуса/колес/окон и helper-ы для LiDAR-пересечений транспорта;
- `citygen/mobile_lidar.py` - ray sampling мобильного LiDAR;
- `citygen/export.py` - PLY-поля, metadata и диагностические агрегаты;
- `citygen/config.py` - значения по умолчанию и валидация параметров.

## Назначение

Вход `sampling`:

- resolved `CityGenConfig` после применения defaults и валидации;
- `Scene` из `generate_scene(config)`: bbox тайла, work bbox с margin, дорожная сеть, здания, parcels, fences, trees, vehicles, biome counts и worldgen context.

Выход `sampling`:

- `list[Point]`, где каждая точка имеет `x`, `y`, `z`, `red`, `green`, `blue`, `class_id`;
- точки уже обрезаны по bbox тайла, а не по расширенному `work_bbox`;
- semantic class и RGB назначаются из `POINT_CLASSES`;
- PLY-поля `red/green/blue` и `class` записываются только если включены `output.include_rgb` и `output.include_class`.

`sampling` не создает дорожную сеть, parcels, здания, fences, trees или vehicles. Эти объекты должны быть уже построены на предыдущих стадиях `roads`, `parcels`, `objects`, `fences`, `trees` и `vehicles`. На стадии sampling они только превращаются в точки.

## Порядок выполнения

Основная точка входа:

```python
sample_scene(config, scene)
```

Фактический порядок:

1. Surface sampling всегда выполняется первым через `_sample_surface_scene(config, scene)`.
2. Если `mobile_lidar.enabled: false`, результат surface sampling сразу возвращается.
3. Если `mobile_lidar.enabled: true`, дополнительно выполняется `sample_mobile_lidar(config, scene)`.
4. LiDAR-точки обрезаются по bbox тайла.
5. При `mobile_lidar.output_mode: lidar_only` возвращаются только LiDAR-точки.
6. При `mobile_lidar.output_mode: additive` surface-точки и LiDAR-точки объединяются и еще раз обрезаются по bbox тайла.

Surface sampling внутри `_sample_surface_scene` выполняется в таком порядке:

1. `_sample_tile_surfaces` - рельеф, дороги, тротуары и road medians.
2. `_sample_building` для каждого здания - крыши и фасады.
3. `sample_fence_segment` для каждого fence segment - тело ограждения и, если нужен, фундамент.
4. `sample_tree` для каждого дерева - ствол и крона.
5. `sample_vehicle` для каждого транспортного средства - корпус, колеса и окна.
6. `_crop_points(points, scene.bbox)` - финальная обрезка по границам тайла.

## Стадии surface sampling

| Стадия | Код | Вход | Выход | Основные параметры |
| --- | --- | --- | --- | --- |
| Подготовка сцены | `generate_scene`, `WorldgenContext` | `CityGenConfig` | `Scene` с `bbox` и `work_bbox` | `tile.size_m`, `tile.margin_m`, `roads`, `buildings`, `parcels`, `fences`, `trees`, `vehicles` |
| Tile surfaces | `_sample_tile_surfaces` | `scene.bbox`, `scene.road_network`, `scene.buildings` | `ground`, `road`, `sidewalk`, `road_median` points | `sampling.ground_spacing_m`, `sampling.road_spacing_m`, `sampling.jitter_ratio`, `terrain`, `roads`, `roads.profiles` |
| Roofs | `_sample_roof` | `Building.footprint`, `Building.roof` | `building_roof` points | `sampling.building_spacing_m`, `sampling.jitter_ratio`, `buildings.roof` |
| Facades | `_sample_facades` | `Building.footprint.boundary_segments`, `base_z`, `eave_z` | `building_facade` points | `sampling.building_spacing_m`, `sampling.jitter_ratio`, `buildings.*`, `buildings.footprint` |
| Fences | `sample_fence_segment` | `FenceSegment` | `fence`, `fence_foundation` points | `fences.sample_spacing_m`, `fences.height_m`, `fences.foundation_*`, `fences.openness`, `fences.decorative` |
| Trees | `sample_tree` | `Tree` | `tree_trunk`, `tree_crown` points | `trees.sample_spacing_m`, `trees.crown_shape`, `trees.crown_segments` |
| Vehicles | `sample_vehicle` | `Vehicle` | `vehicle_body`, `vehicle_wheel`, `vehicle_window` points | `vehicles.sample_spacing_m`, `vehicles.max_points_per_vehicle`, vehicle catalog dimensions |
| Mobile LiDAR | `sample_mobile_lidar` | `Scene`, ray trajectory | LiDAR points with normal semantic classes | `mobile_lidar.*` |
| Cropping | `_crop_points` | all generated points | points inside `scene.bbox` | `tile.x`, `tile.y`, `tile.size_m` |
| Export metadata | `write_metadata` | final points, config, scene | `*.metadata.json` | `output.*`, `mobile_lidar.*`, resolved config |

## Tile surfaces

Tile surfaces cover open ground, roads, sidewalks and road medians. The sampler builds a regular 2D grid over `scene.bbox` with:

```text
spacing = min(sampling.ground_spacing_m, sampling.road_spacing_m)
```

For each grid location:

1. Deterministic jitter is applied to `x/y` using `sampling.jitter_ratio`.
2. The point is clamped back into bbox.
3. The sample is skipped if it falls inside any building footprint.
4. `surface_kind(config, scene, x, y)` asks the road network for semantic surface:
   - `road`;
   - `road_median`;
   - `sidewalk`;
   - `ground`.
5. The desired spacing is selected:
   - `sampling.road_spacing_m` for `road`, `road_median`, `sidewalk`;
   - `sampling.ground_spacing_m` for `ground`.
6. If the base grid is denser than the desired spacing, points are deterministically thinned with keep probability `(spacing / wanted_spacing) ** 2`.
7. `z` is read from `terrain_height(seed, terrain, x, y)`.
8. RGB and class id come from `POINT_CLASSES[kind]`.

Important performance detail: because the base grid uses the smaller of ground and road spacing, a very small `road_spacing_m` makes the sampler scan the whole tile at that spacing, even though most non-road points will later be thinned.

## Buildings

Buildings are sampled only when they exist in `scene.buildings`. `buildings.enabled: false` means there are no roof or facade points.

For each building:

1. Buildings whose footprint does not intersect the tile bbox are skipped.
2. `sampling.building_spacing_m` is used for both roofs and facades.
3. The RNG namespace is stable: `seed + "building-sampling" + building.id`.
4. The roof sampler scans the footprint bbox, applies `sampling.jitter_ratio`, keeps only points inside the actual footprint, then asks the roof height function for `z`.
5. The facade sampler walks each footprint boundary segment, samples positions along the segment and vertical levels from `base_z` to `eave_z`.
6. Roof points get class `building_roof`; facade points get class `building_facade`.

Roof geometry is controlled by `buildings.roof`, not by `sampling`. `sampling.building_spacing_m` changes point density, while `roof.model`, `pitch_degrees`, `flat_slope_degrees`, `ridge_height_ratio`, `mansard_break_ratio` and similar fields change the surface being sampled.

## Fences

Fences are generated before sampling by `build_fences`. They appear only when:

```yaml
parcels:
  enabled: true
fences:
  enabled: true
  mode: perimeter   # or partial
```

Fence sampling is separate from `sampling.building_spacing_m`. It uses `fences.sample_spacing_m`.

For each fence segment:

- points are placed along the segment at `fences.sample_spacing_m`;
- vertical spacing is `max(0.25, fences.sample_spacing_m * 0.5)`;
- massive or explicitly configured foundations produce `fence_foundation` points;
- visible fence body points produce `fence` points;
- `openness`, fence style, posts, rails and decorative elements decide which fence-body points are visible;
- material-specific colors are varied deterministically by position, not by random RNG.

Fence placement itself respects parcels, road clearance, building conflicts, side selection and gate openings before sampling starts. Sampling does not move fence segments; it only turns accepted segments into points.

## Trees

Деревья генерируются до sampling на стадии `trees`. Surface sampling получает уже готовые `Tree` instances и не меняет их placement.

Для каждого дерева:

- основание `base_z` уже вычислено через `terrain_height` в точке посадки;
- ствол семплируется как цилиндр от `base_z` до `base_z + trunk_height_m`;
- крона семплируется по выбранной форме: `round`, `ellipsoid`, `cone`, `columnar` или `umbrella`;
- `trees.sample_spacing_m` задает шаг точек ствола и кроны;
- `trees.crown_segments` задает минимальную угловую детализацию кроны;
- точки ствола получают semantic class `tree_trunk`, точки кроны — `tree_crown`.

Размещение деревьев не происходит в sampling. Оно уже проверило natural ground, road/sidewalk/median clearance, footprints зданий, fences, границы тайла, biome density multipliers и `min_spacing_m`.

## Vehicles

Транспорт генерируется до sampling на стадии `vehicles`. Surface sampling получает готовые `Vehicle` instances и не меняет placement.

Для каждого транспортного средства:

- `base_z` уже вычислен через `terrain_height` в точке установки;
- корпус семплируется как oriented box в world-space;
- колеса семплируются как упрощенные диски/кольца;
- окна семплируются как patches на боках и торцах корпуса;
- `vehicles.sample_spacing_m` задает шаг точек;
- `vehicles.max_points_per_vehicle` ограничивает число точек на объект;
- точки получают semantic classes `vehicle_body`, `vehicle_wheel`, `vehicle_window`.

Размещение транспорта не происходит в sampling. Оно уже проверило road/parking/industrial_yard surface, road profiles, sidewalks/medians, здания, fences, trees, границы тайла, biome density multipliers, type weights и `min_spacing_m`.

## Mobile LiDAR mode

Mobile LiDAR is not a second value of `sampling.mode`. It is controlled by the separate `mobile_lidar` section, while `sampling.mode` must still be `surface`.

When enabled, `sample_mobile_lidar`:

1. Builds sensor positions from `mobile_lidar.trajectory`.
2. Computes horizontal offsets from `horizontal_fov_degrees` and `horizontal_step_degrees`.
3. Computes vertical angles from `vertical_center_degrees`, `vertical_fov_degrees` and `vertical_channels`.
4. Emits one ray for every position, horizontal offset and vertical channel.
5. Applies deterministic drop probability and optional angle jitter per ray.
6. Traces the ray against terrain, roads, sidewalks, medians, building facades, building roofs, trees, vehicles and, when occlusions are enabled, fences.
7. Keeps the nearest hit when `occlusions_enabled: true`.
8. Applies distance attenuation and optional range noise.
9. Assigns the semantic class of the hit surface.

LiDAR points do not receive a separate per-point source field. Source information is available as aggregate metadata in `point_sources`, and LiDAR ray statistics are written under `mobile_lidar`.

## Configuration parameters

### Direct `sampling` settings

| Параметр | Тип | По умолчанию | Допустимые значения | Влияние |
| --- | --- | --- | --- | --- |
| `sampling.mode` | string | `surface` | only `surface` | Единственный поддержанный режим MVP. Любое другое значение вызывает `ConfigError`. |
| `sampling.ground_spacing_m` | number | `2.0` | `> 0` | Целевой шаг точек `ground`. Больше значение уменьшает число ground-точек примерно квадратично. |
| `sampling.road_spacing_m` | number | `1.5` | `> 0` | Целевой шаг точек `road`, `sidewalk`, `road_median`. Больше значение уменьшает плотность hardscape-точек. |
| `sampling.building_spacing_m` | number | `2.0` | `> 0` | Шаг roof/facade sampling. Влияет на `building_roof` и `building_facade`. |
| `sampling.jitter_ratio` | number | `0.18` | `0..0.45` | Смещение sample как доля текущего spacing. `0` дает регулярную сетку; большие значения делают точки менее решетчатыми. |

Notes:

- в текущем коде секция `sampling` не имеет строгой проверки неизвестных ключей, поэтому опечатанные или лишние поля будут проигнорированы загрузчиком;
- `sampling` не содержит отдельного `enabled`;
- нет настроек `max_points`, `per_class_density`, `drop_probability` для surface sampling или явного point budget;
- отдельная плотность fence-точек находится в `fences.sample_spacing_m`;
- отдельная плотность tree-точек находится в `trees.sample_spacing_m`;
- отдельная плотность vehicle-точек находится в `vehicles.sample_spacing_m`, а cap - в `vehicles.max_points_per_vehicle`;
- настройки лучей LiDAR находятся в `mobile_lidar.*`.

### Related settings that affect sampled points

| Секция | Параметры | Как влияет на итоговое облако |
| --- | --- | --- |
| `tile` | `x`, `y`, `size_m`, `margin_m` | `size_m` задает финальную область crop. `margin_m` расширяет рабочую область генерации сцены, но итоговые точки обрезаются по bbox тайла. |
| `terrain` | `base_height_m`, `height_noise_m`, `mountains`, `hills`, `ravines` | Определяет `z` для ground/road/sidewalk/median, базу зданий, fence base и высоту сенсора LiDAR над землей. |
| `roads` | `model`, `spacing_m`, `width_m`, `sidewalk_width_m`, profiles | Меняет распределение surface classes. При profiles может появляться `road_median`. |
| `buildings` | `enabled`, height, footprints, roofs | Определяет, есть ли roof/facade точки, где стоят здания и какую высоту имеют roof surfaces. |
| `parcels` | `enabled`, parcel geometry | Косвенно меняет здания и является условием для fences. |
| `fences` | `enabled`, `mode`, `type`, `sample_spacing_m`, `height_m`, `foundation`, `openness` | Добавляет `fence` и `fence_foundation` points и влияет на LiDAR-окклюзии. |
| `trees` | `enabled`, `density_per_ha`, `biome_density_multipliers`, `crown_shape`, `sample_spacing_m`, clearances | Добавляет `tree_trunk` и `tree_crown` points и влияет на LiDAR-окклюзии. |
| `vehicles` | `enabled`, `density_per_km`, `parking_density_per_ha`, `vehicle_type`, `placement_modes`, `sample_spacing_m`, clearances | Добавляет `vehicle_body`, `vehicle_wheel`, `vehicle_window` points и влияет на LiDAR-окклюзии. |
| `mobile_lidar` | все поля секции | Добавляет ray-sampled точки или заменяет surface output при `output_mode: lidar_only`. |
| `output` | `include_rgb`, `include_class` | Не меняет внутренние точки, но меняет набор PLY-полей. |

## Режимы и их различия

| Режим | Как включить | Результат |
| --- | --- | --- |
| Surface only | `mobile_lidar.enabled: false` | Регулярно сэмплированные поверхности: ground, roads, sidewalks, medians, roofs, facades, fences, trees, vehicles. |
| Surface + LiDAR | `mobile_lidar.enabled: true`, `output_mode: additive` | Surface points плюс ray hits мобильного сенсора. |
| LiDAR only | `mobile_lidar.enabled: true`, `output_mode: lidar_only` | Только видимые с траектории ray hits; surface grid не попадает в итоговый PLY. |
| No-jitter surface | `sampling.jitter_ratio: 0` | Surface grid без случайного смещения. Если `ground_spacing_m != road_spacing_m`, thinning все равно остается детерминированным. |
| Deterministic test mode | фиксированный `seed`, `jitter_ratio: 0`, для LiDAR `angle_jitter_degrees: 0`, `range_noise_m: 0`, `drop_probability: 0`, `distance_attenuation: 0` | Удобно для тестов и golden outputs. Один и тот же конфиг дает одинаковые точки. |

## Примеры конфигураций

Минимальная конфигурация использует defaults:

```yaml
seed: 7
```

Высокая плотность surface points:

```yaml
seed: 7
sampling:
  mode: surface
  ground_spacing_m: 1.0
  road_spacing_m: 0.75
  building_spacing_m: 1.0
  jitter_ratio: 0.12
```

Быстрый preview с малым числом точек:

```yaml
seed: 7
tile:
  size_m: 128
buildings:
  enabled: false
sampling:
  ground_spacing_m: 8
  road_spacing_m: 6
  building_spacing_m: 8
  jitter_ratio: 0
```

Детерминированная surface-конфигурация без jitter и без thinning между ground/road:

```yaml
seed: 7
sampling:
  ground_spacing_m: 4
  road_spacing_m: 4
  building_spacing_m: 4
  jitter_ratio: 0
```

Разные плотности для земли, hardscape, зданий и ограждений:

```yaml
seed: 7
parcels:
  enabled: true
fences:
  enabled: true
  mode: perimeter
  type: mixed
  sample_spacing_m: 0.7
sampling:
  ground_spacing_m: 5
  road_spacing_m: 2
  building_spacing_m: 2.5
  jitter_ratio: 0.16
```

Деревья с отдельной плотностью точек:

```yaml
seed: 7
trees:
  enabled: true
  density_per_ha: 30
  crown_shape: mixed
  sample_spacing_m: 1.8
sampling:
  ground_spacing_m: 5
  road_spacing_m: 2
  building_spacing_m: 2.5
  jitter_ratio: 0.12
```

Mobile LiDAR в режиме `lidar_only`:

```yaml
seed: 7
mobile_lidar:
  enabled: true
  output_mode: lidar_only
  trajectory: line
  start_x: 0
  start_y: 0
  end_x: 256
  end_y: 0
  sensor_height_m: 2.2
  position_step_m: 8
  min_range_m: 1
  max_range_m: 90
  horizontal_fov_degrees: 180
  horizontal_step_degrees: 3
  vertical_fov_degrees: 50
  vertical_center_degrees: -8
  vertical_channels: 12
  angle_jitter_degrees: 0
  range_noise_m: 0
  drop_probability: 0
  distance_attenuation: 0
  occlusions_enabled: true
  ray_step_m: 1
sampling:
  mode: surface
  ground_spacing_m: 4
  road_spacing_m: 4
  building_spacing_m: 4
  jitter_ratio: 0
```

## Влияние настроек на результат

Количество точек обычно меняется примерно как площадь, деленная на квадрат spacing:

```text
tile surface points ~= tile area / spacing^2
```

Но есть важные уточнения:

- roads, sidewalks and medians используют `road_spacing_m`, ground использует `ground_spacing_m`;
- если один spacing меньше другого, базовый grid строится по меньшему spacing, а другой класс прореживается;
- buildings добавляют roof points по площади footprint и facade points по периметру и высоте;
- fences добавляют точки по длине сегментов и высоте;
- trees добавляют точки по высоте стволов и поверхности крон; число деревьев зависит от плотности, биомов и clearances;
- vehicles добавляют точки корпуса, колес и окон; число объектов зависит от road/parking density, биомов, road profiles, parcels и clearances;
- LiDAR добавляет максимум `sensor_positions * horizontal_steps * vertical_channels` лучей, но drop, misses, attenuation and occlusions уменьшают число итоговых точек;
- crop по bbox тайла может удалить точки, построенные в расширенной work area.

`sampling.jitter_ratio` меняет координаты surface points, но не должен заметно менять количество точек. `seed` влияет на jitter, thinning, buildings, fences, trees, vehicles, road details and LiDAR randomness. При одинаковом `seed` и одинаковом resolved config результат детерминирован.

Самые дорогие настройки:

- маленький `min(ground_spacing_m, road_spacing_m)` на большом `tile.size_m`;
- маленький `building_spacing_m` при большом количестве высоких зданий;
- маленький `fences.sample_spacing_m` при плотных parcels;
- маленький `trees.sample_spacing_m` при высокой `trees.density_per_ha`;
- маленький `vehicles.sample_spacing_m` при высокой `vehicles.density_per_km` или `parking_density_per_ha`;
- маленький `mobile_lidar.horizontal_step_degrees`, большой `vertical_channels`, маленький `position_step_m` и маленький `ray_step_m`.

## Semantic class и RGB

Surface и LiDAR используют один и тот же catalog semantic classes:

| Class id | Имя | RGB | Откуда появляется |
| --- | --- | --- | --- |
| `1` | `ground` | `107, 132, 85` | terrain outside hardscape and buildings |
| `2` | `road` | `47, 50, 54` | road carriageway |
| `3` | `sidewalk` | `174, 174, 166` | sidewalk corridor |
| `4` | `building_facade` | `176, 164, 148` | facade boundary sampling or LiDAR facade hit |
| `5` | `building_roof` | `112, 116, 122` | roof height function or LiDAR roof hit |
| `6` | `road_median` | `118, 128, 84` | road profile with `median_width_m > 0` |
| `7` | `fence` | `130, 101, 72` | fence body or LiDAR fence hit |
| `8` | `fence_foundation` | `118, 112, 103` | fence foundation or LiDAR foundation hit |
| `9` | `tree_trunk` | `111, 78, 46` | tree trunk surface or LiDAR trunk hit |
| `10` | `tree_crown` | `54, 128, 70` | tree crown surface or LiDAR crown hit |
| `11` | `vehicle_body` | `52, 93, 142` | vehicle body surface or LiDAR oriented-box hit |
| `12` | `vehicle_wheel` | `28, 30, 33` | vehicle wheel surface sampling |
| `13` | `vehicle_window` | `98, 148, 172` | vehicle window surface sampling |

PLY export may omit RGB or class fields, but metadata still contains `class_counts` and `class_mapping` because internal `Point` objects always carry color and class id.

## CLI progress during sampling

When generation is started through `citygen`, `sample_scene` receives a progress callback from the CLI. The callback is diagnostic only: it does not create RNG calls, does not change point order and does not write extra fields to PLY or metadata.

In an interactive terminal, the CLI uses `tqdm` progress bars for long `sampling` substages and writes them to `stderr`. This keeps normal summaries and `Wrote ...` lines on `stdout`, while still showing a live progress bar:

```text
tile 1/1 (x=0, y=0) sampling tile_surfaces: 100%|██████████| 171/171 row, pts=21263, ground=8409, hardscape=12854
tile 1/1 (x=0, y=0) sampling buildings: 100%|██████████| 8/8 building, pts=5221, roof=837, facade=4384
tile 1/1 (x=0, y=0) sampling trees: 100%|██████████| 58/58 tree, total_tree_points=3797, total_trunk_points=1680, total_crown_points=2117
tile 1/1 (x=0, y=0) sampling vehicles: 100%|██████████| 14/14 vehicle, total_vehicle_points=4200, total_body_points=2600, total_wheel_points=900, total_window_points=700
tile 1/1 (x=0, y=0) sampling mobile LiDAR rays: 100%|██████████| 17856/17856 ray, hits=14302, dropped=360, missed=2871, attenuated=323, pts=14302
```

When stdout or stderr is not a TTY, dynamic bars are disabled and the same structured events are rendered as stable lines suitable for logs and tests:

```text
citygen: tile 1/1 (x=0, y=0) sampling tile_surfaces started - grid_rows=129, grid_columns=129, grid_samples=16641, spacing_m=1.5
citygen: tile 1/1 (x=0, y=0) sampling tile_surfaces progress - rows=33, total_rows=129, grid_samples=4257, total_grid_samples=16641, points=3798, class_counts={ground=1875, road=1296, sidewalk=627}
citygen: tile 1/1 (x=0, y=0) sampling buildings done - buildings=24, points=5221, roof_points=837, facade_points=4384
citygen: tile 1/1 (x=0, y=0) sampling trees done - trees=58, points=3797, trunk_points=1680, crown_points=2117
citygen: tile 1/1 (x=0, y=0) sampling vehicles done - vehicles=14, points=4200, body_points=2600, wheel_points=900, window_points=700
citygen: tile 1/1 (x=0, y=0) sampling surface_total done - tile_surface_points=21263, building_points=5221, fence_points=0, cropped_tree_points=3797, cropped_vehicle_points=4200, surface_points_before_crop=34481, surface_points=34481
```

With `mobile_lidar.enabled: true`, the ray sampler is reported as a `sampling` substage while the CLI still keeps the high-level mobile LiDAR stage boundary:

```text
citygen: tile 1/1 (x=0, y=0) stage 9/11 mobile LiDAR started
citygen: tile 1/1 (x=0, y=0) sampling mobile LiDAR rays progress - positions=8, total_positions=31, processed_rays=4608, emitted_rays=4608, total_rays=17856, successful_hits=3721, dropped_rays=94, missed_rays=712, attenuated_rays=81, lidar_points=3721
citygen: tile 1/1 (x=0, y=0) sampling mobile LiDAR rays done - sensor_positions=31, processed_rays=17856, total_rays=17856, emitted_rays=17856, successful_hits=14302, dropped_rays=360, missed_rays=2871, attenuated_rays=323, lidar_points=14302
```

Progress substages:

| Substage | When it appears | Main counters |
| --- | --- | --- |
| `tile_surfaces` | Always during surface sampling | `grid_rows`, `grid_columns`, `grid_samples`, `rows`, `total_rows`, `points`, `ground_points`, `hardscape_points`, `road_points`, `sidewalk_points`, `road_median_points`, `class_counts` |
| `buildings` | Always, including the zero-buildings case | `buildings`, `points`, `roof_points`, `facade_points`; in `--verbose`, per-building `item_done` also includes `building_id`, `total_roof_points` and `total_facade_points` |
| `fences` | Only when generated fence segments exist | `fence_segments`, `points`, `fence_points`, `foundation_points`; in `--verbose`, per-segment `item_done` also includes `segment_id`, `total_fence_body_points` and `total_foundation_points` |
| `trees` | Only when generated trees exist | `trees`, `points`, `trunk_points`, `crown_points`; in `--verbose`, per-tree `item_done` also includes `tree_id`, `total_trunk_points` and `total_crown_points` |
| `vehicles` | Only when generated vehicles exist | `vehicles`, `points`, `body_points`, `wheel_points`, `window_points`; in `--verbose`, per-vehicle `item_done` also includes `vehicle_id`, `total_body_points`, `total_wheel_points` and `total_window_points` |
| `surface_total` | End of surface sampling before LiDAR merge | `tile_surface_points`, `building_points`, `fence_points`, `ground_points`, `hardscape_points`, `cropped_building_points`, `cropped_fence_points`, `cropped_tree_points`, `cropped_vehicle_points`, `surface_points_before_crop`, `surface_points`, `class_counts` |
| `mobile_lidar_rays` | Only when `mobile_lidar.enabled: true`; printed as `sampling mobile LiDAR rays` | `sensor_positions`, `processed_rays`, `emitted_rays`, `total_rays`, `successful_hits`, `dropped_rays`, `missed_rays`, `attenuated_rays`, `lidar_points` |

Verbosity rules:

- default interactive mode shows compact `tqdm` bars for `tile_surfaces`, `buildings`, `fences`, `trees`, `vehicles` and `mobile_lidar_rays`;
- default non-TTY mode prints compact started/progress/done lines for sampling substages;
- `--quiet` suppresses progress bars and intermediate progress lines, keeping only final `Wrote ...` paths;
- `--verbose` shows extra counters in tqdm postfixes and, in non-TTY mode, prints more detailed item-level diagnostics for buildings, fence segments, trees, vehicles and LiDAR sensor positions.

The `tqdm` dependency is used only by the CLI reporting layer. Sampling code emits structured progress events and remains usable from Python without CLI formatting.

## Metadata and diagnostics

After `write_metadata`, the JSON file contains several fields useful for sampling diagnostics:

| Metadata field | What to inspect |
| --- | --- |
| `point_count` | Total final points after crop and after LiDAR output mode is applied. |
| `class_counts` | Distribution by semantic class name. This is the main surface sampling sanity check. |
| `class_mapping` | Stable mapping from class names to class ids. |
| `class_colors` | Stable RGB palette for semantic classes. |
| `object_feature_counts` | Counts grouped by feature ids such as `terrain_surface`, `road_surface`, `road_sidewalk`, `road_median`, `building_roof`, `parcel_fence`, `fence_foundation`, `tree`, `tree_trunk`, `tree_crown`, `vehicle`, `vehicle_body`, `vehicle_wheel`, `vehicle_window`. |
| `tree_counts` | Total trees, counts by crown shape and biome, height stats, trunk/crown point counts. |
| `vehicle_counts` | Total vehicles, counts by type, placement mode and biome, dimension stats, body/wheel/window point counts. |
| `mobile_lidar` | Whether LiDAR was enabled, sensor positions, emitted rays, successful hits, dropped rays, misses, attenuated rays and hit counts by class. |
| `point_sources` | Aggregate split between `surface_sampling` and `mobile_lidar`, plus mode: `surface_only`, `additive` or `lidar_only`. |
| `config` | Full resolved config after defaults. Use this to confirm actual sampling and LiDAR parameters. |
| `worldgen.stages` | Contains the `sampling` stage in the worldgen pipeline list. |

Surface sampling currently does not write these progress counters into metadata. For persisted diagnostics, use `class_counts`, `object_feature_counts`, `point_sources.surface_sampling` and the resolved `config`; for per-stage runtime counters, use CLI progress output.

Note: `write_metadata` calls `sample_mobile_lidar(config, scene)` to build LiDAR metadata. The LiDAR sampler is deterministic, so this recomputation is expected to match the LiDAR points generated during `sample_scene` for the same config and scene.

## Validation and tests

Validation rules relevant to sampling:

- `sampling.mode` must be `surface`;
- `sampling.ground_spacing_m`, `sampling.road_spacing_m`, `sampling.building_spacing_m` must be positive;
- `sampling.jitter_ratio` must be between `0` and `0.45`;
- `mobile_lidar.output_mode` must be `additive` or `lidar_only`;
- `mobile_lidar.trajectory` must be `centerline`, `line` or `road`;
- `mobile_lidar.min_range_m < mobile_lidar.max_range_m`;
- LiDAR FOVs, probabilities and noise fields are range-checked in `config.py`;
- `fences.enabled` requires `parcels.enabled` because fence geometry comes from parcel boundaries;
- `trees.sample_spacing_m`, dimensions, density, crown shape, weights and biome multipliers are validated in `config.py`.

Existing tests that cover sampling behavior:

- `tests/test_determinism.py` checks same-seed reproducibility and different-seed changes;
- `tests/test_export.py` checks PLY headers and metadata point counts;
- `tests/test_mobile_lidar.py` checks disabled LiDAR compatibility, LiDAR point generation, occlusion behavior, LiDAR metadata and deterministic LiDAR output;
- `tests/test_fences.py` checks fence generation and sampled fence/foundation classes;
- `tests/test_trees.py` checks tree config behavior, natural-ground placement, biome multipliers, deterministic tree points, metadata and LiDAR hits;
- `tests/test_cli_progress.py` checks default, quiet and verbose progress output, sampling substage counters, LiDAR ray progress, multi-tile progress and unchanged deterministic PLY output;
- `tests/test_road_profiles.py` checks road medians and road profile class behavior;
- `tests/test_catalogs.py` checks worldgen stages and documentation coverage for catalog ids.

Useful manual checks:

```bash
uv run python -m unittest discover -s tests
uv run citygen --config configs/mvp.yaml --out outputs/mvp_check.ply
uv run citygen --config configs/demo_trees.yaml --out outputs/demo_trees.ply
uv run citygen --config configs/demo_universal_showcase.yaml --out outputs/demo_universal_showcase.ply
```

For quick metadata inspection:

```bash
jq '{point_count, class_counts, tree_counts, point_sources, mobile_lidar, sampling: .config.sampling}' outputs/demo_trees.metadata.json
```

## Current limitations

- `sampling.mode` has only one supported value: `surface`.
- There is no explicit point budget or max point limit.
- There is no generic per-semantic-class density table. Ground/hardscape/building/fence/LiDAR densities are controlled by separate existing parameters.
- Tree density and tree point density are controlled by `trees.density_per_ha` and `trees.sample_spacing_m`, not by the direct `sampling` section.
- Surface sampling does not store per-point source labels; source split exists only as aggregate metadata.
- Surface sampling has jitter but no independent coordinate noise model. LiDAR has separate angle jitter, range noise, drop probability and distance attenuation.
- Unknown keys in `sampling` are not rejected by the current loader, unlike stricter newer sections such as `fences`, `trees`, `mobile_lidar` and `worldgen`.
