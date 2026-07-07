import sqlite3


PORTAL_SCHEMA_VERSION = 1


def _sqlite_table_sql():
    return [
        """
        CREATE TABLE IF NOT EXISTS library_books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title varchar(180) NOT NULL,
            author varchar(180),
            isbn varchar(80),
            category varchar(80),
            total_copies integer NOT NULL DEFAULT 1,
            available_copies integer NOT NULL DEFAULT 1,
            fine_per_day numeric NOT NULL DEFAULT 0,
            status varchar(40) NOT NULL DEFAULT 'Active'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS textbook_loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id integer NOT NULL,
            book_id integer NULL,
            book_name varchar(180),
            borrowed_date text,
            return_date text,
            status varchar(40) NOT NULL DEFAULT 'Borrowed',
            notes text,
            cleared_date text,
            recorded_by integer,
            cleared_by integer,
            created_at text,
            updated_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_issues (
            issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id integer NOT NULL,
            pupil_id integer,
            issue_date text,
            due_date text,
            return_date text,
            status varchar(40) NOT NULL DEFAULT 'Borrowed',
            notes text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name varchar(255) NOT NULL,
            category varchar(100),
            quantity numeric NOT NULL DEFAULT 0,
            unit varchar(50),
            location varchar(100),
            reorder_level numeric DEFAULT 0,
            sku varchar(100),
            sale_price numeric NOT NULL DEFAULT 0,
            is_sellable varchar(20) DEFAULT '1',
            notes text,
            created_at text,
            updated_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory_movements (
            movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id integer NOT NULL,
            movement_type varchar(50) NOT NULL,
            quantity numeric NOT NULL,
            movement_date text,
            reference_no varchar(100),
            notes text,
            recorded_by integer,
            created_at text,
            sale_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pos_sales (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no varchar(100) NOT NULL,
            sale_date text NOT NULL,
            customer_name varchar(255),
            pupil_id integer,
            payment_method varchar(100),
            reference_no varchar(100),
            total_amount numeric NOT NULL DEFAULT 0,
            notes text,
            recorded_by integer,
            created_at text,
            master_receipt_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pos_sale_items (
            sale_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id integer NOT NULL,
            item_id integer NOT NULL,
            item_name varchar(255) NOT NULL,
            quantity numeric NOT NULL,
            unit_price numeric NOT NULL,
            line_total numeric NOT NULL
        )
        """,
    ]


def _postgres_table_sql():
    return [
        """
        CREATE TABLE IF NOT EXISTS library_books (
            book_id SERIAL PRIMARY KEY,
            title varchar(180) NOT NULL,
            author varchar(180),
            isbn varchar(80),
            category varchar(80),
            total_copies integer NOT NULL DEFAULT 1,
            available_copies integer NOT NULL DEFAULT 1,
            fine_per_day numeric NOT NULL DEFAULT 0,
            status varchar(40) NOT NULL DEFAULT 'Active'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS textbook_loans (
            loan_id SERIAL PRIMARY KEY,
            pupil_id integer NOT NULL,
            book_id integer NULL,
            book_name varchar(180),
            borrowed_date text,
            return_date text,
            status varchar(40) NOT NULL DEFAULT 'Borrowed',
            notes text,
            cleared_date text,
            recorded_by integer,
            cleared_by integer,
            created_at text,
            updated_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_issues (
            issue_id SERIAL PRIMARY KEY,
            book_id integer NOT NULL,
            pupil_id integer,
            issue_date text,
            due_date text,
            return_date text,
            status varchar(40) NOT NULL DEFAULT 'Borrowed',
            notes text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory_items (
            item_id SERIAL PRIMARY KEY,
            item_name varchar(255) NOT NULL,
            category varchar(100),
            quantity numeric NOT NULL DEFAULT 0,
            unit varchar(50),
            location varchar(100),
            reorder_level numeric DEFAULT 0,
            sku varchar(100),
            sale_price numeric NOT NULL DEFAULT 0,
            is_sellable varchar(20) DEFAULT '1',
            notes text,
            created_at text,
            updated_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory_movements (
            movement_id SERIAL PRIMARY KEY,
            item_id integer NOT NULL,
            movement_type varchar(50) NOT NULL,
            quantity numeric NOT NULL,
            movement_date text,
            reference_no varchar(100),
            notes text,
            recorded_by integer,
            created_at text,
            sale_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pos_sales (
            sale_id SERIAL PRIMARY KEY,
            receipt_no varchar(100) NOT NULL,
            sale_date text NOT NULL,
            customer_name varchar(255),
            pupil_id integer,
            payment_method varchar(100),
            reference_no varchar(100),
            total_amount numeric NOT NULL DEFAULT 0,
            notes text,
            recorded_by integer,
            created_at text,
            master_receipt_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pos_sale_items (
            sale_item_id SERIAL PRIMARY KEY,
            sale_id integer NOT NULL,
            item_id integer NOT NULL,
            item_name varchar(255) NOT NULL,
            quantity numeric NOT NULL,
            unit_price numeric NOT NULL,
            line_total numeric NOT NULL
        )
        """,
    ]


def portal_schema_sql(vendor):
    if vendor == "postgresql":
        return _postgres_table_sql()
    return _sqlite_table_sql()


