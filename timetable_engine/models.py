from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class Classroom(models.Model):
    name = models.CharField(max_length=100, unique=True)
    capacity = models.IntegerField()

    class Meta:
        db_table = "timetable_classrooms"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (Cap: {self.capacity})"


class TimetableVersion(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PUBLISHED", "Published"),
    ]

    version_no = models.IntegerField(default=1)
    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear",
        on_delete=models.CASCADE,
        related_name="timetable_versions",
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm",
        on_delete=models.CASCADE,
        related_name="timetable_versions",
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="DRAFT"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "timetable_versions"
        unique_together = ("academic_year", "academic_term", "version_no")
        ordering = ["-academic_year", "-academic_term", "-version_no"]

    def __str__(self):
        return f"Year {self.academic_year.year} Term {self.academic_term.term_number} - v{self.version_no} ({self.status})"


class TimetableEntry(models.Model):
    DAY_CHOICES = [
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]

    version = models.ForeignKey(
        TimetableVersion, on_delete=models.CASCADE, related_name="entries"
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    period_no = models.IntegerField()

    subject = models.ForeignKey(
        "subject_management.Subject",
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )
    form = models.ForeignKey(
        "academic_structure.Form",
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )
    stream = models.ForeignKey(
        "academic_structure.Stream",
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )

    class Meta:
        db_table = "timetable_matrix_entries"
        ordering = ["day_of_week", "start_time", "form", "stream"]

    def __str__(self):
        return f"Day {self.day_of_week} P{self.period_no}: {self.subject.name} in {self.classroom.name}"

    def clean(self):
        super().clean()
        if not all([self.version, self.subject, self.teacher, self.classroom, self.form, self.stream]):
            return

        # 1. Strict time validation
        if self.start_time >= self.end_time:
            raise ValidationError("Start time must be strictly earlier than the end time.")

        # 2. Archive Management / Revision lock: Approved published schedules lock as read-only
        if self.pk:
            original = TimetableEntry.objects.get(pk=self.pk)
            if original.version.status == "PUBLISHED" and original.version == self.version:
                raise ValidationError("Published schedules are locked as read-only. Create a new revision version to make adjustments.")
        elif self.version.status == "PUBLISHED":
            raise ValidationError("Cannot add entries directly to a published timetable version. Please create a new draft version.")

        # 3. Teacher Clash check
        clash_teacher = TimetableEntry.objects.filter(
            version=self.version,
            day_of_week=self.day_of_week,
            period_no=self.period_no,
            teacher=self.teacher,
        )
        if self.pk:
            clash_teacher = clash_teacher.exclude(pk=self.pk)
        if clash_teacher.exists():
            raise ValidationError(
                f"Teacher clash: Teacher is already scheduled for another class in Period {self.period_no} on Day {self.day_of_week}."
            )

        # 4. Classroom Clash check
        clash_room = TimetableEntry.objects.filter(
            version=self.version,
            day_of_week=self.day_of_week,
            period_no=self.period_no,
            classroom=self.classroom,
        )
        if self.pk:
            clash_room = clash_room.exclude(pk=self.pk)
        if clash_room.exists():
            raise ValidationError(
                f"Classroom clash: Classroom '{self.classroom.name}' is already occupied in Period {self.period_no} on Day {self.day_of_week}."
            )

        # 5. Student Subject Clash (Form + Stream scheduled for multiple subjects during the same period)
        clash_student = TimetableEntry.objects.filter(
            version=self.version,
            day_of_week=self.day_of_week,
            period_no=self.period_no,
            form=self.form,
            stream=self.stream,
        )
        if self.pk:
            clash_student = clash_student.exclude(pk=self.pk)
        if clash_student.exists():
            raise ValidationError(
                f"Student clash: Section {self.form.name} {self.stream.name} is already scheduled for another subject in Period {self.period_no} on Day {self.day_of_week}."
            )

        # 6. Subject Clash: Prohibit the duplication of a single subject within the same section loop during the exact same period window
        # Covered by student clash check above as a student group cannot have two entries in the same period window.

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
