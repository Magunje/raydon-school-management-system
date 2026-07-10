from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MedicalCondition(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "medical_conditions"
        ordering = ["name"]

    def __str__(self):
        return self.name


class MedicalProfile(models.Model):
    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
        ("UNKNOWN", "Unknown"),
    ]

    student = models.OneToOneField(
        "student_registry.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="medical_profile",
    )
    employee = models.OneToOneField(
        "human_resources.EmployeeProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="medical_profile",
    )
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUP_CHOICES, default="UNKNOWN")
    allergies = models.TextField(blank=True, null=True)
    chronic_conditions = models.TextField(blank=True, null=True)
    disabilities = models.TextField(blank=True, null=True)
    long_term_medication = models.TextField(blank=True, null=True)
    dietary_restrictions = models.TextField(blank=True, null=True)
    special_needs = models.TextField(blank=True, null=True)
    medical_aid_information = models.TextField(blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=180)
    emergency_contact_relationship = models.CharField(max_length=80, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=50)
    conditions = models.ManyToManyField(MedicalCondition, blank=True, related_name="profiles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medical_profiles"
        ordering = ["-updated_at"]

    @property
    def patient_name(self):
        if self.student:
            return f"{self.student.first_name} {self.student.surname}"
        if self.employee:
            return self.employee.full_name
        return "Unlinked patient"

    @property
    def patient_reference(self):
        if self.student:
            return self.student.admission_no
        if self.employee:
            return self.employee.employee_number
        return ""

    def clean(self):
        super().clean()
        if bool(self.student) == bool(self.employee):
            raise ValidationError("A medical profile must link to exactly one student or one employee.")
        if not self.emergency_contact_name or not self.emergency_contact_phone:
            raise ValidationError("Emergency contact name and phone are required.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient_name} ({self.patient_reference})"


class ClinicVisit(models.Model):
    OUTCOME_CHOICES = [
        ("TREATED", "Treated"),
        ("FOLLOW_UP", "Follow-Up Required"),
        ("REFERRED", "Referred"),
        ("SICK_BAY", "Admitted to Sick Bay"),
        ("CLOSED", "Closed"),
    ]

    visit_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="clinic_visits")
    visit_date = models.DateField()
    visit_time = models.TimeField()
    symptoms = models.TextField()
    diagnosis = models.TextField(blank=True, null=True)
    treatment = models.TextField(blank=True, null=True)
    medication_prescribed = models.TextField(blank=True, null=True)
    medical_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinic_visits_handled",
    )
    outcome = models.CharField(max_length=30, choices=OUTCOME_CHOICES, default="TREATED")
    confidential_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "medical_clinic_visits"
        ordering = ["-visit_date", "-visit_time"]


class Medication(models.Model):
    medicine_code = models.CharField(max_length=50, unique=True)
    medicine_name = models.CharField(max_length=180)
    category = models.CharField(max_length=120, blank=True, null=True)
    quantity_available = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    expiry_date = models.DateField()
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    supplier = models.CharField(max_length=180, blank=True, null=True)
    inventory_item = models.ForeignKey(
        "inventory_management.InventoryItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clinic_medications",
    )
    barcode = models.CharField(max_length=120, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "medical_medications"
        ordering = ["medicine_name"]

    def clean(self):
        super().clean()
        if self.quantity_available < Decimal("0.00"):
            raise ValidationError("Medication stock cannot become negative.")

    def __str__(self):
        return f"{self.medicine_code} - {self.medicine_name}"


class MedicationDispense(models.Model):
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="medication_dispenses")
    clinic_visit = models.ForeignKey(ClinicVisit, on_delete=models.SET_NULL, null=True, blank=True, related_name="dispenses")
    medication = models.ForeignKey(Medication, on_delete=models.PROTECT, related_name="dispenses")
    dosage = models.CharField(max_length=120)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    dispensed_date = models.DateField()
    prescribed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medications_prescribed",
    )
    dispensed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medications_dispensed",
    )

    class Meta:
        db_table = "medical_medication_dispenses"
        ordering = ["-dispensed_date"]


class MedicalEmergency(models.Model):
    INCIDENT_CHOICES = [
        ("ACCIDENT", "Accident"),
        ("INJURY", "Injury"),
        ("ALLERGIC_REACTION", "Allergic Reaction"),
        ("SEVERE_ILLNESS", "Severe Illness"),
        ("SPORTS_INJURY", "Sports Injury"),
        ("MEDICAL_EMERGENCY", "Medical Emergency"),
    ]

    incident_number = models.CharField(max_length=50, unique=True)
    incident_date = models.DateField()
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="emergencies")
    incident_type = models.CharField(max_length=40, choices=INCIDENT_CHOICES)
    description = models.TextField()
    treatment = models.TextField(blank=True, null=True)
    referral_status = models.CharField(max_length=40, default="NOT_REFERRED")
    parent_notification_status = models.CharField(max_length=40, default="PENDING")
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medical_emergencies_handled",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "medical_emergencies"
        ordering = ["-incident_date"]


