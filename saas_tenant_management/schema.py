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
        CREATE TABLE IF NOT EXISTS library_members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id integer NULL,
            staff_id integer NULL,
            card_number varchar(100) UNIQUE,
            barcode_path varchar(255) NULL,
            status varchar(40) NOT NULL DEFAULT 'Active',
            created_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id integer NOT NULL,
            pupil_id integer NULL,
            staff_id integer NULL,
            reserve_date text,
            status varchar(40) NOT NULL DEFAULT 'Pending',
            notification_sent integer DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_digital_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title varchar(255) NOT NULL,
            category varchar(80) NOT NULL,
            file_path varchar(255) NOT NULL,
            original_filename varchar(255),
            uploaded_by integer,
            uploaded_at text,
            allowed_roles varchar(255)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            daily_overdue_fine numeric NOT NULL DEFAULT 0.50,
            damaged_book_penalty numeric NOT NULL DEFAULT 5.00,
            lost_book_penalty numeric NOT NULL DEFAULT 15.00,
            max_books_allowed integer NOT NULL DEFAULT 3,
            borrow_duration_days integer NOT NULL DEFAULT 14
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostels (
            hostel_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostel_code varchar(50) UNIQUE NOT NULL,
            hostel_name varchar(100) NOT NULL,
            hostel_type varchar(40) NOT NULL,
            capacity integer NOT NULL DEFAULT 0,
            warden_id integer NULL,
            status varchar(40) NOT NULL DEFAULT 'Active'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number varchar(50) NOT NULL,
            hostel_id integer NOT NULL,
            floor integer NOT NULL DEFAULT 0,
            capacity integer NOT NULL DEFAULT 0,
            current_occupancy integer NOT NULL DEFAULT 0,
            status varchar(40) NOT NULL DEFAULT 'Available'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_beds (
            bed_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bed_number varchar(50) NOT NULL,
            room_id integer NOT NULL,
            status varchar(40) NOT NULL DEFAULT 'Available',
            current_occupant_id integer NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id integer NOT NULL,
            hostel_id integer NOT NULL,
            room_id integer NOT NULL,
            bed_id integer NOT NULL,
            boarding_date text,
            status varchar(40) NOT NULL DEFAULT 'Active',
            guardian_notified integer NOT NULL DEFAULT 0,
            fee_posted integer NOT NULL DEFAULT 0,
            created_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_transfers (
            transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id integer NOT NULL,
            previous_allocation_id integer NOT NULL,
            new_hostel_id integer NOT NULL,
            new_room_id integer NOT NULL,
            new_bed_id integer NOT NULL,
            reason text,
            transfer_date text,
            approved_by_id integer NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id integer NOT NULL,
            date text NOT NULL,
            time_slot varchar(50) NOT NULL,
            status varchar(40) NOT NULL,
            remarks text,
            recorded_by_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_discipline (
            discipline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id integer NOT NULL,
            incident_date text NOT NULL,
            incident_description text NOT NULL,
            action_taken varchar(100),
            staff_id integer NOT NULL,
            parent_notified integer NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_visitors (
            visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name varchar(180) NOT NULL,
            relationship varchar(100) NOT NULL,
            pupil_id integer NOT NULL,
            visit_date text NOT NULL,
            time_in text NOT NULL,
            time_out text,
            contact_number varchar(50) NOT NULL,
            approval_status varchar(40) NOT NULL DEFAULT 'Pending',
            approved_by_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_inventory (
            inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostel_id integer NOT NULL,
            room_id integer,
            item_name varchar(100) NOT NULL,
            quantity integer NOT NULL DEFAULT 0,
            status varchar(50) NOT NULL DEFAULT 'Good'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_fee_records (
            fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id integer NOT NULL,
            charge_type varchar(80) NOT NULL,
            amount numeric NOT NULL,
            date_charged text NOT NULL,
            status varchar(40) NOT NULL DEFAULT 'Unpaid'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_maintenance (
            maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostel_id integer NOT NULL,
            room_id integer NOT NULL,
            bed_id integer,
            issue_description text NOT NULL,
            reported_by_id integer NOT NULL,
            status varchar(40) NOT NULL DEFAULT 'Pending',
            reported_date text NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_notices (
            notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title varchar(150) NOT NULL,
            content text NOT NULL,
            published_date text NOT NULL,
            is_active integer NOT NULL DEFAULT 1
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
        CREATE TABLE IF NOT EXISTS library_members (
            member_id SERIAL PRIMARY KEY,
            pupil_id integer NULL,
            staff_id integer NULL,
            card_number varchar(100) UNIQUE,
            barcode_path varchar(255) NULL,
            status varchar(40) NOT NULL DEFAULT 'Active',
            created_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_reservations (
            reservation_id SERIAL PRIMARY KEY,
            book_id integer NOT NULL,
            pupil_id integer NULL,
            staff_id integer NULL,
            reserve_date text,
            status varchar(40) NOT NULL DEFAULT 'Pending',
            notification_sent integer DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_digital_resources (
            resource_id SERIAL PRIMARY KEY,
            title varchar(255) NOT NULL,
            category varchar(80) NOT NULL,
            file_path varchar(255) NOT NULL,
            original_filename varchar(255),
            uploaded_by integer,
            uploaded_at text,
            allowed_roles varchar(255)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS library_settings (
            setting_id SERIAL PRIMARY KEY,
            daily_overdue_fine numeric NOT NULL DEFAULT 0.50,
            damaged_book_penalty numeric NOT NULL DEFAULT 5.00,
            lost_book_penalty numeric NOT NULL DEFAULT 15.00,
            max_books_allowed integer NOT NULL DEFAULT 3,
            borrow_duration_days integer NOT NULL DEFAULT 14
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostels (
            hostel_id SERIAL PRIMARY KEY,
            hostel_code varchar(50) UNIQUE NOT NULL,
            hostel_name varchar(100) NOT NULL,
            hostel_type varchar(40) NOT NULL,
            capacity integer NOT NULL DEFAULT 0,
            warden_id integer NULL,
            status varchar(40) NOT NULL DEFAULT 'Active'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_rooms (
            room_id SERIAL PRIMARY KEY,
            room_number varchar(50) NOT NULL,
            hostel_id integer NOT NULL,
            floor integer NOT NULL DEFAULT 0,
            capacity integer NOT NULL DEFAULT 0,
            current_occupancy integer NOT NULL DEFAULT 0,
            status varchar(40) NOT NULL DEFAULT 'Available'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_beds (
            bed_id SERIAL PRIMARY KEY,
            bed_number varchar(50) NOT NULL,
            room_id integer NOT NULL,
            status varchar(40) NOT NULL DEFAULT 'Available',
            current_occupant_id integer NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_allocations (
            allocation_id SERIAL PRIMARY KEY,
            pupil_id integer NOT NULL,
            hostel_id integer NOT NULL,
            room_id integer NOT NULL,
            bed_id integer NOT NULL,
            boarding_date text,
            status varchar(40) NOT NULL DEFAULT 'Active',
            guardian_notified integer NOT NULL DEFAULT 0,
            fee_posted integer NOT NULL DEFAULT 0,
            created_at text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_transfers (
            transfer_id SERIAL PRIMARY KEY,
            pupil_id integer NOT NULL,
            previous_allocation_id integer NOT NULL,
            new_hostel_id integer NOT NULL,
            new_room_id integer NOT NULL,
            new_bed_id integer NOT NULL,
            reason text,
            transfer_date text,
            approved_by_id integer NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_attendance (
            attendance_id SERIAL PRIMARY KEY,
            pupil_id integer NOT NULL,
            date text NOT NULL,
            time_slot varchar(50) NOT NULL,
            status varchar(40) NOT NULL,
            remarks text,
            recorded_by_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_discipline (
            discipline_id SERIAL PRIMARY KEY,
            pupil_id integer NOT NULL,
            incident_date text NOT NULL,
            incident_description text NOT NULL,
            action_taken varchar(100),
            staff_id integer NOT NULL,
            parent_notified integer NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_visitors (
            visitor_id SERIAL PRIMARY KEY,
            visitor_name varchar(180) NOT NULL,
            relationship varchar(100) NOT NULL,
            pupil_id integer NOT NULL,
            visit_date text NOT NULL,
            time_in text NOT NULL,
            time_out text,
            contact_number varchar(50) NOT NULL,
            approval_status varchar(40) NOT NULL DEFAULT 'Pending',
            approved_by_id integer
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_inventory (
            inventory_id SERIAL PRIMARY KEY,
            hostel_id integer NOT NULL,
            room_id integer,
            item_name varchar(100) NOT NULL,
            quantity integer NOT NULL DEFAULT 0,
            status varchar(50) NOT NULL DEFAULT 'Good'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_fee_records (
            fee_id SERIAL PRIMARY KEY,
            pupil_id integer NOT NULL,
            charge_type varchar(80) NOT NULL,
            amount numeric NOT NULL,
            date_charged text NOT NULL,
            status varchar(40) NOT NULL DEFAULT 'Unpaid'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_maintenance (
            maintenance_id SERIAL PRIMARY KEY,
            hostel_id integer NOT NULL,
            room_id integer NOT NULL,
            bed_id integer,
            issue_description text NOT NULL,
            reported_by_id integer NOT NULL,
            status varchar(40) NOT NULL DEFAULT 'Pending',
            reported_date text NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hostel_notices (
            notice_id SERIAL PRIMARY KEY,
            title varchar(150) NOT NULL,
            content text NOT NULL,
            published_date text NOT NULL,
            is_active integer NOT NULL DEFAULT 1
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
    "CREATE INDEX IF NOT EXISTS idx_hostel_allocations_pupil ON hostel_allocations (pupil_id)",
    "CREATE INDEX IF NOT EXISTS idx_hostel_beds_room ON hostel_beds (room_id)",
    "CREATE INDEX IF NOT EXISTS idx_hostel_rooms_hostel ON hostel_rooms (hostel_id)",
    "CREATE INDEX IF NOT EXISTS idx_hostel_attendance_pupil_date ON hostel_attendance (pupil_id, date)",
]


def _ensure_column(cursor, table_name, column_name, column_type, vendor="sqlite"):
    try:
        if vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
                """,
                [table_name, column_name],
            )
            exists = cursor.fetchone() is not None
        else:
            cursor.execute(f"PRAGMA table_info({table_name})")
            exists = any(row[1] == column_name for row in cursor.fetchall())
            
        if not exists:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
    except Exception:
        pass


def ensure_schema_with_cursor(cursor, vendor="sqlite"):
    for statement in portal_schema_sql(vendor):
        cursor.execute(statement)
    for statement in PORTAL_SCHEMA_INDEXES:
        cursor.execute(statement)

    # Ensure extra columns exist on library_books
    _ensure_column(cursor, "library_books", "publisher", "varchar(180) NULL", vendor)
    _ensure_column(cursor, "library_books", "publication_year", "integer NULL", vendor)
    _ensure_column(cursor, "library_books", "subject", "varchar(120) NULL", vendor)
    _ensure_column(cursor, "library_books", "edition", "varchar(80) NULL", vendor)
    _ensure_column(cursor, "library_books", "shelf_location", "varchar(80) NULL", vendor)
    
    # Ensure extra columns exist on library_issues
    _ensure_column(cursor, "library_issues", "staff_id", "integer NULL", vendor)
    _ensure_column(cursor, "library_issues", "librarian_id", "integer NULL", vendor)
    _ensure_column(cursor, "library_issues", "return_librarian_id", "integer NULL", vendor)
    _ensure_column(cursor, "library_issues", "book_condition", "varchar(40) NULL", vendor)
    _ensure_column(cursor, "library_issues", "fine_amount", "numeric NOT NULL DEFAULT 0", vendor)
    _ensure_column(cursor, "library_issues", "fine_paid", "integer NOT NULL DEFAULT 0", vendor)



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
