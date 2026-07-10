from django.test import TestCase
from django.db import connection
from django.contrib.auth import get_user_model
from decimal import Decimal
import datetime

from student_registry.models import Student
from academic_structure.models import AcademicYear, AcademicTerm, Form, Stream, AcademicClass
from human_resources.models import EmployeeProfile
from fees_management.models import StudentFeeAccount, Invoice, InvoiceItem, FeeCategory
from transport.models import (
    TransportVehicle,
    TransportDriver,
    TransportRoute,
    TransportPickupPoint,
    TransportRegistration,
    TransportAttendance,
    TransportMaintenance,
    TransportFuelLog,
    TransportIncident
)
from transport.views import post_transport_invoice
from saas_tenant_management.schema import ensure_schema_with_cursor

User = get_user_model()


class TransportManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Build required SQLite schema in test DB
        with connection.cursor() as cursor:
            ensure_schema_with_cursor(cursor, vendor="sqlite")
            
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
            admission_no="STU-TRANS-001",
            first_name="Anesu",
            surname="Banda",
            gender="Male",
            date_of_birth="2012-01-15",
            admission_date="2026-01-01",
            academic_class=cls.aclass,
            status="Active Student",
        )
        
        cls.fee_account = StudentFeeAccount.objects.filter(student=cls.student).first()
        if not cls.fee_account:
            cls.fee_account = StudentFeeAccount.objects.create(
                student=cls.student,
                academic_year=cls.year,
                academic_term=cls.term,
                total_charges=Decimal("0.00"),
                amount_paid=Decimal("0.00"),
                outstanding_balance=Decimal("0.00"),
            )
        
        # Register an Employee
        cls.employee = EmployeeProfile.objects.create(
            employee_number="EMP-TRANS-01",
            first_name="John",
            surname="Driver",
            gender="Male",
            date_of_birth="1985-05-15",
            national_id="NID-TRANS-01",
            phone_number="0771234567",
            email="driver@school.com",
            employment_date="2022-01-01",
            department="Transport",
            position="Driver",
            employee_category="DRIVER",
            next_of_kin="Sarah Driver",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="0772233445",
            status="ACTIVE",
        )
        
    def test_vehicle_management(self):
        # Register a vehicle
        vehicle = TransportVehicle.objects.create(
            registration_number="AB-1234",
            vehicle_name="School Shuttle A",
            vehicle_type="Bus",
            capacity=15,
            status="Active",
        )
        self.assertEqual(vehicle.registration_number, "AB-1234")
        self.assertEqual(vehicle.capacity, 15)
        self.assertEqual(vehicle.status, "Active")
        
    def test_driver_management(self):
        vehicle = TransportVehicle.objects.create(
            registration_number="AB-5678",
            vehicle_name="School Shuttle B",
            capacity=22,
            status="Active",
        )
        
        # Register driver
        driver = TransportDriver.objects.create(
            employee=self.employee,
            licence_number="LIC-12345",
            licence_expiry=datetime.date.today() + datetime.timedelta(days=100),
            medical_expiry=datetime.date.today() + datetime.timedelta(days=100),
            assigned_vehicle=vehicle,
            status="Active",
        )
        self.assertEqual(driver.employee, self.employee)
        self.assertEqual(driver.assigned_vehicle, vehicle)
        self.assertEqual(driver.licence_number, "LIC-12345")
        
    def test_route_and_stops_management(self):
        vehicle = TransportVehicle.objects.create(
            registration_number="AB-0001",
            vehicle_name="Bus Route A",
            capacity=30,
        )
        driver = TransportDriver.objects.create(
            employee=self.employee,
            licence_number="DRV-99",
            licence_expiry=datetime.date.today() + datetime.timedelta(days=365),
            medical_expiry=datetime.date.today() + datetime.timedelta(days=365),
            assigned_vehicle=vehicle,
        )
        
        # Create route
        route = TransportRoute.objects.create(
            route_code="RT-01",
            route_name="Suburbs shuttle",
            starting_point="Main Campus",
            destination="Northern Suburbs",
            distance=Decimal("12.50"),
            assigned_vehicle=vehicle,
            assigned_driver=driver,
        )
        self.assertEqual(route.route_code, "RT-01")
        self.assertEqual(route.distance, Decimal("12.50"))
        
        # Create stops
        stop = TransportPickupPoint.objects.create(
            route=route,
            location_name="Shopping Mall",
            pickup_time="07:15:00",
        )
        self.assertEqual(stop.location_name, "Shopping Mall")
        self.assertEqual(route.pickup_points.count(), 1)
        
    def test_student_allocation_and_auto_billing(self):
        vehicle = TransportVehicle.objects.create(
            registration_number="AB-0002",
            vehicle_name="Bus Route B",
            capacity=2,
        )
        route = TransportRoute.objects.create(
            route_code="RT-02",
            route_name="Southern Route",
            starting_point="Main Campus",
            destination="Southern Suburbs",
            assigned_vehicle=vehicle,
        )
        stop = TransportPickupPoint.objects.create(
            route=route,
            location_name="Post Office",
            pickup_time="07:30:00",
        )
        
        # Registration
        reg = TransportRegistration.objects.create(
            pupil=self.student,
            route=route,
            pickup_point=stop,
            trip_type="Return Trip",
            effective_date=datetime.date.today(),
            status="Active",
        )
        self.assertEqual(reg.pupil, self.student)
        self.assertEqual(reg.route, route)
        
        # Verify invoice auto-billing integration helper
        self.fee_account.refresh_from_db()
        initial_charges = self.fee_account.total_charges
        invoice = post_transport_invoice(None, self.student, Decimal("45.00"), "Transport Route: Southern Route")
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.current_charges, Decimal("45.00"))
        
        # Verify fee account updated
        self.fee_account.refresh_from_db()
        self.assertEqual(self.fee_account.total_charges, initial_charges + Decimal("45.00"))
        
    def test_maintenance_and_fuel_tracking(self):
        vehicle = TransportVehicle.objects.create(
            registration_number="AB-0003",
            vehicle_name="Bus Route C",
            capacity=15,
        )
        
        # Log Maintenance
        maint = TransportMaintenance.objects.create(
            vehicle=vehicle,
            maintenance_type="Repair",
            service_date=datetime.date.today(),
            cost=Decimal("150.00"),
            description="Replace brake pads",
        )
        self.assertEqual(maint.cost, Decimal("150.00"))
        
        # Log Fuel
        fuel = TransportFuelLog.objects.create(
            vehicle=vehicle,
            fuel_date=datetime.date.today(),
            quantity=Decimal("50.0"),
            cost=Decimal("75.00"),
            mileage=15000,
            supplier="TotalEnergies",
        )
        self.assertEqual(fuel.quantity, Decimal("50.0"))
        self.assertEqual(fuel.cost, Decimal("75.00"))
