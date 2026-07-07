import random
from django.db import transaction
from django.core.exceptions import ValidationError
from exam_coordinator.models import ExamSeating, ExamCandidate, ExamRoomAssignment
from results_centre.models import Assessment, AssessmentComponent, StudentResult
from decimal import Decimal


def generate_random_seating(room_assignment):
    """Auto-generates sequential seat assignments with a randomizing algorithm

    to shuffle student distribution within the room to prevent cheating.
    """
    schedule = room_assignment.exam_schedule

    # Get candidates assigned to this schedule who do not have seating allocated yet
    candidates = list(
        ExamCandidate.objects.filter(
            exam_schedule=schedule, seat_allocation__isnull=True
        )
    )

    # Shuffling student distribution randomly
    random.shuffle(candidates)

    # Room capacity constraints check
    current_seatings_count = ExamSeating.objects.filter(
        room_assignment=room_assignment
    ).count()
    available_seats = room_assignment.capacity - current_seatings_count

    if len(candidates) > available_seats:
        raise ValidationError(
            f"Insufficient room capacity. Remaining seats: {available_seats}, candidates to seat: {len(candidates)}."
        )

    allocated_seatings = []
    with transaction.atomic():
        for index, candidate in enumerate(candidates, start=current_seatings_count + 1):
            seating = ExamSeating.objects.create(
                candidate=candidate,
                room_assignment=room_assignment,
                seat_number=index,
            )
            allocated_seatings.append(seating)

    return allocated_seatings


def handover_exam_scores_to_results_centre(exam_session, user=None):
    """Approved final marks write smoothly to hand over score data directly into

    the Phase 5 Results Centre ledger tables.
    """
    if exam_session.status != "PUBLISHED":
        raise ValidationError(
            "Cannot handover scores to Results Centre unless Exam Session status is 'PUBLISHED'."
        )

    schedules = exam_session.schedules.all()
    results_created = 0

    with transaction.atomic():
        for schedule in schedules:
            subject = schedule.subject
            term = exam_session.academic_term

            # Find candidates with scores
            candidates = schedule.candidates.all()
            for candidate in candidates:
                student = candidate.student
                academic_class = student.academic_class
                if not academic_class:
                    continue

                # Ensure AssessmentComponent exists (using TERMINAL_EXAM type)
                comp, _ = AssessmentComponent.objects.get_or_create(
                    subject=subject,
                    academic_class=academic_class,
                    component_type="TERMINAL_EXAM",
                    defaults={
                        "weighting_percentage": Decimal("100.00"),
                        "max_score": 100
                    }
                )

                # Ensure Assessment configuration exists in Results Centre
                assessment, _ = Assessment.objects.get_or_create(
                    component=comp,
                    academic_year=term.academic_year,
                    academic_term=term,
                    defaults={
                        "name": f"Terminal Exams - {exam_session.name}",
                        "status": "Published",
                    },
                )

                try:
                    seating = candidate.seat_allocation
                except ExamSeating.DoesNotExist:
                    continue

                # Handover score if present and student attended
                if seating.attendance_state == "Present" and seating.score is not None:
                    # Save to Results Centre StudentResult
                    res, created = StudentResult.objects.get_or_create(
                        assessment=assessment,
                        student=student,
                        defaults={
                            "score": seating.score,
                        },
                    )
                    if not created:
                        res.score = seating.score
                        res.save()
                    results_created += 1

    return results_created
