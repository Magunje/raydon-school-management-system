from django.contrib.auth.decorators import login_required

from accounts.permissions import permission_required
from school_system_django.native import delete_record, render_detail_page, render_record_form_page, render_table_page


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


@permission_required("guardians.manage")
def parents(request):
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
