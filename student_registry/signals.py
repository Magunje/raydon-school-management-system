from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from student_registry.models import Student, FeeStructure, StudentFeeRecord
from decimal import Decimal


@receiver(post_save, sender=Student)
def auto_bind_fee_structure(sender, instance, created, **kwargs):
    if not instance.academic_class:
        return

    form_num = instance.academic_class.form.form_number

    # Resolve default amounts from django.conf.settings to ensure they are configurable
    if form_num in [1, 2, 3, 4]:
        level = "O-Level"
        default_amount = Decimal(
            getattr(settings, "O_LEVEL_DEFAULT_FEE", "100.00")
        )
        structure_name = "O-Level Fee Structure"
    elif form_num in [5, 6]:
        level = "A-Level"
        default_amount = Decimal(
            getattr(settings, "A_LEVEL_DEFAULT_FEE", "150.00")
        )
        structure_name = "A-Level Fee Structure"
    else:
        return

    # Get or create FeeStructure
    fee_structure, _ = FeeStructure.objects.get_or_create(
        name=structure_name,
        defaults={"default_amount": default_amount, "academic_level": level},
    )

    # Create the Student Fee Record ledger entry
    StudentFeeRecord.objects.get_or_create(
        student=instance,
        fee_structure=fee_structure,
        defaults={"amount": fee_structure.default_amount},
    )
