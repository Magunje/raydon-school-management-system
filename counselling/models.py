from django.db import models
from django.conf import settings
from student_registry.models import Student
from human_resources.models import EmployeeProfile
import datetime


class CounsellingCase(models.Model):
    CATEGORY_CHOICES = [
        ("Academic", "Academic Counselling"),
        ("Behavioural", "Behavioural Counselling"),
        ("Personal", "Personal Counselling"),
        ("Career", "Career Guidance"),
        ("Social", "Social Counselling"),
    ]
    SEVERITY_CHOICES = [
        ("Low", "Low Risk"),
        ("Medium", "Medium Risk"),
        ("High", "High Risk"),
        ("Critical", "Critical Risk"),
    ]
    STATUS_CHOICES = [
        ("Open", "Open"),
        ("Under Review", "Under Review"),
        ("Follow-Up Required", "Follow-Up Required"),
        ("Closed", "Closed"),
        ("Referred", "Referred"),
    ]
    case_id = models.BigAutoField(primary_key=True)
    case_no = models.CharField(max_length=50, unique=True)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="counselling_cases"
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    severity_level = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="Low")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Open")
    assigned_counsellor = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="counselling_cases"
    )
    date_opened = models.DateField(default=datetime.date.today)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "counselling_cases"
        ordering = ["-date_opened", "-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Automatically update DisciplineProfile counselling referral counter if it exists
        from discipline.models import DisciplineProfile
        profile, created = DisciplineProfile.objects.get_or_create(student=self.student)
        profile.counselling_referrals = self.student.counselling_cases.count()
        profile.save()

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"{self.case_no} - {self.student.full_name} ({self.status})"


class CounsellingSession(models.Model):
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]
    session_id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(
        CounsellingCase, on_delete=models.CASCADE, related_name="sessions"
    )
    session_number = models.IntegerField()
    date = models.DateField(default=datetime.date.today)
    time = models.TimeField(null=True, blank=True)
    counsellor = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="conducted_sessions"
    )
    session_notes = models.TextField(help_text="Detailed notes on counselling session (Strictly confidential)")
    recommendations = models.TextField(blank=True, null=True)
    follow_up_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="Completed")

    class Meta:
        db_table = "counselling_sessions"
        ordering = ["date", "session_number"]

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"Session #{self.session_number} for case {self.case.case_no}"


class CounsellingAppointment(models.Model):
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Attended", "Attended"),
        ("Cancelled", "Cancelled"),
        ("No Show", "No Show"),
    ]
    appointment_id = models.BigAutoField(primary_key=True)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="counselling_appointments"
    )
    counsellor = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments"
    )
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Scheduled")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "counselling_appointments"
        ordering = ["date", "time"]

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"Appointment: {self.student.full_name} on {self.date} at {self.time}"


class CounsellingInterventionPlan(models.Model):
    PLAN_CHOICES = [
        ("Academic", "Academic Improvement"),
        ("Behavioural", "Behavioural Support"),
        ("Emotional", "Emotional Support"),
        ("Social", "Social Intervention"),
    ]
    plan_id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(
        CounsellingCase, on_delete=models.CASCADE, related_name="interventions"
    )
    plan_type = models.CharField(max_length=30, choices=PLAN_CHOICES)
    objectives = models.TextField()
    activities = models.TextField()
    review_date = models.DateField()
    responsible_person = models.CharField(max_length=150)
    progress_notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "counselling_interventions"

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"Intervention Plan - {self.case.case_no} ({self.plan_type})"


class CareerGuidanceSession(models.Model):
    session_id = models.BigAutoField(primary_key=True)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="career_sessions"
    )
    counsellor = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="career_sessions"
    )
    date = models.DateField(default=datetime.date.today)
    career_interests = models.TextField()
    university_info = models.TextField(blank=True, null=True)
    scholarship_info = models.TextField(blank=True, null=True)
    assessment_notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "career_guidance_sessions"

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"Career Guidance - {self.student.full_name} on {self.date}"


class CounsellingParentMeeting(models.Model):
    meeting_id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(
        CounsellingCase, on_delete=models.CASCADE, related_name="parent_meetings"
    )
    date = models.DateField(default=datetime.date.today)
    participants = models.TextField()
    notes = models.TextField()
    actions_taken = models.TextField()
    follow_up_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "counselling_parent_meetings"

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"Parent Consultation for case {self.case.case_no} on {self.date}"
