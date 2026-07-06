# DuRock RJ customization: now that every bairro is its own searchable City
# row (0007), the 4 generic "Rio de Janeiro" zone-umbrella rows (Centro,
# Zona Sul, Zona Norte, Zona Oeste) are redundant and confusing — searching
# "Zona Oeste" already surfaces its bairros directly, so a bare "Rio de
# Janeiro, Zona Oeste" result with no bairro doesn't add anything real.

import typing as t

from django.db import migrations


def remove_umbrella_rows(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    City = apps.get_model("geo", "City")
    City.objects.filter(name="Rio de Janeiro").delete()


def noop_reverse(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("geo", "0007_add_rj_bairros"),
    ]

    operations = [
        migrations.RunPython(remove_umbrella_rows, reverse_code=noop_reverse),
    ]
