# Справочник по контурам зданий (footprints)

Footprint здания — это контур здания на земле в координатах `x/y`. В `citygen` footprint определяет:

- где появляются roof-точки;
- где проходят facade-точки;
- как здание проверяется на близость к дорогам и тротуарам;
- как здание учитывается в metadata.

Высота здания, рельеф, semantic classes и RGB остаются прежними: новые формы меняют именно план здания, а не декоративную детализацию фасада.

Значения YAML по умолчанию и правила валидации описаны в `doc/configuration_reference.md`. Геометрия крыш описана отдельно в `doc/building_roofs.md`; размещение по parcels и oriented buildable areas — в `doc/parcels.md`.

## YAML

Секция находится внутри `buildings`:

```yaml
buildings:
  enabled: true
  footprint_min_m: 18
  footprint_max_m: 40
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
```

Если `buildings.footprint` отсутствует, используется `model: rectangle`, поэтому старые конфиги остаются совместимыми.

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `model` | `rectangle` | Тип footprint или `mixed`. |
| `weights` | `{}` или стандартная смесь для `mixed` | Веса выбора конкретного типа при `model: mixed`. |
| `circle_segments` | `24` | Количество сегментов кругового фасада. |
| `courtyard_ratio` | `0.45` | Размер внутреннего двора относительно внешнего блока. |
| `wing_width_ratio` | `0.35` | Относительная ширина крыла у L/U/T форм. |
| `min_part_width_m` | `5.0` | Минимальная ширина крыла или периметральной части. |
| `align_to_roads` | `true` | Зарезервировано для дальнейшей ориентации slab-форм по дорогам. В parcel mode orientation приходит от parcel geometry. |

## Поддерживаемые типы

| Тип | Характер |
| --- | --- |
| `rectangle` | Базовый прямоугольник. |
| `square` | Квадратная компактная форма. |
| `circle` | Круговая форма, например ротонда. |
| `slab` | Вытянутая пластина или галерейный дом. |
| `courtyard` | Замкнутый периметр с внутренним двором. |
| `l_shape` | Г-образная форма из двух крыльев. |
| `u_shape` | П-образная форма с полузакрытым двором. |
| `t_shape` | Т-образная форма из главного и поперечного крыла. |
| `mixed` | Выбор формы по `weights`. |

Alias-значения:

| Alias | Каноническое значение |
| --- | --- |
| `rotunda` | `circle` |
| `perimeter` | `courtyard` |
| `strip` | `slab` |
| `plate` | `slab` |
| `g_shape` | `l_shape` |
| `p_shape` | `u_shape` |

## Как строится геометрия

В текущем MVP формы реализованы без тяжелых GIS-зависимостей:

- `rectangle`, `square`, `slab` — один прямоугольник в local-space footprint;
- `circle` — круг с фасадом, аппроксимированным регулярной ломаной;
- `courtyard` — внешний прямоугольник плюс прямоугольная пустота;
- `l_shape`, `u_shape`, `t_shape` — union-of-rectangles без фасадов на внутренних стыках.

Для составных форм граница вычисляется по занятым ячейкам, поэтому фасады появляются по внешнему контуру, а не на местах склейки крыльев.

## Семплирование

Семплирование roof:

- использует `sampling.building_spacing_m`;
- проверяет `footprint.contains_xy(x, y)`;
- для `circle` точки попадают внутрь круга;
- для `courtyard` внутренний двор остается пустым;
- для L/U/T формы точки попадают только в занятые крылья.

Семплирование facade:

- идет по `footprint.boundary_segments()`;
- у `courtyard` включает внешний и внутренний контур;
- у L/U/T форм не включает внутренние стыки крыльев;
- вертикальный шаг также управляется `sampling.building_spacing_m`.

## Дорожный clearance и пересечения

Каждый footprint проверяется перед принятием здания:

- bbox должен пересекать рабочую область тайла;
- при `parcels.enabled: true` representative points должны лежать внутри buildable area parcel;
- representative points по bbox, частям и границе должны быть вне effective road hardscape corridor с учетом building setback;
- пересечения зданий фильтруются консервативно по expanded bbox.

Эта модель быстрее и проще полноценного polygon collision. Она может отбрасывать некоторые допустимые здания, но не должна ставить очевидные здания на дороги или тротуары.

Parcel mode использует прямоугольную MVP-аппроксимацию кварталов и участков поверх текущих road primitives. Footprints строятся вокруг центра oriented buildable area и затем получают world-space transform: при `parcels.building_alignment: parcel` локальные оси здания параллельны локальным осям parcel. Если включены `parcels.oriented_blocks`, эта orientation приходит от local-space subdivision повернутого block. Подробно этот слой описан в `doc/parcels.md`.

## Формы

### `rectangle`

Базовая форма и режим обратной совместимости.

Подходит для:

- базовых сцен;
- residential;
- dense downtown;
- быстрых тестов.

### `square`

Квадратная компактная форма.

Подходит для:

- башен;
- компактных городских объемов;
- регулярной сетки кварталов.

### `circle`

Круговая форма, полезная для ротонд, павильонов и башен с круглым планом.

Важные параметры:

- `circle_segments` управляет гладкостью фасада;
- больше сегментов дают более гладкий круг и больше facade-точек.

### `slab`

Вытянутая форма, где одна сторона заметно длиннее другой.

Подходит для:

- галерейных домов;
- складских корпусов;
- застройки вдоль магистралей;
- industrial и linear-сцен.

### `courtyard`

Периметральная форма с пустым внутренним двором.

Особенности:

- roof-точки не появляются во дворе;
- facade-точки появляются по внешнему и внутреннему контуру;
- если footprint слишком мал для заданного `courtyard_ratio` и `min_part_width_m`, генератор возвращается к `rectangle`.

### `l_shape`

Г-образная форма из двух крыльев.

Подходит для:

- угловой застройки;
- небольших квартальных объектов;
- смешанных residential/downtown сцен.

### `u_shape`

П-образная форма с полузакрытым двором.

Подходит для:

- институциональной застройки;
- кампусов;
- кварталов с открытым двором.

Открытая сторона выбирается детерминированно.

### `t_shape`

Т-образная форма из главного и поперечного крыла.

Подходит для:

- общественных зданий;
- кампусных корпусов;
- industrial и mixed-use объектов.

## Метаданные

Metadata содержит агрегаты по зданиям:

```json
{
  "building_counts": {
    "total": 13,
    "by_footprint": {
      "courtyard": 3,
      "rectangle": 4,
      "slab": 3
    },
    "by_biome": {
      "downtown": 2,
      "residential": 9
    },
    "by_footprint_and_biome": {
      "courtyard": {
        "residential": 3
      }
    }
  },
  "supported_footprint_types": [
    "rectangle",
    "square",
    "circle",
    "slab",
    "courtyard",
    "l_shape",
    "u_shape",
    "t_shape"
  ]
}
```

Это удобно проверять после запуска demo-конфигов.

## Демо

Смешанные формы, parcels и roofs в одном большом showcase:

```bash
uv run citygen --config configs/demo_universal_showcase.yaml --out outputs/demo_universal_showcase.ply
```

Смешанные формы на oriented parcels:

```bash
uv run citygen --config configs/demo_oriented_parcels.yaml --out outputs/demo_oriented_parcels.ply
```

Более легкое parcel demo с несколькими типами footprints:

```bash
uv run citygen --config configs/demo_parcels.yaml --out outputs/demo_parcels.ply
```
