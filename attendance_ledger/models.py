from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("Present", "Present"),
        ("Absent", "Absent"),
        ("Late", "Late"),
        ("Excused", "Excused"),
        ("Sick", "Sick"),
        ("On Leave", "On Leave"),
        ("Suspended", "Suspended"),
    ]

    MODE_CHOICES = [
        ("DAILY", "Daily Attendance"),
        ("LESSON", "Lesson/Period Attendance"),
    ]

    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    period = models.ForeignKey(
        "timetable.TimetablePeriodConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )

    class Meta:
        db_table = "attendance_ledger_records"
        ordering = ["-date", "student", "period"]

    def __str__(self):
        period_str = f" - Period {self.period.period_no}" if self.period else ""
        return f"{self.student} ({self.date}{period_str}): {self.status}"

    def clean(self):
        super().clean()
        if not self.student:
            return

        # 1. Structural Entry Filters: Block creation for Archived, Alumni, Withdrawn, Pending ZIMSEC Analysis
        blocked_statuses = [
            "Archived",
            "Alumni",
            "Withdrawn",
            "Pending ZIMSEC Analysis",
        ]
        if self.student.status in blocked_statuses:
            raise ValidationError(
                f"Cannot record attendance for student in stage '{self.student.status}'."
            )

        # 2. Dual-mode Settings Validation
        configured_mode = getattr(settings, "ATTENDANCE_MODE", "DAILY")
        if self.mode != configured_mode:
            raise ValidationError(
                f"Attendance record mode '{self.mode}' does not match system configured mode '{configured_mode}'."
            )

        # 3. Unique records checks
        if self.mode == "DAILY":
            if self.period is not None:
                raise ValidationError(
                    "Daily attendance records must not specify a timetable period."
                )
            duplicates = AttendanceRecord.objects.filter(
                student=self.student, date=self.date, mode="DAILY"
            )
            if self.pk:
                duplicates = duplicates.exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError(
                    "Daily attendance record already exists for this student on this date."
                )
        elif self.mode == "LESSON":
            if self.period is None:
                raise ValidationError(
                    "Lesson attendance records must specify a scheduled timetable period."
                )
            duplicates = AttendanceRecord.objects.filter(
                student=self.student,
                date=self.date,
                period=self.period,
                mode="LESSON",
            )
            if self.pk:
                duplicates = duplicates.exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError(
                    "Lesson attendance record already exists for this student on this date and period."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StudentAttendanceSummary(models.Model):
    student = models.OneToOneField(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="attendance_summary",
    )
    total_days = models.IntegerField(default=0)
    present_days = models.IntegerField(default=0)
    absent_days = models.IntegerField(default=0)
    attendance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("100.00")
    )

    class Meta:
        db_table = "attendance_ledger_summaries"
        verbose_name_plural = "Student Attendance Summaries"

    def __str__(self):
        return f"{self.student} Summary: {self.attendance_percentage}%"

    @property
    def is_chronically_absent(self):
        threshold = Decimal(
            getattr(settings, "CHRONIC_ABSENTEEISM_THRESHOLD", "90.00")
        )
        return self.attendance_percentage < threshold

    @property
    def has_consecutive_absences(self):
        limit = int(getattr(settings, "CONSECUTIVE_ABSENCE_LIMIT", 3))
        recent_records = AttendanceRecord.objects.filter(
            student=self.student
        ).order_by("-date")[:limit]

        if len(recent_records) < limit:
            return False

        return all(r.status == "Absent" for r in recent_records)
