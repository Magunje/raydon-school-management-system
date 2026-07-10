from decimal import Decimal
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from attendance_ledger.models import AttendanceRecord
from medical.models import MedicalAuditLog, MedicalNotification, Medication
from medical.services import (
    create_attendance_excuse,
    create_medical_profile,
    create_referral,
    dispense_medication,
    record_clinic_visit,
    record_emergency,
)
from student_registry.models import Student


User = get_user_model()


class MedicalClinicWorkflowTests(TestCase):
    def setUp(self):
        self.nurse = User.objects.create_user(username="nurse", password="password123")
        self.student = Student.objects.create(
            first_name="Tariro",
            surname="Moyo",
            gender="Female",
            date_of_birth=datetime.date(2012, 4, 1),
            admission_date=datetime.date(2026, 1, 10),
            status="Active Student",
        )
        self.profile = create_medical_profile(
            student=self.student,
            blood_group="O+",
            allergies="Penicillin",
            emergency_contact_name="Mrs Moyo",
            emergency_contact_relationship="Mother",
            emergency_contact_phone="+263771234567",
        )
        self.medication = Medication.objects.create(
            medicine_code="MED-PARA",
            medicine_name="Paracetamol",
            category="Pain Relief",
            quantity_available=Decimal("20.00"),
            expiry_date=datetime.date.today() + datetime.timedelta(days=60),
            reorder_level=Decimal("5.00"),
        )

    def test_clinic_visit_dispensing_emergency_referral_and_attendance(self):
        visit = record_clinic_visit(
            patient=self.profile,
            visit_date=datetime.date(2026, 2, 1),
            visit_time=datetime.time(9, 30),
            symptoms="Headache",
            diagnosis="Mild fever",
            treatment="Rest and fluids",
            medical_officer=self.nurse,
        )
        dispense = dispense_medication(
            patient=self.profile,
            clinic_visit=visit,
            medication=self.medication,
            dosage="1 tablet",
            quantity=Decimal("2.00"),
            dispensed_date=datetime.date.today(),
            prescribed_by=self.nurse,
            dispensed_by=self.nurse,
        )
        self.medication.refresh_from_db()
        self.assertEqual(self.medication.quantity_available, Decimal("18.00"))
        self.assertEqual(dispense.quantity, Decimal("2.00"))

        emergency = record_emergency(
            patient=self.profile,
            incident_date=datetime.date(2026, 2, 2),
            incident_type="ALLERGIC_REACTION",
            description="Rash and swelling",
            treatment="Antihistamine",
            handled_by=self.nurse,
        )
        self.assertTrue(MedicalNotification.objects.filter(patient=self.profile, notification_type="EMERGENCY").exists())

        referral = create_referral(
            patient=self.profile,
            referral_date=datetime.date(2026, 2, 3),
            referral_type="COUNSELLOR",
            institution="School Counselling Office",
            reason="Wellness follow-up",
            created_by=self.nurse,
        )
        self.assertTrue(referral.referral_number.startswith("REF-"))

        excuse = create_attendance_excuse(
            patient=self.profile,
            excuse_type="MEDICAL_LEAVE",
            start_date=datetime.date(2026, 2, 4),
            end_date=datetime.date(2026, 2, 5),
            reason="Medical leave after emergency",
        )
        self.assertTrue(excuse.attendance_updated)
        self.assertEqual(AttendanceRecord.objects.filter(student=self.student, status="Sick").count(), 2)

        audit = MedicalAuditLog.objects.get(action="Clinic visit", reference_number=visit.visit_number)
        self.assertNotIn("Mild fever", str(audit.new_value))
        self.assertTrue(MedicalAuditLog.objects.filter(action="Emergency case", reference_number=emergency.incident_number).exists())

    def test_expired_and_negative_medication_dispensing_are_blocked(self):
        expired = Medication.objects.create(
            medicine_code="MED-OLD",
            medicine_name="Expired Medicine",
            quantity_available=Decimal("10.00"),
            expiry_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            dispense_medication(
                patient=self.profile,
                medication=expired,
                dosage="1 tablet",
                quantity=Decimal("1.00"),
                dispensed_date=timezone.localdate(),
            )
        with self.assertRaises(ValidationError):
            dispense_medication(
                patient=self.profile,
                medication=self.medication,
                dosage="1 tablet",
                quantity=Decimal("50.00"),
                dispensed_date=timezone.localdate(),
            )

    def test_medical_list_view(self):
        self.client.force_login(self.nurse)
        response = self.client.get('/medical-clinic/')
        self.assertEqual(response.status_code, 200)
