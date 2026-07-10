from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Count, Q
from decimal import Decimal
import csv
import datetime

from student_registry.models import Student
from human_resources.models import EmployeeProfile
from portals.views import student_portal_required
from settings_app.views import audit_action
from school_system_django.native import table_exists
from discipline.models import (
    DisciplineCategory,
    DisciplineProfile,
    DisciplinaryIncident,
    DisciplineSanction,
    DisciplineSuspension,
    ParentMeeting,
    BehaviourImprovementPlan
)
from counselling.models import CounsellingCase


@login_required
def dashboard(request):
    total_incidents = DisciplinaryIncident.objects.count()
    active_cases = DisciplinaryIncident.objects.exclude(status__in=["Resolved", "Closed"]).count()
    suspensions = DisciplineSuspension.objects.filter(
        Q(end_date__gte=datetime.date.today()) | Q(end_date__isnull=True)
    ).count()

    # Repeat offenders: students with > 2 incidents
    repeat_offenders = DisciplineProfile.objects.filter(total_incidents__gt=2).count()

    recent_incidents = DisciplinaryIncident.objects.select_related("student", "category", "reported_by")[:10]
    categories = DisciplineCategory.objects.all()

    # Data for charts
    form_data = DisciplinaryIncident.objects.values("student__academic_class__form__name").annotate(count=Count("incident_id"))

    context = {
        "total_incidents": total_incidents,
        "active_cases": active_cases,
        "suspensions": suspensions,
        "repeat_offenders": repeat_offenders,
        "recent_incidents": recent_incidents,
        "categories": categories,
        "form_data": form_data,
    }
    return render(request, "discipline/dashboard.html", context)


@login_required
def incident_list(request):
    incidents = DisciplinaryIncident.objects.all().select_related("student", "category", "reported_by")
    
    # Simple search
    q = request.GET.get("q", "")
    if q:
        incidents = incidents.filter(
            Q(student__admission_no__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__surname__icontains=q) |
            Q(incident_no__icontains=q)
        )
    return render(request, "discipline/incident_list.html", {"incidents": incidents, "q": q})


@login_required
def incident_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        category_id = request.POST.get("category_id")
        reported_by_id = request.POST.get("reported_by_id")
        time_str = request.POST.get("incident_time")
        
        student = get_object_or_404(Student, pk=student_id)
        category = get_object_or_404(DisciplineCategory, pk=category_id)
        reported_by = EmployeeProfile.objects.filter(pk=reported_by_id).first()
        
        inc_count = DisciplinaryIncident.objects.count() + 1
        inc_num = f"INC-{datetime.date.today().year}-{inc_count:05d}"
        
        incident = DisciplinaryIncident.objects.create(
            incident_no=inc_num,
            incident_date=request.POST.get("incident_date") or datetime.date.today(),
            incident_time=time_str if time_str else None,
            student=student,
            category=category,
            severity=category.severity,
            description=request.POST.get("description"),
            witnesses=request.POST.get("witnesses"),
            reported_by=reported_by,
            status=request.POST.get("status", "Under Investigation"),
            hostel_incident=request.POST.get("hostel_incident") == "on"
        )
        audit_action(request, "Disciplinary Incident Recorded", f"Recorded incident {inc_num} for student {student.admission_no}")
        messages.success(request, f"Incident {inc_num} has been successfully recorded.")
        return redirect("discipline:incident_list")
        
    students = Student.objects.filter(status="Active Student")
    categories = DisciplineCategory.objects.all()
    staff = EmployeeProfile.objects.filter(status="ACTIVE")
    return render(request, "discipline/incident_form.html", {
        "students": students,
        "categories": categories,
        "staff": staff
    })


