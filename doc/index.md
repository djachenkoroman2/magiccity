# Документация MagicCity

MagicCity — процедурный генератор городских point clouds. `citygen` строит детерминированные городские тайлы из YAML-конфигов и экспортирует ASCII PLY вместе с JSON-файлом metadata.

Документация описывает runtime-модели, конфиги, дороги, биомы, parcels, ограждения, здания, sampling, catalogs и metadata. Координатная конвенция проекта: горизонтальная плоскость `x/y`, высота `z`.

## Разделы

- [Справочник по конфигурации](configuration_reference.md) — YAML-схема, значения по умолчанию, валидация и примеры.
- [Дороги](roads.md) — road primitives, модели дорог, road profiles и surface-классы.
- [Биомы](biomes.md) — `urban_fields`, классификация районов и влияние биомов на дороги/здания.
- [Parcels](parcels.md) — blocks/parcels, oriented subdivision, buildable areas и placement зданий.
- [Ограждения](fences.md) — заборы по границам parcels, типы материалов, высота, ворота и фундаменты.
- [Footprints зданий](building_footprints.md) — поддержанные footprint types, aliases, геометрия и clearance.
- [Крыши зданий](building_roofs.md) — roof types, aliases, функции высоты и sampling.
- [Генерируемые объекты](generated_objects.md) — object feature ids, semantic classes и metadata counts.
- [Worldgen catalogs](worldgen_catalogs.md) — catalogs, стадии пайплайна и правила добавления ids.
- [Universal showcase](universal_showcase.md) — большой демонстрационный сценарий и поля metadata для проверки.

## Быстрые команды

Собрать HTML-документацию:

```bash
uv run mkdocs build --clean
```

После сборки главная HTML-страница находится здесь:

```text
doc/html/index.html
```
