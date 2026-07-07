from django.shortcuts import render
from accounts.permissions import normalized_role, permission_required
from timetable_engine.models import TimetableEntry
from student_registry.sync import sync_all_legacy_data


@permission_required("timetable.view")
def timetable_list_view(request):
    sync_all_legacy_data()
    entries = TimetableEntry.objects.all()
    if normalized_role(request.user) == "Teacher":
        entries = entries.filter(teacher=request.user)
    rows = []
    for e in entries:
        class_lbl = f"{e.form.name} {e.stream.name}"
        rows.append(
            {
                "data": [
                    e.get_day_of_week_display(),
                    f"Period {e.period_no}",
                    f"{e.start_time.strftime('%H:%M')} - {e.end_time.strftime('%H:%M')}",
                    class_lbl,
                    e.subject.name,
                    e.teacher.username,
                    e.classroom.name,
                ],
                "actions": [],
            }
        )
    return render(
        request,
        "erp_dashboard.html",
        {
            "title": "Timetables",
            "subtitle": "Active subject timetable allocations and conflict-free lesson scheduling matrix.",
            "headers": [
                "Day",
                "Period",
                "Time Slot",
                "Class Stream",
                "Subject",
                "Teacher",
                "Classroom",
            ],
            "rows": rows,
            "has_actions": False,
        },
    )
