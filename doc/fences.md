# Справочник по ограждениям участков

`fences` — это опциональный слой ограждений для parcels. Он добавляет к земельным участкам заборы, стены, прозрачные металлические секции, воротные разрывы и фундаменты для массивных конструкций.

Слой работает в координатах проекта: горизонтальная плоскость `x/y`, высота `z`. Геометрия строится по `Parcel.geometry`, поэтому для ограждений обязательно нужен включенный слой участков:

```yaml
parcels:
  enabled: true
fences:
  enabled: true
```

Полные значения по умолчанию и правила валидации описаны в `doc/configuration_reference.md`. Геометрия parcels описана в `doc/parcels.md`, road hardscape и clearance — в `doc/roads.md`.

## YAML

Минимальный пример:

```yaml
parcels:
  enabled: true
fences:
  enabled: true
```

Пример с частичным ограждением и воротами:

```yaml
fences:
  enabled: true
  mode: partial
  sides:
    - front
    - left
    - right
  type: metal_welded
  height_m: 1.7
  gate_probability: 0.8
  gate_width_m: 4.0
  gate_sides:
    - front
  foundation: never
```

Пример с массивной кирпичной стеной:

```yaml
fences:
  enabled: true
  mode: perimeter
  type: brick
  height_m: 2.4
  foundation: auto
  foundation_height_m: 0.3
  foundation_width_m: 0.45
```

## Параметры

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `enabled` | `false` | Включает генерацию ограждений. |
| `mode` | `perimeter` | Режим размещения: `none`, `partial`, `perimeter`. |
| `type` | `mixed` | Тип ограждения или `mixed`. |
| `weights` | стандартная смесь | Веса выбора типа при `type: mixed`. |
| `height_m` | `1.8` | Базовая высота ограждения. |
| `height_jitter_m` | `0.25` | Детерминированный разброс высоты между участками. |
| `thickness_m` | `0.12` | Толщина ограждения для расчета внутреннего offset. |
| `boundary_offset_m` | `0.35` | Смещение внутрь участка от границы parcel. |
| `road_clearance_m` | `0.5` | Минимальное расстояние до road/sidewalk/median. |
| `coverage_ratio` | `0.65` | Доля сторон в режиме `partial`, если `sides` не указан. |
| `sides` | `[]` | Явные стороны для `partial`: `front`, `back`, `left`, `right`. |
| `gate_probability` | `0.65` | Вероятность оставить разрыв под ворота или калитку. |
| `gate_width_m` | `4.0` | Ширина воротного разрыва. |
| `gate_sides` | `[front]` | Стороны, где разрешены ворота. |
| `foundation` | `auto` | Режим фундамента: `auto`, `always`, `never`. |
| `foundation_height_m` | `0.25` | Высота семплируемого фундамента. |
| `foundation_width_m` | `0.35` | Ширина фундамента, учитываемая при offset. |
| `sample_spacing_m` | `0.8` | Шаг точек ограждения и фундамента. |
| `openness` | `null` | Переопределяет прозрачность типа: `0` — сплошной, `1` — максимально открытый. |
| `decorative` | `false` | Добавляет декоративные верхние элементы для совместимых типов. |

## Типы ограждений

| Тип | Материал | Поведение |
| --- | --- | --- |
| `wood_picket` | дерево | Легкий штакетник с повторяющимися стойками и рейками. |
| `wood_solid` | дерево | Сплошной дощатый забор с высокой закрытостью. |
| `wood_decorative` | дерево | Декоративные деревянные секции с верхними деталями. |
| `metal_profile` | металл | Сплошной забор из профилированного листа. |
| `metal_chain_link` | металл | Прозрачная сетка с диагональным mesh-паттерном. |
| `metal_welded` | металл | Сварные секции с регулярными вертикальными элементами. |
| `metal_forged` | металл | Декоративное кованое ограждение. |
| `stone` | камень | Массивная каменная стена, фундамент включается при `auto`. |
| `brick` | кирпич | Кирпичная стена, фундамент включается при `auto`. |
| `mixed` | смесь | Детерминированный выбор типа по `weights`. |

Alias-значения:

