# DuRock RJ customization: the external event-ingestion endpoint (rockfeed-rj and
# any future scraper) needs an Organization to attach events to when the scraped
# organizer can't be resolved, and every Organization needs an owner. This creates
# a dedicated system RevelUser (never logs in — unusable password) and a single
# "Não classificado" placeholder Organization owned by it, staff-only visibility
# so it never surfaces publicly. Idempotent: skips creation if either already exists.

import typing as t

from django.contrib.auth.hashers import make_password
from django.db import migrations

SYSTEM_USERNAME = "scraper-system@durockrj.com.br"
PLACEHOLDER_ORG_NAME = "Não classificado"
PLACEHOLDER_ORG_SLUG = "nao-classificado"


def create_system_user_and_org(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    RevelUser = apps.get_model("accounts", "RevelUser")
    Organization = apps.get_model("events", "Organization")

    system_user, _ = RevelUser.objects.get_or_create(
        username=SYSTEM_USERNAME,
        defaults={
            "email": SYSTEM_USERNAME,
            "first_name": "Sistema",
            "last_name": "de Ingestão",
            "is_active": True,
            "email_verified": True,
            "password": make_password(None),
        },
    )

    Organization.objects.get_or_create(
        name=PLACEHOLDER_ORG_NAME,
        defaults={
            "slug": PLACEHOLDER_ORG_SLUG,
            "owner": system_user,
            "visibility": "staff-only",
        },
    )


def remove_system_user_and_org(apps: migrations.state.Apps, schema_editor: t.Any) -> None:
    Organization = apps.get_model("events", "Organization")
    RevelUser = apps.get_model("accounts", "RevelUser")

    Organization.objects.filter(name=PLACEHOLDER_ORG_NAME).delete()
    RevelUser.objects.filter(username=SYSTEM_USERNAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0098_add_event_external_uid"),
        ("accounts", "0034_remove_reveluser_pronouns"),
    ]

    operations = [
        migrations.RunPython(create_system_user_and_org, reverse_code=remove_system_user_and_org),
    ]
