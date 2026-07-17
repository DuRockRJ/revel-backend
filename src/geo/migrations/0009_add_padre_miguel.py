# DuRock RJ customization: adds the "Padre Miguel" bairro (Zona Oeste) as its
# own searchable City row, following the same pattern as 0007_add_rj_bairros.
# city_id continues the Zona Oeste range (400 + index) at the next free slot,
# 413. Coordinates are an approximate center (near Realengo/Bangu on the
# SuperVia Santa Cruz line); population is a rough estimate — see 0007 for
# why precision doesn't matter here (search-result ordering only).

import typing as t

from django.contrib.gis.geos import Point
from django.db import migrations
from tzfpy import get_tz

NAME = "Padre Miguel"
ASCII_NAME = "Padre Miguel"
ZONE = "Zona Oeste"
LAT = -22.8780
LNG = -43.4230
POPULATION = 43_000
CITY_ID = 3304557413


def add_padre_miguel(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")

    reference = City.objects.filter(admin_name=ZONE).first()
    if reference is None:
        raise ValueError(f"No existing {ZONE!r} row found; was 0007 applied?")

    City.objects.create(
        name=NAME,
        ascii_name=ASCII_NAME,
        admin_name=ZONE,
        country=reference.country,
        iso2=reference.iso2,
        iso3=reference.iso3,
        capital=None,
        population=POPULATION,
        city_id=CITY_ID,
        location=Point(LNG, LAT),
        timezone=get_tz(LNG, LAT),
    )


def remove_padre_miguel(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")
    City.objects.filter(name=NAME, admin_name=ZONE, city_id=CITY_ID).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("geo", "0008_remove_rj_zone_umbrella_rows"),
    ]

    operations = [
        migrations.RunPython(add_padre_miguel, reverse_code=remove_padre_miguel),
    ]
