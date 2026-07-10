from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required

from accounts.permissions import permission_required
from human_resources.models import EmployeeProfile, LeaveApplication, Vacancy
from human_resources.services import employee_directory_queryset, hr_dashboard_metrics


@permission_required("hr.view")
def employee_list(request):
    queryset = employee_directory_queryset(request.GET)
    paginator = Paginator(queryset, int(request.GET.get("per_page") or 10))
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    metrics = hr_dashboard_metrics()

    context = {
        **metrics,
        "employees": page_obj.object_list,
        "page_obj": page_obj,
        "vacancies": Vacancy.objects.select_related("department_ref", "position").all().order_by("-created_at")[:12],
        "leave_applications": LeaveApplication.objects.select_related("employee").all().order_by("-start_date")[:12],
        "recent_employees": EmployeeProfile.objects.order_by("-created_at")[:8],
        "filters": request.GET,
        "departments": EmployeeProfile.objects.values_list("department", flat=True).distinct().order_by("department"),
        "positions": EmployeeProfile.objects.values_list("position", flat=True).distinct().order_by("position"),
        "category_choices": EmployeeProfile.CATEGORY_CHOICES,
        "employment_type_choices": EmployeeProfile.EMPLOYMENT_TYPE_CHOICES,
        "status_choices": EmployeeProfile.STATUS_CHOICES,
        "gender_choices": EmployeeProfile.objects.values_list("gender", flat=True).distinct().order_by("gender"),
        "total_departments": metrics.get("departments", 0),
        "total_positions": metrics.get("positions", 0),
    }
    return render(request, "human_resources/employee_list.html", context)


@permission_required("hr.view")
def employee_profile(request, employee_id):
    employee = get_object_or_404(
        EmployeeProfile.objects.select_related("department_ref", "position_ref", "supervisor").prefetch_related(
            "qualifications",
            "contracts",
            "leave_applications",
            "attendance_records",
            "performance_reviews",
            "documents",
        ),
        pk=employee_id,
    )
    return render(request, "human_resources/employee_profile.html", {"employee": employee})
