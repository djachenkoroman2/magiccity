# Примеры конфигов

Этот каталог содержит запускаемые YAML-конфиги для `citygen`. Полный справочник по YAML-схеме, значениям по умолчанию и правилам валидации перенесен в `../doc/configuration_reference.md`.

Отдельного demo-конфига для `mobile_lidar` пока нет: секцию `mobile_lidar` можно добавить в любой из примеров ниже.
Отдельный demo-конфиг для деревьев есть: `demo_trees.yaml`.
Отдельный demo-конфиг для транспорта есть: `demo_vehicles.yaml`.

Актуальные примеры:

| Файл | Назначение |
| --- | --- |
| `mvp.yaml` | Базовый MVP-сценарий. |
| `demo_road_profiles.yaml` | Смешанные дороги, road profiles, `road_median`; здания выключены. |
| `demo_parcels.yaml` | Легкое demo разбиения parcels. |
| `demo_parcel_fences.yaml` | Ограждения участков: mixed/частичные стороны, ворота и фундаменты. |
| `demo_trees.yaml` | Деревья: mixed кроны, density по биомам, natural-ground placement и `tree_trunk`/`tree_crown`. |
| `demo_vehicles.yaml` | Транспорт: road vehicles, parking/yard placement, mixed types и `vehicle_body`/`vehicle_wheel`/`vehicle_window`. |
| `demo_parcel_alignment.yaml` | Выравнивание зданий по parcels на смешанных дорогах. |
| `demo_oriented_parcels.yaml` | Oriented block/parcel subdivision. |
| `demo_universal_showcase.yaml` | Большой интеграционный showcase с горами, холмами, оврагами, mixed roads/profiles и parcels; справочник: `../doc/universal_showcase.md`. |

Пример запуска:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
uv run citygen --config configs/demo_parcel_fences.yaml --out outputs/demo_parcel_fences.ply
uv run citygen --config configs/demo_trees.yaml --out outputs/demo_trees.ply
uv run citygen --config configs/demo_vehicles.yaml --out outputs/demo_vehicles.ply
uv run citygen --config configs/demo_oriented_parcels.yaml --out outputs/demo_oriented_parcels.ply
```
