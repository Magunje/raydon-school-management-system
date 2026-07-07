from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class ZIMSECCandidateResult(models.Model):
    SESSION_CHOICES = [
        ("JUNE", "June Examination Session"),
        ("NOVEMBER", "November Examination Session"),
    ]

    GRADE_CHOICES = [
        ("A*", "A* (Distinction)"),
        ("A", "A (Distinction)"),
        ("B", "B (Credit)"),
        ("C", "C (Pass)"),
        ("D", "D (Below Pass)"),
        ("E", "E (Below Pass - A-Level Only)"),
        ("U", "U (Ungraded)"),
    ]

    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="zimsec_results",
    )
    subject = models.ForeignKey(
        "subject_management.Subject",
        on_delete=models.CASCADE,
        related_name="zimsec_results",
    )
    grade = models.CharField(max_length=5, choices=GRADE_CHOICES)
    session = models.CharField(max_length=20, choices=SESSION_CHOICES)
    exam_year = models.IntegerField()

    class Meta:
        db_table = "zimsec_candidate_results"
        unique_together = ("student", "subject", "exam_year")
        ordering = ["-exam_year", "student", "subject"]

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.grade}) [{self.exam_year}]"

    def clean(self):
        super().clean()
        if not self.student or not self.subject:
            return

        # Check Admission Numbers existence
        if not self.student.admission_no:
            raise ValidationError(
                "Cannot register ZIMSEC results for a student without a valid Admission Number."
            )

        # Check for year mismatch
        if self.exam_year < self.student.admission_date.year:
            raise ValidationError(
                f"Examination year ({self.exam_year}) cannot be earlier than "
                f"the student's admission year ({self.student.admission_date.year})."
            )

        # Enforce registered subjects check (student must have registered for the subject)
        from subject_management.models import StudentSubjectRegistration

        registered = StudentSubjectRegistration.objects.filter(
            student=self.student, subject=self.subject
        ).exists()
        if not registered:
            raise ValidationError(
                f"ZIMSEC results registration blocked. Student is not registered for subject "
                f"'{self.subject.name}'."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
