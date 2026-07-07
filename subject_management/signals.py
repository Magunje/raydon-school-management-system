from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from subject_management.models import (
    StudentSubjectRegistration,
    TeacherSubjectAllocation,
    SubjectManagementAuditLog,
)


@receiver(post_save, sender=StudentSubjectRegistration)
def log_student_subject_registration_save(sender, instance, created, **kwargs):
    action = "CREATE" if created else "UPDATE"
    detail = (
        f"Student {instance.student} registered for subject {instance.subject} "
        f"for year {instance.academic_year} term {instance.academic_term}."
    )
    SubjectManagementAuditLog.objects.create(
        action=action,
        model_name="StudentSubjectRegistration",
        object_id=instance.id,
        detail=detail,
    )


@receiver(post_delete, sender=StudentSubjectRegistration)
def log_student_subject_registration_delete(sender, instance, **kwargs):
    detail = (
        f"Student {instance.student} unregistered from subject {instance.subject} "
        f"for year {instance.academic_year} term {instance.academic_term}."
    )
    SubjectManagementAuditLog.objects.create(
        action="DELETE",
        model_name="StudentSubjectRegistration",
        object_id=instance.id,
        detail=detail,
    )


@receiver(post_save, sender=TeacherSubjectAllocation)
def log_teacher_allocation_save(sender, instance, created, **kwargs):
    action = "CREATE" if created else "UPDATE"
    detail = (
        f"Teacher {instance.teacher} allocated to subject {instance.subject} "
        f"for {instance.form} {instance.stream} ({instance.academic_term})."
    )
    SubjectManagementAuditLog.objects.create(
        action=action,
        model_name="TeacherSubjectAllocation",
        object_id=instance.id,
        detail=detail,
    )


@receiver(post_delete, sender=TeacherSubjectAllocation)
def log_teacher_allocation_delete(sender, instance, **kwargs):
    detail = (
        f"Allocation of teacher {instance.teacher} to subject {instance.subject} "
        f"for {instance.form} {instance.stream} ({instance.academic_term}) was deleted."
    )
    SubjectManagementAuditLog.objects.create(
        action="DELETE",
        model_name="TeacherSubjectAllocation",
        object_id=instance.id,
        detail=detail,
    )
