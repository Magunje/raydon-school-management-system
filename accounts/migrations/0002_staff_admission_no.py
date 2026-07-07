import re

from django.db import migrations, models


PREFIX = "AS"


def _columns(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        return [
            getattr(column, "name", column[0])
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        ]


def _staff_number_value(value):
    match = re.fullmatch(rf"{PREFIX}(\d+)", str(value or "").strip().upper())
    return int(match.group(1)) if match else 0


def add_and_backfill_staff_admission_no(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        tables = schema_editor.connection.introspection.table_names(cursor)
    if "users" not in tables:
        return

    quote = schema_editor.quote_name
    columns = _columns(schema_editor, "users")
    if "admission_no" not in columns:
        schema_editor.execute(f"ALTER TABLE {quote('users')} ADD COLUMN {quote('admission_no')} varchar(20)")

    schema_editor.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {quote('idx_users_admission_no_unique')} "
        f"ON {quote('users')} ({quote('admission_no')})"
    )

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT admission_no FROM users WHERE admission_no IS NOT NULL AND UPPER(admission_no) LIKE %s",
            [f"{PREFIX}%"],
        )
        highest = max((_staff_number_value(row[0]) for row in cursor.fetchall()), default=0)

        cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE COALESCE(role, '') NOT IN ('Parent', 'Student')
              AND (admission_no IS NULL OR TRIM(CAST(admission_no AS TEXT)) = '')
            ORDER BY user_id
            """
        )
        for (user_id,) in cursor.fetchall():
            highest += 1
            cursor.execute(
                "UPDATE users SET admission_no = %s WHERE user_id = %s",
                [f"{PREFIX}{highest:03d}", user_id],
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_and_backfill_staff_admission_no, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="legacyuser",
                    name="admission_no",
                    field=models.CharField(blank=True, max_length=20, null=True, unique=True),
                ),
            ],
        ),
    ]
