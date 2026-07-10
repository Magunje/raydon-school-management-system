from django.db import models


class TeacherProfile(models.Model):
    profile_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField(unique=True)
    phone_number = models.CharField(max_length=40, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    qualifications = models.TextField(blank=True, null=True)
    assigned_subjects = models.TextField(blank=True, null=True)
    workload_notes = models.TextField(blank=True, null=True)
    created_at = models.TextField()
    updated_at = models.TextField()

    class Meta:
        managed = False
        db_table = "teacher_profiles"


class TeacherAttendanceRecord(models.Model):
    attendance_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    attendance_date = models.TextField()
    status = models.CharField(max_length=40)
    notes = models.TextField(blank=True, null=True)
    marked_by = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = "teacher_attendance_records"


class TeacherEmployeeProfile(models.Model):
    employee = models.OneToOneField(
        "human_resources.EmployeeProfile",
        on_delete=models.CASCADE,
        related_name="teacher_extension",
    )
    legacy_profile_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    teaching_subjects = models.TextField(blank=True, null=True)
    assigned_forms = models.TextField(blank=True, null=True)
    assigned_classes = models.TextField(blank=True, null=True)
    workload_notes = models.TextField(blank=True, null=True)
    professional_registration = models.CharField(max_length=120, blank=True, null=True)
    teaching_experience_years = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    class_teacher_assignment = models.CharField(max_length=120, blank=True, null=True)
    head_of_department_assignment = models.CharField(max_length=120, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "teacher_employee_profiles"
        ordering = ["employee__surname", "employee__first_name"]

    def __str__(self):
        return f"Teacher extension for {self.employee.full_name}"
