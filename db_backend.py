import re
import sqlite3


try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:
    psycopg = None
    dict_row = None


POSTGRES_SCHEMES = ("postgresql://", "postgres://")

DB_ERRORS = (sqlite3.Error,)
DB_OPERATIONAL_ERRORS = (sqlite3.OperationalError,)
DB_DATABASE_ERRORS = (sqlite3.DatabaseError,)

if psycopg is not None:
    DB_ERRORS = (sqlite3.Error, psycopg.Error)
    DB_OPERATIONAL_ERRORS = (sqlite3.OperationalError, psycopg.OperationalError)
    DB_DATABASE_ERRORS = (sqlite3.DatabaseError, psycopg.DatabaseError)


PRIMARY_KEYS = {
    "academic_year": "academic_id",
    "attendance_records": "attendance_id",
    "audit_log": "audit_id",
    "balance_adjustments": "adjustment_id",
    "class_timetable_entries": "timetable_id",
    "classes": "class_id",
    "communication_log": "communication_id",
    "database_backups_log": "backup_id",
    "e_learning_assignments": "assignment_id",
    "e_learning_notes": "note_id",
    "e_learning_submissions": "submission_id",
    "exam_sessions": "exam_id",
    "expenses": "expense_id",
    "fees_structure": "fee_id",
    "grades": "grade_id",
    "guardians": "guardian_id",
    "inventory_items": "item_id",
    "inventory_movements": "movement_id",
    "library_books": "book_id",
    "library_issues": "issue_id",
    "master_receipts": "master_receipt_id",
    "ml_model_snapshots": "model_id",
    "offline_sync_events": "event_id",
    "online_payment_requests": "request_id",
    "payment_allocations": "allocation_id",
    "payments": "payment_id",
    "payroll_records": "payroll_id",
    "portal_update_events": "event_id",
    "pos_sale_items": "sale_item_id",
    "pos_sales": "sale_id",
    "pupil_fee_overrides": "override_id",
    "pupils": "pupil_id",
    "receipts": "receipt_id",
    "result_entries": "entry_id",
    "result_sheets": "result_id",
    "student_performance_predictions": "prediction_id",
    "subjects": "subject_id",
    "teacher_attendance_records": "attendance_id",
    "teacher_profiles": "profile_id",
    "term_bills": "bill_id",
    "textbook_loans": "loan_id",
    "website_announcements": "announcement_id",
    "users": "user_id",
}


MIGRATION_TABLES = [
    "users",
    "guardians",
    "grades",
    "classes",
    "pupils",
    "fees_structure",
    "payments",
    "payment_allocations",
    "master_receipts",
    "expenses",
    "receipts",
    "online_payment_requests",
    "academic_year",
    "school_settings",
    "term_bills",
    "pupil_fee_overrides",
    "balance_adjustments",
    "textbook_loans",
    "attendance_records",
    "subjects",
    "class_timetable_entries",
    "result_sheets",
    "result_entries",
    "communication_log",
    "portal_update_events",
    "audit_log",
    "teacher_profiles",
    "teacher_attendance_records",
    "exam_sessions",
    "library_books",
    "library_issues",
    "inventory_items",
    "inventory_movements",
    "pos_sales",
    "pos_sale_items",
    "offline_sync_events",
    "e_learning_notes",
    "e_learning_assignments",
    "e_learning_submissions",
    "ml_model_snapshots",
    "student_performance_predictions",
    "payroll_records",
    "database_backups_log",
    "website_announcements",
]


def is_postgres_url(value):
    return bool(value and value.lower().startswith(POSTGRES_SCHEMES))


def split_sql_script(script):
    statements = []
    current = []
    quote = None
    previous = ""
    for character in script:
        if character in {"'", '"'} and previous != "\\":
            quote = None if quote == character else character if quote is None else quote
        if character == ";" and quote is None:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(character)
        previous = character
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def replace_qmark_placeholders(sql):
    return replace_unquoted_sql(sql, lambda chunk: chunk.replace("?", "%s"))


def replace_unquoted_sql(sql, replacer):
    output = []
    chunk = []
    quote = None
    index = 0

    while index < len(sql):
        character = sql[index]
        if quote is None:
            if character in {"'", '"'}:
                if chunk:
                    output.append(replacer("".join(chunk)))
                    chunk = []
                quote = character
                output.append(character)
            else:
                chunk.append(character)
        elif character == quote:
            output.append(character)
            if index + 1 < len(sql) and sql[index + 1] == quote:
                output.append(sql[index + 1])
                index += 1
            else:
                quote = None
        else:
            output.append(character)
        index += 1

    if chunk:
        output.append(replacer("".join(chunk)))

    return "".join(output)


