from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from exam_coordinator.models import ExamSchedule
from student_registry.sync import sync_all_legacy_data


@login_required
def exam_list_view(request):
    sync_all_legacy_data()
    schedules = ExamSchedule.objects.all()
    rows = []
    for s in schedules:
        rows.append(
            {
                "data": [
                    s.session.name,
                    s.session.get_session_type_display(),
                    s.subject.name,
                    s.date.strftime("%Y-%m-%d"),
                    f"{s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}",
                    s.session.status,
                ],
                "actions": [],
            }
        )
    return render(
        request,
        "erp_dashboard.html",
        {
            "title": "Exam Schedules & Seating",
            "subtitle": "Managed examination sessions, status workflows, and randomized student seating plans.",
            "headers": [
                "Session",
                "Session Type",
                "Subject",
                "Date",
                "Time Window",
                "Workflow Status",
            ],
            "rows": rows,
            "has_actions": False,
        },
    )
