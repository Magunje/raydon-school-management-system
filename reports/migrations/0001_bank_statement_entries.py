from django.db import migrations


def create_bank_statement_entries(apps, schema_editor):
    quote = schema_editor.quote_name
    pk_sql = "serial PRIMARY KEY" if schema_editor.connection.vendor == "postgresql" else "integer PRIMARY KEY AUTOINCREMENT"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {quote('bank_statement_entries')} (
                {quote('entry_id')} {pk_sql},
                {quote('transaction_date')} text,
                {quote('description')} text,
                {quote('reference_no')} varchar(120),
                {quote('money_in')} numeric,
                {quote('money_out')} numeric,
                {quote('match_status')} varchar(40),
                {quote('matched_source')} varchar(40),
                {quote('matched_id')} integer,
                {quote('imported_at')} text,
                {quote('imported_by')} integer
            )
            """
        )
        try:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {quote('idx_bank_statement_reference')} ON {quote('bank_statement_entries')} ({quote('reference_no')})"
            )
        except Exception:
            pass


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunPython(create_bank_statement_entries, migrations.RunPython.noop),
    ]
