from django.db import models
from django.core.exceptions import ValidationError
from django.apps import apps


class AcademicYear(models.Model):
    year = models.IntegerField(unique=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "academic_years"
        ordering = ["-year"]

    def __str__(self):
        return f"{self.year}"

    def clean(self):
        super().clean()
        if self.is_active:
            active_years = AcademicYear.objects.filter(is_active=True)
            if self.pk:
                active_years = active_years.exclude(pk=self.pk)
            if active_years.exists():
                raise ValidationError(
                    "Only one academic year can be active globally at any given time."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AcademicTerm(models.Model):
    TERM_CHOICES = [
        (1, "Term 1"),
        (2, "Term 2"),
        (3, "Term 3"),
    ]

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="terms"
    )
    term_number = models.IntegerField(choices=TERM_CHOICES)
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "academic_terms"
        unique_together = ("academic_year", "term_number")
        ordering = ["academic_year", "term_number"]

    def __str__(self):
        return f"{self.academic_year} - Term {self.term_number}"

    def clean(self):
        super().clean()
        if self.term_number not in [1, 2, 3]:
            raise ValidationError("Term number must be strictly 1, 2, or 3.")

        if self.is_active:
            active_terms = AcademicTerm.objects.filter(is_active=True)
            if self.pk:
                active_terms = active_terms.exclude(pk=self.pk)
            if active_terms.exists():
                raise ValidationError(
                    "Only one academic term can be active globally at any given time."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Form(models.Model):
    FORM_NUMBER_CHOICES = [
        (1, "Form 1"),
        (2, "Form 2"),
        (3, "Form 3"),
        (4, "Form 4"),
        (5, "Form 5"),
        (6, "Form 6"),
    ]

    form_number = models.IntegerField(choices=FORM_NUMBER_CHOICES, unique=True)
    name = models.CharField(max_length=50)

    class Meta:
        db_table = "forms"
        ordering = ["form_number"]

    def __str__(self):
        return self.name


class Stream(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "streams"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicClass(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name="classes"
    )
    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name="classes"
    )
    stream = models.ForeignKey(
        Stream, on_delete=models.CASCADE, related_name="classes"
    )
    max_capacity = models.IntegerField(default=40)

    class Meta:
        db_table = "academic_classes"
        unique_together = ("academic_year", "form", "stream")
        ordering = ["academic_year", "form", "stream"]

    def __str__(self):
        return f"{self.form} {self.stream} ({self.academic_year})"

    @property
    def student_count(self):
        return self.allocations.count()

    @property
    def remaining_spaces(self):
        return self.max_capacity - self.student_count

    def clean(self):
        super().clean()
        if not self.form or not self.stream:
            return

        form_num = self.form.form_number
        stream_name = self.stream.name

        # Zimbabwean streaming system matrix validation
        if form_num in [1, 2, 3, 4]:
            if stream_name not in ["A", "B", "C"]:
                raise ValidationError(
                    f"Invalid stream '{stream_name}' for Form {form_num}. "
                    "O Level (Forms 1-4) allowed streams are strictly 'A', 'B', or 'C'."
                )
        elif form_num in [5, 6]:
            if stream_name not in ["Arts", "Commercials", "Sciences"]:
                raise ValidationError(
                    f"Invalid stream '{stream_name}' for Form {form_num}. "
                    "A Level (Forms 5-6) allowed streams are strictly 'Arts', 'Commercials', or 'Sciences'."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def assign_student(self, student, capacity_override=False):
        allocation = StudentClassAllocation(
            student=student, academic_class=self
        )
        allocation.capacity_override = capacity_override
        allocation.save()
        return allocation


class StudentClassAllocation(models.Model):
    student = models.ForeignKey(
        "students.Pupil", on_delete=models.CASCADE, related_name="allocations", db_constraint=False
    )
    academic_class = models.ForeignKey(
        AcademicClass, on_delete=models.CASCADE, related_name="allocations"
    )
    allocated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "student_class_allocations"
        unique_together = ("student", "academic_class")

    def __str__(self):
        return f"{self.student} -> {self.academic_class}"

    def clean(self):
        super().clean()
        if not self.pk:
            override = getattr(self, "capacity_override", False)
            if not override and self.academic_class.remaining_spaces <= 0:
                raise ValidationError(
                    "Class capacity limit reached. Allocation is blocked without administrative override."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
