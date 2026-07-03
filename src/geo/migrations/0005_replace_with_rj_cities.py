# DuRock RJ customization: this platform only serves events in Rio de Janeiro
# state, so the global worldcities sample (mostly foreign capitals, and never
# containing a single RJ municipality) is replaced with the full, official set
# of all 92 municípios of Rio de Janeiro state.
#
# Data is embedded directly (not loaded from a CSV in geo/data/) because that
# directory is volume-mounted over in production (docker-compose.yml mounts
# ./geo-data over /app/src/geo/data for self-hosted worldcities.csv /
# IP2Location datasets), which shadows anything baked into the image there —
# a file-based version of this migration silently finds nothing at runtime.

from django.db import migrations
from django.contrib.gis.geos import Point
from tzfpy import get_tz
import typing as t

# All 92 municípios of Rio de Janeiro state: (name, ascii_name, lat, lng, capital, population, ibge_code)
# Source: IBGE Census 2022 population + kelvins/municipios-brasileiros coordinates.
RJ_CITIES: list[tuple[str, str, float, float, str | None, int, int]] = [
    ("Angra dos Reis", "Angra dos Reis", -23.0011, -44.3196, None, 167434, 3300100),
    ("Aperibé", "Aperibe", -21.6252, -42.1017, None, 11034, 3300159),
    ("Araruama", "Araruama", -22.8697, -42.3326, None, 129671, 3300209),
    ("Areal", "Areal", -22.2283, -43.1118, None, 11828, 3300225),
    (
        "Armação dos Búzios",
        "Armacao dos Buzios",
        -22.7528,
        -41.8846,
        None,
        40006,
        3300233,
    ),
    ("Arraial do Cabo", "Arraial do Cabo", -22.9774, -42.0267, None, 30986, 3300258),
    ("Barra do Piraí", "Barra do Pirai", -22.4715, -43.8269, None, 92883, 3300308),
    ("Barra Mansa", "Barra Mansa", -22.5481, -44.1752, None, 169894, 3300407),
    ("Belford Roxo", "Belford Roxo", -22.764, -43.3992, None, 483087, 3300456),
    ("Bom Jardim", "Bom Jardim", -22.1545, -42.4251, None, 28102, 3300506),
    (
        "Bom Jesus do Itabapoana",
        "Bom Jesus do Itabapoana",
        -21.1449,
        -41.6822,
        None,
        35173,
        3300605,
    ),
    ("Cabo Frio", "Cabo Frio", -22.8894, -42.0286, None, 222161, 3300704),
    (
        "Cachoeiras de Macacu",
        "Cachoeiras de Macacu",
        -22.4658,
        -42.6523,
        None,
        56943,
        3300803,
    ),
    ("Cambuci", "Cambuci", -21.5691, -41.9187, None, 14616, 3300902),
    (
        "Campos dos Goytacazes",
        "Campos dos Goytacazes",
        -21.7622,
        -41.3181,
        None,
        483540,
        3301009,
    ),
    ("Cantagalo", "Cantagalo", -21.9797, -42.3664, None, 19390, 3301108),
    ("Carapebus", "Carapebus", -22.1821, -41.663, None, 13847, 3300936),
    ("Cardoso Moreira", "Cardoso Moreira", -21.4846, -41.6165, None, 12958, 3301157),
    ("Carmo", "Carmo", -21.931, -42.6046, None, 17198, 3301207),
    (
        "Casimiro de Abreu",
        "Casimiro de Abreu",
        -22.4812,
        -42.2066,
        None,
        46110,
        3301306,
    ),
    (
        "Comendador Levy Gasparian",
        "Comendador Levy Gasparian",
        -22.0404,
        -43.214,
        None,
        8741,
        3300951,
    ),
    (
        "Conceição de Macabu",
        "Conceicao de Macabu",
        -22.0834,
        -41.8719,
        None,
        21104,
        3301405,
    ),
    ("Cordeiro", "Cordeiro", -22.0267, -42.3648, None, 20783, 3301504),
    ("Duas Barras", "Duas Barras", -22.0536, -42.5232, None, 10980, 3301603),
    ("Duque de Caxias", "Duque de Caxias", -22.7858, -43.3049, None, 808161, 3301702),
    (
        "Engenheiro Paulo de Frontin",
        "Engenheiro Paulo de Frontin",
        -22.5498,
        -43.6827,
        None,
        12242,
        3301801,
    ),
    ("Guapimirim", "Guapimirim", -22.5347, -42.9895, None, 51696, 3301850),
    ("Iguaba Grande", "Iguaba Grande", -22.8495, -42.2299, None, 27920, 3301876),
    ("Itaboraí", "Itaborai", -22.7565, -42.8639, None, 224267, 3301900),
    ("Itaguaí", "Itaguai", -22.8636, -43.7798, None, 116841, 3302007),
    ("Italva", "Italva", -21.4296, -41.7014, None, 14073, 3302056),
    ("Itaocara", "Itaocara", -21.6748, -42.0758, None, 22919, 3302106),
    ("Itaperuna", "Itaperuna", -21.1997, -41.8799, None, 101041, 3302205),
    ("Itatiaia", "Itatiaia", -22.4897, -44.5675, None, 30908, 3302254),
    ("Japeri", "Japeri", -22.6435, -43.6602, None, 96289, 3302270),
    ("Laje do Muriaé", "Laje do Muriae", -21.2091, -42.1271, None, 7336, 3302304),
    ("Macaé", "Macae", -22.3768, -41.7848, None, 246391, 3302403),
    ("Macuco", "Macuco", -21.9813, -42.2533, None, 5415, 3302452),
    ("Magé", "Mage", -22.6632, -43.0315, None, 228127, 3302502),
    ("Mangaratiba", "Mangaratiba", -22.9594, -44.0409, None, 41220, 3302601),
    ("Maricá", "Marica", -22.9354, -42.8246, None, 197277, 3302700),
    ("Mendes", "Mendes", -22.5245, -43.7312, None, 17502, 3302809),
    ("Mesquita", "Mesquita", -22.8028, -43.4601, None, 167127, 3302858),
    ("Miguel Pereira", "Miguel Pereira", -22.4572, -43.4803, None, 26578, 3302908),
    ("Miracema", "Miracema", -21.4148, -42.1938, None, 26881, 3303005),
    ("Natividade", "Natividade", -21.039, -41.9697, None, 15074, 3303104),
    ("Nilópolis", "Nilopolis", -22.8057, -43.4233, None, 146774, 3303203),
    ("Niterói", "Niteroi", -22.8832, -43.1034, None, 481749, 3303302),
    ("Nova Friburgo", "Nova Friburgo", -22.2932, -42.5377, None, 189939, 3303401),
    ("Nova Iguaçu", "Nova Iguacu", -22.7556, -43.4603, None, 785867, 3303500),
    ("Paracambi", "Paracambi", -22.6078, -43.7108, None, 41375, 3303609),
    ("Paraíba do Sul", "Paraiba do Sul", -22.1585, -43.304, None, 42063, 3303708),
    ("Paraty", "Paraty", -23.2221, -44.7175, None, 44872, 3303807),
    ("Paty do Alferes", "Paty do Alferes", -22.4309, -43.4285, None, 29619, 3303856),
    ("Petrópolis", "Petropolis", -22.52, -43.1926, None, 278881, 3303906),
    ("Pinheiral", "Pinheiral", -22.5172, -44.0022, None, 24298, 3303955),
    ("Piraí", "Pirai", -22.6215, -43.9081, None, 27474, 3304003),
    ("Porciúncula", "Porciuncula", -20.9632, -42.0465, None, 17288, 3304102),
    ("Porto Real", "Porto Real", -22.4175, -44.2952, None, 20373, 3304110),
    ("Quatis", "Quatis", -22.4045, -44.2597, None, 13682, 3304128),
    ("Queimados", "Queimados", -22.7102, -43.5518, None, 140523, 3304144),
    ("Quissamã", "Quissama", -22.1031, -41.4693, None, 22393, 3304151),
    ("Resende", "Resende", -22.4705, -44.4509, None, 129612, 3304201),
    ("Rio Bonito", "Rio Bonito", -22.7181, -42.6276, None, 56276, 3304300),
    ("Rio Claro", "Rio Claro", -22.72, -44.1419, None, 17401, 3304409),
    ("Rio das Flores", "Rio das Flores", -22.1692, -43.5856, None, 8954, 3304508),
    ("Rio das Ostras", "Rio das Ostras", -22.5174, -41.9475, None, 156491, 3304524),
    ("Rio de Janeiro", "Rio de Janeiro", -22.9129, -43.2003, "admin", 6211223, 3304557),
    (
        "Santa Maria Madalena",
        "Santa Maria Madalena",
        -21.9547,
        -42.0098,
        None,
        10232,
        3304607,
    ),
    (
        "Santo Antônio de Pádua",
        "Santo Antonio de Padua",
        -21.541,
        -42.1832,
        None,
        41325,
        3304706,
    ),
    ("São Fidélis", "Sao Fidelis", -21.6551, -41.756, None, 38939, 3304805),
    (
        "São Francisco de Itabapoana",
        "Sao Francisco de Itabapoana",
        -21.4702,
        -41.1091,
        None,
        45059,
        3304755,
    ),
    ("São Gonçalo", "Sao Goncalo", -22.8268, -43.0634, None, 896744, 3304904),
    ("São João da Barra", "Sao Joao da Barra", -21.638, -41.0446, None, 36573, 3305000),
    (
        "São João de Meriti",
        "Sao Joao de Meriti",
        -22.8058,
        -43.3729,
        None,
        440962,
        3305109,
    ),
    ("São José de Ubá", "Sao Jose de Uba", -21.3661, -41.9511, None, 7070, 3305133),
    (
        "São José do Vale do Rio Preto",
        "Sao Jose do Vale do Rio Preto",
        -22.1525,
        -42.9327,
        None,
        22080,
        3305158,
    ),
    (
        "São Pedro da Aldeia",
        "Sao Pedro da Aldeia",
        -22.8429,
        -42.1026,
        None,
        104029,
        3305208,
    ),
    (
        "São Sebastião do Alto",
        "Sao Sebastiao do Alto",
        -21.9578,
        -42.1328,
        None,
        7750,
        3305307,
    ),
    ("Sapucaia", "Sapucaia", -21.9949, -42.9142, None, 17729, 3305406),
    ("Saquarema", "Saquarema", -22.9292, -42.5099, None, 89559, 3305505),
    ("Seropédica", "Seropedica", -22.7526, -43.7155, None, 80596, 3305554),
    ("Silva Jardim", "Silva Jardim", -22.6574, -42.3961, None, 21352, 3305604),
    ("Sumidouro", "Sumidouro", -22.0485, -42.6761, None, 15206, 3305703),
    ("Tanguá", "Tangua", -22.7423, -42.7202, None, 31086, 3305752),
    ("Teresópolis", "Teresopolis", -22.4165, -42.9752, None, 165123, 3305802),
    (
        "Trajano de Moraes",
        "Trajano de Moraes",
        -22.0638,
        -42.0643,
        None,
        10302,
        3305901,
    ),
    ("Três Rios", "Tres Rios", -22.1165, -43.2185, None, 78346, 3306008),
    ("Valença", "Valenca", -22.2445, -43.7129, None, 67753, 3306107),
    ("Varre-Sai", "Varre-Sai", -20.9276, -41.8701, None, 10207, 3306156),
    ("Vassouras", "Vassouras", -22.4059, -43.6686, None, 33976, 3306206),
    ("Volta Redonda", "Volta Redonda", -22.5202, -44.0996, None, 261563, 3306305),
]


def load_rj_cities(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")

    City.objects.all().delete()

    objs: list[t.Any] = []
    for name, ascii_name, lat, lng, capital, population, city_id in RJ_CITIES:
        objs.append(
            City(
                name=name,
                ascii_name=ascii_name,
                country="Brazil",
                iso2="BR",
                iso3="BRA",
                admin_name="Rio de Janeiro",
                capital=capital,
                population=population,
                city_id=city_id,
                location=Point(lng, lat),  # lon, lat
                # bulk_create bypasses City.save(), which is where timezone is
                # normally auto-derived from location — compute it explicitly.
                timezone=get_tz(lng, lat),
            )
        )

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
