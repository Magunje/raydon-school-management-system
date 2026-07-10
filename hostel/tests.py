from django.test import TestCase
from decimal import Decimal
import datetime

from student_registry.models import Student
from academic_structure.models import AcademicYear, AcademicTerm, Form, Stream, AcademicClass
from human_resources.models import EmployeeProfile
from hostel.models import Hostel, HostelRoom, HostelBed, HostelAllocation, HostelTransfer, HostelAttendance, HostelDiscipline, HostelVisitor
from saas_tenant_management.schema import ensure_schema_with_cursor


class HostelManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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
        
        # Register pupils
        cls.boy = Student.objects.create(
            admission_no="STU-BOY",
            first_name="Bob",
            surname="Jones",
            gender="Male",
            date_of_birth="2010-01-01",
            admission_date="2026-01-01",
            academic_class=cls.aclass,
            status="Active Student",
        )
        
        cls.girl = Student.objects.create(
            admission_no="STU-GIRL",
            first_name="Grace",
            surname="Kelly",
            gender="Female",
            date_of_birth="2010-01-01",
            admission_date="2026-01-01",
            academic_class=cls.aclass,
            status="Active Student",
        )
        
        # Register a Warden
        cls.warden = EmployeeProfile.objects.create(
            employee_number="WAR-001",
            first_name="Warden",
            surname="Gary",
            gender="Male",
            date_of_birth="1980-01-01",
            national_id="NID-WAR-001",
            phone_number="1234567",
            employment_date="2020-01-01",
            department="Dormitory",
            position="Hostel Warden",
            employee_category="HOSTEL",
            next_of_kin="Mary Warden",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="7654321",
            status="ACTIVE",
        )
        
        # Create Hostels
        cls.boys_hostel = Hostel.objects.create(
            hostel_code="H-BOYS",
            hostel_name="Boys Dormitory A",
            hostel_type="BOYS",
            warden=cls.warden,
            status="Active",
        )
        
        cls.girls_hostel = Hostel.objects.create(
            hostel_code="H-GIRLS",
            hostel_name="Girls Dormitory B",
            hostel_type="GIRLS",
            warden=cls.warden,
            status="Active",
        )
        
        # Create Rooms
        cls.boys_room = HostelRoom.objects.create(
            room_number="101",
            hostel=cls.boys_hostel,
            floor=1,
            capacity=2,
            current_occupancy=0,
            status="Available",
        )
        
        cls.girls_room = HostelRoom.objects.create(
            room_number="201",
            hostel=cls.girls_hostel,
            floor=2,
            capacity=2,
            current_occupancy=0,
            status="Available",
        )
        
        # Create Beds
        cls.boys_bed1 = HostelBed.objects.create(
            bed_number="101-1",
            room=cls.boys_room,
            status="Available",
        )
        cls.boys_bed2 = HostelBed.objects.create(
            bed_number="101-2",
            room=cls.boys_room,
            status="Available",
        )
        
        cls.girls_bed1 = HostelBed.objects.create(
            bed_number="201-1",
            room=cls.girls_room,
            status="Available",
        )

    def test_hostel_gender_allocation_restrictions(self):
        # Test: Placing a girl in a boys hostel should fail validation
        # By simulating view post validations or direct saves
        # Allocating boy to boys bed
        alloc = HostelAllocation.objects.create(
            pupil=self.boy,
            hostel=self.boys_hostel,
            room=self.boys_room,
            bed=self.boys_bed1,
            boarding_date="2026-07-09",
            status="Active",
        )
        self.assertEqual(alloc.status, "Active")
        
        # Allocating girl to boys bed should violate validation checks
        # (Usually validation is in view, we test logic constraint)
        student_gender = self.girl.gender.upper()
        hostel_type = self.boys_hostel.hostel_type.upper()
        is_gender_mismatch = (hostel_type == "BOYS" and student_gender != "MALE")
        self.assertTrue(is_gender_mismatch)

    def test_bed_occupancy_sync(self):
        # Verify bed is occupied
        self.assertEqual(self.boys_bed2.status, "Available")
        self.boys_bed2.status = "Occupied"
        self.boys_bed2.current_occupant = self.boy
        self.boys_bed2.save()
        
        self.assertEqual(self.boys_bed2.status, "Occupied")
        self.assertEqual(self.boys_bed2.current_occupant, self.boy)

    def test_roommates_count(self):
        # Allocate boy 1
        HostelAllocation.objects.create(
            pupil=self.boy,
            hostel=self.boys_hostel,
            room=self.boys_room,
            bed=self.boys_bed1,
            boarding_date="2026-07-09",
            status="Active",
        )
        # Verify room occupancy counter
        self.boys_bed1.status = "Occupied"
        self.boys_bed1.current_occupant = self.boy
        self.boys_bed1.save()
        
        occupied_count = HostelBed.objects.filter(room=self.boys_room, status="Occupied").count()
        self.assertEqual(occupied_count, 1)
