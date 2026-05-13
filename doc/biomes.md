# Справочник по биомам citygen

Этот документ описывает биомы, которые используются в `citygen` для процедурного выбора характера района. Биом влияет на вероятность появления зданий, размеры footprints, высотность, отступы от дорог, road profiles и, при `roads.model: mixed`, на предпочитаемую модель дорожной сети.

Параметры биомов теперь описаны в едином catalog layer: `citygen/catalogs.py`, `BiomeDefinition`. Старые функции `classify_biome()`, `biome_params()` и `preferred_road_model_for_biome()` сохранены как совместимые фасады.

YAML-поля `urban_fields` описаны в `doc/configuration_reference.md`. Дорожная часть подробнее описана в `doc/roads.md`, а связь биомов с generated object ids — в `doc/generated_objects.md`.

Текущая версия поддерживает четыре биома:

| Биом | Теги | Краткое назначение | Предпочтительная модель дорог | Предпочтения road profiles |
| --- | --- | --- | --- | --- |
| `downtown` | `central`, `dense`, `highrise` | плотный центральный район с высокой застройкой | `radial_ring` | `collector`, `arterial`, `boulevard` |
| `residential` | `urban`, `regular`, `housing` | обычная городская жилая ткань | `grid` | `local`, `collector`, `arterial` |
| `industrial` | `industrial`, `large_footprints` | промышленная зона с крупными низкими объемами | `linear` | `collector`, `arterial`, `boulevard` |
| `suburb` | `suburban`, `green`, `lowrise` | пригородная и зеленая низкоплотная зона | `organic` | `local`, `collector` |

## Где используются биомы

Биомы включаются через секцию `urban_fields`. Если `urban_fields.enabled: false`, вся сцена считается `residential`.

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

Биом вычисляется в мировых координатах `x/y`. Поэтому соседние тайлы при одинаковом `seed` и согласованных `urban_fields` получают непрерывную картину районов.

Основные места применения:

- генерация зданий: `build_probability`, `footprint_scale`, `height_min_multiplier`, `height_max_multiplier`, `setback_scale`;
- дорожная сеть `mixed`: выбор road model по биому в каждой точке;
- road profiles: выбор ширины/типа дороги по biome-aware weights;
- generated objects: catalog хранит object weights для будущих placement stages;
- metadata: распределение биомов пишется в `biome_counts`;
- анализ сцены: биом помогает понять, почему в разных частях тайла различаются плотность, высотность и дороги.

## Городские поля (`urban_fields`)

Перед выбором биома citygen вычисляет набор плавных полей. Все поля clamp-ятся в диапазон `0..1`.

| Поле | Смысл | Основное влияние |
| --- | --- | --- |
| `centrality` | близость к центру города | downtown, height potential, порядок городской ткани |
| `density` | плотность городской ткани | downtown, suburb, шанс зданий, высотность |
| `height_potential` | потенциал высотности | множитель максимальной высоты при включенных urban fields |
| `green_index` | зеленость или открытость | suburb |
| `industrialness` | промышленный характер | industrial |
| `orderliness` | регулярность среды | сейчас вычисляется, но напрямую не меняет дороги или здания |

Если `urban_fields.enabled: false`, поля имеют фиксированные нейтральные значения:

| Поле | Значение |
| --- | --- |
| `centrality` | `0.5` |
| `density` | `0.5` |
| `height_potential` | `0.5` |
| `green_index` | `0.35` |
| `industrialness` | `0.12` |
| `orderliness` | `0.65` |

Такая комбинация всегда классифицируется как `residential`.

## Как выбирается биом

Классификация идет по порядку. Первое подходящее правило побеждает.

```text
if urban_fields.enabled == false:
    biome = residential
else if centrality >= 0.68 and density >= 0.58:
    biome = downtown
else if industrialness >= 0.58 and centrality <= 0.78:
    biome = industrial
else if density <= 0.38:
    biome = suburb
else if green_index >= 0.68 and centrality <= 0.55:
    biome = suburb
else:
    biome = residential
```

Важные особенности:

- `downtown` проверяется первым. Очень центральный и плотный район останется downtown даже при заметной industrialness.
- `industrial` проверяется раньше suburb. Промышленная зона может победить зеленость или низкую плотность, если выполняет свой порог.
- `residential` является запасным биомом.
- `suburb` появляется либо от низкой плотности, либо от высокой зелености вне центра.

## Общая таблица характеристик

