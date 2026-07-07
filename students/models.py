from django.db import models


class Guardian(models.Model):
    guardian_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=180)
    relationship = models.CharField(max_length=80, default="Guardian")
    phone_number = models.CharField(max_length=40)
    alternative_phone = models.CharField(max_length=40, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    occupation = models.CharField(max_length=120, blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=180, blank=True, null=True)
    emergency_phone = models.CharField(max_length=40, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "guardians"

    def __str__(self):
        return self.full_name


class Grade(models.Model):
    grade_id = models.AutoField(primary_key=True)
    grade_name = models.CharField(max_length=80, unique=True)

    class Meta:
        managed = False
        db_table = "grades"

    def __str__(self):
        return self.grade_name


class SchoolClass(models.Model):
    class_id = models.AutoField(primary_key=True)
    class_name = models.CharField(max_length=80)
    grade_id = models.IntegerField()
    academic_year = models.IntegerField()
    class_teacher = models.CharField(max_length=180, blank=True, null=True)
    class_teacher_id = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "classes"

    def __str__(self):
        return f"{self.class_name} {self.academic_year}"


class Pupil(models.Model):
    pupil_id = models.AutoField(primary_key=True)
    admission_no = models.CharField(max_length=80, unique=True)
    first_name = models.CharField(max_length=120)
    surname = models.CharField(max_length=120)
    gender = models.CharField(max_length=20)
    date_of_birth = models.TextField()
    grade = models.CharField(max_length=80)
    class_stream = models.CharField(max_length=80)
    guardian_name = models.CharField(max_length=180)
    guardian_phone = models.CharField(max_length=40)
    address = models.TextField()
    admission_date = models.TextField()
    status = models.CharField(max_length=40, default="Active")
    medical_notes = models.TextField(blank=True, null=True)
    grade_id = models.IntegerField(blank=True, null=True)
    class_id = models.IntegerField(blank=True, null=True)
    guardian_id = models.IntegerField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    completed_on = models.TextField(blank=True, null=True)
    status_changed_on = models.TextField(blank=True, null=True)
    status_reason = models.TextField(blank=True, null=True)
    transfer_destination = models.CharField(max_length=180, blank=True, null=True)
    transfer_letter_no = models.CharField(max_length=80, blank=True, null=True)
    photo_path = models.CharField(max_length=255, blank=True, null=True)
    national_id = models.CharField(max_length=80, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "pupils"

    def __str__(self):
        return f"{self.admission_no} - {self.first_name} {self.surname}"


class StudentSubject(models.Model):
    id = models.AutoField(primary_key=True)
    pupil_id = models.IntegerField()
    subject_id = models.IntegerField()
    academic_year = models.IntegerField()
    form = models.CharField(max_length=50)
    stream = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = "student_subjects"


# Create your models here.
