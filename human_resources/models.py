from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Department(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    ]

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=30, unique=True)
    department_head = models.ForeignKey(
        "EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
    )
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_departments"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Position(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    ]

    title = models.CharField(max_length=120)
    code = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="positions"
    )
    reports_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_reports"
    )
    employment_category = models.CharField(max_length=50, blank=True, null=True)
    minimum_qualification = models.CharField(max_length=180, blank=True, null=True)
    job_description = models.TextField(blank=True, null=True)
    approved_posts = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    class Meta:
        db_table = "hr_positions"
        ordering = ["title"]

    @property
    def filled_posts(self):
        return self.employees.exclude(status__in=["TERMINATED", "ARCHIVED"]).count()

    @property
    def vacant_posts(self):
        return max(self.approved_posts - self.filled_posts, 0)

    def __str__(self):
        return self.title


class EmployeeProfile(models.Model):
    CATEGORY_CHOICES = [
        ("ACADEMIC", "Academic Staff"),
        ("TEACHER", "Teacher"),
        ("HOD", "Head of Department"),
        ("DEPUTY_HEAD", "Deputy Headmaster"),
        ("HEADMASTER", "Headmaster"),
        ("NON_TEACHING", "Non-Teaching Staff"),
        ("FINANCE", "Finance Officer"),
        ("ADMIN", "Administrator"),
        ("SECRETARY", "Secretary"),
        ("LIBRARIAN", "Librarian"),
        ("LAB_TECH", "Laboratory Technician"),
        ("SECURITY", "Security Personnel"),
        ("DRIVER", "Driver"),
        ("CLEANER", "Cleaner"),
        ("HOSTEL", "Hostel Staff"),
    ]
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("ON_LEAVE", "On Leave"),
        ("SUSPENDED", "Suspended"),
        ("TERMINATED", "Terminated"),
        ("RETIRED", "Retired"),
        ("ARCHIVED", "Archived"),
    ]
    EMPLOYMENT_TYPE_CHOICES = [
        ("FULL_TIME", "Full-Time"),
        ("PART_TIME", "Part-Time"),
        ("CONTRACT", "Contract"),
        ("TEMPORARY", "Temporary"),
        ("INTERN", "Intern"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    employee_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=30, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.CharField(max_length=100)
    gender = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    national_id = models.CharField(max_length=80, unique=True)
    marital_status = models.CharField(max_length=40, blank=True, null=True)
    nationality = models.CharField(max_length=80, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    residential_address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=50)
    alternative_phone_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    profile_photo = models.ImageField(upload_to="hr/photos/", null=True, blank=True)
    employment_date = models.DateField()
    department = models.CharField(max_length=120)
    department_ref = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees"
    )
    position = models.CharField(max_length=120)
    position_ref = models.ForeignKey(
        Position, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees"
    )
    employee_category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    employment_type = models.CharField(max_length=80, choices=EMPLOYMENT_TYPE_CHOICES, default="FULL_TIME")
    contract_type = models.CharField(max_length=80, default="Permanent")
    probation_end_date = models.DateField(blank=True, null=True)
    contract_start_date = models.DateField(blank=True, null=True)
    contract_end_date = models.DateField(blank=True, null=True)
    supervisor = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="supervised_employees"
    )
    work_location = models.CharField(max_length=120, blank=True, null=True)
    qualification = models.CharField(max_length=180, blank=True, null=True)
    specialisation = models.CharField(max_length=180, blank=True, null=True)
    professional_registration_number = models.CharField(max_length=100, blank=True, null=True)
    professional_body = models.CharField(max_length=120, blank=True, null=True)
    professional_registration_expiry = models.DateField(blank=True, null=True)
    teaching_subjects = models.TextField(blank=True, null=True)
    assigned_classes = models.TextField(blank=True, null=True)
    years_of_experience = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    next_of_kin = models.CharField(max_length=180)
    next_of_kin_relationship = models.CharField(max_length=80)
    next_of_kin_phone = models.CharField(max_length=50)
    next_of_kin_alt_phone = models.CharField(max_length=50, blank=True, null=True)
    next_of_kin_address = models.TextField(blank=True, null=True)
    bank_name = models.CharField(max_length=120, blank=True, null=True)
    bank_branch = models.CharField(max_length=120, blank=True, null=True)
    bank_account_name = models.CharField(max_length=180, blank=True, null=True)
    bank_account_number = models.CharField(max_length=80, blank=True, null=True)
    payment_method = models.CharField(max_length=40, default="BANK_TRANSFER")
    tax_number = models.CharField(max_length=80, blank=True, null=True)
    pension_number = models.CharField(max_length=80, blank=True, null=True)
    nssa_number = models.CharField(max_length=80, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="ACTIVE")
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_archived",
    )
    archive_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hr_employee_profiles"
        ordering = ["surname", "first_name"]

    @property
    def full_name(self):
        return " ".join(part for part in [self.first_name, self.middle_name, self.surname] if part)

    def __str__(self):
        return f"{self.full_name} ({self.employee_number})"

    def clean(self):
        super().clean()
        duplicates = EmployeeProfile.objects.exclude(pk=self.pk)
        if self.employee_number and duplicates.filter(employee_number__iexact=self.employee_number).exists():
            raise ValidationError("Employee number must be unique.")
        if self.national_id and duplicates.filter(national_id__iexact=self.national_id).exists():
            raise ValidationError("National ID must be unique.")
        if self.email and duplicates.filter(email__iexact=self.email).exists():
            raise ValidationError("Email address must be unique.")
        if self.phone_number and duplicates.filter(phone_number=self.phone_number).exists():
            raise ValidationError("Phone number must be unique.")

    def save(self, *args, **kwargs):
        if not self.department and self.department_ref:
            self.department = self.department_ref.name
        if not self.position and self.position_ref:
            self.position = self.position_ref.title
        self.full_clean()
        super().save(*args, **kwargs)

    def archive(self, user=None, reason=None):
        self.status = "ARCHIVED"
        self.archived_at = timezone.now()
        self.archived_by = user if getattr(user, "is_authenticated", False) else None
        self.archive_reason = reason
        self.save(update_fields=["status", "archived_at", "archived_by", "archive_reason", "updated_at"])


