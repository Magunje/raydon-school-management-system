from django.db import models
from decimal import Decimal


class Hostel(models.Model):
    HOSTEL_TYPES = [
        ("BOYS", "Boys Hostel"),
        ("GIRLS", "Girls Hostel"),
        ("MIXED", "Mixed Hostel"),
    ]
    
    hostel_id = models.AutoField(primary_key=True)
    hostel_code = models.CharField(max_length=50, unique=True)
    hostel_name = models.CharField(max_length=100)
    hostel_type = models.CharField(max_length=40, choices=HOSTEL_TYPES, default="MIXED")
    capacity = models.IntegerField(default=0)
    warden = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warden_hostels",
    )
    status = models.CharField(max_length=40, default="Active")

    class Meta:
        db_table = "hostels"

    def __str__(self):
        return f"{self.hostel_name} ({self.hostel_code})"


class HostelRoom(models.Model):
    ROOM_STATUS = [
        ("Available", "Available"),
        ("Full", "Full"),
        ("Maintenance", "Under Maintenance"),
        ("Closed", "Closed"),
    ]
    
    room_id = models.AutoField(primary_key=True)
    room_number = models.CharField(max_length=50)
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="rooms")
    floor = models.IntegerField(default=0)
    capacity = models.IntegerField(default=0)
    current_occupancy = models.IntegerField(default=0)
    status = models.CharField(max_length=40, choices=ROOM_STATUS, default="Available")

    class Meta:
        db_table = "hostel_rooms"

    def __str__(self):
        return f"Room {self.room_number} - {self.hostel.hostel_name}"


class HostelBed(models.Model):
    BED_STATUS = [
        ("Available", "Available"),
        ("Occupied", "Occupied"),
        ("Reserved", "Reserved"),
        ("Maintenance", "Under Maintenance"),
    ]
    
    bed_id = models.AutoField(primary_key=True)
    bed_number = models.CharField(max_length=50)
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, related_name="beds")
    status = models.CharField(max_length=40, choices=BED_STATUS, default="Available")
    current_occupant = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hostel_bed_allocations",
    )

    class Meta:
        db_table = "hostel_beds"

    def __str__(self):
        return f"Bed {self.bed_number} in Room {self.room.room_number} ({self.room.hostel.hostel_name})"


class HostelAllocation(models.Model):
    ALLOCATION_STATUS = [
        ("Active", "Active"),
        ("Transferred", "Transferred"),
        ("Vacated", "Vacated"),
    ]
    
    allocation_id = models.AutoField(primary_key=True)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="hostel_allocations",
    )
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="allocations")
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, related_name="allocations")
    bed = models.ForeignKey(HostelBed, on_delete=models.CASCADE, related_name="allocations")
    boarding_date = models.TextField()
    status = models.CharField(max_length=40, choices=ALLOCATION_STATUS, default="Active")
    guardian_notified = models.IntegerField(default=0)
    fee_posted = models.IntegerField(default=0)
    created_at = models.TextField()

    class Meta:
        db_table = "hostel_allocations"

    def __str__(self):
        return f"Allocation: {self.pupil.first_name} {self.pupil.surname} in {self.bed}"


class HostelTransfer(models.Model):
    transfer_id = models.AutoField(primary_key=True)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="hostel_transfers",
    )
    previous_allocation_id = models.IntegerField()
    new_hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE)
    new_room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE)
    new_bed = models.ForeignKey(HostelBed, on_delete=models.CASCADE)
    reason = models.TextField(blank=True, null=True)
    transfer_date = models.TextField()
    approved_by = models.ForeignKey("human_resources.EmployeeProfile", on_delete=models.CASCADE)

    class Meta:
        db_table = "hostel_transfers"

    def __str__(self):
        return f"Transfer of {self.pupil.admission_no} to {self.new_bed}"


