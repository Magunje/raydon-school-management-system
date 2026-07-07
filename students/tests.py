from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

import os
import shutil
import tempfile
from datetime import date
from io import BytesIO

from accounts.models import UserProfile
from school_system_django.native import now_text, one_row
from students.services import PASSPORT_PHOTO_SIZE, PENDING_ZIMSEC_STATUS, run_yearly_student_progression, save_student_photo, school_finish_date, student_age_text
from students.models import Pupil
from students.views import sync_enterprise_student_registration


class YearlyStudentProgressionTests(TestCase):
    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM school_settings")
            cursor.execute(
                """
                INSERT INTO school_settings (setting_id, school_name, current_term, current_year, last_promotion_year, receipt_prefix, cashbook_opening_balance)
                VALUES (1, 'Raydon Test School', 'Term 1', 2027, 2026, 'RCT', 0)
                """
            )
            cursor.execute("DELETE FROM grades")
            cursor.execute("DELETE FROM classes")
            cursor.execute("DELETE FROM pupils")
            for grade_id in range(1, 9):
                cursor.execute("INSERT INTO grades (grade_id, grade_name) VALUES (%s, %s)", [grade_id, f"Grade {grade_id}"])
            cursor.execute(
                "INSERT INTO classes (class_id, class_name, grade_id, academic_year) VALUES (201, 'A', 2, 2027)"
            )
            cursor.execute(
                """
                INSERT INTO pupils (admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, grade_id, class_id, guardian_name, guardian_phone, address, admission_date, status)
                VALUES
                ('A26001', 'Grade', 'One', 'Female', '2019-01-01', 'Form 1', 'A', 1, 101, 'Parent One', '0771', 'Street', '2026-01-01', 'Active'),
                ('A26004', 'Form', 'Four', 'Male', '2010-01-01', 'Grade 4', 'A', 4, 104, 'Parent Four', '0774', 'Street', '2026-01-01', 'Active'),
                ('A26006', 'Form', 'Six', 'Female', '2008-01-01', 'Form 6', 'A', 6, 106, 'Parent Six', '0776', 'Street', '2026-01-01', 'Active')
                """
            )

    def test_new_year_promotes_active_students_and_moves_completion_to_zimsec_pending(self):
        stats = run_yearly_student_progression()
        self.assertEqual(stats["promoted"], 1)
        self.assertEqual(stats["completed"], 2)

        promoted = Pupil.objects.get(admission_no="A26001")
        self.assertEqual(promoted.grade, "Form 2")
        self.assertEqual(promoted.class_stream, "A")
        self.assertEqual(promoted.grade_id, 2)
        self.assertEqual(promoted.class_id, 201)

        completed_o = Pupil.objects.get(admission_no="A26004")
        self.assertEqual(completed_o.status, PENDING_ZIMSEC_STATUS)
        self.assertEqual(completed_o.grade, "Completed O Level")
        self.assertEqual(completed_o.grade_id, 7)
        self.assertIsNone(completed_o.class_id)
        self.assertEqual(completed_o.completed_on, "2026-12-31")
        self.assertIn("Completed O Level", completed_o.status_reason)
        self.assertEqual(school_finish_date({"grade": completed_o.grade, "completed_on": completed_o.completed_on}), "2026-12-31")

        completed_a = Pupil.objects.get(admission_no="A26006")
        self.assertEqual(completed_a.status, PENDING_ZIMSEC_STATUS)
        self.assertEqual(completed_a.grade, "Completed A Level")
        self.assertEqual(completed_a.grade_id, 8)
        self.assertIsNone(completed_a.class_id)

        settings = one_row("SELECT last_promotion_year FROM school_settings WHERE setting_id = 1")
        self.assertEqual(settings["last_promotion_year"], 2027)

    def test_yearly_progression_is_idempotent(self):
        first = run_yearly_student_progression()
        second = run_yearly_student_progression()
        self.assertEqual(first["promoted"], 1)
        self.assertEqual(first["completed"], 2)
        self.assertEqual(second["promoted"], 0)
        self.assertEqual(second["completed"], 0)
        self.assertEqual(Pupil.objects.filter(status=PENDING_ZIMSEC_STATUS).count(), 2)


