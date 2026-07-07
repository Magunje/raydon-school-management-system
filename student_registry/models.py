from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal
import datetime


class Student(models.Model):
    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
    ]

    ALLOWED_TRANSITIONS = {
        "Applicant": ["Pending Registration", "Withdrawn"],
        "Pending Registration": ["Active Student", "Withdrawn"],
        "Active Student": [
            "Suspended",
            "Pending ZIMSEC Analysis",
            "Archived",
            "Withdrawn",
            "Deceased",
        ],
        "Suspended": ["Active Student", "Archived", "Withdrawn", "Deceased"],
        "Pending ZIMSEC Analysis": [
            "Reactivated",
            "Archived",
            "Alumni",
            "Withdrawn",
            "Deceased",
        ],
        "Archived": ["Active Student", "Reactivated", "Deceased"],
        "Reactivated": [
            "Active Student",
            "Suspended",
            "Archived",
            "Alumni",
            "Withdrawn",
            "Deceased",
        ],
        "Alumni": ["Archived", "Deceased"],
        "Withdrawn": ["Archived", "Deceased"],
        "Deceased": [],
    }

    admission_no = models.CharField(max_length=50, unique=True, blank=True)
    national_id = models.CharField(
        max_length=50, blank=True, null=True, unique=True
    )
    first_name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    admission_date = models.DateField()
    academic_class = models.ForeignKey(
        "academic_structure.AcademicClass",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="students",
    )
    status = models.CharField(max_length=50, default="Applicant")

    class Meta:
        db_table = "registry_students"
        ordering = ["surname", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.surname} ({self.admission_no})"

    def clean(self):
        super().clean()
        if not self.first_name:
            raise ValidationError("First name is mandatory.")
        if not self.surname:
            raise ValidationError("Surname is mandatory.")
        if not self.gender:
            raise ValidationError("Gender is mandatory.")
        if not self.date_of_birth:
            raise ValidationError("Date of birth is mandatory.")
        if not self.admission_date:
            raise ValidationError("Admission date is mandatory.")

        # Check duplicate student on creation
        if not self.pk:
            dups = Student.objects.filter(
                first_name=self.first_name,
                surname=self.surname,
                date_of_birth=self.date_of_birth,
            )
            if dups.exists():
                raise ValidationError(
                    "A student with this name and date of birth already exists in the registry."
                )
            if self.national_id and Student.objects.filter(national_id=self.national_id).exists():
                raise ValidationError(
                    "A student with this National ID already exists."
                )

        if self.pk:
            original = Student.objects.get(pk=self.pk)
            # Enforce immutability of admission number after creation
            if original.admission_no != self.admission_no:
                raise ValidationError("Admission number is immutable once assigned.")

            # Validate that exactly one primary guardian exists if there are guardians
            guardians = self.guardians.all()
            if guardians.exists():
                primary_count = guardians.filter(is_primary=True).count()
                if primary_count != 1:
                    raise ValidationError(
                        "Exactly one guardian must be designated as primary."
                    )

        if self.academic_class:
            # Hook into Phase 1 validation logic
            self.academic_class.clean()

    def save(self, *args, **kwargs):
        if not self.admission_no:
            # Auto-generate immutable admission number on creation
            year_str = str(self.admission_date.year)[2:]
            prefix = f"A{year_str}"
            latest = (
                Student.objects.filter(admission_no__startswith=prefix)
                .order_by("-admission_no")
                .first()
            )
            if latest:
                try:
                    last_num = int(latest.admission_no[3:])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1
            self.admission_no = f"{prefix}{next_num:03d}"

        self.full_clean()
        super().save(*args, **kwargs)

    def transition_to(self, to_status, user, reason):
        if to_status not in self.ALLOWED_TRANSITIONS.get(self.status, []):
            raise ValidationError(
                f"Invalid lifecycle status transition from '{self.status}' to '{to_status}'."
            )

        # Freeze period check for Pending ZIMSEC Analysis
        if self.status == "Pending ZIMSEC Analysis":
            last_log = (
                self.status_logs.filter(new_status="Pending ZIMSEC Analysis")
                .order_by("-changed_at")
                .first()
            )
            entry_year = (
                last_log.changed_at.year
                if last_log
                else datetime.date.today().year
            )
            freeze_until = datetime.date(entry_year + 1, 3, 1)

            if datetime.date.today() < freeze_until:
                is_admin = user and (user.is_superuser or user.is_staff)
                if not is_admin:
                    raise ValidationError(
                        "Lifecycle status transitions out of Pending ZIMSEC Analysis are frozen until March 1."
                    )

            # Workflow Coupling: Block archiving or alumni state transitions if no ZIMSEC results exist
            if to_status in ["Archived", "Alumni"]:
                from django.apps import apps
                try:
                    ZIMSECCandidateResult = apps.get_model("zimsec_analytics", "ZIMSECCandidateResult")
                    if not ZIMSECCandidateResult.objects.filter(student=self).exists():
                        raise ValidationError(
                            "Cannot transition student out of Pending ZIMSEC Analysis "
                            "until ZIMSEC exam results are recorded and analyzed."
                        )
                except LookupError:
                    pass

        old_status = self.status
        self.status = to_status
        self.save()

        # Log transition in audit trail
        StudentStatusLog.objects.create(
            student=self,
            previous_status=old_status,
            new_status=to_status,
            changed_by=user,
            reason=reason,
        )


class StudentStatusLog(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="status_logs"
    )
    previous_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "registry_student_status_logs"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.student} ({self.previous_status} -> {self.new_status})"


class Guardian(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="guardians"
    )
    full_name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=80)
    phone_number = models.CharField(max_length=40)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "registry_guardians"

    def __str__(self):
        return f"{self.full_name} ({self.relationship})"

    def clean(self):
        super().clean()
        if self.is_primary:
            # Ensure only one guardian can be primary per student
            existing_primaries = Guardian.objects.filter(
                student=self.student, is_primary=True
            )
            if self.pk:
                existing_primaries = existing_primaries.exclude(pk=self.pk)
            if existing_primaries.exists():
                raise ValidationError(
                    "A student can only have exactly one primary guardian."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class FeeStructure(models.Model):
    LEVEL_CHOICES = [
        ("O-Level", "O-Level"),
        ("A-Level", "A-Level"),
    ]

    name = models.CharField(max_length=100, unique=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2)
    academic_level = models.CharField(max_length=20, choices=LEVEL_CHOICES)

    class Meta:
        db_table = "registry_fee_structures"

    def __str__(self):
        return f"{self.name} - USD {self.default_amount}"


class StudentFeeRecord(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="fee_records"
    )
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.CASCADE, related_name="student_records"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registry_student_fee_records"
        unique_together = ("student", "fee_structure")

    def __str__(self):
        return f"{self.student} - {self.fee_structure.name} (USD {self.amount})"
