from django.db import models


class AttendanceRecord(models.Model):
    attendance_id = models.AutoField(primary_key=True)
    pupil_id = models.IntegerField()
    class_id = models.IntegerField()
    attendance_date = models.TextField()
    status = models.CharField(max_length=40, default="Present")
    notes = models.TextField(blank=True, null=True)
    marked_by = models.IntegerField(blank=True, null=True)
    marked_at = models.TextField()
    updated_at = models.TextField()

    class Meta:
        managed = False
        db_table = "attendance_records"

# Create your models here.
