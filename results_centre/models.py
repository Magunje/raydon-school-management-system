from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal


class AssessmentQuerySet(models.QuerySet):
    def for_teacher(self, teacher_user):
        if teacher_user.is_superuser or teacher_user.is_staff:
            return self
        
        from subject_management.models import TeacherSubjectAllocation
        allocations = TeacherSubjectAllocation.objects.filter(teacher=teacher_user)
        if not allocations.exists():
            return self.none()
            
        q_filters = models.Q()
        for alloc in allocations:
            q_filters |= models.Q(
                component__subject=alloc.subject,
                component__academic_class__form=alloc.form,
                component__academic_class__stream=alloc.stream,
                academic_year=alloc.academic_year,
                academic_term=alloc.academic_term,
            )
        return self.filter(q_filters)


class StudentResultQuerySet(models.QuerySet):
    def for_teacher(self, teacher_user):
        if teacher_user.is_superuser or teacher_user.is_staff:
            return self
            
        from subject_management.models import TeacherSubjectAllocation
        allocations = TeacherSubjectAllocation.objects.filter(teacher=teacher_user)
        if not allocations.exists():
            return self.none()
            
        q_filters = models.Q()
        for alloc in allocations:
            q_filters |= models.Q(
                assessment__component__subject=alloc.subject,
                assessment__component__academic_class__form=alloc.form,
                assessment__component__academic_class__stream=alloc.stream,
                assessment__academic_year=alloc.academic_year,
                assessment__academic_term=alloc.academic_term,
            )
        return self.filter(q_filters)


