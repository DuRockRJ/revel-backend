# DuRock RJ customization: adds "Pechincha" and "Joá" (Zona Oeste) and "Glória"
# (Zona Sul) as their own searchable City rows, following the same pattern as
# 0007_add_rj_bairros / 0009_add_padre_miguel. Glória sits administratively in
# the Centro region, but is grouped here with Zona Sul to match this app's
# existing colloquial zoning (it's the bairro right after Catete on the way to
# Lapa, and Cariocas commonly place it in Zona Sul, same as this list already
# does for e.g. Humaitá/Cosme Velho). city_id continues each zone's range
# (200 + index for Zona Sul, 400 + index for Zona Oeste) at the next free
# slots: 217, 414, 415. Coordinates are each bairro's approximate center;
# population is a rough estimate — see 0007 for why precision doesn't matter
# here (search-result ordering only).

import typing as t

from django.contrib.gis.geos import Point
from django.db import migrations
from tzfpy import get_tz

# (name, ascii_name, zone, lat, lng, population, city_id)
NEW_BAIRROS: list[tuple[str, str, str, float, float, int, int]] = [
    ("Glória", "Gloria", "Zona Sul", -22.9186, -43.1752, 5_000, 3304557217),
    ("Pechincha", "Pechincha", "Zona Oeste", -22.9270, -43.3670, 47_000, 3304557414),
    ("Joá", "Joa", "Zona Oeste", -22.9970, -43.2870, 1_500, 3304557415),
]


def add_bairros(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")

    for name, ascii_name, zone, lat, lng, population, city_id in NEW_BAIRROS:
        reference = City.objects.filter(admin_name=zone).first()
        if reference is None:
            raise ValueError(f"No existing {zone!r} row found; was 0007 applied?")

        City.objects.create(
            name=name,
            ascii_name=ascii_name,
            admin_name=zone,
            country=reference.country,
            iso2=reference.iso2,
            iso3=reference.iso3,
            capital=None,
            population=population,
            city_id=city_id,
            location=Point(lng, lat),
            timezone=get_tz(lng, lat),
        )


def remove_bairros(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")
    City.objects.filter(city_id__in=[city_id for *_, city_id in NEW_BAIRROS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("geo", "0009_add_padre_miguel"),
    ]

    operations = [
        migrations.RunPython(add_bairros, reverse_code=remove_bairros),
    ]
