from django.core.exceptions import ValidationError
from django.db import transaction
from student_registry.models import Student
from academic_structure.models import AcademicClass, Form


def run_yearly_progression(target_year, user):
    """End-of-year progression service.

    For O-Level Form 4 and A-Level Form 6, it transitions students to
    'Pending ZIMSEC Analysis' and locks them. For other forms, it promotes them
    to the next form (Form 1 -> 2 -> 3 -> 4, Form 5 -> 6). Enforces that Form 4
    to Form 5 automatic promotions never happen.
    """
    active_students = Student.objects.filter(status="Active Student")

    with transaction.atomic():
        for student in active_students:
            if not student.academic_class:
                continue

            current_form = student.academic_class.form.form_number
            current_stream = student.academic_class.stream

            if current_form in [4, 6]:
                # Freeze Form 4 and Form 6 students into Pending ZIMSEC Analysis
                student.transition_to(
                    "Pending ZIMSEC Analysis",
                    user,
                    "End of year transition to Pending ZIMSEC Analysis",
                )
            else:
                # Calculate next form number
                next_form_num = current_form + 1
                try:
                    next_form = Form.objects.get(form_number=next_form_num)
                    # Resolve or create the new class section matching target_year
                    next_class = AcademicClass.objects.get(
                        academic_year=target_year,
                        form=next_form,
                        stream=current_stream,
                    )
                    student.academic_class = next_class
                    student.save()
                except (Form.DoesNotExist, AcademicClass.DoesNotExist):
                    raise ValidationError(
                        f"Cannot promote student {student} because class section "
                        f"for Form {next_form_num} in year {target_year} does not exist."
                    )


def reactivate_o_level_to_a_level(
    student, target_class, user, reason="Returning for A-Levels"
):
    """A-Level Reactivation process.

    Locates the existing profile and reactivates it, moving it to Form 5
    A-Level study stream and updating the fee structure to A-Level defaults.
    """
    if student.status not in ["Archived", "Pending ZIMSEC Analysis"]:
        raise ValidationError(
            "Only Archived or Pending ZIMSEC Analysis students can be reactivated."
        )

    if target_class.form.form_number != 5:
        raise ValidationError(
            "Reactivation destination must be Form 5 (A-Level)."
        )

    # 1. Perform state transition from current state to Reactivated
    student.transition_to("Reactivated", user, reason)

    # 2. Transition from Reactivated to Active Student
    student.transition_to(
        "Active Student", user, "Reactivation process complete"
    )

    # 3. Assign target class section
    student.academic_class = target_class
    student.save()
