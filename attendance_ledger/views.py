from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from attendance_ledger.models import AttendanceRecord
from student_registry.sync import sync_all_legacy_data


@login_required
def attendance_list_view(request):
    sync_all_legacy_data()
    records = AttendanceRecord.objects.all()
    rows = []
    for r in records:
        rows.append(
            {
                "data": [
                    r.student.admission_no,
                    f"{r.student.first_name} {r.student.surname}",
                    r.date.strftime("%Y-%m-%d"),
                    r.tracking_mode,
                    r.status,
                    r.remarks or "-",
                ],
                "actions": [],
            }
        )
    return render(
        request,
        "erp_dashboard.html",
        {
            "title": "Attendance Ledger",
            "subtitle": "Dual-mode Daily and Lesson timetable period attendance tracking ledger.",
            "headers": [
                "Admission No",
                "Student Name",
                "Date",
                "Tracking Mode",
                "Attendance Status",
                "Remarks",
            ],
            "rows": rows,
            "has_actions": False,
        },
    )
