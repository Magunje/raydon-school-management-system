from django.conf import settings
from django.db import models


ROLE_CHOICES = [
    ("Super Admin", "Super Admin"),
    ("Administrator", "Administrator"),
    ("Headmaster", "Headmaster"),
    ("Headmaster / Headmistress", "Headmaster / Headmistress"),
    ("Deputy Head", "Deputy Head"),
    ("HOD", "HOD"),
    ("Bursar / Accounts Clerk", "Bursar / Accounts Clerk"),
    ("Accountant", "Accountant"),
    ("Registrar / Office Clerk", "Registrar / Office Clerk"),
    ("Clerk", "Clerk"),
    ("Teacher", "Teacher"),
    ("Librarian", "Librarian"),
    ("Transport Staff", "Transport Staff"),
    ("Hostel Staff", "Hostel Staff"),
    ("Nurse", "Nurse"),
    ("Parent", "Parent"),
    ("Student", "Student"),
]


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    legacy_user_id = models.PositiveIntegerField(blank=True, null=True, unique=True)
    full_name = models.CharField(max_length=180, blank=True)
    role = models.CharField(max_length=80, choices=ROLE_CHOICES, default="Teacher")
    status = models.CharField(max_length=30, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.full_name or self.user.username} ({self.role})"


class LegacyUser(models.Model):
    user_id = models.AutoField(primary_key=True)
    admission_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.TextField()
    role = models.CharField(max_length=80)
    full_name = models.CharField(max_length=180, blank=True, null=True)
    status = models.CharField(max_length=30, default="Active")
    created_at = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "users"

    def __str__(self):
        return self.full_name or self.username

# Create your models here.
