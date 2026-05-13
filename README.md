# MagicCity

MagicCity — MVP CLI-генератора синтетической городской застройки в формате облака точек. `citygen` строит процедурный городской тайл из YAML-конфига и экспортирует ASCII PLY плюс соседний JSON-файл с metadata.

Координатная конвенция проекта: горизонтальная плоскость `x/y`, высота `z`.

## Возможности

- детерминированная генерация по `seed`;
- координатная модель для одного тайла и multi-tile запусков;
- дорожные primitives и модели дорог: `grid`, `radial_ring`, `radial`, `linear`, `organic`, `mixed`, `free`;
- дорожные профили: `local`, `collector`, `arterial`, `boulevard`, включая `road_median`;
- `urban_fields` и биомы: `downtown`, `residential`, `industrial`, `suburb`;
- опциональное разбиение blocks/parcels, включая oriented block/parcel subdivision;
- размещение зданий с учетом parcels и выравнивание по parcel orientation;
- опциональные ограждения участков: деревянные, металлические, каменные и кирпичные заборы с высотой, прозрачностью, воротами и фундаментом;
- footprints зданий: `rectangle`, `square`, `circle`, `slab`, `courtyard`, `l_shape`, `u_shape`, `t_shape`;
- геометрия крыш: `flat`, `shed`, `gable`, `hip`, `half_hip`, `pyramid`, `mansard`, `dome`, `barrel`, `cone`;
- семплирование поверхностей земли, дорог, median, тротуаров, фасадов и крыш;
- semantic class ids и опциональный RGB;
- сводки `worldgen`/catalogs в metadata.

## Документация

Основная документация живет в `doc/` и строится от кода, схемы конфигов, каталогов и metadata, которую пишет генератор.

| Документ | Назначение |
| --- | --- |
| `doc/configuration_reference.md` | Полный YAML-справочник: значения по умолчанию, правила валидации, примеры. |
| `doc/roads.md` | Модели дорог, primitives, профили, surface-классы и метаданные. |
| `doc/biomes.md` | `urban_fields`, классификация биомов и их влияние на генерацию. |
| `doc/parcels.md` | Кварталы и parcels, ориентированное разбиение и зоны застройки. |
| `doc/fences.md` | Ограждения участков: типы заборов, высота, ворота, фундаменты и metadata. |
| `doc/building_footprints.md` | Идентификаторы footprints, aliases, геометрия и семплирование. |
| `doc/building_roofs.md` | Идентификаторы roofs, aliases, функции высоты и семплирование. |
| `doc/generated_objects.md` | Feature ids генерируемых объектов и semantic classes. |
| `doc/worldgen_catalogs.md` | Каталоги, стадии пайплайна и добавление новых ids. |
| `doc/universal_showcase.md` | Справочник по большому интеграционному демонстрационному сценарию. |

`configs/README.md` оставлен только как короткий указатель на примеры и `doc/configuration_reference.md`.

## HTML-документация

Исходники документации находятся в `doc/*.md`. Статическая HTML-версия собирается через MkDocs:

```bash
uv run mkdocs build --clean
```

MkDocs собирает сайт во временную директорию вне `doc/`, а post-build hook переносит результат в `doc/html/`. Это защищает сборку от рекурсивного чтения уже сгенерированного HTML.

После сборки единая точка входа находится здесь:

```text
doc/html/index.html
```

Файл можно открыть локально в браузере. Для режима предварительного просмотра доступен встроенный сервер MkDocs:

```bash
uv run mkdocs serve
```

## Быстрый старт

Установка:

```bash
uv sync
```