class EmployeeQualification(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="qualifications")
    qualification = models.CharField(max_length=180)
    institution = models.CharField(max_length=180, blank=True, null=True)
    field_of_study = models.CharField(max_length=180, blank=True, null=True)
    date_obtained = models.DateField(blank=True, null=True)
    grade_or_classification = models.CharField(max_length=120, blank=True, null=True)
    certificate = models.FileField(upload_to="hr/qualifications/", null=True, blank=True)

    class Meta:
        db_table = "hr_employee_qualifications"
        ordering = ["employee", "-date_obtained"]


class Vacancy(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
        ("SHORTLISTING", "Shortlisting"),
        ("INTERVIEW", "Interview"),
        ("FILLED", "Filled"),
        ("CANCELLED", "Cancelled"),
    ]

    vacancy_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=150)
    department = models.CharField(max_length=120)
    department_ref = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="vacancies"
    )
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, related_name="vacancies")
    number_of_posts = models.PositiveIntegerField(default=1)
    employment_type = models.CharField(max_length=80, default="FULL_TIME")
    opening_date = models.DateField(default=timezone.localdate)
    description = models.TextField()
    minimum_qualifications = models.TextField(blank=True, null=True)
    experience_required = models.TextField(blank=True, null=True)
    application_instructions = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="OPEN")
    closing_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_vacancies"
        ordering = ["-created_at"]


