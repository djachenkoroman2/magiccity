# Справочник по building roofs

Building roof — это процедурная форма верхней поверхности здания. В `citygen` крыша определяет:

- высоту `building_roof` точек;
- верхнюю границу фасада, или eave-line;
- распределение roof types в metadata;
- визуальный характер здания без перехода к полноценному mesh/CAD.

Footprint по-прежнему задает область на земле. Roof sampling никогда не должен выходить за footprint и не должен попадать во внутренний двор `courtyard`. Если footprint получил parcel orientation, roof height вычисляется в local-space footprint, а точки остаются в world-space `x/y/z`.

## YAML

Секция находится внутри `buildings`:

```yaml
buildings:
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

Если `buildings.roof` отсутствует, используется `model: flat`. При `flat_slope_degrees: 0` поведение совпадает со старой плоской крышей.

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `model` | `flat` | Тип крыши или `mixed`. |
| `weights` | `{}` или стандартная смесь для `mixed` | Веса выбора concrete roof type. |
| `pitch_degrees` | `28.0` | Базовый угол ската. |
| `pitch_jitter_degrees` | `8.0` | Детерминированное отклонение угла по зданию. |
| `flat_slope_degrees` | `0.0` | Малый уклон плоской крыши. |
| `eave_overhang_m` | `0.0` | Зарезервировано для будущего выноса карниза. |
| `ridge_height_ratio` | `0.35` | Максимальный rise крыши как доля высоты здания. |
| `mansard_break_ratio` | `0.45` | Положение перелома мансардной крыши. |
| `dome_segments` | `16` | Зарезервировано для детализации curved roofs. |
| `align_to_long_axis` | `true` | Ориентация ridge/arch относительно длинной оси footprint в local-space. |

## Поддерживаемые типы

| Тип | Характер |
| --- | --- |
| `flat` | Плоская крыша. |
| `shed` | Односкатная крыша. |
| `gable` | Двускатная крыша с коньком. |
| `hip` | Четырехскатная вальмовая крыша. |
| `half_hip` | Полувальмовая крыша. |
| `pyramid` | Шатровая крыша с вершиной в центре. |
| `mansard` | Ломаная мансардная крыша. |
| `dome` | Купольная крыша. |
| `barrel` | Арочная или сводчатая крыша. |
| `cone` | Коническая крыша. |
| `mixed` | Выбор roof type по `weights`. |

Alias-значения:

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

## Высота

`Building.height_m` остается общей высотой до максимальной точки крыши:

```text
base_z + height_m = max_roof_z
```

Для скатных и curved roofs вычисляется `eave_z`:

```text
eave_z = max_roof_z - roof_rise_m
```

Фасады семплируются до `eave_z`, крыша семплируется отдельно. Для `flat` без уклона `eave_z == max_roof_z`.

## Типы крыш

### `flat`

Плоская крыша. При `flat_slope_degrees: 0` все roof points лежат на `max_roof_z`. Если задать небольшой уклон, высота будет плавно меняться вдоль одной оси.

### `shed`

Односкатная крыша. Высота монотонно растет от одной стороны footprint local bbox к другой. Подходит для industrial и современных зданий.

### `gable`

Двускатная крыша. Высота максимальна вдоль конька и снижается к двум противоположным сторонам. Конек ориентируется по длинной оси footprint local bbox.

### `hip`

Вальмовая крыша. Все стороны наклонены, максимум находится около центра или короткого конька. Для квадратов приближается к `pyramid`.

### `half_hip`

Полувальмовая крыша. Похожа на `gable`, но высота дополнительно снижается у концов конька.

### `pyramid`

Шатровая крыша с максимумом в центре footprint local bbox и снижением к краям.

### `mansard`

Ломаная мансардная крыша. Нижняя часть ската круче, верхняя мягче. `mansard_break_ratio` задает положение перелома.

### `dome`

Купольная крыша. Высота плавно поднимается к центру и снижается к краю. Хорошо смотрится на `circle`, `square` и компактных footprints.

### `barrel`

Арочная или сводчатая крыша. Высота меняется по дуге в одном направлении и вытянута вдоль другой оси. Хорошо подходит для `slab`.

### `cone`

Коническая крыша. Высота максимальна в центре и линейно снижается к краю. Хорошо подходит для круговых footprints и ротонд.

## Footprint compatibility

Все roof types работают со всеми footprint types, потому что roof height function применяется только к точкам, которые уже прошли `footprint.contains_xy`.

Практически удачные сочетания:

| Footprint | Roofs |
| --- | --- |
| `rectangle` | `flat`, `shed`, `gable`, `hip`, `half_hip`, `mansard` |
| `square` | `flat`, `hip`, `pyramid`, `dome` |
| `circle` | `flat`, `dome`, `cone` |
| `slab` | `flat`, `shed`, `gable`, `barrel` |
| `courtyard` | `flat`, `gable`, `hip`, `mansard` |

## Metadata

Metadata содержит roof aggregates:

```json
{
  "building_counts": {
    "by_roof": {
      "flat": 5,
      "gable": 2,
      "dome": 4
    },
    "by_roof_and_footprint": {
      "dome": {
        "circle": 2,
        "square": 2
      }
    },
    "by_roof_and_biome": {
      "gable": {
        "residential": 2
      }
    }
  },
  "supported_roof_types": [
    "flat",
    "shed",
    "gable",
    "hip",
    "half_hip",
    "pyramid",
    "mansard",
    "dome",
    "barrel",
    "cone"
  ]
}
```

## Демо

Все типы крыш:

```bash
uv run citygen --config configs/demo_building_roofs.yaml --out outputs/demo_building_roofs.ply
```

Скатные крыши:

```bash
uv run citygen --config configs/demo_pitched_roofs.yaml --out outputs/demo_pitched_roofs.ply
```

Curved roofs:

```bash
uv run citygen --config configs/demo_curved_roofs.yaml --out outputs/demo_curved_roofs.ply
```
