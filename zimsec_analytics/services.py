from django.db.models import Avg
from zimsec_analytics.models import ZIMSECCandidateResult
from subject_management.models import TeacherSubjectAllocation
from decimal import Decimal


def calculate_student_analytics(student):
    """Calculates student metrics: total passes, distinction counts, A-Level

    eligibility.
    """
    results = student.zimsec_results.all()
    passed_subjects = 0
    distinction_count = 0
    has_english = False
    has_math = False

    for res in results:
        grade = res.grade
        level = res.subject.level
        code = res.subject.code.upper()
        name = res.subject.name.lower()

        # O-Level Pass: A*, A, B, C. A-Level Pass: A*, A, B, C, D, E
        is_pass = False
        if level == "O_LEVEL":
            if grade in ["A*", "A", "B", "C"]:
                is_pass = True
                if "ENG" in code or "english" in name:
                    has_english = True
                if "MAT" in code or "mathematics" in name:
                    has_math = True
        elif level == "A_LEVEL":
            if grade in ["A*", "A", "B", "C", "D", "E"]:
                is_pass = True

        if is_pass:
            passed_subjects += 1

        if grade in ["A*", "A"]:
            distinction_count += 1

    # ZIMSEC A-Level eligibility: Minimum 5 O-Level passes including English and Mathematics
    is_eligible_for_a_level = (
        passed_subjects >= 5 and has_english and has_math
    )

    return {
        "total_passed_subjects": passed_subjects,
        "distinction_count": distinction_count,
        "is_eligible_for_a_level": is_eligible_for_a_level,
    }


def calculate_section_analytics(exam_year):
    """Calculates aggregate metrics (pass rate %, distinctions, performance

    averages) grouped by: Subject, Teacher, Stream, Form, and Department.
    """
    results = ZIMSECCandidateResult.objects.filter(exam_year=exam_year)

    # Initialise dictionaries for groupings
    groupings = {
        "subject": {},
        "teacher": {},
        "stream": {},
        "form": {},
        "department": {},
    }

    # Pre-cache teacher allocations for speed
    allocations = TeacherSubjectAllocation.objects.filter(
        academic_year__year=exam_year
    )
    alloc_map = {}
    for alloc in allocations:
        key = (alloc.subject_id, alloc.form_id, alloc.stream_id)
        teacher = alloc.teacher
        t_name = getattr(teacher, 'full_name', '') or f"{teacher.first_name} {teacher.last_name}".strip() or teacher.username
        alloc_map[key] = t_name

    for res in results:
        subject_name = res.subject.name
        department = res.subject.department
        academic_class = res.student.academic_class

        if not academic_class:
            continue

        form_name = academic_class.form.name
        stream_name = academic_class.stream.name

        # Resolve Teacher
        alloc_key = (res.subject_id, academic_class.form_id, academic_class.stream_id)
        teacher_name = alloc_map.get(alloc_key, "Unallocated Teacher")

        # Determine pass/distinction
        is_pass = False
        if res.subject.level == "O_LEVEL" and res.grade in ["A*", "A", "B", "C"]:
            is_pass = True
        elif res.subject.level == "A_LEVEL" and res.grade in [
            "A*",
            "A",
            "B",
            "C",
            "D",
            "E",
        ]:
            is_pass = True

        is_distinction = res.grade in ["A*", "A"]

        # Helper to increment stats
        def add_to_group(group_type, group_key):
            dict_ref = groupings[group_type]
            if group_key not in dict_ref:
                dict_ref[group_key] = {"total": 0, "passed": 0, "distinctions": 0}
            dict_ref[group_key]["total"] += 1
            if is_pass:
                dict_ref[group_key]["passed"] += 1
            if is_distinction:
                dict_ref[group_key]["distinctions"] += 1

        add_to_group("subject", subject_name)
        add_to_group("teacher", teacher_name)
        add_to_group("stream", stream_name)
        add_to_group("form", form_name)
        add_to_group("department", department)

    # Process percentages
    analytics_report = {}
    for group_type, data in groupings.items():
        analytics_report[group_type] = {}
        for key, stats in data.items():
            total = stats["total"]
            passed = stats["passed"]
            pass_rate = (passed / total) * 100 if total > 0 else 0
            analytics_report[group_type][key] = {
                "total_sat": total,
                "total_passed": passed,
                "pass_rate_percentage": round(pass_rate, 2),
                "distinctions": stats["distinctions"],
            }

    return analytics_report
