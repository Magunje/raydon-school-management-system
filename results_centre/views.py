from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from results_centre.models import StudentResult
from student_registry.sync import sync_all_legacy_data


@login_required
def result_list_view(request):
    sync_all_legacy_data()
    results = StudentResult.objects.all()
    rows = []
    for r in results:
        rows.append(
            {
                "data": [
                    r.student.admission_no,
                    f"{r.student.first_name} {r.student.surname}",
                    r.assessment.component.subject.name,
                    r.assessment.name,
                    f"{r.score:.2f} / {r.assessment.component.max_score}",
                    f"{r.percentage:.2f}%",
                    r.alpha_grade,
                ],
                "actions": [],
            }
        )
    return render(
        request,
        "erp_dashboard.html",
        {
            "title": "Results Centre & ZIMSEC Analytics",
            "subtitle": "Managed final term assessment entries, auto-calculated percentage scales, and ZIMSEC grade mappings.",
            "headers": [
                "Admission No",
                "Student Name",
                "Subject",
                "Assessment",
                "Score Achieved",
                "Percentage",
                "ZIMSEC Grade",
            ],
            "rows": rows,
            "has_actions": False,
        },
    )
