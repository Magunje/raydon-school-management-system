from django.db import models
from django.conf import settings
from student_registry.models import Student
from human_resources.models import EmployeeProfile
import datetime


class DisciplineCategory(models.Model):
    SEVERITY_CHOICES = [
        ("Minor", "Minor"),
        ("Moderate", "Moderate"),
        ("Major", "Major"),
    ]
    name = models.CharField(max_length=120, unique=True)
    default_points = models.IntegerField(default=0)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="Minor")

    class Meta:
        db_table = "discipline_categories"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.severity} - {self.default_points} pts)"


class DisciplineProfile(models.Model):
    student = models.OneToOneField(
        Student, on_delete=models.CASCADE, related_name="discipline_profile"
    )
    behaviour_score = models.IntegerField(default=100)
    active_sanctions = models.IntegerField(default=0)
    total_incidents = models.IntegerField(default=0)
    counselling_referrals = models.IntegerField(default=0)
    parent_meetings = models.IntegerField(default=0)
    suspension_history = models.IntegerField(default=0)

    class Meta:
        db_table = "discipline_profiles"

    def update_profile_stats(self):
        # Calculate behaviour score: 100 base minus sum of all incident points
        incidents = self.student.disciplinary_incidents.all()
        deductions = 0
        for inc in incidents:
            if inc.category:
                deductions += inc.category.default_points
        self.behaviour_score = max(0, 100 - deductions)
        self.total_incidents = incidents.count()
        self.active_sanctions = self.student.discipline_sanctions.filter(is_active=True).count()
        self.suspension_history = self.student.discipline_suspensions.count()
        self.save()

    def __str__(self):
        return f"{self.student.full_name} (Score: {self.behaviour_score})"


class DisciplinaryIncident(models.Model):
    STATUS_CHOICES = [
        ("Under Investigation", "Under Investigation"),
        ("Pending Action", "Pending Action"),
        ("Resolved", "Resolved"),
        ("Closed", "Closed"),
        ("Appealed", "Appealed"),
    ]
    incident_id = models.BigAutoField(primary_key=True)
    incident_no = models.CharField(max_length=50, unique=True)
    incident_date = models.DateField(default=datetime.date.today)
    incident_time = models.TimeField(null=True, blank=True)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="disciplinary_incidents"
    )
    category = models.ForeignKey(
        DisciplineCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents"
    )
    severity = models.CharField(max_length=20, default="Minor")
    description = models.TextField()
    witnesses = models.TextField(blank=True, null=True)
    reported_by = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="reported_incidents"
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Under Investigation")
    hostel_incident = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "disciplinary_incidents"
        ordering = ["-incident_date", "-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ensure discipline profile exists and updates
        profile, _ = DisciplineProfile.objects.get_or_create(student=self.student)
        profile.update_profile_stats()

    def delete(self, *args, **kwargs):
        # Prevent physical deletions as per rules
        pass

    def __str__(self):
        return f"{self.incident_no} - {self.student.full_name} ({self.status})"


class DisciplineSanction(models.Model):
    SANCTION_CHOICES = [
        ("Verbal Warning", "Verbal Warning"),
        ("Written Warning", "Written Warning"),
        ("Community Service", "Community Service"),
        ("Detention", "Detention"),
        ("Suspension", "Suspension"),
        ("Expulsion Recommendation", "Expulsion Recommendation"),
        ("Parent Meeting", "Parent Meeting"),
        ("Counselling Referral", "Counselling Referral"),
    ]
    sanction_id = models.BigAutoField(primary_key=True)
    incident = models.ForeignKey(
        DisciplinaryIncident, on_delete=models.CASCADE, related_name="sanctions"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="discipline_sanctions"
    )
    sanction_type = models.CharField(max_length=40, choices=SANCTION_CHOICES)
    start_date = models.DateField(default=datetime.date.today)
    end_date = models.DateField(null=True, blank=True)
    reason = models.TextField()
    approved_by = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_sanctions"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "discipline_sanctions"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.sanction_type == "Counselling Referral":
            from counselling.models import CounsellingCase
            case_count = CounsellingCase.objects.count() + 1
            case_num = f"CNS-{datetime.date.today().year}-{case_count:05d}"
            CounsellingCase.objects.create(
                case_no=case_num,
                student=self.student,
                category="Behavioural",
                description=f"Disciplinary Referral from sanction of type {self.sanction_type}. Reason: {self.reason}",
                severity_level="Medium",
                status="Open"
            )
        profile, _ = DisciplineProfile.objects.get_or_create(student=self.student)
        profile.update_profile_stats()

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"{self.sanction_type} - {self.student.full_name}"


class DisciplineSuspension(models.Model):
    SUSPENSION_CHOICES = [
        ("In-School", "In-School Suspension"),
        ("External", "External Suspension"),
        ("Indefinite", "Indefinite Suspension"),
    ]
    suspension_id = models.BigAutoField(primary_key=True)
    sanction = models.ForeignKey(
        DisciplineSanction, on_delete=models.CASCADE, related_name="suspensions"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="discipline_suspensions"
    )
    suspension_type = models.CharField(max_length=30, choices=SUSPENSION_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    reason = models.TextField()
    conditions = models.TextField(blank=True, null=True)
    return_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "discipline_suspensions"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        profile, _ = DisciplineProfile.objects.get_or_create(student=self.student)
        profile.update_profile_stats()

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"{self.suspension_type} - {self.student.full_name}"


class ParentMeeting(models.Model):
    meeting_id = models.BigAutoField(primary_key=True)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="parent_meetings"
    )
    incident = models.ForeignKey(
        DisciplinaryIncident, on_delete=models.SET_NULL, null=True, blank=True, related_name="meetings"
    )
    date = models.DateField(default=datetime.date.today)
    participants = models.TextField(help_text="Names of parents, teachers, and administrators attending")
    minutes = models.TextField()
    outcomes = models.TextField()
    follow_up_actions = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "discipline_parent_meetings"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        profile, _ = DisciplineProfile.objects.get_or_create(student=self.student)
        profile.parent_meetings = self.student.parent_meetings.count()
        profile.save()

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"Parent Meeting - {self.student.full_name} on {self.date}"


class BehaviourImprovementPlan(models.Model):
    STATUS_CHOICES = [
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Discontinued", "Discontinued"),
    ]
    plan_id = models.BigAutoField(primary_key=True)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="behaviour_plans"
    )
    mentor = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="mentored_plans"
    )
    start_date = models.DateField(default=datetime.date.today)
    review_date = models.DateField()
    targets = models.TextField()
    activities = models.TextField()
    progress_notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="In Progress")

    class Meta:
        db_table = "behaviour_improvement_plans"

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return f"Improvement Plan - {self.student.full_name} (Status: {self.status})"
