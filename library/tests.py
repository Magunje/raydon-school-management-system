from django.test import TestCase
from django.db import connection
from django.contrib.auth import get_user_model
from decimal import Decimal
import datetime

from student_registry.models import Student
from academic_structure.models import AcademicYear, AcademicTerm, Form, Stream, AcademicClass
from human_resources.models import EmployeeProfile
from library.models import LibraryBook, LibraryMember, LibraryIssue, LibraryReservation
from library.views import get_library_settings, post_library_fine, update_book_availability
from saas_tenant_management.schema import ensure_schema_with_cursor

User = get_user_model()


class LibraryManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Build required SQLite schema in test DB
        with connection.cursor() as cursor:
            ensure_schema_with_cursor(cursor, vendor="sqlite")
            
        # Create default library settings
        get_library_settings()
        
        # Build academic structure
        cls.year = AcademicYear.objects.create(year=2026, is_active=True)
        cls.term = AcademicTerm.objects.create(academic_year=cls.year, term_number=1, is_active=True)
        cls.form = Form.objects.create(form_number=1, name="Form 1")
        cls.stream = Stream.objects.create(name="A")
        cls.aclass = AcademicClass.objects.create(
            form=cls.form,
            stream=cls.stream,
            academic_year=cls.year,
        )
        
        # Register a Student
        cls.student = Student.objects.create(
            admission_no="STU-001",
            first_name="Alice",
            surname="Smith",
            gender="Female",
            date_of_birth="2010-01-01",
            admission_date="2026-01-01",
            academic_class=cls.aclass,
            status="Active Student",
        )
        
        # Register an Employee
        cls.staff = EmployeeProfile.objects.create(
            employee_number="EMP-001",
            first_name="John",
            surname="Doe",
            gender="Male",
            date_of_birth="1980-01-01",
            national_id="NID-001",
            phone_number="1234567",
            employment_date="2020-01-01",
            department="Science",
            position="Teacher",
            employee_category="TEACHER",
            next_of_kin="Mary Doe",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="7654321",
            status="ACTIVE",
        )
        
        # Register a Book
        cls.book = LibraryBook.objects.create(
            title="Introduction to Algebra",
            author="Dr. Euler",
            isbn="978-0123456789",
            category="Mathematics",
            total_copies=3,
            available_copies=3,
            fine_per_day=Decimal("0.50"),
            shelf_location="Shelf M-1",
            status="Active",
        )

    def test_auto_library_membership(self):
        # Alice and John should have auto memberships via signals
        member_student = LibraryMember.objects.filter(pupil=self.student).first()
        self.assertIsNotNone(member_student)
        self.assertEqual(member_student.card_number, "LIB-S-STU-001")
        self.assertEqual(member_student.status, "Active")
        
        member_staff = LibraryMember.objects.filter(staff=self.staff).first()
        self.assertIsNotNone(member_staff)
        self.assertEqual(member_staff.card_number, "LIB-T-EMP-001")
        
    def test_book_availability_sync(self):
        self.assertEqual(self.book.available_copies, 3)
        
        # Issue 1 copy
        issue = LibraryIssue.objects.create(
            book=self.book,
            pupil=self.student,
            issue_date="2026-07-01",
            due_date="2026-07-15",
            status="Borrowed",
        )
        update_book_availability(self.book.pk)
        
        # Check availability decremented
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)
        
        # Return book
        issue.status = "Returned"
        issue.return_date = "2026-07-10"
        issue.save()
        update_book_availability(self.book.pk)
        
        # Check availability restored
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 3)

    def test_library_fine_billing_integration(self):
        # Post fine of $5.50
        invoice = post_library_fine(
            None,
            self.student,
            Decimal("5.50"),
            "Overdue Algebra book"
        )
        
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.current_charges, Decimal("5.50"))
        
        # Verify student account charges updated
        self.student.refresh_from_db()
        account = self.student.fee_account
        self.assertEqual(account.total_charges, Decimal("105.50")) # 100 base O-Level + 5.50 library fine
        self.assertEqual(account.outstanding_balance, Decimal("105.50"))

    def test_reservation_waitlist_flow(self):
        # Set copies to 0
        self.book.total_copies = 0
        self.book.available_copies = 0
        self.book.save()
        
        # Create reservation
        res = LibraryReservation.objects.create(
            book=self.book,
            pupil=self.student,
            reserve_date="2026-07-09",
            status="Pending",
        )
        self.assertEqual(res.status, "Pending")
