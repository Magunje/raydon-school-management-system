from django.db import models


class Subject(models.Model):
    subject_id = models.AutoField(primary_key=True)
    subject_code = models.CharField(max_length=40, unique=True)
    subject_name = models.CharField(max_length=120)
    grade = models.CharField(max_length=80)
    display_order = models.IntegerField(default=0)
    status = models.CharField(max_length=40, default="Active")

    class Meta:
        managed = False
        db_table = "subjects"

    def __str__(self):
        return self.subject_name


class ClassTimetableEntry(models.Model):
    timetable_id = models.AutoField(primary_key=True)
    class_id = models.IntegerField()
    academic_year = models.IntegerField()
    day_name = models.CharField(max_length=20)
    day_order = models.IntegerField()
    period_no = models.IntegerField()
    start_time = models.CharField(max_length=20)
    end_time = models.CharField(max_length=20)
    subject_id = models.IntegerField(blank=True, null=True)
    subject_name = models.CharField(max_length=120)
    teacher_name = models.CharField(max_length=180, blank=True, null=True)
    generated_by = models.IntegerField(blank=True, null=True)
    generated_at = models.TextField()
    room_name = models.CharField(max_length=80, blank=True, null=True)
    is_locked = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "class_timetable_entries"


class ELearningNote(models.Model):
    note_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=180)
    grade = models.CharField(max_length=80)
    class_stream = models.CharField(max_length=80, blank=True, null=True)
    subject_id = models.IntegerField(blank=True, null=True)
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    description = models.TextField(blank=True, null=True)
    file_path = models.CharField(max_length=255, blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    uploaded_by = models.IntegerField(blank=True, null=True)
    uploaded_at = models.TextField()

    class Meta:
        managed = False
        db_table = "e_learning_notes"


class ELearningAssignment(models.Model):
    assignment_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=180)
    grade = models.CharField(max_length=80)
    class_stream = models.CharField(max_length=80, blank=True, null=True)
    subject_id = models.IntegerField(blank=True, null=True)
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    instructions = models.TextField(blank=True, null=True)
    file_path = models.CharField(max_length=255, blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    due_date = models.TextField(blank=True, null=True)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, default=100)
    status = models.CharField(max_length=40, default="Open")
    uploaded_by = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()
    updated_at = models.TextField()

    class Meta:
        managed = False
        db_table = "e_learning_assignments"


class ELearningSubmission(models.Model):
    submission_id = models.AutoField(primary_key=True)
    assignment_id = models.IntegerField()
    pupil_id = models.IntegerField()
    answer_text = models.TextField(blank=True, null=True)
    file_path = models.CharField(max_length=255, blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=40, default="Submitted")
    score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    submitted_at = models.TextField()
    marked_by = models.IntegerField(blank=True, null=True)
    marked_at = models.TextField(blank=True, null=True)
    updated_at = models.TextField()

    class Meta:
        managed = False
        db_table = "e_learning_submissions"

# Create your models here.
