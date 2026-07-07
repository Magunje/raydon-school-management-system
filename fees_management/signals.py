from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from student_registry.models import Student
from academic_structure.models import AcademicYear, AcademicTerm
from fees_management.models import (
    StudentFeeAccount,
    FeeStructure,
    Invoice,
    InvoiceItem,
    FeeCategory,
    ReceiptControl,
)
from decimal import Decimal
import datetime


@receiver(post_save, sender=Student)
def auto_create_fee_account_and_bill(sender, instance, created, **kwargs):
    """Automatically assigns correct fee structure (O/A Level) and bills

    students on registration.
    """
    # Trigger account creation on registration creation or when class gets assigned
    if not instance.academic_class:
        return

    # Check if a fee account already exists
    if hasattr(instance, "fee_account"):
        return

    # Resolve active term and year
    year = instance.academic_class.academic_year
    term = AcademicTerm.objects.filter(academic_year=year, is_active=True).first()
    if not term:
        # Fallback to first term if no active term configured
        term = AcademicTerm.objects.filter(academic_year=year).first()

    if not term:
        return

    # Determine Fee level based on class grade name
    grade_name = instance.academic_class.form.name.upper()
    if "FORM 5" in grade_name or "FORM 6" in grade_name:
        level = "A_LEVEL"
        amount = Decimal("150.00")
    else:
        level = "O_LEVEL"
        amount = Decimal("100.00")

    with transaction.atomic():
        # Get or create FeeStructure
        deadline = datetime.date(year.year, 2, 1)  # Default deadline
        fee_struct, _ = FeeStructure.objects.get_or_create(
            academic_year=year,
            academic_term=term,
            level=level,
            defaults={"amount": amount, "payment_deadline": deadline},
        )

        # Get or create Tuition Fees Category
        tuition_cat, _ = FeeCategory.objects.get_or_create(
            name="Tuition Fees", defaults={"is_active": True}
        )

        # Create Fee Account
        account = StudentFeeAccount.objects.create(
            student=instance,
            academic_year=year,
            academic_term=term,
            fee_structure=fee_struct,
            total_charges=fee_struct.amount,
            amount_paid=Decimal("0.00"),
            arrears=Decimal("0.00"),
        )

        # Retrieve/initialize ReceiptControl
        control, _ = ReceiptControl.objects.get_or_create(
            pk=1,
            defaults={
                "receipt_prefix": "REC",
                "invoice_prefix": "INV",
                "last_receipt_no": 0,
                "last_invoice_no": 0,
            },
        )

        # Generate unique sequential invoice number
        control.last_invoice_no += 1
        control.save()

        inv_num = f"{control.invoice_prefix}-{year.year}-{control.last_invoice_no:05d}"

        # Generate Invoice
        invoice = Invoice.objects.create(
            invoice_number=inv_num,
            student_account=account,
            due_date=fee_struct.payment_deadline,
            previous_balance=Decimal("0.00"),
            current_charges=fee_struct.amount,
            discounts=Decimal("0.00"),
            scholarships=Decimal("0.00"),
        )

        # Create Invoice Item
        InvoiceItem.objects.create(
            invoice=invoice, category=tuition_cat, amount=fee_struct.amount
        )
