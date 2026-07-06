# DuRock RJ customization: searching a bairro name (e.g. "Bangu") returned
# nothing, because 0006 only folded bairro names into the zone row's
# ascii_name as hidden search keywords — matching, but displaying as
# "Rio de Janeiro, Zona Oeste" instead of "Bangu, Zona Oeste". Users expect
# the same experience as searching a município: the bairro itself as the
# result, with its zone as the region. This adds each bairro as its own City
# row (name=bairro, admin_name=zone), alongside the existing zone rows.
#
# city_id is synthesized (no IBGE code exists below municipality level):
# 3304557101-3304557112 for Centro, 201-216 for Zona Sul, 301-316 for Zona
# Norte, 401-412 for Zona Oeste. Coordinates are each bairro's approximate
# center; population is a rough estimate (order of magnitude only — it's
# used solely for search-result ordering, not displayed).

import typing as t

from django.contrib.gis.geos import Point
from django.db import migrations
from tzfpy import get_tz

# (zone_name, city_id_offset, [(name, ascii_name, lat, lng, population), ...])
RJ_BAIRROS: list[tuple[str, int, list[tuple[str, str, float, float, int]]]] = [
    (
        "Centro",
        100,
        [
            ("Centro", "Centro", -22.9068, -43.1729, 41_142),
            ("Lapa", "Lapa", -22.9137, -43.1797, 4_102),
            ("Santa Teresa", "Santa Teresa", -22.9220, -43.1890, 40_540),
            ("Cidade Nova", "Cidade Nova", -22.9070, -43.2000, 4_573),
            ("Gamboa", "Gamboa", -22.8970, -43.1930, 8_187),
            ("Saúde", "Saude", -22.8940, -43.1870, 5_278),
            ("Santo Cristo", "Santo Cristo", -22.8990, -43.2030, 8_014),
            ("São Cristóvão", "Sao Cristovao", -22.8980, -43.2210, 20_367),
            ("Caju", "Caju", -22.8790, -43.2270, 15_203),
            ("Paquetá", "Paqueta", -22.7700, -43.1070, 3_361),
            ("Praça da Bandeira", "Praca da Bandeira", -22.9110, -43.2130, 9_564),
            ("Rio Comprido", "Rio Comprido", -22.9210, -43.2130, 37_215),
        ],
    ),
    (
        "Zona Sul",
        200,
        [
            ("Copacabana", "Copacabana", -22.9711, -43.1822, 146_392),
            ("Ipanema", "Ipanema", -22.9838, -43.2096, 43_617),
            ("Leblon", "Leblon", -22.9844, -43.2246, 42_082),
            ("Botafogo", "Botafogo", -22.9519, -43.1806, 82_637),
            ("Flamengo", "Flamengo", -22.9328, -43.1755, 51_357),
            ("Laranjeiras", "Laranjeiras", -22.9345, -43.1856, 20_477),
            ("Catete", "Catete", -22.9256, -43.1770, 16_145),
            ("Humaitá", "Humaita", -22.9530, -43.1950, 14_799),
            ("Cosme Velho", "Cosme Velho", -22.9426, -43.1930, 6_838),
            ("Gávea", "Gavea", -22.9770, -43.2330, 15_899),
            ("Jardim Botânico", "Jardim Botanico", -22.9673, -43.2223, 9_398),
            ("Lagoa", "Lagoa", -22.9680, -43.2050, 6_595),
            ("Urca", "Urca", -22.9490, -43.1650, 6_672),
            ("São Conrado", "Sao Conrado", -22.9990, -43.2660, 10_842),
            ("Rocinha", "Rocinha", -22.9890, -43.2470, 69_161),
            ("Vidigal", "Vidigal", -22.9930, -43.2350, 7_738),
        ],
    ),
    (
        "Zona Norte",
        300,
        [
            ("Tijuca", "Tijuca", -22.9249, -43.2277, 163_805),
            ("Vila Isabel", "Vila Isabel", -22.9147, -43.2461, 51_791),
            ("Grajaú", "Grajau", -22.9270, -43.2622, 21_224),
            ("Maracanã", "Maracana", -22.9122, -43.2302, 10_073),
            ("Méier", "Meier", -22.9012, -43.2789, 40_461),
            ("Madureira", "Madureira", -22.8735, -43.3400, 36_072),
            ("Bonsucesso", "Bonsucesso", -22.8664, -43.2513, 30_940),
            ("Ramos", "Ramos", -22.8556, -43.2603, 27_772),
            ("Penha", "Penha", -22.8390, -43.2790, 58_673),
            ("Olaria", "Olaria", -22.8556, -43.2740, 27_449),
            ("Irajá", "Iraja", -22.8320, -43.3260, 30_749),
            ("Pavuna", "Pavuna", -22.8047, -43.3550, 74_412),
            ("Ilha do Governador", "Ilha do Governador", -22.8090, -43.2130, 211_169),
            ("Del Castilho", "Del Castilho", -22.8880, -43.2790, 21_466),
            ("Todos os Santos", "Todos os Santos", -22.8960, -43.2870, 9_547),
            ("Cascadura", "Cascadura", -22.8860, -43.3320, 21_133),
        ],
    ),
    (
        "Zona Oeste",
        400,
        [
            ("Barra da Tijuca", "Barra da Tijuca", -23.0000, -43.3650, 135_924),
            ("Deodoro", "Deodoro", -22.8620, -43.3860, 14_690),
            ("Recreio dos Bandeirantes", "Recreio dos Bandeirantes", -23.0210, -43.4650, 46_876),
            ("Jacarepaguá", "Jacarepagua", -22.9590, -43.3650, 157_367),
            ("Campo Grande", "Campo Grande", -22.9030, -43.5610, 328_235),
            ("Santa Cruz", "Santa Cruz", -22.9130, -43.6870, 217_333),
            ("Bangu", "Bangu", -22.8790, -43.4680, 250_394),
            ("Guaratiba", "Guaratiba", -23.0560, -43.5940, 110_049),
            ("Realengo", "Realengo", -22.8760, -43.4330, 59_000),
            ("Sepetiba", "Sepetiba", -22.9660, -43.7010, 44_268),
            ("Vargem Grande", "Vargem Grande", -22.9760, -43.4700, 20_491),
            ("Vargem Pequena", "Vargem Pequena", -22.9660, -43.4400, 12_530),
        ],
    ),
]


def add_bairros(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")

    zone_rows = {c.admin_name: c for c in City.objects.filter(name="Rio de Janeiro")}
    shared = {
        "country": zone_rows["Centro"].country,
        "iso2": zone_rows["Centro"].iso2,
        "iso3": zone_rows["Centro"].iso3,
    }

    objs: list[t.Any] = []
    for zone_name, id_offset, bairros in RJ_BAIRROS:
        if zone_name not in zone_rows:
            raise ValueError(f"No zone row found for {zone_name!r}; was 0006 applied?")
        for index, (name, ascii_name, lat, lng, population) in enumerate(bairros, start=1):
            objs.append(
                City(
                    name=name,
                    ascii_name=ascii_name,
                    admin_name=zone_name,
                    capital=None,
                    population=population,
                    city_id=3304557000 + id_offset + index,
                    location=Point(lng, lat),
                    timezone=get_tz(lng, lat),
                    **shared,
                )
            )
    City.objects.bulk_create(objs, batch_size=100)


def noop_reverse(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("geo", "0006_add_regions_and_split_rj_zones"),
    ]

    operations = [
        migrations.RunPython(add_bairros, reverse_code=noop_reverse),
    ]
