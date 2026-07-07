from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from academic_structure.models import (
    AcademicYear,
    Form,
    Stream,
    AcademicClass,
)
from timetable.models import TimetablePeriodConfig
from student_registry.models import Student
from attendance_ledger.models import (
    AttendanceRecord,
    StudentAttendanceSummary,
)
import datetime
from decimal import Decimal


class AttendanceLedgerTestCase(TestCase):
    def setUp(self):
        # Create academic structures
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.form_1 = Form.objects.create(form_number=1, name="Form 1")
        self.stream_a = Stream.objects.create(name="A")
        self.academic_class = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_1, stream=self.stream_a
        )

        # Create period
        self.period_1 = TimetablePeriodConfig.objects.create(
            period_no=1,
            start_time="08:00",
            end_time="08:40",
            period_type="Lesson",
            label="Period 1",
        )

        # Create students in different lifecycle stages
        self.student_active = Student.objects.create(
            first_name="Rutendo",
            surname="Zhou",
            gender="Female",
            date_of_birth=datetime.date(2011, 3, 15),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )
        self.student_archived = Student.objects.create(
            first_name="Tinashe",
            surname="Maringe",
            gender="Male",
            date_of_birth=datetime.date(2010, 6, 25),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Archived",
        )

    @override_settings(ATTENDANCE_MODE="DAILY")
    def test_daily_mode_tracking_constraints(self):
        # Create daily record (succeeds)
        rec = AttendanceRecord.objects.create(
            student=self.student_active,
            date=datetime.date(2026, 3, 1),
            status="Present",
            mode="DAILY",
        )
        self.assertIsNotNone(rec)

        # Attempt to create lesson record under DAILY mode should fail
        with self.assertRaises(ValidationError):
            AttendanceRecord.objects.create(
                student=self.student_active,
                date=datetime.date(2026, 3, 2),
                status="Present",
                mode="LESSON",
                period=self.period_1,
            )

    @override_settings(ATTENDANCE_MODE="LESSON")
    def test_lesson_mode_tracking_constraints(self):
        # Create lesson record (succeeds)
        rec = AttendanceRecord.objects.create(
            student=self.student_active,
            date=datetime.date(2026, 3, 1),
            status="Present",
            mode="LESSON",
            period=self.period_1,
        )
        self.assertIsNotNone(rec)

        # Attempt to create daily record under LESSON mode should fail
        with self.assertRaises(ValidationError):
            AttendanceRecord.objects.create(
                student=self.student_active,
                date=datetime.date(2026, 3, 2),
                status="Present",
                mode="DAILY",
            )

    @override_settings(ATTENDANCE_MODE="DAILY")
    def test_structural_lifecycle_entry_filters(self):
        # Active student succeeds
        rec_ok = AttendanceRecord.objects.create(
            student=self.student_active,
            date=datetime.date(2026, 3, 1),
            status="Present",
            mode="DAILY",
        )
        self.assertIsNotNone(rec_ok)

        # Archived student fails validation
        with self.assertRaises(ValidationError):
            AttendanceRecord.objects.create(
                student=self.student_archived,
                date=datetime.date(2026, 3, 1),
                status="Present",
                mode="DAILY",
            )

    @override_settings(
        ATTENDANCE_MODE="DAILY",
        CHRONIC_ABSENTEEISM_THRESHOLD="90.00",
        CONSECUTIVE_ABSENCE_LIMIT=3,
    )
    def test_chronic_absenteeism_and_consecutive_absences_telemetry(self):
        # Create 10 attendance records: 8 Present, 2 Absent (80% rate)
        dates = [datetime.date(2026, 3, i) for i in range(1, 11)]
        statuses = [
            "Present",
            "Present",
            "Absent",
            "Present",
            "Present",
            "Absent",
            "Present",
            "Present",
            "Present",
            "Present",
        ]

        for dt, stat in zip(dates, statuses):
            AttendanceRecord.objects.create(
                student=self.student_active, date=dt, status=stat, mode="DAILY"
            )

        summary = self.student_active.attendance_summary
        summary.refresh_from_db()
        self.assertEqual(summary.total_days, 10)
        self.assertEqual(summary.present_days, 8)
        self.assertEqual(summary.absent_days, 2)
        self.assertEqual(summary.attendance_percentage, Decimal("80.00"))

        # Threshold check: 80% is below 90%
        self.assertTrue(summary.is_chronically_absent)
        # No 3 consecutive absences yet
        self.assertFalse(summary.has_consecutive_absences)

        # Add 3 consecutive absent records
        AttendanceRecord.objects.create(
            student=self.student_active,
            date=datetime.date(2026, 3, 11),
            status="Absent",
            mode="DAILY",
        )
        AttendanceRecord.objects.create(
            student=self.student_active,
            date=datetime.date(2026, 3, 12),
            status="Absent",
            mode="DAILY",
        )
        AttendanceRecord.objects.create(
            student=self.student_active,
            date=datetime.date(2026, 3, 13),
            status="Absent",
            mode="DAILY",
        )

        summary.refresh_from_db()
        self.assertTrue(summary.has_consecutive_absences)
