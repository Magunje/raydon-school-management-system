from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class ExamSession(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SCHEDULED", "Scheduled"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("PUBLISHED", "Published"),
    ]

    SESSION_TYPE_CHOICES = [
        ("MID_TERM", "Mid-Term Examination"),
        ("END_OF_TERM", "End-of-Term Examination"),
        ("MOCK", "Mock Examination"),
        ("PRACTICALS", "Practicals Session"),
    ]

    name = models.CharField(max_length=150)
    session_type = models.CharField(max_length=30, choices=SESSION_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="DRAFT"
    )
    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear",
        on_delete=models.CASCADE,
        related_name="exam_sessions",
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm",
        on_delete=models.CASCADE,
        related_name="exam_sessions",
    )

    class Meta:
        db_table = "exam_coord_sessions"
        ordering = ["-academic_year", "-academic_term", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_session_type_display()}) - {self.status}"


class ExamSchedule(models.Model):
    session = models.ForeignKey(
        ExamSession, on_delete=models.CASCADE, related_name="schedules"
    )
    subject = models.ForeignKey(
        "subject_management.Subject",
        on_delete=models.CASCADE,
        related_name="exam_schedules",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        db_table = "exam_coord_schedules"
        unique_together = ("session", "subject", "date")
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.session.name} - {self.subject.name} [{self.date}]"


class ExamCandidate(models.Model):
    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="exam_candidates",
    )
    exam_schedule = models.ForeignKey(
        ExamSchedule, on_delete=models.CASCADE, related_name="candidates"
    )

    class Meta:
        db_table = "exam_coord_candidates"
        unique_together = ("student", "exam_schedule")

    def __str__(self):
        return f"{self.student.full_name} sittings for {self.exam_schedule.subject.name}"

    def clean(self):
        super().clean()
        if not self.student or not self.exam_schedule:
            return

        # Eligibility check: Candidate must hold a valid active subject registration
        from subject_management.models import StudentSubjectRegistration

        registered = StudentSubjectRegistration.objects.filter(
            student=self.student,
            subject=self.exam_schedule.subject,
            academic_year=self.exam_schedule.session.academic_year,
            academic_term=self.exam_schedule.session.academic_term,
        ).exists()

        if not registered:
            raise ValidationError(
                f"Candidate eligibility blocked. Student is not registered for subject "
                f"'{self.exam_schedule.subject.name}' for the active term."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ExamRoomAssignment(models.Model):
    exam_schedule = models.ForeignKey(
        ExamSchedule, on_delete=models.CASCADE, related_name="room_assignments"
    )
    classroom = models.ForeignKey(
        "timetable_engine.Classroom",
        on_delete=models.CASCADE,
        related_name="exam_assignments",
    )
    capacity = models.IntegerField()

    class Meta:
        db_table = "exam_coord_room_assignments"
        unique_together = ("exam_schedule", "classroom")

    def __str__(self):
        return f"{self.classroom.name} assigned to {self.exam_schedule.subject.name}"

    def clean(self):
        super().clean()
        if not self.classroom:
            return

        # Room physical capacity bounds check
        if self.capacity > self.classroom.capacity:
            raise ValidationError(
                f"Assigned capacity ({self.capacity}) cannot exceed classroom's "
                f"physical limit ({self.classroom.capacity})."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ExamSeating(models.Model):
    ATTENDANCE_CHOICES = [
        ("Present", "Present"),
        ("Absent", "Absent"),
        ("Late", "Late"),
        ("Excused", "Excused"),
        ("Withheld", "Withheld"),
    ]

    candidate = models.OneToOneField(
        ExamCandidate, on_delete=models.CASCADE, related_name="seat_allocation"
    )
    room_assignment = models.ForeignKey(
        ExamRoomAssignment, on_delete=models.CASCADE, related_name="seatings"
    )
    seat_number = models.IntegerField()
    attendance_state = models.CharField(
        max_length=20, choices=ATTENDANCE_CHOICES, default="Present"
    )
    score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    class Meta:
        db_table = "exam_coord_seatings"
        unique_together = ("room_assignment", "seat_number")
        ordering = ["seat_number"]

    def __str__(self):
        return f"Seat {self.seat_number} - {self.candidate.student.full_name} ({self.attendance_state})"

    def clean(self):
        super().clean()
        if not self.room_assignment:
            return

        # Capacity overlap check
        if self.seat_number > self.room_assignment.capacity:
            raise ValidationError(
                f"Seat number ({self.seat_number}) exceeds room assignment capacity ({self.room_assignment.capacity})."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
