# DuRock RJ customization: adds five more well-known bairros as their own
# searchable City rows, following the same pattern as 0007/0009/0010.
# Freguesia (Jacarepaguá), Taquara and Anil are Zona Oeste (Jacarepaguá
# cluster, alongside the already-listed Pechincha). Estácio is Centro.
# Mangueira is administratively Centro (RA II) but is grouped here with Zona
# Norte to match this app's colloquial zoning — it borders Maracanã/Vila
# Isabel (both already Zona Norte in this list) and is popularly associated
# with that zone (same reasoning already applied to Glória/Zona Sul in
# 0010). "Freguesia" is disambiguated in the name since Rio has a second,
# unrelated "Freguesia" on Ilha do Governador that isn't in this list.
# city_id continues each zone's range at the next free slots: 113 (Centro),
# 317 (Zona Norte), 416-418 (Zona Oeste). Coordinates are each bairro's
# approximate center; population is a rough estimate — see 0007 for why
# precision doesn't matter here (search-result ordering only).

import typing as t

from django.contrib.gis.geos import Point
from django.db import migrations
from tzfpy import get_tz

# (name, ascii_name, zone, lat, lng, population, city_id)
NEW_BAIRROS: list[tuple[str, str, str, float, float, int, int]] = [
    ("Estácio", "Estacio", "Centro", -22.9080, -43.2080, 15_000, 3304557113),
    ("Mangueira", "Mangueira", "Zona Norte", -22.9130, -43.2350, 4_000, 3304557317),
    ("Freguesia (Jacarepaguá)", "Freguesia (Jacarepagua)", "Zona Oeste", -22.9420, -43.3550, 34_000, 3304557416),
    ("Taquara", "Taquara", "Zona Oeste", -22.9280, -43.3780, 40_000, 3304557417),
    ("Anil", "Anil", "Zona Oeste", -22.9520, -43.3400, 15_000, 3304557418),
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
        ("geo", "0010_add_pechincha_gloria_and_joa"),
    ]

    operations = [
        migrations.RunPython(add_bairros, reverse_code=remove_bairros),
    ]
