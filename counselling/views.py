from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Count, Q
import csv
import datetime

from student_registry.models import Student
from human_resources.models import EmployeeProfile
from portals.views import student_portal_required
from settings_app.views import audit_action
from accounts.permissions import normalized_role, ROLE_COUNSELLOR, ROLE_SUPER_ADMIN, ROLE_ADMIN
from counselling.models import (
    CounsellingCase,
    CounsellingSession,
    CounsellingAppointment,
    CounsellingInterventionPlan,
    CareerGuidanceSession,
    CounsellingParentMeeting
)


def has_counsellor_access(user):
    role = normalized_role(user)
    return role in [ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_COUNSELLOR]


@login_required
def dashboard(request):
    if not has_counsellor_access(request.user):
        return HttpResponseForbidden("Access Denied: You do not have permission to view Counselling files.")
        
    total_cases = CounsellingCase.objects.count()
    open_cases = CounsellingCase.objects.filter(status="Open").count()
    high_risk = CounsellingCase.objects.filter(severity_level__in=["High", "Critical"]).count()
    
    upcoming_appointments = CounsellingAppointment.objects.filter(
        date__gte=datetime.date.today(),
        status="Scheduled"
    ).select_related("student", "counsellor")[:5]
    
    recent_cases = CounsellingCase.objects.filter(status="Open").select_related("student", "assigned_counsellor")[:10]
    
    context = {
        "total_cases": total_cases,
        "open_cases": open_cases,
        "high_risk": high_risk,
        "upcoming_appointments": upcoming_appointments,
        "recent_cases": recent_cases,
    }
    return render(request, "counselling/dashboard.html", context)


@login_required
def case_list(request):
    if not has_counsellor_access(request.user):
        return HttpResponseForbidden("Access Denied.")
        
    cases = CounsellingCase.objects.all().select_related("student", "assigned_counsellor")
    q = request.GET.get("q", "")
    if q:
        cases = cases.filter(
            Q(student__admission_no__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__surname__icontains=q) |
            Q(case_no__icontains=q)
        )
    return render(request, "counselling/case_list.html", {"cases": cases, "q": q})


@login_required
def case_detail(request, case_id):
    if not has_counsellor_access(request.user):
        return HttpResponseForbidden("Access Denied.")
        
    case = get_object_or_404(CounsellingCase, pk=case_id)
    sessions = case.sessions.all()
    interventions = case.interventions.all()
    parent_meetings = case.parent_meetings.all()
    
    context = {
        "case": case,
        "sessions": sessions,
        "interventions": interventions,
        "parent_meetings": parent_meetings,
    }
    return render(request, "counselling/case_detail.html", context)


@login_required
def case_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        student = get_object_or_404(Student, pk=student_id)
        
        # Check permissions for case registration: teachers can submit referrals
        case_count = CounsellingCase.objects.count() + 1
        case_num = f"CNS-{datetime.date.today().year}-{case_count:05d}"
        
        counsellor_id = request.POST.get("assigned_counsellor_id")
        assigned_counsellor = EmployeeProfile.objects.filter(pk=counsellor_id).first()
        
        case = CounsellingCase.objects.create(
            case_no=case_num,
            student=student,
            category=request.POST.get("category"),
            description=request.POST.get("description"),
            severity_level=request.POST.get("severity_level", "Low"),
            status="Open",
            assigned_counsellor=assigned_counsellor,
            date_opened=request.POST.get("date_opened") or datetime.date.today()
        )
        audit_action(request, "Counselling Case Opened", f"Opened case {case_num} for student {student.admission_no}")
        messages.success(request, f"Counselling Case {case_num} has been successfully opened.")
        return redirect("counselling:case_list")
        
    students = Student.objects.filter(status="Active Student")
    staff = EmployeeProfile.objects.filter(status="ACTIVE")
    return render(request, "counselling/case_form.html", {"students": students, "staff": staff})


@login_required
def session_new(request, case_id):
    if not has_counsellor_access(request.user):
        return HttpResponseForbidden("Access Denied.")
        
    case = get_object_or_404(CounsellingCase, pk=case_id)
    if request.method == "POST":
        notes = request.POST.get("session_notes")
        recommendations = request.POST.get("recommendations")
        follow_date_str = request.POST.get("follow_up_date")
        
        session_num = case.sessions.count() + 1
        
        CounsellingSession.objects.create(
            case=case,
            session_number=session_num,
            date=request.POST.get("date") or datetime.date.today(),
            time=request.POST.get("time") or None,
            counsellor=case.assigned_counsellor,
            session_notes=notes,
            recommendations=recommendations,
            follow_up_date=follow_date_str if follow_date_str else None,
            status="Completed"
        )
        
        # Update case status if requested
        new_status = request.POST.get("case_status")
        if new_status:
            case.status = new_status
            case.save()
            
        audit_action(request, "Counselling Session Recorded", f"Recorded session {session_num} for case {case.case_no}. Detailed notes were protected.")
        messages.success(request, "Counselling session notes logged successfully.")
        return redirect("counselling:case_detail", case_id=case.pk)
        
    return render(request, "counselling/session_form.html", {"case": case})


