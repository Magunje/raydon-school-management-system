from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from attendance_ledger.models import AttendanceRecord
from attendance_ledger.services import update_student_attendance_summary


@receiver(post_save, sender=AttendanceRecord)
def handle_attendance_record_save(sender, instance, created, **kwargs):
    update_student_attendance_summary(instance.student)


@receiver(post_delete, sender=AttendanceRecord)
def handle_attendance_record_delete(sender, instance, **kwargs):
    update_student_attendance_summary(instance.student)