class CursorResult:
    def __init__(self, cursor=None, rows=None, lastrowid=None, rowcount=-1):
        self.cursor = cursor
        self.rows = rows
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def fetchone(self):
        if self.rows is not None:
            return self.rows.pop(0) if self.rows else None
        return self.cursor.fetchone()

    def fetchall(self):
        if self.rows is not None:
            rows = self.rows
            self.rows = []
            return rows
        return self.cursor.fetchall()

    def __iter__(self):
        return iter(self.fetchall())


class PostgresConnection:
    def __init__(self, url):
        if psycopg is None:
            raise RuntimeError(
                "PostgreSQL support requires psycopg. Run: pip install -r requirements.txt"
            )
        self.connection = psycopg.connect(url, row_factory=dict_row)

    def execute(self, sql, params=None):
        special = self._special_result(sql)
        if special is not None:
            return special

        translated_sql, returning_pk = self._translate(sql)
        if translated_sql is None:
            return CursorResult(rows=[])

        cursor = self.connection.cursor()
        cursor.execute(translated_sql, params or ())

        lastrowid = None
        if returning_pk:
            row = cursor.fetchone()
            if row:
                lastrowid = row.get(returning_pk)

        return CursorResult(cursor=cursor, lastrowid=lastrowid, rowcount=cursor.rowcount)

    def executemany(self, sql, rows):
        translated_sql, _returning_pk = self._translate(sql, force_no_returning=True)
        cursor = self.connection.cursor()
        cursor.executemany(translated_sql, rows)
        return CursorResult(cursor=cursor, rowcount=cursor.rowcount)

    def executescript(self, script):
        for statement in split_sql_script(script):
            self.execute(statement)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def table_columns(self, table_name):
        return [
            row["column_name"]
            for row in self.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            ).fetchall()
        ]

    def _special_result(self, sql):
        stripped = sql.strip().rstrip(";")
        table_info_match = re.fullmatch(r"PRAGMA\s+table_info\((\w+)\)", stripped, re.I)
        if table_info_match:
            rows = [{"name": column_name} for column_name in self.table_columns(table_info_match.group(1))]
            return CursorResult(rows=rows)
        if stripped.upper().startswith("PRAGMA "):
            return CursorResult(rows=[])
        return None

    def _translate(self, sql, force_no_returning=False):
        statement = sql.strip().rstrip(";")
        if not statement:
            return None, None
        if statement.upper().startswith("PRAGMA "):
            return None, None

        insert_or_ignore = bool(re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", statement, re.I))
        statement = re.sub(
            r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
            "BIGSERIAL PRIMARY KEY",
            statement,
            flags=re.I,
        )
        statement = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", statement, flags=re.I)
        statement = re.sub(r"\bdate\s*\(\s*'now'\s*\)", "CURRENT_DATE::text", statement, flags=re.I)
        statement = re.sub(r"\bdatetime\s*\(\s*'now'\s*\)", "CURRENT_TIMESTAMP::text", statement, flags=re.I)
        statement = replace_unquoted_sql(
            statement,
            lambda chunk: re.sub(r"\bLIKE\b", "ILIKE", chunk, flags=re.I),
        )
        statement = replace_unquoted_sql(
            statement,
            lambda chunk: re.sub(r"(\w+)\s+COLLATE\s+NOCASE", r"LOWER(\1)", chunk, flags=re.I),
        )
        statement = replace_qmark_placeholders(statement)

        returning_pk = None
        insert_match = re.match(r"\s*INSERT\s+INTO\s+(\w+)\b", statement, flags=re.I)
        if insert_match and "ON CONFLICT" not in statement.upper() and insert_or_ignore:
            statement = f"{statement} ON CONFLICT DO NOTHING"

        if insert_match and not force_no_returning and " RETURNING " not in statement.upper():
            table_name = insert_match.group(1)
            returning_pk = PRIMARY_KEYS.get(table_name)
            if returning_pk:
                statement = f"{statement} RETURNING {returning_pk}"

        return statement, returning_pk


def connect_postgres(url):
    return PostgresConnection(url)
