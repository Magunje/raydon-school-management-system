from django.db import connection, transaction

from accounts.permissions import permission_required
from school_system_django.native import (
    dict_rows,
    delete_record,
    now_text,
    qn,
    render_detail_page,
    render_record_form_page,
    render_table_page,
    table_columns,
    table_exists,
)


GUARDIAN_FIELDS = [
    "full_name",
    "relationship",
    "phone_number",
    "alternative_phone",
    "email",
    "address",
    "occupation",
    "emergency_contact",
    "emergency_phone",
]


def _guardian_key(name, phone):
    return ((name or "").strip().lower(), (phone or "").strip())


def sync_guardians_from_pupils():
    if not table_exists("guardians") or not table_exists("pupils"):
        return 0

    guardian_columns = set(table_columns("guardians"))
    pupil_columns = set(table_columns("pupils"))
    if not {"full_name", "phone_number"}.issubset(guardian_columns):
        return 0
    if not {"pupil_id", "guardian_name", "guardian_phone"}.issubset(pupil_columns):
        return 0

    existing = {}
    for guardian in dict_rows("SELECT guardian_id, full_name, phone_number FROM guardians"):
        key = _guardian_key(guardian.get("full_name"), guardian.get("phone_number"))
        if key[0] and key[1] and key not in existing:
            existing[key] = guardian["guardian_id"]

    pupils = dict_rows(
        """
        SELECT pupil_id, guardian_id, guardian_name, guardian_phone, address
        FROM pupils
        WHERE TRIM(COALESCE(guardian_name, '')) != ''
          AND TRIM(COALESCE(guardian_phone, '')) != ''
        """
    )
    if not pupils:
        return 0

    insert_columns = ["full_name", "relationship", "phone_number"]
    optional_values = {
        "address": lambda pupil: pupil.get("address") or "",
        "created_at": lambda pupil: now_text(),
    }
    for column in optional_values:
        if column in guardian_columns:
            insert_columns.append(column)

    created = 0
    with transaction.atomic():
        for pupil in pupils:
            key = _guardian_key(pupil.get("guardian_name"), pupil.get("guardian_phone"))
            if not key[0] or not key[1]:
                continue

            guardian_id = existing.get(key)
            if not guardian_id:
                values = {
                    "full_name": pupil.get("guardian_name").strip(),
                    "relationship": "Guardian",
                    "phone_number": pupil.get("guardian_phone").strip(),
                }
                for column, value_func in optional_values.items():
                    if column in guardian_columns:
                        values[column] = value_func(pupil)

                placeholders = ", ".join(["%s"] * len(insert_columns))
                quoted_columns = ", ".join(qn(column) for column in insert_columns)
                if connection.vendor == "postgresql":
                    sql = f"INSERT INTO {qn('guardians')} ({quoted_columns}) VALUES ({placeholders}) RETURNING guardian_id"
                    with connection.cursor() as cursor:
                        cursor.execute(sql, [values[column] for column in insert_columns])
                        result = cursor.fetchone()
                        guardian_id = result[0] if result else None
                else:
                    sql = f"INSERT INTO {qn('guardians')} ({quoted_columns}) VALUES ({placeholders})"
                    with connection.cursor() as cursor:
                        cursor.execute(sql, [values[column] for column in insert_columns])
                        guardian_id = getattr(cursor, "lastrowid", None)
                if guardian_id:
                    existing[key] = guardian_id
                    created += 1

            if guardian_id and "guardian_id" in pupil_columns and pupil.get("guardian_id") != guardian_id:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {qn('pupils')} SET {qn('guardian_id')} = %s WHERE {qn('pupil_id')} = %s",
                        [guardian_id, pupil["pupil_id"]],
                    )

    return created


@permission_required("guardians.manage")
def parents(request):
    sync_guardians_from_pupils()
    return render_table_page(
        request,
        "Parent and Guardian Contacts",
        "guardians",
        ["full_name", "relationship", "phone_number", "alternative_phone", "email", "emergency_contact"],
        "Parent registration, contacts, and emergency details.",
        order_by="full_name",
        search_columns=["full_name", "phone_number", "email"],
        pk_column="guardian_id",
        create_href="/guardians/new",
        create_label="Register Guardian",
        row_actions=[
            {"label": "View", "href": "/guardians/{guardian_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/guardians/{guardian_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/guardians/{guardian_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this guardian?"},
        ],
    )


@permission_required("guardians.manage")
def detail(request, guardian_id):
    return render_detail_page(request, "Guardian Profile", "guardians", "guardian_id", guardian_id)


@permission_required("guardians.manage")
def new(request):
    return render_record_form_page(
        request,
        "Register Guardian",
        "guardians",
        GUARDIAN_FIELDS,
        subtitle="Parent and guardian contact details.",
        redirect_to="/guardians",
    )


@permission_required("guardians.manage")
def edit(request, guardian_id):
    return render_record_form_page(
        request,
        "Edit Guardian",
        "guardians",
        GUARDIAN_FIELDS,
        pk_column="guardian_id",
        pk_value=guardian_id,
        redirect_to=f"/guardians/{guardian_id}",
    )


@permission_required("guardians.manage")
def delete(request, guardian_id):
    return delete_record(request, "Guardian", "guardians", "guardian_id", guardian_id, "/guardians")


def portal(request):
    from django.shortcuts import redirect

    return redirect("portal_login")

# Create your views here.