@login_required
def appointment_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        counsellor_id = request.POST.get("counsellor_id")
        
        student = get_object_or_404(Student, pk=student_id)
        counsellor = get_object_or_404(EmployeeProfile, pk=counsellor_id)
        
        appointment = CounsellingAppointment.objects.create(
            student=student,
            counsellor=counsellor,
            date=request.POST.get("date"),
            time=request.POST.get("time"),
            status="Scheduled",
            notes=request.POST.get("notes")
        )
        audit_action(request, "Counselling Appointment Scheduled", f"Scheduled appointment for {student.admission_no} with counsellor {counsellor.full_name}")
        messages.success(request, "Appointment has been scheduled successfully.")
        return redirect("counselling:dashboard")
        
    students = Student.objects.filter(status="Active Student")
    staff = EmployeeProfile.objects.filter(status="ACTIVE")
    return render(request, "counselling/appointment_form.html", {"students": students, "staff": staff})


@login_required
def intervention_new(request, case_id):
    if not has_counsellor_access(request.user):
        return HttpResponseForbidden("Access Denied.")
        
    case = get_object_or_404(CounsellingCase, pk=case_id)
    if request.method == "POST":
        CounsellingInterventionPlan.objects.create(
            case=case,
            plan_type=request.POST.get("plan_type"),
            objectives=request.POST.get("objectives"),
            activities=request.POST.get("activities"),
            review_date=request.POST.get("review_date"),
            responsible_person=request.POST.get("responsible_person")
        )
        messages.success(request, "Intervention plan added successfully.")
        return redirect("counselling:case_detail", case_id=case.pk)
        
    return render(request, "counselling/intervention_form.html", {"case": case})


@login_required
def career_session_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        counsellor_id = request.POST.get("counsellor_id")
        
        student = get_object_or_404(Student, pk=student_id)
        counsellor = get_object_or_404(EmployeeProfile, pk=counsellor_id)
        
        CareerGuidanceSession.objects.create(
            student=student,
            counsellor=counsellor,
            date=request.POST.get("date") or datetime.date.today(),
            career_interests=request.POST.get("career_interests"),
            university_info=request.POST.get("university_info"),
            scholarship_info=request.POST.get("scholarship_info"),
            assessment_notes=request.POST.get("assessment_notes")
        )
        audit_action(request, "Career Guidance Logged", f"Logged career advice for {student.admission_no}")
        messages.success(request, f"Career Guidance profile for {student.full_name} logged successfully.")
        return redirect("counselling:dashboard")
        
    students = Student.objects.filter(status="Active Student")
    staff = EmployeeProfile.objects.filter(status="ACTIVE")
    return render(request, "counselling/career_session_form.html", {"students": students, "staff": staff})


@login_required
def reports_view(request):
    if not has_counsellor_access(request.user):
        return HttpResponseForbidden("Access Denied.")
    return render(request, "counselling/reports.html")


@login_required
def export_cases_csv(request):
    if not has_counsellor_access(request.user):
        return HttpResponseForbidden("Access Denied.")
        
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="counselling_cases.csv"'
    
    writer = csv.writer(response)
    writer.writerow(["Case No", "Student Name", "Category", "Severity Risk", "Status", "Date Opened", "Assigned Counsellor"])
    
    cases = CounsellingCase.objects.all().select_related("student", "assigned_counsellor")
    for case in cases:
        counsellor_name = case.assigned_counsellor.full_name if case.assigned_counsellor else "Unassigned"
        writer.writerow([case.case_no, case.student.full_name, case.category, case.severity_level, case.status, case.date_opened, counsellor_name])
        
    return response


@student_portal_required
def student_portal_counselling(request, pupil):
    pupil_id = pupil["pupil_id"]
    student = Student.objects.get(pk=pupil_id)
    appointments = CounsellingAppointment.objects.filter(student=student).select_related("counsellor")
    
    # Strictly confidential: do not show sensitive case details or session notes to portal
    context = {
        "student": student,
        "appointments": appointments,
    }
    return render(request, "portals/student_counselling.html", context)
