from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class Subject(models.Model):
    LEVEL_CHOICES = [
        ("O_LEVEL", "Ordinary Level (O-Level)"),
        ("A_LEVEL", "Advanced Level (A-Level)"),
    ]

    DEPT_CHOICES = [
        ("Languages", "Languages"),
        ("Sciences", "Sciences"),
        ("Commercials", "Commercials"),
        ("Humanities", "Humanities"),
        ("Practicals", "Practicals"),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    department = models.CharField(max_length=50, choices=DEPT_CHOICES, default="Languages")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "subject_catalog"
        ordering = ["level", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class StudentSubjectRegistrationQuerySet(models.QuerySet):
    def for_teacher(self, teacher_user):
        if teacher_user.is_superuser or teacher_user.is_staff:
            return self

        # A teacher is isolated and can only view registrations for subject sections (Form + Stream)
        # to which they are actively allocated in the same year and term.
        allocations = TeacherSubjectAllocation.objects.filter(
            teacher=teacher_user
        )
        if not allocations.exists():
            return self.none()

        q_filters = models.Q()
        for alloc in allocations:
            q_filters |= models.Q(
                subject=alloc.subject,
                student__academic_class__form=alloc.form,
                student__academic_class__stream=alloc.stream,
                academic_year=alloc.academic_year,
                academic_term=alloc.academic_term,
            )
        return self.filter(q_filters)


class StudentSubjectRegistration(models.Model):
    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="subject_registrations",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="student_registrations"
    )
    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear", on_delete=models.CASCADE
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm", on_delete=models.CASCADE
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    objects = StudentSubjectRegistrationQuerySet.as_manager()

    class Meta:
        db_table = "student_subject_registrations"
        unique_together = (
            "student",
            "subject",
            "academic_year",
            "academic_term",
        )
        ordering = ["student", "subject"]

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.academic_term})"

    def clean(self):
        super().clean()
        if not self.student:
            return

        if not self.student.academic_class:
            raise ValidationError(
                "Student must be assigned to an academic class before subjects can be registered."
            )

        form_num = self.student.academic_class.form.form_number
        max_allowed = 10 if form_num in [1, 2, 3, 4] else 5

        # Check duplicate subject registrations
        existing_regs = StudentSubjectRegistration.objects.filter(
            student=self.student,
            academic_year=self.academic_year,
            academic_term=self.academic_term,
        )
        if self.pk:
            existing_regs = existing_regs.exclude(pk=self.pk)

        if existing_regs.filter(subject=self.subject).exists():
            raise ValidationError(
                f"Student is already registered for subject '{self.subject.name}' in this term."
            )

        level_name = (
            "O-Level (Forms 1-4)"
            if form_num in [1, 2, 3, 4]
            else "A-Level (Forms 5-6)"
        )

        # Enforce level-specific subject registration caps
        if existing_regs.count() >= max_allowed:
            raise ValidationError(
                f"Subject limit reached. {level_name} students are strictly capped at a maximum of {max_allowed} subjects."
            )

        # Verify that subject level matches student academic level
        student_level = "O_LEVEL" if form_num in [1, 2, 3, 4] else "A_LEVEL"
        if self.subject.level != student_level:
            raise ValidationError(
                f"Cannot register '{self.subject.name}' ({self.subject.level}) "
                f"for a student in {level_name}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_assigned_students_for_teacher(cls, teacher_user):
        return cls.objects.all().for_teacher(teacher_user)


class TeacherSubjectAllocation(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subject_allocations",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="teacher_allocations"
    )
    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear", on_delete=models.CASCADE
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm", on_delete=models.CASCADE
    )
    form = models.ForeignKey(
        "academic_structure.Form", on_delete=models.CASCADE
    )
    stream = models.ForeignKey(
        "academic_structure.Stream", on_delete=models.CASCADE
    )

    class Meta:
        db_table = "teacher_subject_allocations"
        unique_together = (
            "teacher",
            "subject",
            "academic_year",
            "academic_term",
            "form",
            "stream",
        )
        ordering = ["teacher", "subject", "form", "stream"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "subject", "academic_year", "academic_term", "form", "stream"],
                name="unique_teacher_subject_allocation_constraint"
            )
        ]

    def __str__(self):
        return f"{self.teacher} -> {self.subject} ({self.form} {self.stream})"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class SubjectManagementAuditLog(models.Model):
    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.IntegerField()
    detail = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "subject_mgmt_audit_logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} on {self.model_name} (ID: {self.object_id})"
