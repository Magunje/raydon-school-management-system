from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import payroll_required
from accounts.permissions import permission_required

from .forms import (
    EmployeePayrollProfileForm,
    PayrollAdjustmentForm,
    PayrollFilterForm,
    PayrollProcessForm,
    PayrollReportForm,
    PayrollRunForm,
)
from .models import EmployeePayrollProfile, PayrollAdjustment, PayrollPeriod, PayrollRun
from .services import (
    add_adjustment,
    build_bank_export,
    build_period_payslips_pdf,
    build_payslip_pdf,
    delete_adjustment,
    get_or_create_payslip,
    payroll_summary,
    payslip_lines,
    process_period,
    transition_period,
    update_run_adjustments,
)


@payroll_required
def dashboard(request):
    process_form = PayrollProcessForm()
    periods = (
        PayrollPeriod.objects.annotate(
            employee_count=Count("runs"),
            gross_total=Sum("runs__gross_salary"),
            deduction_total=Sum("runs__total_deductions"),
            net_total=Sum("runs__net_salary"),
        )
        .order_by("-year", "-month")[:18]
    )
    stats = {
        "active_profiles": EmployeePayrollProfile.objects.filter(employment_status="Active").count(),
        "profiles": EmployeePayrollProfile.objects.count(),
        "periods": PayrollPeriod.objects.count(),
        "latest_net": periods[0].net_total if periods else 0,
    }
    return render(request, "payroll/dashboard.html", {"process_form": process_form, "periods": periods, "stats": stats})


