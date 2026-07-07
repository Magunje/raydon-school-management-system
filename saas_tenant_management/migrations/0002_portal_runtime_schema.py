from django.db import migrations

from saas_tenant_management.schema import ensure_schema_with_cursor


def ensure_portal_runtime_schema(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        ensure_schema_with_cursor(cursor, schema_editor.connection.vendor)


class Migration(migrations.Migration):

    dependencies = [
        ("saas_tenant_management", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_portal_runtime_schema, migrations.RunPython.noop),
    ]
