from results_centre.models import StudentResult
from django.db.models import Avg
from decimal import Decimal


def calculate_rankings_for_assessment(assessment):
    """Calculates and stores section averages and class rankings for all student

    results under the given assessment.
    """
    results = list(
        StudentResult.objects.filter(assessment=assessment).order_by("-score")
    )
    if not results:
        return

    # Calculate assessment class average
    avg_val = (
        StudentResult.objects.filter(assessment=assessment).aggregate(
            Avg("score")
        )["score__avg"]
        or 0
    )
    avg_score = Decimal(str(avg_val))

    # Update ranks and averages
    for rank, result in enumerate(results, start=1):
        result.class_rank = rank
        result.class_average = avg_score
        result.allow_correction = (
            True  # Bypass read-only lock during telemetry updates
        )
        result.save()
