from django.db import transaction
from django.core.exceptions import ValidationError
from fees_management.models import (
    StudentFeeAccount,
    Payment,
    ReceiptControl,
    FinanceSetting,
    Sponsorship,
    Discount,
    ReconciliationRecord,
)
from decimal import Decimal
import datetime


def get_active_exchange_rate():
    setting = FinanceSetting.objects.first()
    if not setting:
        return Decimal("1.0000"), "USD"
    return setting.zig_exchange_rate, setting.operating_currency


def record_payment(
    student_account,
    amount,
    currency,
    payment_method,
    transaction_reference=None,
    cashier=None,
    payment_date=None,
):
    """Processes student payments with multi-currency handling and immediate balance updates."""
    if amount <= Decimal("0.00"):
        raise ValidationError("Payment amount must be greater than zero.")

    if not payment_date:
        payment_date = datetime.date.today()

    rate, operating_curr = get_active_exchange_rate()

    # Convert to operating currency
    if currency == operating_curr:
        amount_in_operating = amount
    elif currency == "ZIG" and operating_curr == "USD":
        amount_in_operating = (amount / rate).quantize(Decimal("0.01"))
    elif currency == "USD" and operating_curr == "ZIG":
        amount_in_operating = (amount * rate).quantize(Decimal("0.01"))
    else:
        amount_in_operating = amount

    with transaction.atomic():
        # Get receipt number control
        control, _ = ReceiptControl.objects.get_or_create(
            pk=1,
            defaults={
                "receipt_prefix": "REC",
                "invoice_prefix": "INV",
                "last_receipt_no": 0,
                "last_invoice_no": 0,
            },
        )
        control.last_receipt_no += 1
        control.save()

        year_suffix = payment_date.year
        receipt_num = f"{control.receipt_prefix}-{year_suffix}-{control.last_receipt_no:05d}"

        # Create payment record
        payment = Payment.objects.create(
            receipt_number=receipt_num,
            student_account=student_account,
            payment_date=payment_date,
            amount=amount,
            currency=currency,
            exchange_rate=rate,
            amount_in_operating=amount_in_operating,
            payment_method=payment_method,
            transaction_reference=transaction_reference,
            received_by=cashier,
        )

        # Update fee account balances immediately
        student_account.amount_paid += amount_in_operating
        student_account.save()  # Auto-recalculates outstanding balance

    return payment


def apply_sponsorship(
    student_account,
    sponsor_name,
    sponsorship_type,
    coverage_percentage=None,
    coverage_amount=None,
    start_date=None,
    end_date=None,
):
    """Registers a sponsorship program and applies it immediately to reduce charges."""
    if not start_date:
        start_date = datetime.date.today()
    if not end_date:
        end_date = start_date + datetime.timedelta(days=365)

    with transaction.atomic():
        sponsorship = Sponsorship.objects.create(
            student_account=student_account,
            sponsor_name=sponsor_name,
            sponsorship_type=sponsorship_type,
            coverage_percentage=coverage_percentage,
            coverage_amount=coverage_amount,
            start_date=start_date,
            end_date=end_date,
        )

        # Calculate discount amount
        deduction = Decimal("0.00")
        if coverage_percentage:
            deduction = (
                student_account.total_charges
                * (coverage_percentage / Decimal("100.00"))
            ).quantize(Decimal("0.01"))
        elif coverage_amount:
            deduction = coverage_amount

        # Apply to student account
        student_account.amount_paid += deduction
        student_account.save()

    return sponsorship


def apply_discount(
    student_account,
    discount_type,
    approved_by,
    amount=None,
    percentage=None,
    reason="",
):
    """Applies adjustments or waivers to fee balances with reason audits."""
    if not reason:
        raise ValidationError("A valid adjustment reason is strictly required.")

    with transaction.atomic():
        discount = Discount.objects.create(
            student_account=student_account,
            discount_type=discount_type,
            amount=amount,
            percentage=percentage,
            reason=reason,
            approved_by=approved_by,
        )

        deduction = Decimal("0.00")
        if discount_type == "PERCENTAGE" and percentage:
            deduction = (
                student_account.total_charges * (percentage / Decimal("100.00"))
            ).quantize(Decimal("0.01"))
        elif discount_type in ["FIXED_AMOUNT", "WAIVER"] and amount:
            deduction = amount

        # Apply immediately
        student_account.amount_paid += deduction
        student_account.save()

    return discount


def reconcile_payments(
    reconciliation_date, payment_method, actual_total, resolved_by=None
):
    """Reconciles payment records against actual bank/cash totals to highlight discrepancies."""
    payments = Payment.objects.filter(
        payment_date=reconciliation_date,
        payment_method=payment_method,
        is_reversed=False,
    )
    system_total = sum(p.amount for p in payments)

    discrepancy = actual_total - system_total
    status = "RECONCILED" if discrepancy == Decimal("0.00") else "DISCREPANCY"

    record, _ = ReconciliationRecord.objects.update_or_create(
        reconciliation_date=reconciliation_date,
        payment_method=payment_method,
        defaults={
            "system_total": system_total,
            "actual_total": actual_total,
            "discrepancy": discrepancy,
            "status": status,
            "resolved_by": resolved_by,
            "resolution_notes": (
                "Automatic Reconciliation Run"
                if status == "RECONCILED"
                else "Discrepancy identified"
            ),
        },
    )

    return record