| Биом | `build_probability` | `footprint_scale` | `height_min_multiplier` | `height_max_multiplier` | `setback_scale` | Предпочтительная модель дорог | Object weights |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `downtown` | `0.94` | `1.08` | `1.45` | `1.75` | `0.65` | `radial_ring` | `building`, `road_network`, `parcel_blocks` |
| `residential` | `0.78` | `0.92` | `0.85` | `0.82` | `1.00` | `grid` | `building`, `road_network`, `parcel_blocks` |
| `industrial` | `0.64` | `1.45` | `0.90` | `0.75` | `0.85` | `linear` | `building`, `road_network`, `parcel_blocks` |
| `suburb` | `0.38` | `0.72` | `0.55` | `0.45` | `1.45` | `organic` | `building`, `road_network`, `parcel_blocks` |

Пояснения к параметрам:

| Параметр | Что означает |
| --- | --- |
| `build_probability` | Базовая вероятность принять candidate-здание до проверки дорог, отступов и пересечений. |
| `footprint_scale` | Множитель для `buildings.footprint_min_m` и `buildings.footprint_max_m`. |
| `height_min_multiplier` | Множитель для `buildings.min_height_m`. |
| `height_max_multiplier` | Множитель для `buildings.max_height_m`. |
| `setback_scale` | Множитель для `buildings.setback_m`. |
| `preferred_road_model` | Модель дорог, которую использует `roads.model: mixed` в области этого биома. |

## Как биом меняет здания

Для каждого candidate-здания `citygen`:

1. Вычисляет биом в центре candidate.
2. Берет параметры биома.
3. Считает вероятность постройки.
4. Масштабирует footprint, высоту и setback.
5. Проверяет clearance от дорог и пересечение с другими зданиями.

Формулы:

```text
effective_probability = biome.build_probability

if urban_fields.enabled:
    effective_probability = min(
        0.97,
        biome.build_probability * (0.72 + density * 0.55)
    )

effective_setback = max(1.0, buildings.setback_m * biome.setback_scale)

effective_footprint_min = max(
    4.0,
    buildings.footprint_min_m * biome.footprint_scale
)

effective_footprint_max = max(
    effective_footprint_min,
    buildings.footprint_max_m * biome.footprint_scale
)

effective_min_height = buildings.min_height_m * biome.height_min_multiplier
effective_max_height = buildings.max_height_m * biome.height_max_multiplier

if urban_fields.enabled:
    effective_max_height *= 0.72 + height_potential * 0.72

effective_max_height = max(effective_min_height, effective_max_height)
```

Clearance от дороги в совместимом default-profile режиме:

```text
roads.width_m / 2 + roads.sidewalk_width_m + effective_setback
```

Если включены `roads.profiles`, используется effective hardscape width назначенного road profile; для зданий и parcels это проходит через `nearest_hardscape_distance(x, y)`.

Поэтому даже при высокой `build_probability` здание может не появиться, если квартал слишком узкий, footprint слишком крупный, дороги слишком широкие или setback слишком большой.

## Как биом меняет дороги

Биомы всегда могут влиять на выбор road profile, если включен `roads.profiles.enabled`. На выбор геометрической модели дороги биомы влияют только при:

```yaml
roads:
  model: mixed
```

В этом режиме заранее строятся четыре сети:

- `grid`;
- `radial_ring`;
- `linear`;
- `organic`.

При классификации каждой точки выбирается preferred road model текущего биома:

| Биом | Road model в `mixed` | Типичные road profiles |
| --- | --- | --- |
| `downtown` | `radial_ring` | `collector`, `arterial`, `boulevard`; широкий median встречается чаще |
| `residential` | `grid` | `local`, `collector`, иногда `arterial` |
| `industrial` | `linear` | широкие `collector`/`arterial`, иногда `boulevard` |
| `suburb` | `organic` | в основном `local`, иногда `collector` |

Если выбрать обычный `roads.model`, например `grid` или `organic`, биомы все равно будут влиять на здания и, при включенных `roads.profiles`, на ширину/тип road primitive. Но геометрическая модель сети переключаться не будет.

Road profile выбирается детерминированно по seed, road model, anchor-точке primitive и биому этой anchor-точки. Это MVP-подход поверх текущих road primitives: он дает стабильную ширину у каждой primitive и избегает мелкого мерцания ширины между соседними sample points.

