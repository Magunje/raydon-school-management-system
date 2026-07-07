from django.db.models import Count
from timetable.models import TeacherAvailability
from accounts.models import UserProfile
from academics.models import ClassTimetableEntry

class WorkloadManager:
    @staticmethod
    def get_teacher_availability(teacher_id):
        """
        Retrieves or creates default availability settings for a teacher.
        """
        try:
            profile = UserProfile.objects.get(id=teacher_id)
        except UserProfile.DoesNotExist:
            return None
            
        availability, created = TeacherAvailability.objects.get_or_create(
            teacher=profile,
            defaults={
                'max_periods_per_day': 6,
                'max_periods_per_week': 30,
                'available_days': "Monday,Tuesday,Wednesday,Thursday,Friday",
                'available_periods': "1,2,3,4,5,6,7,8"
            }
        )
        return availability

    @staticmethod
    def get_weekly_workload(teacher_name, academic_year):
        """
        Counts the total periods assigned to a teacher in a given academic year.
        """
        if not teacher_name:
            return 0
        return ClassTimetableEntry.objects.filter(
            teacher_name=teacher_name,
            academic_year=academic_year
        ).count()

    @staticmethod
    def get_daily_workload(teacher_name, day_name, academic_year):
        """
        Counts the total periods assigned to a teacher on a specific day.
        """
        if not teacher_name or not day_name:
            return 0
        return ClassTimetableEntry.objects.filter(
            teacher_name=teacher_name,
            day_name=day_name,
            academic_year=academic_year
        ).count()

    @staticmethod
    def check_workload_limits(teacher_id, teacher_name, day_name, academic_year, added_periods=1):
        """
        Validates if adding periods to a teacher exceeds daily or weekly limits.
        Returns (is_valid, error_msg)
        """
        if not teacher_name:
            return True, ""
            
        availability = WorkloadManager.get_teacher_availability(teacher_id)
        if not availability:
            return True, ""

        # Check weekly limit
        weekly_current = WorkloadManager.get_weekly_workload(teacher_name, academic_year)
        if weekly_current + added_periods > availability.max_periods_per_week:
            return False, f"Teacher {teacher_name} exceeds max weekly periods limit of {availability.max_periods_per_week} (currently has {weekly_current})."

        # Check daily limit
        daily_current = WorkloadManager.get_daily_workload(teacher_name, day_name, academic_year)
        if daily_current + added_periods > availability.max_periods_per_day:
            return False, f"Teacher {teacher_name} exceeds max daily periods limit of {availability.max_periods_per_day} on {day_name} (currently has {daily_current})."

        return True, ""

    @staticmethod
    def get_all_workloads_summary(academic_year):
        """
        Compiles a summary of workloads for all active teachers for the dashboard.
        """
        teacher_profiles = UserProfile.objects.filter(role='Teacher', status='Active')
        summary = []
        
        for profile in teacher_profiles:
            avail = WorkloadManager.get_teacher_availability(profile.id)
            current_week = WorkloadManager.get_weekly_workload(profile.full_name, academic_year)
            
            # Days break-down
            days_breakdown = {}
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
                days_breakdown[day] = WorkloadManager.get_daily_workload(profile.full_name, day, academic_year)

            summary.append({
                'teacher_id': profile.id,
                'teacher_name': profile.full_name,
                'assigned_periods': current_week,
                'max_periods': avail.max_periods_per_week,
                'is_overloaded': current_week > avail.max_periods_per_week,
                'days_breakdown': days_breakdown
            })
            
        return summary