| Alias | Канонический тип |
| --- | --- |
| `wood`, `wooden` | `wood_picket` |
| `wood_board`, `timber` | `wood_solid` |
| `profile`, `corrugated` | `metal_profile` |
| `chain_link`, `rabitz`, `mesh` | `metal_chain_link` |
| `welded` | `metal_welded` |
| `forged` | `metal_forged` |
| `masonry` | `stone` |
| `brick_wall` | `brick` |

## Как это работает

1. Генератор берет только buildable parcels.
2. Для каждого участка выбираются стороны ограждения: весь периметр или частичный набор.
3. Выбирается тип ограждения. Для `mixed` используется deterministic weighted sampling от `seed` и `parcel.id`.
4. Геометрия участка inset-ится внутрь на `boundary_offset_m`, толщину и, если нужен фундамент, ширину фундамента.
5. На сторонах из `gate_sides` может появиться разрыв под ворота.
6. Сегмент пропускается, если он слишком короткий, нарушает `road_clearance_m` или попадает в footprint здания этого parcel.
7. В sampling попадают точки semantic class `fence`; для фундамента дополнительно создаются точки `fence_foundation`.

Все решения детерминированы: одинаковый конфиг и `seed` дают одинаковые сегменты, ворота, типы и высоты.

## Фундаменты

`foundation: auto` включает основание для тяжелых типов:

- `stone`;
- `brick`.

`foundation: always` добавляет основание для любого типа, включая дерево и металл. `foundation: never` полностью отключает фундаменты даже для камня и кирпича.

Фундамент влияет на:

- наличие точек semantic class `fence_foundation`;
- вертикальное положение основной части ограждения;
- внутренний offset от границы участка через `foundation_width_m`;
- metadata поле `fence_counts.foundation_segments`.

## Ворота

Ворота в MVP представлены разрывом в линии ограждения. Отдельного mesh или створок пока нет.

Разрыв появляется, если:

- сторона входит в `gate_sides`;
- длина стороны достаточна для `gate_width_m`;
- deterministic random check проходит по `gate_probability`.

Metadata считает уникальные разрывы в `fence_counts.gate_openings`.

## Метаданные

Пример секции:

```json
{
  "fence_counts": {
    "segments": 135,
    "parcels_with_fences": 36,
    "foundation_segments": 19,
    "gate_openings": 18,
    "total_length_m": 2832.183,
    "average_height_m": 1.848,
    "by_type": {
      "brick": 8,
      "metal_chain_link": 25,
      "wood_solid": 36
    },
    "by_side": {
      "back": 33,
      "front": 44,
      "left": 28,
      "right": 30
    }
  }
}
```

Связанные поля:

- `class_counts.fence`;
- `class_counts.fence_foundation`;
- `class_mapping.fence`;
- `class_mapping.fence_foundation`;
- `object_feature_counts.parcel_fence`;
- `object_feature_counts.fence_foundation`;
- `supported_fence_types`;
- `config.fences`.

## Демо

Специальный demo-конфиг:

```bash
uv run citygen --config configs/demo_parcel_fences.yaml --out outputs/demo_parcel_fences.ply
```

Быстрый просмотр metadata:

```bash
jq '{point_count, class_counts, fence_counts, supported_fence_types}' outputs/demo_parcel_fences.metadata.json
```

## Практические подсказки

Если ограждения не появляются:

- проверь, что `parcels.enabled: true`;
- проверь, что есть buildable parcels;
- уменьши `road_clearance_m`;
- уменьши `boundary_offset_m` или `foundation_width_m`;
- для проверки поставь `buildings.enabled: false`, чтобы footprints не отсеивали сегменты.

Если точек заборов слишком много:

- увеличь `fences.sample_spacing_m`;
- уменьши `height_m`;
- используй более открытые типы или `openness`.

Если нужно больше массивных стен:

- задай `type: brick` или `type: stone`;
- либо увеличь веса `brick` и `stone` в `weights`;
- оставь `foundation: auto` или поставь `foundation: always`.

## Ограничения MVP

- Ограждения строятся по прямоугольным или oriented-rect parcels, а не по произвольным кадастровым полигонам.
- Нет точного polygon clipping с дорожными коридорами; используется clearance через representative points.
- Ворота пока являются разрывом, без створок, калиток как отдельных объектов и без отдельного semantic class.
- Материалы различаются цветами, плотностью точек и паттернами sampling, а не полноценными текстурами или mesh-материалами.
- Между соседними участками возможны параллельные заборы, потому что слой не выполняет глобальное объединение общих границ.
