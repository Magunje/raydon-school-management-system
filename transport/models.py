from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class TransportVehicle(models.Model):
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Under Maintenance", "Under Maintenance"),
        ("Out of Service", "Out of Service"),
        ("Retired", "Retired"),
    ]

    vehicle_id = models.BigAutoField(primary_key=True)
    registration_number = models.CharField(max_length=50, unique=True)
    vehicle_name = models.CharField(max_length=100)
    vehicle_type = models.CharField(max_length=50, help_text="e.g. Bus, minibus, SUV", blank=True, null=True)
    make = models.CharField(max_length=50, blank=True, null=True)
    model = models.CharField(max_length=50, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    capacity = models.IntegerField()
    fuel_type = models.CharField(max_length=30, blank=True, null=True)
    purchase_date = models.DateField(blank=True, null=True)
    current_mileage = models.IntegerField(default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Active")

    class Meta:
        db_table = "transport_vehicles"
        ordering = ["vehicle_name"]

    def __str__(self):
        return f"{self.vehicle_name} ({self.registration_number})"


class TransportDriver(models.Model):
    driver_id = models.BigAutoField(primary_key=True)
    employee = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.CASCADE,
        related_name="driver_profiles",
    )
    licence_number = models.CharField(max_length=50)
    licence_expiry = models.DateField()
    medical_expiry = models.DateField()
    assigned_vehicle = models.ForeignKey(
        TransportVehicle,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="drivers",
    )
    status = models.CharField(max_length=30, default="Active")

    class Meta:
        db_table = "transport_drivers"

    def __str__(self):
        return f"{self.employee.full_name} ({self.employee.employee_number})"


class TransportRoute(models.Model):
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    ]

    route_id = models.BigAutoField(primary_key=True)
    route_code = models.CharField(max_length=30, unique=True)
    route_name = models.CharField(max_length=100)
    starting_point = models.CharField(max_length=150)
    destination = models.CharField(max_length=150)
    distance = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    estimated_duration = models.CharField(max_length=50, blank=True, null=True)
    assigned_vehicle = models.ForeignKey(
        TransportVehicle,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="routes",
    )
    assigned_driver = models.ForeignKey(
        TransportDriver,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="routes",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")

    class Meta:
        db_table = "transport_routes"
        ordering = ["route_code"]

    def __str__(self):
        return f"{self.route_code} - {self.route_name}"


class TransportPickupPoint(models.Model):
    pickup_id = models.BigAutoField(primary_key=True)
    route = models.ForeignKey(
        TransportRoute, on_delete=models.CASCADE, related_name="pickup_points"
    )
    location_name = models.CharField(max_length=150)
    pickup_time = models.TimeField()
    status = models.CharField(max_length=20, default="Active")

    class Meta:
        db_table = "transport_pickup_points"

    def __str__(self):
        return f"{self.location_name} ({self.pickup_time})"


class TransportRegistration(models.Model):
    TRIP_CHOICES = [
        ("One-Way", "One-Way"),
        ("Return Trip", "Return Trip"),
        ("Temporary", "Temporary"),
        ("Permanent", "Permanent"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Cancelled", "Cancelled"),
    ]

    registration_id = models.BigAutoField(primary_key=True)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="transport_registrations",
    )
    route = models.ForeignKey(
        TransportRoute,
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    pickup_point = models.ForeignKey(
        TransportPickupPoint,
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    trip_type = models.CharField(max_length=30, choices=TRIP_CHOICES, default="Return Trip")
    effective_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")

    class Meta:
        db_table = "transport_registrations"

    def __str__(self):
        return f"{self.pupil.first_name} {self.pupil.surname} - {self.route.route_name}"


class TransportAttendance(models.Model):
    STATUS_CHOICES = [
        ("Present", "Present"),
        ("Absent", "Absent"),
        ("Sick", "Sick"),
        ("Excused", "Excused"),
    ]

    attendance_id = models.BigAutoField(primary_key=True)
    pupil = models.ForeignKey("student_registry.Student", on_delete=models.CASCADE)
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE)
    date = models.DateField()
    status_morning = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Present")
    status_afternoon = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Present")
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "transport_attendance"
        unique_together = ("pupil", "route", "date")


class TransportMaintenance(models.Model):
    TYPE_CHOICES = [
        ("Preventive", "Preventive"),
        ("Repair", "Repair"),
        ("Insurance", "Insurance"),
        ("Licence", "Licence"),
        ("Tyre", "Tyre"),
    ]

    maintenance_id = models.BigAutoField(primary_key=True)
    vehicle = models.ForeignKey(
        TransportVehicle, on_delete=models.CASCADE, related_name="maintenance_logs"
    )
    maintenance_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    service_date = models.DateField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    next_service_date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "transport_maintenance"
        ordering = ["-service_date"]


class TransportFuelLog(models.Model):
    fuel_id = models.BigAutoField(primary_key=True)
    vehicle = models.ForeignKey(
        TransportVehicle, on_delete=models.CASCADE, related_name="fuel_logs"
    )
    fuel_date = models.DateField()
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    mileage = models.IntegerField()
    supplier = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "transport_fuel_logs"
        ordering = ["-fuel_date"]


class TransportIncident(models.Model):
    incident_id = models.BigAutoField(primary_key=True)
    incident_date = models.DateField()
    description = models.TextField()
    vehicle = models.ForeignKey(
        TransportVehicle, on_delete=models.SET_NULL, blank=True, null=True
    )
    driver = models.ForeignKey(
        TransportDriver, on_delete=models.SET_NULL, blank=True, null=True
    )
    action_taken = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "transport_incidents"
        ordering = ["-incident_date"]
