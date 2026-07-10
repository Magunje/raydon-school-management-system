from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from human_resources.models import (
    Applicant,
    Department,
    EmployeeProfile,
    EmploymentContract,
    HRAuditLog,
    LeaveApplication,
    LeaveBalance,
    Position,
    StaffAttendanceRecord,
    Vacancy,
)


def next_hr_number(prefix, model):
    return f"{prefix}-{model.objects.count() + 1:05d}"


def next_employee_number():
    year = timezone.localdate().year
    prefix = f"EMP-{year}-"
    latest = EmployeeProfile.objects.filter(employee_number__startswith=prefix).order_by("-employee_number").first()
    if not latest:
        return f"{prefix}0001"
    try:
        number = int(latest.employee_number.rsplit("-", 1)[-1]) + 1
    except ValueError:
        number = 1
    return f"{prefix}{number:04d}"


def log_hr_action(action, reference_number=None, user=None, new_value=None, reason=None):
    return HRAuditLog.objects.create(
        action=action,
        reference_number=reference_number,
        user=user,
        new_value=new_value,
        reason=reason,
    )


def create_employee(**kwargs):
    kwargs.setdefault("employee_number", next_employee_number())
    employee = EmployeeProfile.objects.create(**kwargs)
    if employee.employee_category in {"TEACHER", "ACADEMIC", "HOD"}:
        create_teacher_extension(employee)
    log_hr_action(
        "Employee creation",
        reference_number=employee.employee_number,
        new_value={"name": employee.full_name, "department": employee.department},
    )
    return employee


def create_teacher_extension(employee, legacy_profile_id=None, **kwargs):
    from teachers.models import TeacherEmployeeProfile

    extension, _ = TeacherEmployeeProfile.objects.update_or_create(
        employee=employee,
        defaults={
            "legacy_profile_id": legacy_profile_id,
            "teaching_subjects": kwargs.get("teaching_subjects") or employee.teaching_subjects,
            "assigned_classes": kwargs.get("assigned_classes") or employee.assigned_classes,
            "workload_notes": kwargs.get("workload_notes"),
            "professional_registration": kwargs.get("professional_registration") or employee.professional_registration_number,
            "teaching_experience_years": employee.years_of_experience,
        },
    )
    log_hr_action(
        "Teacher employee linking",
        reference_number=employee.employee_number,
        new_value={"legacy_profile_id": legacy_profile_id},
    )
    return extension


def employee_directory_queryset(params=None):
    params = params or {}
    qs = EmployeeProfile.objects.select_related("department_ref", "position_ref", "supervisor").order_by("surname", "first_name")
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(employee_number__icontains=q)
            | Q(first_name__icontains=q)
            | Q(middle_name__icontains=q)
            | Q(surname__icontains=q)
            | Q(email__icontains=q)
            | Q(phone_number__icontains=q)
            | Q(national_id__icontains=q)
        )
    for field in ["department", "position", "employee_category", "employment_type", "status", "gender"]:
        value = (params.get(field) or "").strip()
        if value:
            qs = qs.filter(**{field: value})
    return qs


def hr_dashboard_metrics():
    today = timezone.localdate()
    month_start = today.replace(day=1)
    employees = EmployeeProfile.objects.all()
    return {
        "total_employees": employees.count(),
        "active_employees": employees.filter(status="ACTIVE").count(),
        "on_leave": employees.filter(status="ON_LEAVE").count(),
        "open_vacancies": Vacancy.objects.filter(status="OPEN").count(),
        "new_employees": employees.filter(employment_date__gte=month_start).count(),
        "pending_leave": LeaveApplication.objects.filter(status__in=["SUBMITTED", "PENDING", "SUPERVISOR_APPROVED"]).count(),
        "contracts_expiring": contract_expiry_alerts(days=30).count(),
        "pending_appraisals": employees.filter(performance_reviews__isnull=True, status="ACTIVE").count(),
        "departments": Department.objects.filter(status="ACTIVE").count(),
        "positions": Position.objects.filter(status="ACTIVE").count(),
        "employees_by_department": list(employees.values("department").annotate(total=Count("id")).order_by("department")),
        "employees_by_category": list(employees.values("employee_category").annotate(total=Count("id")).order_by("employee_category")),
        "employees_by_status": list(employees.values("status").annotate(total=Count("id")).order_by("status")),
        "gender_distribution": list(employees.values("gender").annotate(total=Count("id")).order_by("gender")),
    }


