from django.db import models


class ExamSession(models.Model):
    exam_id = models.AutoField(primary_key=True)
    exam_name = models.CharField(max_length=180)
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    grade = models.CharField(max_length=80, blank=True, null=True)
    start_date = models.TextField(blank=True, null=True)
    end_date = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=40, default="Planned")
    notes = models.TextField(blank=True, null=True)
    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = "exam_sessions"


class ResultSheet(models.Model):
    result_id = models.AutoField(primary_key=True)
    pupil_id = models.IntegerField()
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    status = models.CharField(max_length=40, default="Draft")
    total_marks = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average_mark = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    teacher_comment = models.TextField(blank=True, null=True)
    published_at = models.TextField(blank=True, null=True)
    published_by = models.IntegerField(blank=True, null=True)
    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()
    updated_at = models.TextField()
    grade_snapshot = models.CharField(max_length=80, blank=True, null=True)
    class_stream_snapshot = models.CharField(max_length=80, blank=True, null=True)
    class_position = models.IntegerField(blank=True, null=True)
    grade_position = models.IntegerField(blank=True, null=True)
    headmaster_comment = models.TextField(blank=True, null=True)
    next_term_fees = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "result_sheets"


class ResultEntry(models.Model):
    entry_id = models.AutoField(primary_key=True)
    result_id = models.IntegerField()
    subject_id = models.IntegerField()
    mark = models.DecimalField(max_digits=8, decimal_places=2)
    grade = models.CharField(max_length=20)
    created_at = models.TextField()
    updated_at = models.TextField()
    subject_comment = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "result_entries"

# Create your models here.