class Applicant(models.Model):
    STATUS_CHOICES = [
        ("RECEIVED", "Received"),
        ("UNDER_REVIEW", "Under Review"),
        ("SHORTLISTED", "Shortlisted"),
        ("INTERVIEW_SCHEDULED", "Interview Scheduled"),
        ("INTERVIEWED", "Interviewed"),
        ("SELECTED", "Selected"),
        ("REJECTED", "Rejected"),
        ("WITHDRAWN", "Withdrawn"),
    ]

    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name="applicants")
    applicant_number = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=180)
    phone_number = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    qualification = models.CharField(max_length=180, blank=True, null=True)
    cv = models.FileField(upload_to="hr/applicants/cv/", null=True, blank=True)
    supporting_documents = models.FileField(upload_to="hr/applicants/supporting/", null=True, blank=True)
    interview_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default="RECEIVED")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_applicants"
        ordering = ["full_name"]


class Interview(models.Model):
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="interviews")
    scheduled_at = models.DateTimeField()
    panel = models.TextField(blank=True, null=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    result = models.CharField(max_length=40, default="PENDING")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "hr_interviews"


class EmploymentContract(models.Model):
    CONTRACT_CHOICES = [
        ("PERMANENT", "Permanent"),
        ("TEMPORARY", "Temporary"),
        ("PART_TIME", "Part-Time"),
    ]

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="contracts")
    contract_number = models.CharField(max_length=50, unique=True)
    contract_type = models.CharField(max_length=30, choices=CONTRACT_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    salary_or_grade = models.CharField(max_length=120, blank=True, null=True)
    probation_period = models.CharField(max_length=120, blank=True, null=True)
    terms_and_conditions = models.TextField(blank=True, null=True)
    renewal_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=30, default="ACTIVE")
    document = models.FileField(upload_to="hr/contracts/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_employment_contracts"
        ordering = ["-start_date"]


class LeaveBalance(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="leave_balances")
    leave_type = models.CharField(max_length=40)
    allocated_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    used_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "hr_leave_balances"
        unique_together = ("employee", "leave_type")

    @property
    def remaining_days(self):
        return self.allocated_days - self.used_days


class LeaveType(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=30, unique=True)
    default_annual_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    paid = models.BooleanField(default=True)
    requires_document = models.BooleanField(default=False)
    includes_weekends = models.BooleanField(default=False)
    includes_public_holidays = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "hr_leave_types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveApplication(models.Model):
    LEAVE_CHOICES = [
        ("ANNUAL", "Annual Leave"),
        ("SICK", "Sick Leave"),
        ("MATERNITY", "Maternity Leave"),
        ("COMPASSIONATE", "Compassionate Leave"),
        ("STUDY", "Study Leave"),
        ("UNPAID", "Unpaid Leave"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("PENDING", "Pending"),
        ("SUPERVISOR_APPROVED", "Supervisor Approved"),
        ("HR_APPROVED", "HR Approved"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    ]

    application_number = models.CharField(max_length=50, unique=True)
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="leave_applications")
    leave_type = models.CharField(max_length=30, choices=LEAVE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.DecimalField(max_digits=6, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    supporting_document = models.FileField(upload_to="hr/leave/", null=True, blank=True)
    remaining_leave_balance = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    covering_employee = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="covering_leave_applications"
    )
    supervisor_recommendation = models.TextField(blank=True, null=True)
    hr_decision = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="SUBMITTED")
    supervisor_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_supervisor_approvals",
    )
    hr_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_hr_approvals",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_leave_applications"
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError("Leave end date cannot be before start date.")
        if self.employee_id and self.start_date and self.end_date:
            overlap = LeaveApplication.objects.filter(
                employee=self.employee,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            ).exclude(status__in=["REJECTED", "CANCELLED"])
            if self.pk:
                overlap = overlap.exclude(pk=self.pk)
            if overlap.exists():
                raise ValidationError("This employee already has overlapping leave.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StaffAttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("LATE", "Late"),
        ("ON_LEAVE", "On Leave"),
        ("OFFICIAL_DUTY", "Official Duty"),
        ("HALF_DAY", "Half Day"),
        ("HOLIDAY", "Holiday"),
    ]

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="attendance_records")
    attendance_date = models.DateField()
    clock_in = models.TimeField(blank=True, null=True)
    clock_out = models.TimeField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="PRESENT")
    late_minutes = models.PositiveIntegerField(default=0)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    absent = models.BooleanField(default=False)
    biometric_reference = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        db_table = "hr_staff_attendance"
        unique_together = ("employee", "attendance_date")
        ordering = ["-attendance_date"]


