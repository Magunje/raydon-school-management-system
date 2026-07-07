from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from student_registry.models import Student
from student_registry.sync import sync_all_legacy_data


@login_required
def student_list_view(request):
    # Dynamically sync legacy sqlite data
    sync_all_legacy_data()

    students = Student.objects.all()
    rows = []
    for s in students:
        class_lbl = (
            f"{s.academic_class.form.name} {s.academic_class.stream.name}"
            if s.academic_class
            else "Unassigned"
        )
        rows.append(
            {
                "data": [
                    s.admission_no,
                    f"{s.first_name} {s.surname}",
                    s.gender,
                    s.date_of_birth.strftime("%Y-%m-%d"),
                    class_lbl,
                    s.status,
                ],
                "actions": [
                    {
                        "label": "Transition",
                        "href": f"/pupils/transition/{s.pk}",
                        "class": "btn-outline-primary",
                        "icon": "bi-arrow-right-short",
                    }
                ],
            }
        )
    return render(
        request,
        "erp_dashboard.html",
        {
            "title": "Student Registry & Lifecycle",
            "subtitle": "Managed student demographic profiles and lifecycle state machine transitions.",
            "headers": [
                "Admission No",
                "Full Name",
                "Gender",
                "Date of Birth",
                "Academic Class",
                "Lifecycle Status",
            ],
            "rows": rows,
            "has_actions": True,
            "create_href": "/pupils/register",
            "create_label": "Register Student",
        },
    )


@login_required
def student_transition_view(request, pk):
    """Allows administrators to transition students through lifecycle stages."""
    student = Student.objects.get(pk=pk)
    if request.method == "POST":
        target = request.POST.get("target_status")
        try:
            student.transition_to(target)
            messages.success(
                request, f"Successfully transitioned student to status '{target}'."
            )
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("/pupils")

    allowed = Student.ALLOWED_TRANSITIONS.get(student.status, [])
    return render(
        request,
        "students/transition.html",
        {"student": student, "allowed_transitions": allowed},
    )