@login_required
def sanction_new(request, incident_id):
    incident = get_object_or_404(DisciplinaryIncident, pk=incident_id)
    if request.method == "POST":
        sanction_type = request.POST.get("sanction_type")
        start_date = request.POST.get("start_date") or datetime.date.today()
        end_date = request.POST.get("end_date")
        reason = request.POST.get("reason")
        approved_by_id = request.POST.get("approved_by_id")
        
        approved_by = EmployeeProfile.objects.filter(pk=approved_by_id).first()
        
        sanction = DisciplineSanction.objects.create(
            incident=incident,
            student=incident.student,
            sanction_type=sanction_type,
            start_date=start_date,
            end_date=end_date if end_date else None,
            reason=reason,
            approved_by=approved_by,
            is_active=True
        )
        
        # Counselling Referral is automatically created in the model save method.
        if sanction_type == "Counselling Referral":
            audit_action(request, "Counselling Referral Autocreated", f"Created counselling case via sanction referral.")

        # If Suspension, create suspension record
        if sanction_type == "Suspension":
            susp_type = request.POST.get("suspension_type", "External")
            conditions = request.POST.get("suspension_conditions")
            DisciplineSuspension.objects.create(
                sanction=sanction,
                student=incident.student,
                suspension_type=susp_type,
                start_date=start_date,
                end_date=end_date if end_date else None,
                reason=reason,
                conditions=conditions
            )
            
        incident.status = "Resolved"
        incident.save()
        
        audit_action(request, "Sanction Added", f"Added sanction {sanction_type} for student {incident.student.admission_no}")
        messages.success(request, "Sanction has been assigned and registered successfully.")
        return redirect("discipline:incident_list")
        
    staff = EmployeeProfile.objects.filter(status="ACTIVE")
    return render(request, "discipline/sanction_form.html", {"incident": incident, "staff": staff})


@login_required
def parent_meeting_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        incident_id = request.POST.get("incident_id")
        
        student = get_object_or_404(Student, pk=student_id)
        incident = DisciplinaryIncident.objects.filter(pk=incident_id).first()
        
        meeting = ParentMeeting.objects.create(
            student=student,
            incident=incident,
            date=request.POST.get("date") or datetime.date.today(),
            participants=request.POST.get("participants"),
            minutes=request.POST.get("minutes"),
            outcomes=request.POST.get("outcomes"),
            follow_up_actions=request.POST.get("follow_up_actions")
        )
        
        if incident:
            incident.status = "Closed"
            incident.save()
            
        audit_action(request, "Parent Disciplinary Meeting Logged", f"Logged meeting for student {student.admission_no}")
        messages.success(request, "Parent meeting minutes and outcomes saved successfully.")
        return redirect("discipline:dashboard")
        
    students = Student.objects.filter(status="Active Student")
    incidents = DisciplinaryIncident.objects.exclude(status__in=["Closed", "Resolved"])
    return render(request, "discipline/parent_meeting_form.html", {"students": students, "incidents": incidents})


@login_required
def behaviour_plan_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        mentor_id = request.POST.get("mentor_id")
        
        student = get_object_or_404(Student, pk=student_id)
        mentor = get_object_or_404(EmployeeProfile, pk=mentor_id)
        
        plan = BehaviourImprovementPlan.objects.create(
            student=student,
            mentor=mentor,
            start_date=request.POST.get("start_date") or datetime.date.today(),
            review_date=request.POST.get("review_date"),
            targets=request.POST.get("targets"),
            activities=request.POST.get("activities"),
            status="In Progress"
        )
        audit_action(request, "Behaviour Improvement Plan Set", f"Created behavior plan for student {student.admission_no} under mentor {mentor.full_name}")
        messages.success(request, f"Behaviour Improvement Plan for {student.full_name} created successfully.")
        return redirect("discipline:dashboard")
        
    students = Student.objects.filter(status="Active Student")
    staff = EmployeeProfile.objects.filter(status="ACTIVE")
    return render(request, "discipline/behaviour_plan_form.html", {"students": students, "staff": staff})


@login_required
def reports_view(request):
    return render(request, "discipline/reports.html")


@login_required
def export_discipline_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="discipline_register.csv"'
    
    writer = csv.writer(response)
    writer.writerow(["Incident No", "Date", "Student Name", "Class", "Offence Category", "Severity", "Reported By", "Status"])
    
    incidents = DisciplinaryIncident.objects.all().select_related("student", "category", "reported_by")
    for inc in incidents:
        class_name = inc.student.academic_class.class_name if inc.student.academic_class else "N/A"
        reported = inc.reported_by.full_name if inc.reported_by else "N/A"
        cat_name = inc.category.name if inc.category else "N/A"
        writer.writerow([inc.incident_no, inc.incident_date, inc.student.full_name, class_name, cat_name, inc.severity, reported, inc.status])
        
    return response


@student_portal_required
def student_portal_discipline(request, pupil):
    pupil_id = pupil["pupil_id"]
    student = Student.objects.get(pk=pupil_id)
    profile, _ = DisciplineProfile.objects.get_or_create(student=student)
    incidents = student.disciplinary_incidents.all().select_related("category", "reported_by")
    sanctions = student.discipline_sanctions.all().select_related("approved_by")
    
    context = {
        "student": student,
        "profile": profile,
        "incidents": incidents,
        "sanctions": sanctions,
    }
    return render(request, "portals/student_discipline.html", context)
