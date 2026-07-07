from django.db import migrations


def add_textbook_loan_book_id(apps, schema_editor):
    connection = schema_editor.connection
    quote = schema_editor.quote_name
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        if "textbook_loans" not in tables:
            return

        columns = [getattr(column, "name", column[0]) for column in connection.introspection.get_table_description(cursor, "textbook_loans")]
        if "book_id" not in columns:
            cursor.execute(f"ALTER TABLE {quote('textbook_loans')} ADD COLUMN {quote('book_id')} integer NULL")

        try:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {quote('idx_textbook_loans_book_id')} ON {quote('textbook_loans')} ({quote('book_id')})"
            )
        except Exception:
            pass

        if "library_books" not in tables:
            return

        if connection.vendor == "postgresql":
            cursor.execute(
                """
                UPDATE textbook_loans tl
                SET book_id = lb.book_id
                FROM library_books lb
                WHERE tl.book_id IS NULL
                  AND tl.book_name IS NOT NULL
                  AND UPPER(TRIM(tl.book_name)) = UPPER(TRIM(lb.title))
                """
            )
        else:
            cursor.execute(
                """
                UPDATE textbook_loans
                SET book_id = (
                    SELECT lb.book_id
                    FROM library_books lb
                    WHERE UPPER(TRIM(lb.title)) = UPPER(TRIM(textbook_loans.book_name))
                    ORDER BY lb.book_id
                    LIMIT 1
                )
                WHERE book_id IS NULL
                  AND book_name IS NOT NULL
                  AND TRIM(book_name) != ''
                """
            )


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_textbook_loan_book_id, migrations.RunPython.noop),
    ]
