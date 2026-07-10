from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from attendance_ledger.models import AttendanceRecord
from medical.models import (
    ClinicVisit,
    ImmunisationRecord,
    MedicalAppointment,
    MedicalAttendanceExcuse,
    MedicalAuditLog,
    MedicalEmergency,
    MedicalNotification,
    MedicalProfile,
    MedicalReferral,
    Medication,
    MedicationDispense,
    SickBayAdmission,
)


def next_medical_number(prefix, model):
    return f"{prefix}-{model.objects.count() + 1:05d}"


def log_medical_action(action, reference_number=None, user=None, new_value=None, reason=None):
    # Keep sensitive clinical notes out of the audit log by design.
    return MedicalAuditLog.objects.create(
        action=action,
        reference_number=reference_number,
        user=user,
        new_value=new_value,
        reason=reason,
    )


def create_medical_profile(**kwargs):
    profile = MedicalProfile.objects.create(**kwargs)
    log_medical_action(
        "Medical profile creation",
        reference_number=profile.patient_reference,
        new_value={"patient": profile.patient_reference, "blood_group": profile.blood_group},
    )
    return profile


def record_clinic_visit(patient, visit_date, visit_time, symptoms, diagnosis="", treatment="", medication_prescribed="", medical_officer=None, outcome="TREATED"):
    visit = ClinicVisit.objects.create(
        visit_number=next_medical_number("VIS", ClinicVisit),
        patient=patient,
        visit_date=visit_date,
        visit_time=visit_time,
        symptoms=symptoms,
        diagnosis=diagnosis,
        treatment=treatment,
        medication_prescribed=medication_prescribed,
        medical_officer=medical_officer,
        outcome=outcome,
    )
    log_medical_action(
        "Clinic visit",
        reference_number=visit.visit_number,
        user=medical_officer,
        new_value={"patient": patient.patient_reference, "outcome": outcome},
    )
    return visit


@transaction.atomic
def dispense_medication(patient, medication, dosage, quantity, dispensed_date, prescribed_by=None, dispensed_by=None, clinic_visit=None):
    if quantity <= Decimal("0.00"):
        raise ValidationError("Medication quantity must be greater than zero.")
    if medication.expiry_date < dispensed_date:
        raise ValidationError("Expired medication cannot be dispensed.")

    medication = Medication.objects.select_for_update().get(pk=medication.pk)
    if medication.quantity_available < quantity:
        raise ValidationError("Medication stock cannot become negative.")
    medication.quantity_available -= quantity
    medication.full_clean()
    medication.save(update_fields=["quantity_available"])

    if medication.inventory_item:
        medication.inventory_item.current_quantity = max(
            medication.inventory_item.current_quantity - quantity,
            Decimal("0.00"),
        )
        medication.inventory_item.save(update_fields=["current_quantity"])

    dispense = MedicationDispense.objects.create(
        patient=patient,
        clinic_visit=clinic_visit,
        medication=medication,
        dosage=dosage,
        quantity=quantity,
        dispensed_date=dispensed_date,
        prescribed_by=prescribed_by,
        dispensed_by=dispensed_by,
    )
    log_medical_action(
        "Medication dispensing",
        reference_number=medication.medicine_code,
        user=dispensed_by,
        new_value={"patient": patient.patient_reference, "quantity": str(quantity)},
    )
    return dispense


def record_emergency(patient, incident_date, incident_type, description, treatment="", handled_by=None, parent_notification_status="PENDING"):
    emergency = MedicalEmergency.objects.create(
        incident_number=next_medical_number("EMR", MedicalEmergency),
        incident_date=incident_date,
        patient=patient,
        incident_type=incident_type,
        description=description,
        treatment=treatment,
        handled_by=handled_by,
        parent_notification_status=parent_notification_status,
    )
    MedicalNotification.objects.create(
        patient=patient,
        notification_type="EMERGENCY",
        message=f"Medical emergency recorded for {patient.patient_name}. Parent contact required.",
        status="QUEUED",
    )
    log_medical_action(
        "Emergency case",
        reference_number=emergency.incident_number,
        user=handled_by,
        new_value={"patient": patient.patient_reference, "incident_type": incident_type},
    )
    return emergency


def create_referral(patient, referral_date, referral_type, institution, reason, created_by=None):
    referral = MedicalReferral.objects.create(
        referral_number=next_medical_number("REF", MedicalReferral),
        patient=patient,
        referral_date=referral_date,
        referral_type=referral_type,
        institution=institution,
        reason=reason,
        created_by=created_by,
    )
    if referral_type in {"PSYCHOLOGIST", "COUNSELLOR"}:
        MedicalNotification.objects.create(
            patient=patient,
            notification_type="REFERRAL",
            message=f"Mental health/counselling referral scheduled with {institution}.",
        )
    log_medical_action(
        "Medical referral",
        reference_number=referral.referral_number,
        user=created_by,
        new_value={"patient": patient.patient_reference, "type": referral_type, "institution": institution},
    )
    return referral


def create_appointment(patient, appointment_type, scheduled_at, notes=None):
    appointment = MedicalAppointment.objects.create(
        appointment_number=next_medical_number("APP", MedicalAppointment),
        patient=patient,
        appointment_type=appointment_type,
        scheduled_at=scheduled_at,
        notes=notes,
    )
    MedicalNotification.objects.create(
        patient=patient,
        notification_type="FOLLOW_UP" if appointment_type == "FOLLOW_UP" else "REFERRAL",
        message=f"Medical appointment scheduled for {scheduled_at:%Y-%m-%d %H:%M}.",
    )
    log_medical_action("Appointment scheduling", reference_number=appointment.appointment_number)
    return appointment


def immunisations_due(days=30):
    today = timezone.localdate()
    limit = today + timezone.timedelta(days=days)
    return ImmunisationRecord.objects.filter(next_due_date__gte=today, next_due_date__lte=limit)


def low_stock_medications():
    return Medication.objects.filter(quantity_available__lte=models.F("reorder_level"))


def admit_to_sick_bay(patient, bed_number, admission_time, observations="", treatment_notes=""):
    admission = SickBayAdmission.objects.create(
        admission_number=next_medical_number("SB", SickBayAdmission),
        patient=patient,
        bed_number=bed_number,
        admission_time=admission_time,
        observations=observations,
        treatment_notes=treatment_notes,
    )
    log_medical_action("Sick bay admission", reference_number=admission.admission_number)
    return admission


def create_attendance_excuse(patient, excuse_type, start_date, end_date, reason):
    excuse = MedicalAttendanceExcuse.objects.create(
        patient=patient,
        excuse_type=excuse_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
    )
    if patient.student:
        current = start_date
        while current <= end_date:
            AttendanceRecord.objects.update_or_create(
                student=patient.student,
                date=current,
                mode="DAILY",
                defaults={"status": "Sick" if excuse_type == "MEDICAL_LEAVE" else "Excused"},
            )
            current += timezone.timedelta(days=1)
        excuse.attendance_updated = True
        excuse.save(update_fields=["attendance_updated"])
    log_medical_action(
        "Attendance integration",
        reference_number=patient.patient_reference,
        new_value={"start": str(start_date), "end": str(end_date), "type": excuse_type},
        reason=reason,
    )
    return excuse