Минимальный запуск:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
```

Эквивалентно через Python-модуль:

```bash
uv run python -m citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
```

После успешного запуска появятся:

```text
outputs/mvp_tile.ply
outputs/mvp_tile.metadata.json
```

## CLI

```bash
citygen --config CONFIG_PATH [--out OUTPUT_PATH_OR_DIRECTORY]
```

`--config` обязателен. `--out` может быть:

- путем к `.ply` файлу;
- директорией, куда будет записан `tile_X_Y.ply`;
- пропущен, тогда результат пишется в `outputs/tile_X_Y.ply`.

Если конфиг содержит `tiles`, `--out` должен быть директорией или отсутствовать.

## Актуальные примеры конфигов

| Конфиг | Что проверяет |
| --- | --- |
| `configs/mvp.yaml` | Базовый MVP: дороги `grid`, рельеф, здания, RGB и class labels. |
| `configs/demo_road_profiles.yaml` | Смешанные дороги, road profiles и `road_median`; здания выключены. |
| `configs/demo_parcels.yaml` | Легкое разбиение parcels и здания, привязанные к parcels. |
| `configs/demo_parcel_fences.yaml` | Разные ограждения участков, воротные разрывы и фундаменты. |
| `configs/demo_parcel_alignment.yaml` | Выравнивание зданий по parcels на смешанных дорогах/profiles. |
| `configs/demo_oriented_parcels.yaml` | Ориентированное разбиение blocks/parcels и выровненные здания. |
| `configs/demo_universal_showcase.yaml` | Большой демонстрационный сценарий: mixed roads, profiles, биомы, parcels, footprints, roofs. |

Примеры:

```bash
uv run citygen --config configs/demo_road_profiles.yaml --out outputs/demo_road_profiles.ply
uv run citygen --config configs/demo_parcel_fences.yaml --out outputs/demo_parcel_fences.ply
uv run citygen --config configs/demo_oriented_parcels.yaml --out outputs/demo_oriented_parcels.ply
uv run citygen --config configs/demo_universal_showcase.yaml --out outputs/demo_universal_showcase.ply
```

## Минимальный YAML

```yaml
seed: 7
```

Более полный справочник, включая `tile`, `tiles`, `terrain`, `urban_fields`, `roads`, `buildings`, `parcels`, `fences`, `sampling`, `output` и `worldgen`, находится в `doc/configuration_reference.md`.

## Метаданные

Рядом с каждым PLY пишется JSON-файл с metadata. Поля верхнего уровня включают:

- `seed`, `tile`, `point_count`;
- `class_counts`, `class_mapping`;
- `worldgen`, `catalogs`, `biome_catalog`, `object_feature_counts`;
- `road_models`, `road_profile_counts`, `road_profile_counts_by_biome`, `road_widths`, `road_median`;
- `biome_counts`;
- `building_counts`;
- `parcel_counts`, `fence_counts`, `parcel_building_alignment`, `building_orientations`, `block_geometry`, `parcel_geometry`;
- `supported_footprint_types`, `supported_roof_types`, `supported_fence_types`;
- resolved `config`.

Быстрый просмотр:

```bash
jq '{point_count, class_counts, road_models, building_counts, parcel_counts, fence_counts}' outputs/demo_parcel_fences.metadata.json
```

## Семантические классы

| ID | Класс | RGB |
| --- | --- | --- |
| `1` | `ground` | `107, 132, 85` |
| `2` | `road` | `47, 50, 54` |
| `3` | `sidewalk` | `174, 174, 166` |
| `4` | `building_facade` | `176, 164, 148` |
| `5` | `building_roof` | `112, 116, 122` |
| `6` | `road_median` | `118, 128, 84` |
| `7` | `fence` | `130, 101, 72` |
| `8` | `fence_foundation` | `118, 112, 103` |

Существующие semantic class ids стабильны, и их нельзя менять без явного breaking change.

## Структура проекта

```text
citygen/
  cli.py
  config.py
  generator.py
  roads.py
  parcels.py
  fences.py
  footprints.py
  roofs.py
  sampling.py
  export.py
  catalogs.py
  ...
configs/
  *.yaml
doc/
  *.md
tests/
  test_*.py
```

## Тесты

```bash
uv run python -m unittest discover -s tests
```

Полезные smoke-запуски:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_check.ply
uv run citygen --config configs/demo_parcel_fences.yaml --out outputs/demo_parcel_fences.ply
uv run citygen --config configs/demo_oriented_parcels.yaml --out outputs/demo_oriented_parcels.ply
```

## Ограничения MVP

- Нет полноценного GIS/topology road graph.
- Нет точного polygon clipping дорожных коридоров.
- Parcels представлены прямоугольными или oriented-rect приближениями, а не кадастровыми полигонами.
- Buildings и roofs являются аналитическими поверхностями, которые семплируются в облака точек, а не полноценными объемными meshes.
- Нет LAS/LAZ, CRS/georeferencing, LiDAR ray simulation, intensity или returns.
