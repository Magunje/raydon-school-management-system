import datetime
from decimal import Decimal
from django.db import connection, transaction
from student_registry.models import Student, Guardian
from academic_structure.models import AcademicClass, AcademicYear, AcademicTerm, Form, Stream
from subject_management.models import Subject
from attendance_ledger.models import AttendanceRecord
from results_centre.models import AssessmentComponent, Assessment, StudentResult
from timetable_engine.models import TimetableVersion, Classroom, TimetableEntry
from exam_coordinator.models import ExamSession, ExamSchedule
from django.contrib.auth import get_user_model
from school_system_django.native import (
    academic_grade_number,
    class_stream_name,
    resolve_legacy_class_record,
    school_settings,
)

User = get_user_model()

def dict_rows(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        desc = cursor.description
        return [dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()]


def academic_class_for_legacy_pupil(pupil):
    if pupil.get("class_id"):
        class_obj = AcademicClass.objects.filter(pk=pupil["class_id"]).first()
        if class_obj:
            return class_obj

    legacy_class = resolve_legacy_class_record(
        grade=pupil.get("grade"),
        stream=pupil.get("class_stream"),
        grade_id=pupil.get("grade_id"),
    )
    if legacy_class:
        class_obj = AcademicClass.objects.filter(pk=legacy_class["class_id"]).first()
        if class_obj:
            return class_obj

    form_number = academic_grade_number(pupil.get("grade"), pupil.get("grade_id"))
    stream_name = class_stream_name(
        grade=pupil.get("grade"),
        stream=pupil.get("class_stream"),
        grade_id=pupil.get("grade_id"),
    )
    settings = school_settings()
    year_number = settings.get("current_year") or 2026
    if form_number and stream_name:
        return AcademicClass.objects.filter(
            academic_year__year=year_number,
            form__form_number=form_number,
            stream__name__iexact=stream_name,
        ).first()
    return None

def sync_all_legacy_data():
    """Runs a complete synchronization process from legacy raw SQLite tables into Django ORM models."""
    try:
        with transaction.atomic():
            # 1. Resolve Admin / Staff default user for sync actions
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.create_superuser(
                    username="sync_admin",
                    password="password123",
                    email="admin@raydonschool.co.zw"
                )

            # 2. Sync Pupils to Student Registry
            pupils = dict_rows("SELECT * FROM pupils")
            for p in pupils:
                aclass_obj = academic_class_for_legacy_pupil(p)

                # Parse dates
                dob = datetime.date(2010, 1, 1)
                if p.get("date_of_birth"):
                    try:
                        dob = datetime.datetime.strptime(p["date_of_birth"], "%Y-%m-%d").date()
                    except ValueError:
                        pass
                
                adm_date = datetime.date(2026, 1, 1)
                if p.get("admission_date"):
                    try:
                        adm_date = datetime.datetime.strptime(p["admission_date"], "%Y-%m-%d").date()
                    except ValueError:
                        pass

                status = p.get("status") or "Active Student"
                if status == "Active":
                    status = "Active Student"

                existing_student = Student.objects.filter(admission_no=p["admission_no"]).first()
                defaults = {
                    "first_name": p.get("first_name") or "Student",
                    "surname": p.get("surname") or "Record",
                    "gender": p.get("gender") or "Male",
                    "date_of_birth": dob,
                    "admission_date": adm_date,
                    "status": status,
                }
                if aclass_obj is not None or existing_student is None:
                    defaults["academic_class"] = aclass_obj

                Student.objects.update_or_create(
                    admission_no=p["admission_no"],
                    defaults=defaults,
                )

            # 3. Sync Attendance Records
            records = dict_rows("SELECT * FROM attendance_records")
            for r in records:
                pupil_row = dict_rows("SELECT admission_no FROM pupils WHERE pupil_id = %s", [r["pupil_id"]])
                if not pupil_row:
                    continue
                
                student = Student.objects.filter(admission_no=pupil_row[0]["admission_no"]).first()
                if not student:
                    continue

                att_date = datetime.date.today()
                if r.get("attendance_date"):
                    try:
                        att_date = datetime.datetime.strptime(r["attendance_date"], "%Y-%m-%d").date()
                    except ValueError:
                        pass

                AttendanceRecord.objects.get_or_create(
                    student=student,
                    date=att_date,
                    defaults={
                        "status": r.get("status") or "Present",
                        "remarks": r.get("notes") or "",
                        "tracking_mode": "DAILY"
                    }
                )

            # 4. Sync Timetable Entries
            tt_entries = dict_rows("SELECT * FROM class_timetable_entries")
            active_year = AcademicYear.objects.filter(is_active=True).first()
            active_term = AcademicTerm.objects.filter(is_active=True).first()
            if not active_year:
                active_year, _ = AcademicYear.objects.get_or_create(year=2026, is_active=True)
            if not active_term:
                active_term, _ = AcademicTerm.objects.get_or_create(
                    academic_year=active_year,
                    term_number=2,
                    defaults={
                        "start_date": datetime.date(2026, 5, 1),
                        "end_date": datetime.date(2026, 8, 31),
                        "is_active": True
                    }
                )
            default_version, _ = TimetableVersion.objects.get_or_create(
                academic_year=active_year,
                academic_term=active_term,
                version_no=1,
                defaults={"status": "PUBLISHED"}
            )
            for tt in tt_entries:
                aclass = AcademicClass.objects.filter(pk=tt["class_id"]).first()
                if not aclass:
                    continue

                sub_obj = Subject.objects.filter(code=f"SUB-{tt['subject_id']}").first()
                if not sub_obj:
                    sub_obj, _ = Subject.objects.get_or_create(
                        code=f"SUB-{tt['subject_id']}",
                        defaults={
                            "name": tt.get("subject_name") or "Subject",
                            "level": "O_LEVEL",
                            "department": "Languages",
                            "is_active": True
                        }
                    )

                room_obj, _ = Classroom.objects.get_or_create(
                    name=tt.get("room_name") or "Classroom A",
                    defaults={"capacity": 40}
                )

                day_val = 1
                day_name = (tt.get("day_name") or "").upper()
                if "MON" in day_name: day_val = 1
                elif "TUE" in day_name: day_val = 2
                elif "WED" in day_name: day_val = 3
                elif "THU" in day_name: day_val = 4
                elif "FRI" in day_name: day_val = 5

                # Parse times
                st = datetime.time(8, 0)
                et = datetime.time(9, 0)
                try:
                    if tt.get("start_time"): st = datetime.datetime.strptime(tt["start_time"], "%H:%M").time()
                    if tt.get("end_time"): et = datetime.datetime.strptime(tt["end_time"], "%H:%M").time()
                except ValueError:
                    pass

                TimetableEntry.objects.get_or_create(
                    version=default_version,
                    day_of_week=day_val,
                    period_no=tt.get("period_no") or 1,
                    start_time=st,
                    end_time=et,
                    form=aclass.form,
                    stream=aclass.stream,
                    defaults={
                        "subject": sub_obj,
                        "teacher": admin_user,
                        "classroom": room_obj
                    }
                )

            # 5. Sync Exam Sessions & Schedules
            exams = dict_rows("SELECT * FROM exam_sessions")
            for ex in exams:
                sess, _ = ExamSession.objects.get_or_create(
                    name=ex["exam_name"],
                    defaults={
                        "term": ex.get("term") or "Term 1",
                        "year": ex.get("year") or 2026,
                        "status": "PUBLISHED"
                    }
                )

                # Sync marks to results centre
                entries = dict_rows(
                    "SELECT e.*, s.pupil_id FROM result_entries e JOIN result_sheets s ON e.result_id = s.result_id WHERE s.term = %s AND s.year = %s",
                    [ex.get("term"), ex.get("year")]
                )
                for ent in entries:
                    pupil_row = dict_rows("SELECT admission_no, class_id FROM pupils WHERE pupil_id = %s", [ent["pupil_id"]])
                    if not pupil_row:
                        continue

                    student = Student.objects.filter(admission_no=pupil_row[0]["admission_no"]).first()
                    if not student or not student.academic_class:
                        continue

                    legacy_sub = dict_rows("SELECT subject_code FROM subjects WHERE subject_id = %s", [ent["subject_id"]])
                    sub_obj = None
                    if legacy_sub:
                        sub_obj = Subject.objects.filter(code=legacy_sub[0]["subject_code"]).first()
                    if not sub_obj:
                        continue

                    # Resolve component
                    comp, _ = AssessmentComponent.objects.get_or_create(
                        subject=sub_obj,
                        academic_class=student.academic_class,
                        component_type="TERMINAL_EXAM",
                        defaults={"weighting_percentage": Decimal("100.00"), "max_score": 100}
                    )

                    # Resolve assessment
                    assess, _ = Assessment.objects.get_or_create(
                        component=comp,
                        name=f"{ex['exam_name']} Final",
                        defaults={"status": "Closed"}
                    )

                    # Create student result
                    score_val = Decimal(str(ent.get("mark") or 0.00))
                    StudentResult.objects.get_or_create(
                        student=student,
                        assessment=assess,
                        defaults={
                            "score": score_val,
                            "percentage": score_val,
                            "alpha_grade": ent.get("grade") or "U"
                        }
                    )
            print("Successfully synchronized legacy data into Django models!")
    except Exception as e:
        print(f"Error during legacy database synchronization: {e}")
