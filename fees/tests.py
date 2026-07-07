from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import connection
from fees.models import Payment, PaymentAllocation, TermBill, FeesStructure
from students.models import Pupil
from school_system_django.native import insert_record, now_text, today_text
from fees.services import ensure_current_term_bills_for_active_students, ensure_standard_fee_structure, next_admission_no, next_receipt_no, receipt_context, save_payment

class FeesTestCase(TestCase):
    def setUp(self):
        # Create users
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='admin', password='admin123')
        
        # Create a standard user (bursar role)
        self.bursar_user = User.objects.create_user(username='bursar', password='bursar123')
        # Create a profile for the bursar user
        with connection.cursor() as cursor:
            # We insert into users table first since profile links to it or uses legacy_user_id
            cursor.execute("INSERT INTO users (username, password_hash, role, status) VALUES ('bursar', 'bursar123', 'Bursar / Accounts Clerk', 'Active')")
            b_id = cursor.lastrowid
            
            # Create the auth user profile mapping
            cursor.execute(
                """
                INSERT INTO accounts_userprofile (user_id, legacy_user_id, full_name, role, status, created_at, updated_at)
                VALUES (%s, %s, 'Test Bursar', 'Bursar / Accounts Clerk', 'Active', %s, %s)
                """,
                [self.bursar_user.id, b_id, now_text(), now_text()]
            )

        # Create a teacher user
        self.teacher_user = User.objects.create_user(username='teacher', password='teacher123')
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO users (username, password_hash, role, status) VALUES ('teacher', 'teacher123', 'Teacher', 'Active')")
            t_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO accounts_userprofile (user_id, legacy_user_id, full_name, role, status, created_at, updated_at)
                VALUES (%s, %s, 'Test Teacher', 'Teacher', 'Active', %s, %s)
                """,
                [self.teacher_user.id, t_id, now_text(), now_text()]
            )

        # Log in admin client
        self.client = Client()
        self.client.login(username='admin', password='admin123')

        # Insert pupils directly
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pupils (admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, guardian_name, guardian_phone, address, admission_date, status)
                VALUES 
                ('A26001', 'Alice', 'Smith', 'Female', '2015-01-01', 'Form 1', 'A', 'John Smith', '12345', 'Street 1', '2026-01-01', 'Active')
                """
            )
            cursor.execute("SELECT pupil_id FROM pupils WHERE admission_no = 'A26001'")
            self.pupil_id = cursor.fetchone()[0]

            # Insert an active subject and register Alice for it
            cursor.execute(
                """
                INSERT INTO subjects (subject_code, subject_name, grade, display_order, status)
                VALUES ('MATH', 'Mathematics', 'Form 1', 1, 'Active')
                """
            )
            self.subject_id = cursor.lastrowid
            
            cursor.execute(
                """
                INSERT INTO student_subjects (pupil_id, subject_id, academic_year, form, stream)
                VALUES (%s, %s, 2026, 'Form 1', 'A')
                """,
                [self.pupil_id, self.subject_id]
            )

            cursor.execute(
                """
                INSERT INTO fees_structure (grade, term, year, amount_required, payment_deadline, notes)
                VALUES ('Form 1', 'Term 1', 2026, 100.0, '2026-02-01', 'O Level Fees')
                """
            )
            self.fee_id = cursor.lastrowid

            # Set up school settings
            cursor.execute("DELETE FROM school_settings")
            cursor.execute(
                """
                INSERT INTO school_settings (setting_id, school_name, school_address, school_phone, current_term, current_year, receipt_prefix, cashbook_opening_balance)
                VALUES (1, 'Raydon Test School', 'Harare', '0777123456', 'Term 1', 2026, 'RCT', 0.0)
                """
            )

    def test_next_admission_no(self):
        # The next admission number for 2026 (prefix A26) should be A26002 since A26001 is taken
        no = next_admission_no("2026")
        self.assertEqual(no, "A26002")

    def test_register_student_auto_bills_current_term(self):
        response = self.client.post("/pupils/register", {
            "first_name": "Brian",
            "surname": "Moyo",
            "gender": "Male",
            "date_of_birth": "2015-03-14",
            "grade": "Form 1",
            "class_stream": "B",
            "guardian_name": "Parent Moyo",
            "guardian_phone": "0777000000",
            "address": "Street 2",
            "admission_date": "2026-01-15",
            "status": "Active",
            "subjects": [str(self.subject_id)],
        })
        self.assertEqual(response.status_code, 302)
        pupil = Pupil.objects.get(first_name="Brian", surname="Moyo")
        bill = TermBill.objects.filter(pupil_id=pupil.pupil_id, term="Term 1", year=2026).first()
        self.assertIsNotNone(bill)
        self.assertEqual(float(bill.amount_billed), 100.0)

    def test_register_student_auto_creates_o_and_a_level_fee_structures(self):
        response = self.client.post("/pupils/register", {
            "first_name": "Chipo",
            "surname": "Ncube",
            "gender": "Female",
            "date_of_birth": "2019-09-02",
            "grade": "Form 2",
            "class_stream": "A",
            "guardian_name": "Parent Ncube",
            "guardian_phone": "0777111222",
            "address": "Street 3",
            "admission_date": "2026-01-15",
            "status": "Active",
            "subjects": [str(self.subject_id)],
        })
        self.assertEqual(response.status_code, 302)
        pupil = Pupil.objects.get(first_name="Chipo", surname="Ncube")
        bill = TermBill.objects.filter(pupil_id=pupil.pupil_id, term="Term 1", year=2026).first()
        self.assertIsNotNone(bill)
        self.assertEqual(float(bill.amount_billed), 100.0)
        for grade_id in range(1, 7):
            structure = FeesStructure.objects.filter(grade_id=grade_id, term="Term 1", year=2026).first()
            self.assertIsNotNone(structure)
            expected = 150.0 if grade_id in {5, 6} else 100.0
            self.assertEqual(float(structure.amount_required), expected)

    def test_configured_fee_amount_is_not_overwritten(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fees_structure (grade, grade_id, term, year, amount_required, payment_deadline, notes)
                VALUES ('Form 5', 5, 'Term 3', 2026, 175.0, '2026-09-01', 'Custom A Level amount')
                """
            )
        structure = ensure_standard_fee_structure("Term 3", 2026, 5)
        self.assertEqual(float(structure["amount_required"]), 175.0)

    def test_current_term_billing_is_idempotent_for_new_term(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fees_structure (grade, term, year, amount_required, payment_deadline, notes)
                VALUES ('Form 1', 'Term 2', 2026, 100.0, '2026-05-01', 'O Level Term 2 Fees')
                """
            )
            cursor.execute(
                """
                UPDATE school_settings
                SET current_term = 'Term 2', current_year = 2026
                WHERE setting_id = 1
                """
            )

        stats = ensure_current_term_bills_for_active_students()
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["missing_fee_structure"], 0)
        bill_count = TermBill.objects.filter(pupil_id=self.pupil_id, term="Term 2", year=2026).count()
        self.assertEqual(bill_count, 1)

        second_stats = ensure_current_term_bills_for_active_students()
        self.assertEqual(second_stats["created"], 0)
        self.assertEqual(second_stats["existing"], 1)
        bill_count = TermBill.objects.filter(pupil_id=self.pupil_id, term="Term 2", year=2026).count()
        self.assertEqual(bill_count, 1)

    def test_fee_billing_and_payment(self):
        # 1. Generate term bills for Alice
        # Alice is in Form 1, Term 1 2026. O Level fees are USD 100.00.
        response = self.client.post("/fees-structure/generate-bills", {
            "term": "Term 1",
            "year": "2026"
        })
        self.assertEqual(response.status_code, 302)

        # Verify bill exists
        bill = TermBill.objects.filter(pupil_id=self.pupil_id, term="Term 1", year=2026).first()
        self.assertIsNotNone(bill)
        self.assertEqual(float(bill.amount_billed), 100.0)

        # 2. Record payment of USD 300.00
        response = self.client.post("/payments/new", {
            "pupil_query": "A26001",  # Search query
            "amount_paid": "300.00",
            "payment_date": today_text(),
            "payment_method": "Cash",
            "term": "Term 1",
            "year": "2026",
            "reference_no": ""
        })
        self.assertEqual(response.status_code, 302)

        # Verify payment recorded and allocated
        payment = Payment.objects.filter(pupil_id=self.pupil_id).first()
        self.assertIsNotNone(payment)
        self.assertEqual(float(payment.amount_paid), 300.0)

        allocations = list(PaymentAllocation.objects.filter(payment_id=payment.payment_id).order_by("year", "term"))
        self.assertEqual(sum(float(item.amount_allocated) for item in allocations), 300.0)
        self.assertEqual((allocations[0].term, allocations[0].year, float(allocations[0].amount_allocated)), ("Term 1", 2026, 100.0))

    def test_archived_student_cannot_receive_new_payment(self):
        with connection.cursor() as cursor:
            cursor.execute("UPDATE pupils SET status = 'Transferred' WHERE admission_no = 'A26001'")

        response = self.client.post("/payments/new", {
            "pupil_query": "A26001",
            "amount_paid": "100.00",
            "payment_date": today_text(),
            "payment_method": "Cash",
            "term": "Term 1",
            "year": "2026",
            "reference_no": "",
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Payment.objects.filter(pupil_id=self.pupil_id).exists())

    def test_overpayment_allocates_to_following_term(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fees_structure (grade, term, year, amount_required, payment_deadline, notes)
                VALUES ('Form 1', 'Term 2', 2026, 100.0, '2026-05-01', 'O Level Term 2 Fees')
                """
            )

        response = self.client.post("/payments/new", {
            "pupil_query": "A26001",
            "amount_paid": "200.00",
            "payment_date": today_text(),
            "payment_method": "Cash",
            "term": "Term 1",
            "year": "2026",
            "reference_no": "",
        })

        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.filter(pupil_id=self.pupil_id).order_by("-payment_id").first()
        self.assertIsNotNone(payment)
        allocations = list(PaymentAllocation.objects.filter(payment_id=payment.payment_id).order_by("year", "term"))
        self.assertEqual(len(allocations), 2)
        self.assertEqual((allocations[0].term, allocations[0].year, float(allocations[0].amount_allocated)), ("Term 1", 2026, 100.0))
        self.assertEqual((allocations[1].term, allocations[1].year, float(allocations[1].amount_allocated)), ("Term 2", 2026, 100.0))
        next_bill = TermBill.objects.filter(pupil_id=self.pupil_id, term="Term 2", year=2026).first()
        self.assertIsNotNone(next_bill)
        self.assertEqual(float(next_bill.amount_billed), 100.0)
        context = receipt_context(receipt_no=payment.receipt_no)
        self.assertEqual(float(context["current_paid"]), 100.0)
        self.assertEqual(float(context["advance_paid"]), 100.0)
        self.assertEqual(float(context["credit"]), 0.0)

    def test_receipt_pdf(self):
        # Create a payment
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payments (pupil_id, receipt_no, amount_paid, payment_date, payment_method, term, year)
                VALUES (%s, 'RCT202600001', 400.0, '2026-06-15', 'Cash', 'Term 1', 2026)
                """,
                [self.pupil_id]
            )
            pay_id = cursor.lastrowid
            cursor.execute("INSERT INTO receipts (payment_id, receipt_no, issued_date) VALUES (%s, 'RCT202600001', '2026-06-15')", [pay_id])

        # Test PDF receipt download
        response = self.client.get(f"/receipt/RCT202600001/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_receipt_permissions_and_protection(self):
        # Create a payment
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payments (pupil_id, receipt_no, amount_paid, payment_date, payment_method, term, year)
                VALUES (%s, 'RCT202600002', 200.0, '2026-06-15', 'Cash', 'Term 1', 2026)
                """,
                [self.pupil_id]
            )
            pay_id = cursor.lastrowid

        # 1. Bursar edits receipt -> should be denied
        bursar_client = Client()
        bursar_client.login(username='bursar', password='bursar123')
        
        response = bursar_client.post(f"/payments/{pay_id}/edit", {
            "amount_paid": "250.00",
            "payment_date": "2026-06-15",
            "payment_method": "Cash",
            "term": "Term 1",
            "year": "2026",
            "edit_reason": "Correction"
        })
        # Denied and redirected
        self.assertEqual(response.status_code, 302)
        # Verify amount remains 200.0
        payment = Payment.objects.get(payment_id=pay_id)
        self.assertEqual(float(payment.amount_paid), 200.0)

        # 2. Admin edits receipt -> should succeed
        admin_client = Client()
        admin_client.login(username='admin', password='admin123')
        
        response = admin_client.post(f"/payments/{pay_id}/edit", {
            "amount_paid": "250.00",
            "payment_date": "2026-06-15",
            "payment_method": "Cash",
            "term": "Term 1",
            "year": "2026",
            "edit_reason": "Correction"
        })
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get(payment_id=pay_id)
        self.assertEqual(float(payment.amount_paid), 250.0)

    def test_record_payment_resolves_by_name(self):
        # Generate bills first
        self.client.post("/fees-structure/generate-bills", {
            "term": "Term 1",
            "year": "2026"
        })
        # Record payment using name instead of admission number
        response = self.client.post("/payments/new", {
            "admission_no": "",  # Empty/missing
            "pupil_query": "Alice Smith",  # Name query
            "amount_paid": "150.00",
            "payment_date": today_text(),
            "payment_method": "Cash",
            "term": "Term 1",
            "year": "2026",
            "reference_no": ""
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify payment recorded and allocated to Alice
        payment = Payment.objects.filter(pupil_id=self.pupil_id).first()
        self.assertIsNotNone(payment)
        self.assertEqual(float(payment.amount_paid), 150.0)

    def test_record_payment_invalid_student_error(self):
        # Record payment for a non-existent student
        response = self.client.post("/payments/new", {
            "admission_no": "INVALID999",
            "pupil_query": "Nonexistent Pupil",
            "amount_paid": "100.00",
            "payment_date": today_text(),
            "payment_method": "Cash",
            "term": "Term 1",
            "year": "2026",
            "reference_no": ""
        })
        self.assertEqual(response.status_code, 302)
        
        # Check that the error message displays the submitted identifier
        from django.contrib.messages import get_messages
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Student was not found for 'Nonexistent Pupil'" in str(m) for m in messages))

