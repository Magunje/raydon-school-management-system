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

# Create your models here.
