# Примеры конфигов

Этот каталог содержит запускаемые YAML-конфиги для `citygen`. Полный справочник по YAML-схеме, значениям по умолчанию и правилам валидации перенесен в `../doc/configuration_reference.md`.

Актуальные примеры:

| Файл | Назначение |
| --- | --- |
| `mvp.yaml` | Базовый MVP-сценарий. |
| `demo_road_profiles.yaml` | Смешанные дороги, road profiles, `road_median`; здания выключены. |
| `demo_parcels.yaml` | Легкое demo разбиения parcels. |
| `demo_parcel_fences.yaml` | Ограждения участков: mixed/частичные стороны, ворота и фундаменты. |
| `demo_parcel_alignment.yaml` | Выравнивание зданий по parcels на смешанных дорогах. |
| `demo_oriented_parcels.yaml` | Oriented block/parcel subdivision. |
| `demo_universal_showcase.yaml` | Большой интеграционный showcase; справочник: `../doc/universal_showcase.md`. |

Пример запуска:

```bash
uv run citygen --config configs/mvp.yaml --out outputs/mvp_tile.ply
uv run citygen --config configs/demo_parcel_fences.yaml --out outputs/demo_parcel_fences.ply
uv run citygen --config configs/demo_oriented_parcels.yaml --out outputs/demo_oriented_parcels.ply
```