@permission_required("payroll.process")
def process_payroll(request):
    if request.method != "POST":
        return redirect("payroll:dashboard")
    form = PayrollProcessForm(request.POST)
    if form.is_valid():
        period_value = form.cleaned_data["period"]
        try:
            period, created_count = process_period(
                year=period_value["year"],
                month=period_value["month"],
                user=request.user,
                copy_previous=form.cleaned_data["copy_previous"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("payroll:dashboard")
        messages.success(request, f"{period.period_code} payroll processed. {created_count} employee(s) loaded.")
        return redirect("payroll:period_detail", period_id=period.id)
    messages.error(request, "Select a valid payroll month.")
    return redirect("payroll:dashboard")


@payroll_required
def profile_list(request):
    query = (request.GET.get("q") or "").strip()
    profiles = EmployeePayrollProfile.objects.all()
    if query:
        profiles = profiles.filter(full_name__icontains=query) | profiles.filter(employee_number__icontains=query) | profiles.filter(department__icontains=query)
    paginator = Paginator(profiles.order_by("full_name"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "payroll/profile_list.html", {"page": page, "q": query})


@permission_required("payroll.process")
def profile_create(request):
    form = EmployeePayrollProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        from .services import create_audit
        from .models import PayrollAuditAction

        create_audit(PayrollAuditAction.PROFILE_CREATED, actor=request.user, details=f"Payroll profile created for {profile.employee_number}.")
        messages.success(request, "Payroll profile saved.")
        return redirect("payroll:profile_list")
    return render(request, "payroll/profile_form.html", {"form": form, "profile": None})


@permission_required("payroll.process")
def profile_edit(request, profile_id):
    profile = get_object_or_404(EmployeePayrollProfile, pk=profile_id)
    form = EmployeePayrollProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        from .services import create_audit
        from .models import PayrollAuditAction

        create_audit(PayrollAuditAction.PROFILE_UPDATED, actor=request.user, details=f"Payroll profile updated for {profile.employee_number}.")
        messages.success(request, "Payroll profile updated.")
        return redirect("payroll:profile_list")
    return render(request, "payroll/profile_form.html", {"form": form, "profile": profile})


@payroll_required
def period_detail(request, period_id):
    period = get_object_or_404(PayrollPeriod, pk=period_id)
    filter_form = PayrollFilterForm(request.GET or None)
    runs = period.runs.select_related("employee_profile").order_by("employee_name")
    departments = period.runs.order_by("department").values_list("department", flat=True).distinct()
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        department = filter_form.cleaned_data.get("department")
        status = filter_form.cleaned_data.get("status")
        if q:
            runs = runs.filter(employee_name__icontains=q) | runs.filter(employee_number__icontains=q) | runs.filter(job_title__icontains=q)
        if department:
            runs = runs.filter(department=department)
        if status:
            runs = runs.filter(status=status)
    paginator = Paginator(runs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "payroll/period_detail.html",
        {
            "period": period,
            "page": page,
            "summary": payroll_summary(period),
            "departments": departments,
            "filter_form": filter_form,
        },
    )


@permission_required("payroll.process")
def run_edit(request, run_id):
    run = get_object_or_404(PayrollRun.objects.select_related("period", "employee_profile"), pk=run_id)
    run_form = PayrollRunForm(request.POST or None, instance=run, prefix="run")
    adjustment_form = PayrollAdjustmentForm(request.POST or None, prefix="adjustment")

    if request.method == "POST":
        if run.period.locked or run.locked:
            messages.error(request, "This payroll run is locked.")
            return redirect("payroll:period_detail", period_id=run.period_id)
        if request.POST.get("form_kind") == "adjustment":
            if adjustment_form.is_valid():
                add_adjustment(run, adjustment_form, user=request.user)
                messages.success(request, "Adjustment added.")
                return redirect("payroll:run_edit", run_id=run.id)
        elif run_form.is_valid():
            run = run_form.save(commit=False)
            update_run_adjustments(run, user=request.user)
            messages.success(request, "Payroll adjustments updated.")
            return redirect("payroll:period_detail", period_id=run.period_id)

    adjustments = run.adjustments.order_by("adjustment_type", "code")
    return render(
        request,
        "payroll/run_form.html",
        {"run": run, "run_form": run_form, "adjustment_form": adjustment_form, "adjustments": adjustments},
    )


@permission_required("payroll.process")
def adjustment_delete(request, adjustment_id):
    adjustment = get_object_or_404(PayrollAdjustment.objects.select_related("run", "run__period"), pk=adjustment_id)
    run = adjustment.run
    if request.method == "POST":
        try:
            delete_adjustment(adjustment, user=request.user)
            messages.success(request, "Adjustment removed.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("payroll:run_edit", run_id=run.id)


@permission_required("payroll.approve")
def period_workflow(request, period_id):
    period = get_object_or_404(PayrollPeriod, pk=period_id)
    if request.method == "POST":
        action = request.POST.get("action", "")
        notes = request.POST.get("notes", "")
        try:
            transition_period(period, action, user=request.user, notes=notes)
            messages.success(request, f"Payroll marked as {period.status}.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("payroll:period_detail", period_id=period.id)


@permission_required("payroll.process")
def bank_export(request, period_id):
    period = get_object_or_404(PayrollPeriod, pk=period_id)
    try:
        file_name, buffer = build_bank_export(period, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("payroll:period_detail", period_id=period.id)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("payroll:period_detail", period_id=period.id)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@payroll_required
def period_payslips_pdf(request, period_id):
    period = get_object_or_404(PayrollPeriod, pk=period_id)
    try:
        file_name, buffer = build_period_payslips_pdf(period, user=request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("payroll:period_detail", period_id=period.id)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@payroll_required
def payslip(request, run_id):
    run = get_object_or_404(PayrollRun.objects.select_related("period", "employee_profile"), pk=run_id)
    payslip_record = get_or_create_payslip(run, user=request.user)
    earnings, deductions = payslip_lines(run)
    return render(request, "payroll/payslip.html", {"run": run, "payslip": payslip_record, "earnings": earnings, "deductions": deductions})


@payroll_required
def payslip_pdf(request, run_id):
    run = get_object_or_404(PayrollRun.objects.select_related("period", "employee_profile"), pk=run_id)
    file_name, buffer = build_payslip_pdf(run, user=request.user)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@payroll_required
def reports(request):
    form = PayrollReportForm(request.GET or None)
    selected_report = "monthly"
    employee_number = ""
    if form.is_valid():
        selected_report = form.cleaned_data.get("report") or "monthly"
        employee_number = form.cleaned_data.get("employee_number") or ""

    context = {"form": form, "selected_report": selected_report}
    if selected_report == "department":
        context["rows"] = PayrollRun.objects.values("period__year", "period__month", "department").annotate(
            employees=Count("id"),
            gross=Sum("gross_salary"),
            deductions=Sum("total_deductions"),
            net=Sum("net_salary"),
        ).order_by("-period__year", "-period__month", "department")
    elif selected_report == "employee":
        runs = PayrollRun.objects.select_related("period").order_by("-period__year", "-period__month", "employee_name")
        if employee_number:
            runs = runs.filter(employee_number__icontains=employee_number)
        context["rows"] = runs[:100]
    elif selected_report == "cost":
        context["rows"] = PayrollRun.objects.values("period__year", "period__month").annotate(
            employees=Count("id"),
            gross=Sum("gross_salary"),
            deductions=Sum("total_deductions"),
            net=Sum("net_salary"),
        ).order_by("-period__year", "-period__month")
    elif selected_report == "bank":
        context["rows"] = PayrollRun.objects.select_related("period").filter(period__status__in=["Approved", "Paid"]).order_by("-period__year", "-period__month", "employee_name")
    else:
        context["rows"] = PayrollPeriod.objects.annotate(
            employees=Count("runs"),
            gross=Sum("runs__gross_salary"),
            deductions=Sum("runs__total_deductions"),
            net=Sum("runs__net_salary"),
        ).order_by("-year", "-month")

    return render(request, "payroll/reports.html", context)

# Create your views here.
