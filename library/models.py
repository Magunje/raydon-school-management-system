from django.db import models
from decimal import Decimal


class LibraryBook(models.Model):
    book_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=180)
    author = models.CharField(max_length=180, blank=True, null=True)
    isbn = models.CharField(max_length=80, blank=True, null=True)
    category = models.CharField(max_length=80, blank=True, null=True)
    total_copies = models.IntegerField(default=1)
    available_copies = models.IntegerField(default=1)
    fine_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=40, default="Active")
    
    # New fields
    publisher = models.CharField(max_length=180, blank=True, null=True)
    publication_year = models.IntegerField(blank=True, null=True)
    subject = models.CharField(max_length=120, blank=True, null=True)
    edition = models.CharField(max_length=80, blank=True, null=True)
    shelf_location = models.CharField(max_length=80, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "library_books"

    def __str__(self):
        return self.title


class LibraryMember(models.Model):
    member_id = models.AutoField(primary_key=True)
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="library_memberships",
    )
    staff = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="library_memberships",
    )
    card_number = models.CharField(max_length=100, unique=True)
    barcode_path = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=40, default="Active")
    created_at = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "library_members"

    def __str__(self):
        if self.pupil:
            return f"Member: {self.pupil.first_name} {self.pupil.surname} ({self.card_number})"
        elif self.staff:
            return f"Member: {self.staff.first_name} {self.staff.surname} ({self.card_number})"
        return f"Member: {self.card_number}"


class LibraryIssue(models.Model):
    issue_id = models.AutoField(primary_key=True)
    book = models.ForeignKey(
        LibraryBook,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_issues",
    )
    staff = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_issues",
    )
    issue_date = models.TextField()
    due_date = models.TextField()
    return_date = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=40, default="Borrowed")
    notes = models.TextField(blank=True, null=True)
    
    # Audit and fine columns
    librarian_id = models.IntegerField(blank=True, null=True)
    return_librarian_id = models.IntegerField(blank=True, null=True)
    book_condition = models.CharField(max_length=40, blank=True, null=True)
    fine_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    fine_paid = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "library_issues"

    def __str__(self):
        borrower = self.pupil or self.staff or "Unknown"
        return f"{self.book.title} issued to {borrower}"


class LibraryReservation(models.Model):
    reservation_id = models.AutoField(primary_key=True)
    book = models.ForeignKey(
        LibraryBook,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    pupil = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="library_reservations",
    )
    staff = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="library_reservations",
    )
    reserve_date = models.TextField()
    status = models.CharField(max_length=40, default="Pending")
    notification_sent = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "library_reservations"

    def __str__(self):
        borrower = self.pupil or self.staff or "Unknown"
        return f"Reservation of {self.book.title} for {borrower}"


class LibraryDigitalResource(models.Model):
    resource_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=80)
    file_path = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.IntegerField(blank=True, null=True)
    uploaded_at = models.TextField()
    allowed_roles = models.CharField(max_length=255, blank=True, null=True) # comma-separated list of roles

    class Meta:
        managed = False
        db_table = "library_digital_resources"

    def __str__(self):
        return f"{self.title} ({self.category})"
