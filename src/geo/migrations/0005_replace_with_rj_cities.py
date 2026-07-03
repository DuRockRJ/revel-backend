# DuRock RJ customization: this platform only serves events in Rio de Janeiro
# state, so the global worldcities sample (mostly foreign capitals, and never
# containing a single RJ municipality) is replaced with the full, official set
# of all 92 municípios of Rio de Janeiro state (IBGE codes, Census 2022
# population, geo/data/rj_cities.csv).

from pathlib import Path
from django.db import migrations
from django.contrib.gis.geos import Point
from tzfpy import get_tz
import csv
import typing as t

RJ_CITIES_CSV = Path(__file__).resolve().parent.parent / "data" / "rj_cities.csv"


def load_rj_cities(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")

    if not RJ_CITIES_CSV.exists():
        raise FileNotFoundError(
            f"RJ cities import failed: no CSV found at {RJ_CITIES_CSV}"
        )

    with RJ_CITIES_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, str]] = list(reader)

    City.objects.all().delete()

    objs: list[t.Any] = []
    for row in rows:
        try:
            lng, lat = float(row["lng"]), float(row["lat"])
            obj = City(
                name=row["city"],
                ascii_name=row["city_ascii"],
                country=row["country"],
                iso2=row["iso2"],
                iso3=row["iso3"],
                admin_name=row.get("admin_name") or None,
                capital=row.get("capital") or None,
                population=int(float(row["population"])) if row["population"] else None,
                city_id=int(row["id"]),
                location=Point(lng, lat),  # lon, lat
                # bulk_create bypasses City.save(), which is where timezone is
                # normally auto-derived from location — compute it explicitly.
                timezone=get_tz(lng, lat),
            )
            objs.append(obj)
        except Exception as e:
            raise ValueError(f"Failed to parse RJ city row: {row}") from e

    City.objects.bulk_create(objs, batch_size=100)


def noop_reverse(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    # Irreversible: the previous worldcities.mini.csv rows aren't recoverable
    # from state. Re-running migration 0002 manually would restore them.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("geo", "0004_add_city_timezone"),
    ]

    operations = [
        migrations.RunPython(load_rj_cities, reverse_code=noop_reverse),
    ]