class AssessmentComponent(models.Model):
    COMPONENT_CHOICES = [
        ("CLASS_TEST", "Class Test"),
        ("ASSIGNMENT", "Assignment"),
        ("PRACTICAL", "Practical"),
        ("TERMINAL_EXAM", "Terminal Exam"),
    ]

    subject = models.ForeignKey(
        "subject_management.Subject",
        on_delete=models.CASCADE,
        related_name="components",
    )
    academic_class = models.ForeignKey(
        "academic_structure.AcademicClass",
        on_delete=models.CASCADE,
        related_name="assessment_components",
    )
    component_type = models.CharField(
        max_length=20, choices=COMPONENT_CHOICES
    )
    weighting_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.IntegerField(default=100)

    class Meta:
        db_table = "results_assessment_components"
        unique_together = ("subject", "academic_class", "component_type")

    def __str__(self):
        return f"{self.subject.name} - {self.get_component_type_display()} ({self.weighting_percentage}%)"

    def clean(self):
        super().clean()
        if not self.subject or not self.academic_class:
            return

        # Weighting percentage checks
        total_weight = (
            AssessmentComponent.objects.filter(
                subject=self.subject, academic_class=self.academic_class
            )
            .exclude(pk=self.pk)
            .aggregate(models.Sum("weighting_percentage"))[
                "weighting_percentage__sum"
            ]
            or Decimal("0.00")
        )

        if total_weight + self.weighting_percentage > Decimal("100.00"):
            raise ValidationError(
                f"The combined weighting percentage for this subject and class cannot exceed 100%. "
                f"Currently configured weightings sum to {total_weight}%."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Assessment(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Open", "Open"),
        ("Closed", "Closed"),
        ("Published", "Published"),
    ]

    component = models.ForeignKey(
        AssessmentComponent, on_delete=models.CASCADE, related_name="assessments"
    )
    name = models.CharField(max_length=150)
    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear", on_delete=models.CASCADE
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, default="Draft", choices=STATUS_CHOICES
    )

    objects = AssessmentQuerySet.as_manager()

    class Meta:
        db_table = "results_assessments"
        ordering = ["academic_year", "academic_term", "name"]

    def __str__(self):
        return f"{self.name} - {self.component.subject.name} ({self.status})"

    def clean(self):
        super().clean()
        if self.status == "Published":
            # Combined weighting percentages contributing to final terminal mark must sum to exactly 100%
            total_weight = (
                AssessmentComponent.objects.filter(
                    subject=self.component.subject,
                    academic_class=self.component.academic_class,
                ).aggregate(models.Sum("weighting_percentage"))[
                    "weighting_percentage__sum"
                ]
                or Decimal("0.00")
            )

            if total_weight != Decimal("100.00"):
                raise ValidationError(
                    f"The combined weighting percentage for this subject and class must sum to exactly 100% "
                    f"before publishing results. Currently, it sums to {total_weight}%."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StudentResult(models.Model):
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="results"
    )
    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="results",
    )
    score = models.DecimalField(max_digits=5, decimal_places=2)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    alpha_grade = models.CharField(max_length=5, blank=True)

    # Telemetry and caching properties
    class_rank = models.IntegerField(blank=True, null=True)
    class_average = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )

    objects = StudentResultQuerySet.as_manager()

    class Meta:
        db_table = "results_student_scores"
        unique_together = ("assessment", "student")
        ordering = ["class_rank", "student"]

    def __str__(self):
        return (
            f"{self.student} -> {self.assessment.name}: {self.score} "
            f"({self.alpha_grade})"
        )

    def clean(self):
        super().clean()
        if not self.student or not self.assessment:
            return

        # Row-level security: Teacher allocation verification
        request_user = getattr(self, "request_user", None)
        if request_user and not (request_user.is_superuser or request_user.is_staff):
            from subject_management.models import TeacherSubjectAllocation
            is_allocated = TeacherSubjectAllocation.objects.filter(
                teacher=request_user,
                subject=self.assessment.component.subject,
                academic_year=self.assessment.academic_year,
                academic_term=self.assessment.academic_term,
                form=self.assessment.component.academic_class.form,
                stream=self.assessment.component.academic_class.stream
            ).exists()
            if not is_allocated:
                raise ValidationError(
                    "You are not authorized to record or update marks for this unassigned class, stream, or subject."
                )

        # Integration Rigidity: Student must be active
        if (
            self.student.status != "Active Student"
            and self.student.status != "Active"
        ):
            raise ValidationError(
                "Marks can only be recorded for students with status 'Active Student' or 'Active'."
            )

        # Integration Rigidity: Student must be explicitly registered for this subject
        from subject_management.models import StudentSubjectRegistration

        is_registered = StudentSubjectRegistration.objects.filter(
            student=self.student,
            subject=self.assessment.component.subject,
            academic_year=self.assessment.academic_year,
            academic_term=self.assessment.academic_term,
        ).exists()

        if not is_registered:
            raise ValidationError(
                f"Student '{self.student}' is not actively registered for subject "
                f"'{self.assessment.component.subject.name}' for this academic term."
            )

        # Verify score bounds
        max_score = Decimal(self.assessment.component.max_score)
        if self.score < Decimal("0.00") or self.score > max_score:
            raise ValidationError(
                f"Score must be between 0 and maximum allowed score of {max_score}."
            )

        # Write-Once Compliance Security Check
        if self.pk:
            original = StudentResult.objects.get(pk=self.pk)
            if original.assessment.status == "Published":
                override = getattr(self, "allow_correction", False)
                if not override:
                    raise ValidationError(
                        "Assessment results are Published and locked as read-only. "
                        "Reopening score corrections requires administrative override settings."
                    )

    def save(self, *args, **kwargs):
        # Auto-calculate Percentage and Alpha Grade
        if (
            self.score is not None
            and self.assessment
            and self.assessment.component
        ):
            max_score = Decimal(self.assessment.component.max_score)
            self.percentage = ((self.score / max_score) * 100).quantize(Decimal("0.01"))

            # ZIMSEC Grade mapping
            if self.percentage >= 80:
                self.alpha_grade = "A"
            elif self.percentage >= 70:
                self.alpha_grade = "B"
            elif self.percentage >= 60:
                self.alpha_grade = "C"
            elif self.percentage >= 50:
                self.alpha_grade = "D"
            elif self.percentage >= 40:
                self.alpha_grade = "E"
            else:
                self.alpha_grade = "U"

        # Log correction entry if score changes on a Published assessment
        if self.pk:
            original = StudentResult.objects.get(pk=self.pk)
            if (
                original.assessment.status == "Published"
                and original.score != self.score
            ):
                corrected_by_user = getattr(self, "corrected_by_user", None)
                correction_reason = getattr(
                    self, "correction_reason", "Administrative Score Correction"
                )

                ResultCorrectionLog.objects.create(
                    student_result=self,
                    previous_score=original.score,
                    new_score=self.score,
                    corrected_by=corrected_by_user,
                    reason=correction_reason,
                )

        self.full_clean()
        super().save(*args, **kwargs)


class ResultCorrectionLog(models.Model):
    student_result = models.ForeignKey(
        StudentResult, on_delete=models.CASCADE, related_name="correction_logs"
    )
    previous_score = models.DecimalField(max_digits=5, decimal_places=2)
    new_score = models.DecimalField(max_digits=5, decimal_places=2)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reason = models.TextField()
    corrected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "results_correction_logs"
        ordering = ["-corrected_at"]

    def __str__(self):
        return f"Correction on {self.student_result} ({self.previous_score} -> {self.new_score})"