class HostelAttendance(models.Model):
    ATTENDANCE_CHOICES = [
        ("Present", "Present"),
        ("Absent", "Absent"),
        ("Sick", "Sick"),
        ("Excused", "Excused"),
    ]
    
    attendance_id = models.AutoField(primary_key=True)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="hostel_attendance",
    )
    date = models.TextField()
    time_slot = models.CharField(max_length=50) # Morning, Evening, Weekend
    status = models.CharField(max_length=40, choices=ATTENDANCE_CHOICES)
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "hostel_attendance"

    def __str__(self):
        return f"{self.pupil.admission_no} - {self.date} ({self.time_slot}): {self.status}"


class HostelDiscipline(models.Model):
    discipline_id = models.AutoField(primary_key=True)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="hostel_discipline_records",
    )
    incident_date = models.TextField()
    incident_description = models.TextField()
    action_taken = models.CharField(max_length=100, blank=True, null=True)
    staff = models.ForeignKey("human_resources.EmployeeProfile", on_delete=models.CASCADE)
    parent_notified = models.IntegerField(default=0)

    class Meta:
        db_table = "hostel_discipline"

    def __str__(self):
        return f"Discipline: {self.pupil.admission_no} on {self.incident_date}"


class HostelVisitor(models.Model):
    VISITOR_STATUS = [
        ("Pending", "Pending Approval"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Completed", "Completed (Checked Out)"),
    ]
    
    visitor_id = models.AutoField(primary_key=True)
    visitor_name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=100)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="hostel_visitors",
    )
    visit_date = models.TextField()
    time_in = models.TextField()
    time_out = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=50)
    approval_status = models.CharField(max_length=40, choices=VISITOR_STATUS, default="Pending")
    approved_by = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_visitors",
    )

    class Meta:
        db_table = "hostel_visitors"

    def __str__(self):
        return f"Visitor {self.visitor_name} to {self.pupil.admission_no}"


class HostelInventory(models.Model):
    inventory_id = models.AutoField(primary_key=True)
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="inventory")
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, null=True, blank=True, related_name="inventory")
    item_name = models.CharField(max_length=100)
    quantity = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default="Good")

    class Meta:
        db_table = "hostel_inventory"

    def __str__(self):
        return f"{self.item_name} ({self.quantity}) - {self.hostel.hostel_name}"


class HostelFeeRecord(models.Model):
    FEE_STATUS = [
        ("Unpaid", "Unpaid"),
        ("Paid", "Paid"),
        ("Cancelled", "Cancelled"),
    ]
    
    fee_id = models.AutoField(primary_key=True)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="hostel_fees",
    )
    charge_type = models.CharField(max_length=80) # Boarding Fee, Damage Penalty, Laundry Fee, etc.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_charged = models.TextField()
    status = models.CharField(max_length=40, choices=FEE_STATUS, default="Unpaid")

    class Meta:
        db_table = "hostel_fee_records"

    def __str__(self):
        return f"{self.charge_type} - {self.pupil.admission_no}: ${self.amount}"


class HostelMaintenance(models.Model):
    MAINTENANCE_STATUS = [
        ("Pending", "Pending"),
        ("In Progress", "In Progress"),
        ("Resolved", "Resolved"),
        ("Cancelled", "Cancelled"),
    ]
    
    maintenance_id = models.AutoField(primary_key=True)
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="maintenance")
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, related_name="maintenance")
    bed = models.ForeignKey(HostelBed, on_delete=models.CASCADE, null=True, blank=True, related_name="maintenance")
    issue_description = models.TextField()
    reported_by = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="reported_maintenance",
    )
    status = models.CharField(max_length=40, choices=MAINTENANCE_STATUS, default="Pending")
    reported_date = models.TextField()

    class Meta:
        db_table = "hostel_maintenance"

    def __str__(self):
        return f"Issue {self.maintenance_id} in room {self.room.room_number} ({self.status})"


class HostelNotice(models.Model):
    notice_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=150)
    content = models.TextField()
    published_date = models.TextField()
    is_active = models.IntegerField(default=1)

    class Meta:
        db_table = "hostel_notices"

    def __str__(self):
        return self.title