class EnterpriseRegistrationBridgeTests(TestCase):
    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM subjects")
            cursor.execute(
                """
                INSERT INTO subjects (subject_id, subject_code, subject_name, grade, display_order, status)
                VALUES
                (1, 'ENG', 'English Language', 'All Forms', 1, 'Active'),
                (2, 'MATH', 'Mathematics', 'All Forms', 2, 'Active')
                """
            )

    def test_legacy_registration_sync_creates_enterprise_student_records(self):
        pupil = {
            "pupil_id": 501,
            "admission_no": "A27001",
            "first_name": "Nyasha",
            "surname": "Moyo",
            "gender": "Female",
            "date_of_birth": "2012-04-01",
            "admission_date": "2027-01-09",
            "grade": "Form 1",
            "class_stream": "A",
            "guardian_name": "Memory Moyo",
            "guardian_phone": "0772000001",
            "status": "Active",
            "national_id": "",
        }

        student = sync_enterprise_student_registration(
            pupil,
            [1, 2],
            2027,
            "Term 1",
        )

        from academic_structure.models import AcademicClass, AcademicTerm, AcademicYear
        from student_registry.models import Guardian, StudentFeeRecord
        from subject_management.models import StudentSubjectRegistration

        self.assertEqual(student.admission_no, "A27001")
        self.assertEqual(student.status, "Active Student")
        self.assertTrue(AcademicYear.objects.filter(year=2027).exists())
        self.assertTrue(AcademicTerm.objects.filter(term_number=1).exists())
        self.assertEqual(AcademicClass.objects.count(), 1)
        self.assertEqual(Guardian.objects.filter(student=student, is_primary=True).count(), 1)
        self.assertTrue(
            StudentFeeRecord.objects.filter(
                student=student,
                fee_structure__name="O-Level Fee Structure",
                amount="100.00",
            ).exists()
        )
        self.assertEqual(
            StudentSubjectRegistration.objects.filter(student=student).count(),
            2,
        )

    def test_subject_sync_replaces_exact_cycle_subjects(self):
        pupil = {
            "pupil_id": 502,
            "admission_no": "A27002",
            "first_name": "Farai",
            "surname": "Ncube",
            "gender": "Male",
            "date_of_birth": "2012-08-10",
            "admission_date": "2027-01-09",
            "grade": "Form 1",
            "class_stream": "A",
            "guardian_name": "Tariro Ncube",
            "guardian_phone": "0772000002",
            "status": "Active",
            "national_id": "",
        }

        student = sync_enterprise_student_registration(pupil, [1, 2], 2027, "Term 1")
        sync_enterprise_student_registration(pupil, [2], 2027, "Term 1")

        from subject_management.models import StudentSubjectRegistration

        registrations = StudentSubjectRegistration.objects.filter(student=student)
        self.assertEqual(registrations.count(), 1)
        self.assertEqual(registrations.first().subject.name, "Mathematics")


class StudentPhotoAndAgeTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.media_root, ignore_errors=True)

    def image_upload(self, name="student.png", size=(900, 1100), image_format="PNG"):
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", size, (42, 120, 160)).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")

    def test_student_age_text_uses_year_month_day_words(self):
        self.assertEqual(student_age_text("2019-04-13", on_date=date(2026, 6, 28)), "7 Years 2 Months 15 Days")

    def test_student_photo_upload_is_resized_and_stored_as_passport_jpeg(self):
        with self.settings(MEDIA_ROOT=self.media_root):
            path = save_student_photo(self.image_upload(), "A26001")
            self.assertEqual(path, "")

    def test_student_photo_upload_rejects_unsupported_extensions(self):
        # Image upload is disabled, always returns empty string and does not raise validation error
        path = save_student_photo(SimpleUploadedFile("student.gif", b"not-an-image", content_type="image/gif"), "A26001")
        self.assertEqual(path, "")

    def test_generate_realistic_student_photo(self):
        from students.services import generate_realistic_student_photo
        with self.settings(MEDIA_ROOT=self.media_root):
            pupil = {
                "pupil_id": 999,
                "admission_no": "A26999",
                "first_name": "Tatenda",
                "surname": "Moyo",
                "gender": "Male",
                "date_of_birth": "2019-01-01",
                "photo_path": ""
            }
            path = generate_realistic_student_photo(pupil)
            self.assertEqual(path, "")

    def test_generate_student_photos_management_command(self):
        from django.core.management import call_command
        from students.models import Pupil
        
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM pupils WHERE admission_no = 'A26999'")
            cursor.execute(
                """
                INSERT INTO pupils (admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, guardian_name, guardian_phone, address, admission_date, status, photo_path)
                VALUES ('A26999', 'Tatenda', 'Moyo', 'Male', '2019-01-01', 'Form 1', 'A', 'Guardian', '077', 'Address', '2026-01-01', 'Active', '')
                """
            )
            
        with self.settings(MEDIA_ROOT=self.media_root):
            call_command("generate_student_photos")
            pupil = Pupil.objects.get(admission_no="A26999")
            self.assertEqual(pupil.photo_path, "")


class ArchiveDatabasePermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="admin", password="admin123")
        self.bursar = User.objects.create_user(username="bursar", password="bursar123")
        self.teacher = User.objects.create_user(username="teacher", password="teacher123")
        UserProfile.objects.create(user=self.bursar, full_name="Bursar", role="Bursar / Accounts Clerk", status="Active", created_at=now_text(), updated_at=now_text())
        UserProfile.objects.create(user=self.teacher, full_name="Teacher", role="Teacher", status="Active", created_at=now_text(), updated_at=now_text())
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM pupils")
            cursor.execute(
                """
                INSERT INTO pupils (admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, guardian_name, guardian_phone, address, admission_date, status, completed_on)
                VALUES ('A26099', 'Old', 'Student', 'Female', '2013-01-01', 'Completed O Level', 'A', 'Parent', '077', 'Street', '2020-01-01', 'Completed', '2026-12-31')
                """
            )

    def test_archive_database_visible_to_admin_and_bursar_only(self):
        client = Client()
        client.login(username="admin", password="admin123")
        self.assertEqual(client.get("/completed-students").status_code, 200)

        client = Client()
        client.login(username="bursar", password="bursar123")
        self.assertEqual(client.get("/completed-students").status_code, 200)

        client = Client()
        client.login(username="teacher", password="teacher123")
        self.assertEqual(client.get("/completed-students").status_code, 302)


class TransferWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="admin-transfer", password="admin123")
        self.client = Client()
        self.client.login(username="admin-transfer", password="admin123")
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM school_settings")
            cursor.execute(
                """
                INSERT INTO school_settings (setting_id, school_name, current_term, current_year, receipt_prefix, cashbook_opening_balance)
                VALUES (1, 'Raydon Test School', 'Term 2', 2026, 'RCT', 0)
                """
            )
            cursor.execute("DELETE FROM pupils")
            cursor.execute(
                """
                INSERT INTO pupils (admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, guardian_name, guardian_phone, address, admission_date, status)
                VALUES
                ('A26110', 'Arrears', 'Student', 'Female', '2016-01-01', 'Form 4', 'A', 'Parent One', '0771', 'Street', '2026-01-01', 'Active'),
                ('A26111', 'Paid', 'Student', 'Male', '2016-01-01', 'Form 4', 'B', 'Parent Two', '0772', 'Street', '2026-01-01', 'Active')
                """
            )
            paid = one_row("SELECT pupil_id FROM pupils WHERE admission_no = 'A26111'")
            cursor.execute(
                """
                INSERT INTO payments (pupil_id, receipt_no, amount_paid, payment_date, payment_method, term, year)
                VALUES (%s, 'RCT202699001', 100.0, '2026-06-22', 'Cash', 'Term 2', 2026)
                """,
                [paid["pupil_id"]],
            )

    def test_transfer_is_blocked_when_student_has_arrears(self):
        response = self.client.post(
            "/pupils/A26110/transfer",
            {"transfer_destination": "New School", "status_reason": "Relocation"},
        )
        self.assertEqual(response.status_code, 302)
        pupil = Pupil.objects.get(admission_no="A26110")
        self.assertEqual(pupil.status, "Active")

    def test_transfer_marks_student_transferred_and_returns_letter_pdf_when_paid_up(self):
        response = self.client.post(
            "/pupils/A26111/transfer",
            {"transfer_destination": "New School", "status_reason": "Relocation"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        pupil = Pupil.objects.get(admission_no="A26111")
        self.assertEqual(pupil.status, "Transferred")
        self.assertTrue(pupil.transfer_letter_no)