class PerformanceReview(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("EMPLOYEE_REVIEW", "Employee Review"),
        ("SUPERVISOR_REVIEW", "Supervisor Review"),
        ("HR_REVIEW", "HR Review"),
        ("COMPLETED", "Completed"),
    ]

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="performance_reviews")
    review_period = models.CharField(max_length=80)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    performance_criteria = models.TextField(blank=True, null=True)
    employee_self_assessment = models.TextField(blank=True, null=True)
    supervisor_assessment = models.TextField(blank=True, null=True)
    kpi_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    strengths = models.TextField(blank=True, null=True)
    areas_for_improvement = models.TextField(blank=True, null=True)
    training_needs = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="DRAFT")
    promotion_recommendation = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_performance_reviews"
        ordering = ["-created_at"]


class TrainingProgram(models.Model):
    title = models.CharField(max_length=180)
    provider = models.CharField(max_length=180, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    venue = models.CharField(max_length=180, blank=True, null=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    objectives = models.TextField(blank=True, null=True)
    evaluation = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, default="PLANNED")
    certificate_required = models.BooleanField(default=False)

    class Meta:
        db_table = "hr_training_programs"


class EmployeeTrainingRecord(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="training_records")
    program = models.ForeignKey(TrainingProgram, on_delete=models.PROTECT, related_name="employee_records")
    certificate = models.FileField(upload_to="hr/training/", null=True, blank=True)
    certificate_expiry_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=30, default="COMPLETED")

    class Meta:
        db_table = "hr_employee_training_records"
        unique_together = ("employee", "program")


class DisciplinaryAction(models.Model):
    ACTION_CHOICES = [
        ("WARNING", "Warning"),
        ("SUSPENSION", "Suspension"),
        ("INVESTIGATION", "Investigation"),
        ("HEARING", "Hearing"),
        ("APPEAL", "Appeal"),
    ]

    case_number = models.CharField(max_length=50, unique=True)
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="disciplinary_actions")
    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)
    incident_date = models.DateField()
    description = models.TextField()
    outcome = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_disciplinary_actions"
        ordering = ["-created_at"]


class StaffDocument(models.Model):
    DOCUMENT_CHOICES = [
        ("CONTRACT", "Employment Contract"),
        ("QUALIFICATION", "Qualification"),
        ("CERTIFICATE", "Certificate"),
        ("NATIONAL_ID", "National ID"),
        ("CV", "CV"),
        ("PERFORMANCE", "Performance Report"),
        ("DISCIPLINARY", "Disciplinary Document"),
        ("POLICE_CLEARANCE", "Police Clearance"),
        ("MEDICAL", "Medical Document"),
        ("LEAVE", "Leave Document"),
        ("TRAINING", "Training Certificate"),
        ("OTHER", "Other Document"),
    ]
    ACCESS_CHOICES = [
        ("PUBLIC_HR", "HR Visible"),
        ("RESTRICTED", "Restricted"),
        ("CONFIDENTIAL", "Confidential"),
    ]

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_CHOICES)
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to="hr/documents/")
    expiry_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    access_level = models.CharField(max_length=30, choices=ACCESS_CHOICES, default="RESTRICTED")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_staff_documents"
        ordering = ["-uploaded_at"]


class HRDocumentAccessLog(models.Model):
    document = models.ForeignKey(StaffDocument, on_delete=models.CASCADE, related_name="access_logs")
    accessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=40, default="VIEW")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_document_access_logs"
        ordering = ["-accessed_at"]


class HRAuditLog(models.Model):
    module = models.CharField(max_length=80, default="Human Resources")
    action = models.CharField(max_length=120)
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hr_audit_logs"
        ordering = ["-created_at"]