def create_contract(employee, contract_type, start_date, end_date=None, renewal_date=None, document=None):
    contract = EmploymentContract.objects.create(
        employee=employee,
        contract_number=next_hr_number("CTR", EmploymentContract),
        contract_type=contract_type,
        start_date=start_date,
        end_date=end_date,
        renewal_date=renewal_date,
        document=document,
    )
    log_hr_action(
        "Contract changes",
        reference_number=contract.contract_number,
        new_value={"employee": employee.employee_number, "contract_type": contract_type},
    )
    return contract


def contract_expiry_alerts(days=30):
    today = timezone.localdate()
    limit = today + timezone.timedelta(days=days)
    return EmploymentContract.objects.filter(
        status="ACTIVE",
        end_date__isnull=False,
        end_date__gte=today,
        end_date__lte=limit,
    )


def apply_leave(employee, leave_type, start_date, end_date, days_requested, reason=None):
    balance = LeaveBalance.objects.filter(employee=employee, leave_type=leave_type).first()
    application = LeaveApplication.objects.create(
        application_number=next_hr_number("LV", LeaveApplication),
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days_requested=days_requested,
        reason=reason,
        remaining_leave_balance=balance.remaining_days if balance else None,
    )
    log_hr_action(
        "Leave application",
        reference_number=application.application_number,
        new_value={"employee": employee.employee_number, "days": str(days_requested)},
        reason=reason,
    )
    return application


@transaction.atomic
def approve_leave(application, stage, approved_by, notes=None):
    if stage == "SUPERVISOR":
        application.status = "SUPERVISOR_APPROVED"
        application.supervisor_approved_by = approved_by
    elif stage == "HR":
        if application.status != "SUPERVISOR_APPROVED":
            raise ValidationError("Supervisor approval is required before HR approval.")
        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            employee=application.employee,
            leave_type=application.leave_type,
            defaults={"allocated_days": Decimal("0.00"), "used_days": Decimal("0.00")},
        )
        if application.leave_type != "UNPAID" and balance.remaining_days < application.days_requested:
            raise ValidationError("Insufficient leave balance.")
        balance.used_days += application.days_requested
        balance.save(update_fields=["used_days"])
        application.status = "HR_APPROVED"
        application.hr_approved_by = approved_by
        application.employee.status = "ON_LEAVE"
        application.employee.save(update_fields=["status"])
    else:
        raise ValidationError("Unsupported leave approval stage.")
    application.save()
    log_hr_action(
        "Leave approvals",
        reference_number=application.application_number,
        user=approved_by,
        new_value={"stage": stage, "status": application.status},
        reason=notes,
    )
    return application


def record_attendance(employee, attendance_date, clock_in=None, clock_out=None, late_minutes=0, overtime_hours=Decimal("0.00"), absent=False, biometric_reference=None):
    status = "ABSENT" if absent else ("LATE" if late_minutes else "PRESENT")
    attendance, _ = StaffAttendanceRecord.objects.update_or_create(
        employee=employee,
        attendance_date=attendance_date,
        defaults={
            "clock_in": clock_in,
            "clock_out": clock_out,
            "status": status,
            "late_minutes": late_minutes,
            "overtime_hours": overtime_hours,
            "absent": absent,
            "biometric_reference": biometric_reference,
        },
    )
    log_hr_action(
        "Attendance tracking",
        reference_number=f"{employee.employee_number}-{attendance_date}",
        new_value={"late_minutes": late_minutes, "overtime_hours": str(overtime_hours), "absent": absent},
    )
    return attendance
