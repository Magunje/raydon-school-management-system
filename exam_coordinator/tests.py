from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academic_structure.models import (
    AcademicYear,
    AcademicTerm,
    Form,
    Stream,
    AcademicClass,
)
from timetable_engine.models import Classroom
from student_registry.models import Student
from subject_management.models import Subject, StudentSubjectRegistration
from exam_coordinator.models import (
    ExamSession,
    ExamSchedule,
    ExamCandidate,
    ExamRoomAssignment,
    ExamSeating,
)
from exam_coordinator.services import (
    generate_random_seating,
    handover_exam_scores_to_results_centre,
)
from results_centre.models import StudentResult
import datetime
from decimal import Decimal

User = get_user_model()


class ExamCoordinatorTestCase(TestCase):
    def setUp(self):
        # Create academic context
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.term = AcademicTerm.objects.create(
            academic_year=self.year, term_number=1, is_active=True
        )

        self.form_1 = Form.objects.create(form_number=1, name="Form 1")
        self.stream_a = Stream.objects.create(name="A")
        self.academic_class = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_1, stream=self.stream_a
        )

        # Subjects
        self.sub_eng = Subject.objects.create(
            code="OL_ENG", name="English", level="O_LEVEL"
        )
        self.sub_mat = Subject.objects.create(
            code="OL_MAT", name="Mathematics", level="O_LEVEL"
        )

        # Classroom
        self.room_101 = Classroom.objects.create(name="Room 101", capacity=2)

        # Students
        self.student_1 = Student.objects.create(
            first_name="Ruvimbo",
            surname="Tsvangirai",
            gender="Female",
            date_of_birth=datetime.date(2011, 4, 12),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )
        self.student_2 = Student.objects.create(
            first_name="Tatenda",
            surname="Mutasa",
            gender="Male",
            date_of_birth=datetime.date(2011, 8, 22),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )

        # Student Subject Registrations
        StudentSubjectRegistration.objects.create(
            student=self.student_1,
            subject=self.sub_eng,
            academic_year=self.year,
            academic_term=self.term,
        )
        # Note: student_2 is registered for English too
        StudentSubjectRegistration.objects.create(
            student=self.student_2,
            subject=self.sub_eng,
            academic_year=self.year,
            academic_term=self.term,
        )

        # Exam Session & Schedules
        self.session = ExamSession.objects.create(
            name="Term 1 Exams",
            session_type="END_OF_TERM",
            status="DRAFT",
            academic_year=self.year,
            academic_term=self.term,
        )

        self.schedule_eng = ExamSchedule.objects.create(
            session=self.session,
            subject=self.sub_eng,
            date=datetime.date(2026, 4, 5),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )

    def test_exam_candidate_eligibility_filter(self):
        # student_1 registered for English exam (succeeds)
        candidate = ExamCandidate.objects.create(
            student=self.student_1, exam_schedule=self.schedule_eng
        )
        self.assertIsNotNone(candidate)

        # Attempt to register student_1 for Mathematics exam (fails since not registered for Maths subject)
        schedule_mat = ExamSchedule.objects.create(
            session=self.session,
            subject=self.sub_mat,
            date=datetime.date(2026, 4, 6),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )

        with self.assertRaises(ValidationError):
            ExamCandidate.objects.create(
                student=self.student_1, exam_schedule=schedule_mat
            )

    def test_room_capacity_bounds_check(self):
        # Room 101 physical capacity is 2.
        # Assign capacity 3 should fail
        with self.assertRaises(ValidationError):
            ExamRoomAssignment.objects.create(
                exam_schedule=self.schedule_eng,
                classroom=self.room_101,
                capacity=3,
            )

        # Assign capacity 2 succeeds
        assignment = ExamRoomAssignment.objects.create(
            exam_schedule=self.schedule_eng, classroom=self.room_101, capacity=2
        )
        self.assertIsNotNone(assignment)

    def test_random_seating_scheduler_and_handover(self):
        assignment = ExamRoomAssignment.objects.create(
            exam_schedule=self.schedule_eng, classroom=self.room_101, capacity=2
        )

        # Register candidates
        cand_1 = ExamCandidate.objects.create(
            student=self.student_1, exam_schedule=self.schedule_eng
        )
        cand_2 = ExamCandidate.objects.create(
            student=self.student_2, exam_schedule=self.schedule_eng
        )

        # Generate seating allocation
        seatings = generate_random_seating(assignment)
        self.assertEqual(len(seatings), 2)
        self.assertEqual(seatings[0].seat_number, 1)
        self.assertEqual(seatings[1].seat_number, 2)

        # Set scores and attendance
        seatings[0].score = Decimal("82.50")
        seatings[0].save()

        seatings[1].score = Decimal("91.00")
        seatings[1].save()

        # Try handover in DRAFT state -> raises ValidationError
        with self.assertRaises(ValidationError):
            handover_exam_scores_to_results_centre(self.session)

        # Transition session to PUBLISHED
        self.session.status = "PUBLISHED"
        self.session.save()

        # Handover exam scores
        results_count = handover_exam_scores_to_results_centre(self.session)
        self.assertEqual(results_count, 2)

        # Verify Results Centre entries
        all_results = list(StudentResult.objects.all())
        print("ALL STUDENT RESULTS:", [(r.student.pk, r.score, r.student.status) for r in all_results])
        
        # Dynamically fetch the assigned scores after shuffling
        score_1 = self.student_1.exam_candidates.get().seat_allocation.score
        score_2 = self.student_2.exam_candidates.get().seat_allocation.score

        res_1 = StudentResult.objects.filter(
            student=self.student_1, score=score_1
        ).exists()
        res_2 = StudentResult.objects.filter(
            student=self.student_2, score=score_2
        ).exists()

        self.assertTrue(res_1)
        self.assertTrue(res_2)
