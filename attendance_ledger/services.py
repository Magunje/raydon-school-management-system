from attendance_ledger.models import AttendanceRecord, StudentAttendanceSummary
from decimal import Decimal


def update_student_attendance_summary(student):
    """Recalculates and updates the running attendance summaries for a student."""
    records = AttendanceRecord.objects.filter(student=student)
    total = records.count()

    # Calculate present days (Present and Late are counted as attending)
    present_days = records.filter(status__in=["Present", "Late"]).count()
    absent_days = records.filter(status="Absent").count()

    percentage = (present_days / total) * 100 if total > 0 else 100.00

    summary, _ = StudentAttendanceSummary.objects.get_or_create(student=student)
    summary.total_days = total
    summary.present_days = present_days
    summary.absent_days = absent_days
    summary.attendance_percentage = Decimal(f"{percentage:.2f}")
    summary.save()
    return summary
