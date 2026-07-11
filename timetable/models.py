from django.db import models
from django.conf import settings
from students.models import SchoolClass
from academics.models import Subject
from accounts.models import UserProfile

class Room(models.Model):
    ROOM_TYPES = [
        ('Classroom', 'Normal Classroom'),
        ('Science Lab', 'Science Lab'),
        ('Computer Lab', 'Computer Lab'),
        ('Library', 'Library'),
        ('Special Room', 'Special Room'),
    ]
    
    room_id = models.AutoField(primary_key=True)
    room_name = models.CharField(max_length=80, unique=True)
    room_type = models.CharField(max_length=50, choices=ROOM_TYPES, default='Classroom')
    capacity = models.IntegerField(default=40)

    def __str__(self):
        return f"{self.room_name} ({self.get_room_type_display()})"


class SubjectAllocation(models.Model):
    SESSION_CHOICES = [
        ('Morning', 'Morning Session'),
        ('Afternoon', 'Afternoon Session'),
        ('Any', 'Any Session'),
    ]

    allocation_id = models.AutoField(primary_key=True)
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        db_column='class_id',
        related_name='subject_allocations',
        db_constraint=False,
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, db_column='subject_id', related_name='allocations')
    teacher = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='teacher_id', related_name='subject_allocations', limit_choices_to={'role': 'Teacher'})
    periods_per_week = models.IntegerField(default=4)
    preferred_days = models.CharField(max_length=100, blank=True, null=True, help_text="Comma-separated day names e.g., 'Monday, Wednesday'")
    preferred_sessions = models.CharField(max_length=50, choices=SESSION_CHOICES, default='Any')
    is_practical = models.BooleanField(default=False, help_text="Practical subjects allow consecutive double periods")
    required_room_type = models.CharField(max_length=50, choices=Room.ROOM_TYPES, default='Classroom')

    class Meta:
        unique_together = ('school_class', 'subject')

    def __str__(self):
        return f"{self.school_class.class_name} - {self.subject.subject_name} ({self.teacher.full_name})"


class TeacherAvailability(models.Model):
    availability_id = models.AutoField(primary_key=True)
    teacher = models.OneToOneField(UserProfile, on_delete=models.CASCADE, db_column='teacher_id', related_name='availability', limit_choices_to={'role': 'Teacher'})
    max_periods_per_day = models.IntegerField(default=6)
    max_periods_per_week = models.IntegerField(default=30)
    available_days = models.CharField(max_length=100, default="Monday,Tuesday,Wednesday,Thursday,Friday", help_text="Comma-separated day names")
    available_periods = models.CharField(max_length=100, default="1,2,3,4,5,6,7,8", help_text="Comma-separated period numbers")

    def __str__(self):
        return f"Availability for {self.teacher.full_name}"


class TimetablePeriodConfig(models.Model):
    PERIOD_TYPES = [
        ('Lesson', 'Lesson Period'),
        ('Break', 'Tea/Short Break'),
        ('Lunch', 'Lunch Break'),
    ]

    config_id = models.AutoField(primary_key=True)
    period_no = models.IntegerField(unique=True)
    period_type = models.CharField(max_length=50, choices=PERIOD_TYPES, default='Lesson')
    start_time = models.CharField(max_length=20)
    end_time = models.CharField(max_length=20)
    label = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. Break, Lunch, Period 1")

    class Meta:
        ordering = ['period_no']

    def __str__(self):
        return f"Period {self.period_no}: {self.start_time} - {self.end_time} ({self.period_type})"
