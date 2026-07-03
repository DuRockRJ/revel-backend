# DuRock RJ customization: replace the "Cidade, Estado, País" display with
# "Cidade, Região" — grouping the state's 91 non-capital municípios into the
# 7 "regiões fluminenses" used colloquially across Rio de Janeiro state, and
# splitting the single "Rio de Janeiro" capital entry into 4 zone-based
# entries (Centro, Zona Sul, Zona Norte, Zona Oeste), since a single entry
# can't distinguish "a show in Copacabana" from one in Barra da Tijuca.
#
# This is NOT the official 8-region CEPERJ government scheme (which further
# splits e.g. "Região Metropolitana" and "Noroeste Fluminense" / "Médio
# Paraíba" out separately) — those are folded into the nearest region below:
# Região Metropolitana (minus the capital) -> Baixada Fluminense or Leste
# Fluminense depending on which side of Guanabara Bay; Noroeste Fluminense ->
# Norte Fluminense; Médio Paraíba + Centro-Sul Fluminense -> Sul Fluminense.

import typing as t

from django.contrib.gis.geos import Point
from django.db import migrations

REGIONS: dict[str, str] = {}

for _name in [
    "Belford Roxo",
    "Duque de Caxias",
    "Guapimirim",
    "Itaguaí",
    "Japeri",
    "Magé",
    "Mesquita",
    "Nilópolis",
    "Nova Iguaçu",
    "Paracambi",
    "Queimados",
    "São João de Meriti",
    "Seropédica",
]:
    REGIONS[_name] = "Baixada Fluminense"

for _name in [
    "Cachoeiras de Macacu",
    "Itaboraí",
    "Maricá",
    "Niterói",
    "Rio Bonito",
    "São Gonçalo",
    "Tanguá",
]:
    REGIONS[_name] = "Leste Fluminense"

for _name in [
    "Bom Jardim",
    "Cantagalo",
    "Carmo",
    "Cordeiro",
    "Duas Barras",
    "Macuco",
    "Nova Friburgo",
    "Petrópolis",
    "Santa Maria Madalena",
    "São José do Vale do Rio Preto",
    "São Sebastião do Alto",
    "Sumidouro",
    "Teresópolis",
    "Trajano de Moraes",
]:
    REGIONS[_name] = "Região Serrana"

for _name in [
    "Araruama",
    "Armação dos Búzios",
    "Arraial do Cabo",
    "Cabo Frio",
    "Casimiro de Abreu",
    "Iguaba Grande",
    "Rio das Ostras",
    "Saquarema",
    "São Pedro da Aldeia",
    "Silva Jardim",
]:
    REGIONS[_name] = "Região dos Lagos"

for _name in ["Angra dos Reis", "Mangaratiba", "Paraty"]:
    REGIONS[_name] = "Costa Verde"

for _name in [
    "Aperibé",
    "Bom Jesus do Itabapoana",
    "Cambuci",
    "Campos dos Goytacazes",
    "Carapebus",
    "Cardoso Moreira",
    "Conceição de Macabu",
    "Italva",
    "Itaocara",
    "Itaperuna",
    "Laje do Muriaé",
    "Macaé",
    "Miracema",
    "Natividade",
    "Porciúncula",
    "Quissamã",
    "Santo Antônio de Pádua",
    "São Fidélis",
    "São Francisco de Itabapoana",
    "São João da Barra",
    "São José de Ubá",
    "Varre-Sai",
]:
    REGIONS[_name] = "Norte Fluminense"

for _name in [
    "Areal",
    "Barra do Piraí",
    "Barra Mansa",
    "Comendador Levy Gasparian",
    "Engenheiro Paulo de Frontin",
    "Itatiaia",
    "Mendes",
    "Miguel Pereira",
    "Paraíba do Sul",
    "Paty do Alferes",
    "Pinheiral",
    "Piraí",
    "Porto Real",
    "Quatis",
    "Resende",
    "Rio Claro",
    "Rio das Flores",
    "Sapucaia",
    "Três Rios",
    "Valença",
    "Vassouras",
    "Volta Redonda",
]:
    REGIONS[_name] = "Sul Fluminense"

# The four traditional zones the capital is split into. city_id is
# synthesized from the real IBGE code (3304557) since IBGE only tracks the
# municipality as a whole, not its zones. Coordinates are each zone's
# best-known central neighborhood (Centro, Copacabana, Tijuca, Barra da
# Tijuca). Population is apportioned from the 2022 Census total (6,211,223)
# using widely-cited planning-area shares — Zona Norte and Zona Oeste are the
# most populous, Centro is mostly commercial with low residency.
RJ_ZONES: list[tuple[str, float, float, int, int]] = [
    ("Centro", -22.9068, -43.1729, 41_000, 3304557001),
    ("Zona Sul", -22.9711, -43.1822, 600_000, 3304557002),
    ("Zona Norte", -22.9249, -43.2277, 2_700_000, 3304557003),
    ("Zona Oeste", -22.9990, -43.3653, 2_870_223, 3304557004),
]


def apply_regions(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")

    capital = City.objects.get(name="Rio de Janeiro")
    shared = {
        "country": capital.country,
        "iso2": capital.iso2,
        "iso3": capital.iso3,
        "timezone": capital.timezone,
    }
    capital.delete()

    City.objects.bulk_create(
        [
            City(
                name="Rio de Janeiro",
                ascii_name="Rio de Janeiro",
                admin_name=zone_name,
                capital="admin" if zone_name == "Centro" else None,
                population=population,
                city_id=city_id,
                location=Point(lng, lat),
                **shared,
            )
            for zone_name, lat, lng, population, city_id in RJ_ZONES
        ]
    )

    to_update = []
    for city in City.objects.exclude(name="Rio de Janeiro"):
        region = REGIONS.get(city.name)
        if region is None:
            raise ValueError(f"No region mapping for município: {city.name!r}")
        city.admin_name = region
        to_update.append(city)
    City.objects.bulk_update(to_update, ["admin_name"], batch_size=100)


def noop_reverse(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    # Irreversible: the previous admin_name="Rio de Janeiro" values and the
    # single capital row aren't recoverable from state.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("geo", "0005_replace_with_rj_cities"),
    ]

    operations = [
        migrations.RunPython(apply_regions, reverse_code=noop_reverse),
    ]