PORTAL_SCHEMA_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_library_books_title ON library_books (title)",
    "CREATE INDEX IF NOT EXISTS idx_textbook_loans_pupil_id ON textbook_loans (pupil_id)",
    "CREATE INDEX IF NOT EXISTS idx_textbook_loans_book_id ON textbook_loans (book_id)",
    "CREATE INDEX IF NOT EXISTS idx_library_issues_book_id ON library_issues (book_id)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_items_name ON inventory_items (item_name)",
    "CREATE INDEX IF NOT EXISTS idx_pos_sales_receipt ON pos_sales (receipt_no)",
    "CREATE INDEX IF NOT EXISTS idx_pos_sale_items_sale ON pos_sale_items (sale_id)",
]


def ensure_schema_with_cursor(cursor, vendor="sqlite"):
    for statement in portal_schema_sql(vendor):
        cursor.execute(statement)
    for statement in PORTAL_SCHEMA_INDEXES:
        cursor.execute(statement)


def _table_exists(cursor, table_name):
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def _columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _clean_text(value):
    return " ".join(str(value or "").strip().split())


def _grade_number(grade=None, grade_id=None):
    text = str(grade or grade_id or "")
    digits = "".join(ch if ch.isdigit() else " " for ch in text).split()
    return int(digits[0]) if digits else None


def _stream_from_class_name(class_name, grade_id=None):
    text = _clean_text(class_name)
    number = _grade_number(grade_id=grade_id)
    if not text or not number:
        return text
    lowered = text.lower()
    for prefix in (f"form {number}", f"grade {number}", str(number)):
        if lowered.startswith(prefix):
            return _clean_text(text[len(prefix):])
    compact_prefix = str(number)
    if lowered.startswith(compact_prefix) and len(text) > len(compact_prefix):
        return _clean_text(text[len(compact_prefix):])
    return text


def _stream_candidates(class_name, grade_id=None):
    raw = _clean_text(class_name)
    stream = _stream_from_class_name(class_name, grade_id)
    number = _grade_number(grade_id=grade_id)
    values = [raw, stream]
    if number and stream:
        values.extend([f"Form {number} {stream}", f"{number}{stream}", f"{number} {stream}"])
    return sorted({value.upper() for value in values if value})


def _grade_candidates(grade_id=None):
    number = _grade_number(grade_id=grade_id)
    values = [grade_id]
    if number:
        values.extend([str(number), f"Form {number}", f"Grade {number}"])
    return sorted({str(value).strip().upper() for value in values if str(value or "").strip()})


def _ensure_sqlite_student_class_links(cursor):
    required = {"pupils", "classes"}
    if any(not _table_exists(cursor, table) for table in required):
        return

    pupil_cols = _columns(cursor, "pupils")
    class_cols = _columns(cursor, "classes")
    needed_pupil_cols = {"class_id", "grade_id", "grade", "class_stream", "status"}
    needed_class_cols = {"class_id", "class_name", "grade_id"}
    if not needed_pupil_cols.issubset(pupil_cols) or not needed_class_cols.issubset(class_cols):
        return

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pupils_status_class_id ON pupils (status, class_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pupils_status_grade_stream ON pupils (status, grade_id, class_stream)")
    if _table_exists(cursor, "student_subjects"):
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_subjects_lookup ON student_subjects (pupil_id, subject_id, academic_year)")
    if _table_exists(cursor, "result_sheets"):
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_sheets_pupil_term_year ON result_sheets (pupil_id, term, year)")
    if _table_exists(cursor, "attendance_records"):
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_records_pupil_date ON attendance_records (pupil_id, attendance_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_records_class_date ON attendance_records (class_id, attendance_date)")

    order_by = "academic_year DESC, class_id" if "academic_year" in class_cols else "class_id"
    cursor.execute(f"SELECT class_id, class_name, grade_id FROM classes ORDER BY {order_by}")
    for class_id, class_name, grade_id in cursor.fetchall():
        stream_values = _stream_candidates(class_name, grade_id)
        grade_values = _grade_candidates(grade_id)
        if not stream_values or not grade_values:
            continue
        stream_placeholders = ", ".join(["?"] * len(stream_values))
        grade_placeholders = ", ".join(["?"] * len(grade_values))
        cursor.execute(
            f"""
            UPDATE pupils
            SET class_id = ?
            WHERE status = 'Active'
              AND (class_id IS NULL OR class_id = '' OR class_id NOT IN (SELECT class_id FROM classes))
              AND (
                    grade_id = ?
                    OR UPPER(TRIM(COALESCE(grade, ''))) IN ({grade_placeholders})
                  )
              AND UPPER(TRIM(COALESCE(class_stream, ''))) IN ({stream_placeholders})
            """,
            [class_id, grade_id] + grade_values + stream_values,
        )

    if _table_exists(cursor, "registry_students") and _table_exists(cursor, "academic_classes"):
        registry_cols = _columns(cursor, "registry_students")
        if {"admission_no", "academic_class_id"}.issubset(registry_cols) and "admission_no" in pupil_cols:
            cursor.execute(
                """
                UPDATE registry_students
                SET academic_class_id = (
                    SELECT p.class_id
                    FROM pupils p
                    WHERE p.admission_no = registry_students.admission_no
                      AND p.class_id IS NOT NULL
                    LIMIT 1
                )
                WHERE EXISTS (
                    SELECT 1
                    FROM pupils p
                    JOIN academic_classes ac ON ac.id = p.class_id
                    WHERE p.admission_no = registry_students.admission_no
                      AND p.class_id IS NOT NULL
                      AND (registry_students.academic_class_id IS NULL OR registry_students.academic_class_id != p.class_id)
                )
                """
            )


def ensure_sqlite_tenant_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        ensure_schema_with_cursor(cursor, vendor="sqlite")
        _ensure_sqlite_student_class_links(cursor)
        conn.commit()
    finally:
        conn.close()
