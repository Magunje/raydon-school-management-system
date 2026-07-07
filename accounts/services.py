import re

from django.db import connection, transaction

from school_system_django.native import dict_rows, one_row, qn, table_columns, table_exists


STAFF_NUMBER_PREFIX = "AS"
NON_STAFF_ROLES = {"Parent", "Student"}


def has_staff_admission_column():
    return table_exists("users") and "admission_no" in table_columns("users")


def is_staff_role(role):
    return (role or "").strip() not in NON_STAFF_ROLES


def _staff_number_value(value):
    match = re.fullmatch(rf"{STAFF_NUMBER_PREFIX}(\d+)", str(value or "").strip().upper())
    return int(match.group(1)) if match else 0


def _highest_staff_number():
    rows = dict_rows(
        "SELECT admission_no FROM users WHERE admission_no IS NOT NULL AND UPPER(admission_no) LIKE %s",
        [f"{STAFF_NUMBER_PREFIX}%"],
    )
    return max((_staff_number_value(row.get("admission_no")) for row in rows), default=0)


def next_staff_admission_no(start=None):
    if not has_staff_admission_column():
        return ""
    number = int(start or _highest_staff_number())
    while True:
        number += 1
        candidate = f"{STAFF_NUMBER_PREFIX}{number:03d}"
        if not one_row("SELECT user_id FROM users WHERE UPPER(admission_no) = %s", [candidate]):
            return candidate


def ensure_existing_staff_admission_numbers():
    if not has_staff_admission_column():
        return 0
    rows = dict_rows(
        """
        SELECT user_id
        FROM users
        WHERE COALESCE(role, '') NOT IN ('Parent', 'Student')
          AND (admission_no IS NULL OR TRIM(CAST(admission_no AS TEXT)) = '')
        ORDER BY user_id
        """
    )
    if not rows:
        return 0
    current = _highest_staff_number()
    assigned = 0
    with transaction.atomic():
        with connection.cursor() as cursor:
            for row in rows:
                while True:
                    current += 1
                    candidate = f"{STAFF_NUMBER_PREFIX}{current:03d}"
                    if not one_row("SELECT user_id FROM users WHERE UPPER(admission_no) = %s", [candidate]):
                        break
                cursor.execute(
                    f"UPDATE {qn('users')} SET {qn('admission_no')} = %s WHERE {qn('user_id')} = %s",
                    [candidate, row["user_id"]],
                )
                assigned += 1
    return assigned


def admission_no_for_user_save(existing_user=None, role=None):
    if not has_staff_admission_column():
        return None
    if not is_staff_role(role):
        return None
    existing = (existing_user or {}).get("admission_no")
    if existing:
        return str(existing).strip().upper()
    return next_staff_admission_no()
