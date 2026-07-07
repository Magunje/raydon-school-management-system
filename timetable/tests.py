from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from students.models import SchoolClass
from academics.models import Subject, ClassTimetableEntry
from accounts.models import UserProfile
from timetable.models import Room, SubjectAllocation, TeacherAvailability, TimetablePeriodConfig
from timetable.services.scheduler import TimetableScheduler
from timetable.services.conflict_checker import ConflictChecker
from timetable.services.workload_manager import WorkloadManager
from timetable.services.room_allocator import RoomAllocator

User = get_user_model()

class TimetableTestCase(TestCase):
    def setUp(self):
        # 1. Create User and UserProfile for Teacher
        self.user = User.objects.create_user(username="test_teacher", password="password123")
        self.teacher_profile = UserProfile.objects.create(
            user=self.user,
            full_name="Mr. Moyo",
            role="Teacher",
            status="Active"
        )

        # 2. Create another Teacher
        self.user_2 = User.objects.create_user(username="test_teacher_2", password="password123")
        self.teacher_profile_2 = UserProfile.objects.create(
            user=self.user_2,
            full_name="Mrs. Ndlovu",
            role="Teacher",
            status="Active"
        )

        # 3. Create Class
        # SchoolClass has fields class_name, grade_id, academic_year, class_teacher, class_teacher_id
        # Let's check how to construct SchoolClass. Wait, SchoolClass Meta has managed=False but is overridden to True in testing.
        self.school_class = SchoolClass.objects.create(
            class_name="Form 1A",
            grade_id=1,
            academic_year=2026,
            class_teacher=self.teacher_profile.full_name,
            class_teacher_id=self.teacher_profile.id
        )
        
        self.school_class_2 = SchoolClass.objects.create(
            class_name="Form 1B",
            grade_id=1,
            academic_year=2026,
            class_teacher=self.teacher_profile_2.full_name,
            class_teacher_id=self.teacher_profile_2.id
        )

        # 4. Create Subjects
        self.subject_math = Subject.objects.create(
            subject_code="MATH101",
            subject_name="Mathematics",
            grade="Form 1",
            status="Active"
        )
        
        self.subject_science = Subject.objects.create(
            subject_code="SCI101",
            subject_name="Science",
            grade="Form 1",
            status="Active"
        )

        # 5. Create Rooms
        self.room_classroom = Room.objects.create(
            room_name="Room 101",
            room_type="Classroom",
            capacity=45
        )
        
        self.room_lab = Room.objects.create(
            room_name="Science Lab A",
            room_type="Science Lab",
            capacity=30
        )

        # 6. Pre-populate default period configurations
        TimetableScheduler.pre_populate_configs_if_empty()

    def test_conflict_checker_class_overlap(self):
        """
        Verify that ConflictChecker detects class double-bookings (one class, two subjects).
        """
        # Create an entry directly in database
        entry = ClassTimetableEntry.objects.create(
            class_id=self.school_class.class_id,
            academic_year=2026,
            day_name="Monday",
            day_order=1,
            period_no=1,
            start_time="08:00",
            end_time="08:40",
            subject_id=self.subject_math.subject_id,
            subject_name=self.subject_math.subject_name,
            teacher_name=self.teacher_profile.full_name,
            room_name=self.room_classroom.room_name,
            generated_at=timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Now check if another subject at same time triggers conflict
        conflicts = ConflictChecker.check_conflicts(
            class_id=self.school_class.class_id,
            teacher_name="Mrs. Ndlovu",
            room_name="Room 102",
            day_name="Monday",
            period_no=1,
            academic_year=2026
        )
        self.assertTrue(any(c["type"] == "Class Period Overlap" for c in conflicts))

    def test_conflict_checker_teacher_double_booking(self):
        """
        Verify that ConflictChecker detects teacher double-bookings (same teacher, two classes).
        """
        ClassTimetableEntry.objects.create(
            class_id=self.school_class.class_id,
            academic_year=2026,
            day_name="Monday",
            day_order=1,
            period_no=1,
            start_time="08:00",
            end_time="08:40",
            subject_id=self.subject_math.subject_id,
            subject_name=self.subject_math.subject_name,
            teacher_name=self.teacher_profile.full_name,
            room_name=self.room_classroom.room_name,
            generated_at="2026-06-18"
        )

        # Test if same teacher assigned to Form 1B at same time triggers conflict
        conflicts = ConflictChecker.check_conflicts(
            class_id=self.school_class_2.class_id,
            teacher_name=self.teacher_profile.full_name,
            room_name="Room 102",
            day_name="Monday",
            period_no=1,
            academic_year=2026
        )
        self.assertTrue(any(c["type"] == "Teacher Double Booking" for c in conflicts))

    def test_conflict_checker_room_double_booking(self):
        """
        Verify that ConflictChecker detects room double-bookings (same room, two classes).
        """
        ClassTimetableEntry.objects.create(
            class_id=self.school_class.class_id,
            academic_year=2026,
            day_name="Monday",
            day_order=1,
            period_no=1,
            start_time="08:00",
            end_time="08:40",
            subject_id=self.subject_math.subject_id,
            subject_name=self.subject_math.subject_name,
            teacher_name=self.teacher_profile.full_name,
            room_name=self.room_classroom.room_name,
            generated_at="2026-06-18"
        )

        # Test if another class booked in Room 101 at same time triggers conflict
        conflicts = ConflictChecker.check_conflicts(
            class_id=self.school_class_2.class_id,
            teacher_name="Mrs. Ndlovu",
            room_name=self.room_classroom.room_name,
            day_name="Monday",
            period_no=1,
            academic_year=2026
        )
        self.assertTrue(any(c["type"] == "Room Double Booking" for c in conflicts))

    def test_teacher_availability_restrictions(self):
        """
        Verify that ConflictChecker respects teacher day/period availability restrictions.
        """
        # Configure teacher to be available only on Tuesdays
        TeacherAvailability.objects.create(
            teacher=self.teacher_profile,
            max_periods_per_day=6,
            max_periods_per_week=30,
            available_days="Tuesday",
            available_periods="1,2,3,4"
        )

        # Checking Monday should fail
        conflicts_monday = ConflictChecker.check_conflicts(
            class_id=self.school_class.class_id,
            teacher_name=self.teacher_profile.full_name,
            room_name=self.room_classroom.room_name,
            day_name="Monday",
            period_no=1,
            academic_year=2026
        )
        self.assertTrue(any(c["type"] == "Teacher Unavailable" for c in conflicts_monday))

        # Checking Tuesday Period 5 should fail (not in available_periods)
        conflicts_tuesday_p5 = ConflictChecker.check_conflicts(
            class_id=self.school_class.class_id,
            teacher_name=self.teacher_profile.full_name,
            room_name=self.room_classroom.room_name,
            day_name="Tuesday",
            period_no=5,
            academic_year=2026
        )
        self.assertTrue(any(c["type"] == "Teacher Unavailable" for c in conflicts_tuesday_p5))

    def test_teacher_workload_limit(self):
        """
        Verify that WorkloadManager correctly audits workload limits.
        """
        avail = TeacherAvailability.objects.create(
            teacher=self.teacher_profile,
            max_periods_per_day=2,
            max_periods_per_week=5,
            available_days="Monday,Tuesday,Wednesday",
            available_periods="1,2,3,4"
        )

        # Create two entries for Mr. Moyo on Monday
        ClassTimetableEntry.objects.create(
            class_id=self.school_class.class_id,
            academic_year=2026,
            day_name="Monday",
            day_order=1,
            period_no=1,
            start_time="08:00",
            end_time="08:40",
            subject_id=self.subject_math.subject_id,
            subject_name=self.subject_math.subject_name,
            teacher_name=self.teacher_profile.full_name,
            room_name=self.room_classroom.room_name,
            generated_at="2026-06-18"
        )
        ClassTimetableEntry.objects.create(
            class_id=self.school_class.class_id,
            academic_year=2026,
            day_name="Monday",
            day_order=1,
            period_no=2,
            start_time="08:40",
            end_time="09:20",
            subject_id=self.subject_math.subject_id,
            subject_name=self.subject_math.subject_name,
            teacher_name=self.teacher_profile.full_name,
            room_name=self.room_classroom.room_name,
            generated_at="2026-06-18"
        )

        # Now checking a 3rd period on Monday should violate the daily limit
        is_valid, msg = WorkloadManager.check_workload_limits(
            self.teacher_profile.id,
            self.teacher_profile.full_name,
            "Monday",
            2026,
            added_periods=1
        )
        self.assertFalse(is_valid)
        self.assertIn("max daily periods limit", msg)

    def test_timetable_generator_csp(self):
        """
        Verify that TimetableScheduler generates conflict-free schedules automatically.
        """
        # Create Subject Allocations
        SubjectAllocation.objects.create(
            school_class=self.school_class,
            subject=self.subject_math,
            teacher=self.teacher_profile,
            periods_per_week=4,
            required_room_type="Classroom"
        )
        SubjectAllocation.objects.create(
            school_class=self.school_class,
            subject=self.subject_science,
            teacher=self.teacher_profile_2,
            periods_per_week=2,
            is_practical=True,
            required_room_type="Science Lab"
        )

        # Run Scheduler
        result = TimetableScheduler.generate(academic_year=2026, target_class_id=self.school_class.class_id, replace_existing=True)
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["skipped"], 0)
        self.assertGreater(result["created"], 0)

        # Verify Science (practical) was scheduled consecutively as a double period
        science_entries = list(ClassTimetableEntry.objects.filter(
            class_id=self.school_class.class_id,
            subject_id=self.subject_science.subject_id
        ).order_by('day_order', 'period_no'))
        
        self.assertEqual(len(science_entries), 2)
        # Verify same day
        self.assertEqual(science_entries[0].day_name, science_entries[1].day_name)
        # Verify consecutive periods
        self.assertEqual(science_entries[1].period_no - science_entries[0].period_no, 1)
        # Verify assigned to science lab
        self.assertEqual(science_entries[0].room_name, self.room_lab.room_name)