При `parcels.oriented_blocks: true` биом через `roads.model: mixed` также может влиять на orientation квартала: `residential/grid` и `industrial/linear` используют `roads.angle_degrees`, `downtown/radial_ring` использует направление вокруг city center, а `suburb/organic` получает детерминированный jitter. Подробности — в `doc/parcels.md`.

## `downtown`

`downtown` представляет центральное ядро города: плотное, высотное, с высокой вероятностью застройки и меньшими отступами от дорог.

Условие выбора:

```text
centrality >= 0.68 and density >= 0.58
```

Характеристики:

| Характеристика | Значение | Эффект |
| --- | ---: | --- |
| `build_probability` | `0.94` | почти каждый подходящий candidate пытается стать зданием |
| `footprint_scale` | `1.08` | footprints немного крупнее базовых |
| `height_min_multiplier` | `1.45` | минимальные высоты заметно выше |
| `height_max_multiplier` | `1.75` | максимальные высоты сильно выше |
| `setback_scale` | `0.65` | здания ближе к улицам |
| preferred road model | `radial_ring` | лучи и кольца вокруг центра |

Визуально и структурно:

- высокая концентрация точек `building_roof` и `building_facade`;
- более высокие вертикальные объемы;
- меньше свободного пространства у дорог;
- хорошо сочетается с частыми улицами и небольшими кварталами;
- в `mixed` получает радиально-кольцевую структуру.

Полезные настройки:

```yaml
urban_fields:
  enabled: true
  center_x: 128
  center_y: 128
  city_radius_m: 400
  noise_scale_m: 160
  density_bias: 0.08
roads:
  model: mixed
  spacing_m: 54
  radial_count: 16
  ring_spacing_m: 58
buildings:
  min_height_m: 12
  max_height_m: 76
  setback_m: 5
```

## `residential`

`residential` представляет обычную городскую жилую ткань. Это основной запасной биом, который заполняет области без ярко выраженного центра, индустрии или пригорода.

Условие выбора:

```text
запасной вариант, если не подошли downtown, industrial и suburb
```

При `urban_fields.enabled: false` вся сцена всегда становится `residential`.

Характеристики:

| Характеристика | Значение | Эффект |
| --- | ---: | --- |
| `build_probability` | `0.78` | достаточно плотная, но не максимальная застройка |
| `footprint_scale` | `0.92` | footprints чуть меньше базовых |
| `height_min_multiplier` | `0.85` | минимальные высоты чуть ниже базовых |
| `height_max_multiplier` | `0.82` | максимальные высоты ниже базовых |
| `setback_scale` | `1.00` | базовые отступы без изменения |
| preferred road model | `grid` | регулярная сетка улиц |

Визуально и структурно:

- средняя плотность зданий;
- умеренная высотность;
- достаточно регулярная городская структура;
- хорошо подходит для базовых MVP-сцен;
- наиболее предсказуемый биом для тестов и базовых конфигов.

Полезные настройки:

```yaml
urban_fields:
  enabled: true
  center_x: 128
  center_y: 128
  city_radius_m: 700
  noise_scale_m: 240
roads:
  model: mixed
  spacing_m: 64
buildings:
  min_height_m: 8
  max_height_m: 48
  setback_m: 6
```

## `industrial`

`industrial` представляет промышленные и складские районы. Он дает более крупные footprints, меньшую высотность и линейную дорожную структуру в `mixed`.

Условие выбора:

```text
industrialness >= 0.58 and centrality <= 0.78
```

Характеристики:

| Характеристика | Значение | Эффект |
| --- | ---: | --- |
| `build_probability` | `0.64` | зданий меньше, чем в residential и downtown |
| `footprint_scale` | `1.45` | footprints значительно крупнее |
| `height_min_multiplier` | `0.90` | минимальные высоты немного ниже базовых |
| `height_max_multiplier` | `0.75` | максимальные высоты ниже базовых |
| `setback_scale` | `0.85` | отступы чуть меньше базовых |
| preferred road model | `linear` | вытянутая линейная структура |

Визуально и структурно:

- меньше зданий, но они крупнее в плане;
- высотность обычно ниже, чем в downtown;
- кварталы выглядят более складскими или производственными;
- в `mixed` дороги организуются вдоль основной оси с редкими поперечными улицами;
- чаще проявляется ближе к кольцевой зоне вокруг центра, потому что поле industrialness использует industrial ring.

Полезные настройки:

```yaml
urban_fields:
  enabled: true
  center_x: 160
  center_y: 160
  city_radius_m: 300
  noise_scale_m: 140
  industrial_bias: 0.12
roads:
  model: mixed
  spacing_m: 76
  angle_degrees: 18
buildings:
  footprint_min_m: 16
  footprint_max_m: 44
  max_height_m: 42
```