class MedicalReferral(models.Model):
    REFERRAL_CHOICES = [
        ("LOCAL_CLINIC", "Local Clinic"),
        ("HOSPITAL", "Hospital"),
        ("SPECIALIST", "Specialist"),
        ("PSYCHOLOGIST", "Psychologist"),
        ("COUNSELLOR", "Counsellor"),
    ]

    referral_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="referrals")
    referral_date = models.DateField()
    referral_type = models.CharField(max_length=40, choices=REFERRAL_CHOICES)
    institution = models.CharField(max_length=180)
    reason = models.TextField()
    outcome = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "medical_referrals"
        ordering = ["-referral_date"]


class ImmunisationRecord(models.Model):
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="immunisations")
    vaccine_name = models.CharField(max_length=150)
    vaccination_date = models.DateField()
    next_due_date = models.DateField(blank=True, null=True)
    provider = models.CharField(max_length=180, blank=True, null=True)
    batch_number = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        db_table = "medical_immunisations"
        ordering = ["next_due_date", "-vaccination_date"]


class MedicalAppointment(models.Model):
    APPOINTMENT_CHOICES = [
        ("FOLLOW_UP", "Follow-Up Visit"),
        ("SPECIALIST", "Specialist Appointment"),
        ("ROUTINE", "Routine Check-Up"),
    ]

    appointment_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="appointments")
    appointment_type = models.CharField(max_length=30, choices=APPOINTMENT_CHOICES)
    scheduled_at = models.DateTimeField()
    reminder_sent = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "medical_appointments"
        ordering = ["scheduled_at"]


class SickBayAdmission(models.Model):
    admission_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="sick_bay_admissions")
    bed_number = models.CharField(max_length=50)
    admission_time = models.DateTimeField()
    discharge_time = models.DateTimeField(blank=True, null=True)
    observations = models.TextField(blank=True, null=True)
    treatment_notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "medical_sick_bay_admissions"
        ordering = ["-admission_time"]


class MedicalCertificate(models.Model):
    CERTIFICATE_CHOICES = [
        ("SICK_NOTE", "Sick Note"),
        ("CLEARANCE", "Medical Clearance Letter"),
        ("REFERRAL", "Referral Letter"),
        ("REPORT", "Medical Report"),
    ]

    certificate_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="certificates")
    certificate_type = models.CharField(max_length=30, choices=CERTIFICATE_CHOICES)
    issued_date = models.DateField()
    summary = models.TextField()
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    pdf_file = models.FileField(upload_to="medical/certificates/", null=True, blank=True)

    class Meta:
        db_table = "medical_certificates"
        ordering = ["-issued_date"]


class MedicalAttendanceExcuse(models.Model):
    EXCUSE_CHOICES = [
        ("MEDICAL_LEAVE", "Medical Leave"),
        ("HOSPITALISATION", "Hospitalisation"),
        ("EXCUSED_ABSENCE", "Excused Absence"),
    ]

    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="attendance_excuses")
    excuse_type = models.CharField(max_length=30, choices=EXCUSE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    attendance_updated = models.BooleanField(default=False)

    class Meta:
        db_table = "medical_attendance_excuses"
        ordering = ["-start_date"]


class MedicalNotification(models.Model):
    NOTIFICATION_CHOICES = [
        ("EMERGENCY", "Medical Emergency"),
        ("PARENT_CONTACT", "Parent Contact Required"),
        ("MEDICATION_REMINDER", "Medication Reminder"),
        ("FOLLOW_UP", "Follow-Up Appointment"),
        ("IMMUNISATION_DUE", "Immunisation Due"),
        ("REFERRAL", "Referral Appointment"),
    ]

    patient = models.ForeignKey(MedicalProfile, on_delete=models.PROTECT, related_name="medical_notifications")
    notification_type = models.CharField(max_length=40, choices=NOTIFICATION_CHOICES)
    message = models.TextField()
    channel = models.CharField(max_length=30, default="PORTAL")
    status = models.CharField(max_length=30, default="QUEUED")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "medical_notifications"
        ordering = ["-created_at"]


class MedicalAuditLog(models.Model):
    module = models.CharField(max_length=80, default="Medical")
    action = models.CharField(max_length=120)
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "medical_audit_logs"
        ordering = ["-created_at"]