## `suburb`

`suburb` представляет пригородные, зеленые и низкоплотные зоны. Он снижает вероятность зданий, уменьшает footprints и высоты, но увеличивает отступы.

Условия выбора:

```text
density <= 0.38
```

или:

```text
green_index >= 0.68 and centrality <= 0.55
```

Характеристики:

| Характеристика | Значение | Эффект |
| --- | ---: | --- |
| `build_probability` | `0.38` | застройка редкая |
| `footprint_scale` | `0.72` | footprints меньше базовых |
| `height_min_multiplier` | `0.55` | минимальные высоты сильно ниже |
| `height_max_multiplier` | `0.45` | максимальные высоты сильно ниже |
| `setback_scale` | `1.45` | отступы заметно больше |
| preferred road model | `organic` | волнистые, менее регулярные улицы |

Визуально и структурно:

- низкая плотность зданий;
- низкая высотность;
- больше свободного пространства между дорогой и зданиями;
- органичные улицы в `mixed`;
- хорошо сочетается с более выраженным рельефом и крупными кварталами.

Полезные настройки:

```yaml
urban_fields:
  enabled: true
  center_x: 128
  center_y: 128
  city_radius_m: 460
  noise_scale_m: 180
  green_bias: 0.08
roads:
  model: mixed
  spacing_m: 72
  organic_wander_m: 18
buildings:
  min_height_m: 5
  max_height_m: 28
  setback_m: 10
```

## Настройка распределения биомов

Главные ручки управления находятся в `urban_fields`.

| Цель | Что изменить |
| --- | --- |
| Больше downtown | увеличить `density_bias`, расположить `center_x/center_y` внутри тайла, уменьшить или умеренно подобрать `city_radius_m` |
| Шире центральная зона | увеличить `city_radius_m` |
| Более резкие и мелкие пятна районов | уменьшить `noise_scale_m` |
| Более плавные и крупные районы | увеличить `noise_scale_m` |
| Больше industrial | увеличить `industrial_bias` |
| Больше suburb | увеличить `green_bias` или уменьшить `density_bias` |
| Меньше suburb | увеличить `density_bias` или уменьшить `green_bias` |
| Разнообразнее дороги в `mixed` | включить `urban_fields` и подобрать bias так, чтобы в metadata было несколько `biome_counts` |

## Диагностика через метаданные

После генерации рядом с PLY создается файл:

```text
outputs/example.metadata.json
```

В нем полезны поля:

| Поле | Что показывает |
| --- | --- |
| `biome_counts` | сколько sample-точек bbox попало в каждый биом |
| `road_models` | какие модели дорог использовала сцена |
| `road_profile_counts` | какие road profiles были назначены road primitives |
| `road_profile_counts_by_biome` | распределение road profiles по биомам anchor-точек |
| `road_widths` | минимальная/максимальная ширина проезжей части, median и полного коридора |
| `class_counts` | распределение point classes: ground, road, road_median, sidewalk, facades, roofs |
| `config` | итоговый конфиг после применения значений по умолчанию |

Пример:

```json
{
  "biome_counts": {
    "downtown": 12,
    "industrial": 18,
    "residential": 34,
    "suburb": 17
  },
  "road_models": ["grid", "linear", "organic", "radial_ring"]
}
```

Если `biome_counts` содержит только `residential`, проверь:

- включен ли `urban_fields.enabled`;
- находится ли `center_x/center_y` рядом с тайлом;
- не слишком ли большой или маленький `city_radius_m`;
- нужны ли `density_bias`, `industrial_bias` или `green_bias`;
- достаточно ли большой тайл, чтобы увидеть несколько зон.

## Связанные демо-конфиги

| Файл | Что полезно смотреть |
| --- | --- |
| `configs/demo_road_profiles.yaml` | mixed roads, urban fields, road profiles по биомам и `road_median` без зданий |
| `configs/demo_universal_showcase.yaml` | mixed roads, несколько биомов, parcels, mixed footprints и mixed roofs |
| `configs/demo_oriented_parcels.yaml` | mixed road context плюс oriented block/parcel subdivision |
| `configs/demo_parcel_alignment.yaml` | placement с учетом parcels на mixed roads и urban fields |
| `configs/mvp.yaml` | базовое поведение, близкое к `residential`, при выключенных `urban_fields` |
