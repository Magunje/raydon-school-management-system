from django.db import transaction
from django.core.exceptions import ValidationError
from fees_management.models import (
    StudentFeeAccount,
    Payment,
    PaymentAllocation,
    Receipt,
    ReceiptControl,
    FinanceSetting,
    Sponsorship,
    Discount,
    ReconciliationRecord,
    ReconciliationItem,
    FinanceAuditLog,
)
from decimal import Decimal
import datetime
from django.utils import timezone


def get_active_exchange_rate():
    setting = FinanceSetting.objects.first()
    if not setting:
        return Decimal("1.0000"), "USD"
    return setting.zig_exchange_rate, setting.operating_currency


def log_finance_action(
    action,
    transaction_number=None,
    user=None,
    previous_value=None,
    new_value=None,
    reason=None,
):
    return FinanceAuditLog.objects.create(
        action=action,
        transaction_number=transaction_number,
        user=user,
        previous_value=previous_value,
        new_value=new_value,
        reason=reason,
    )


def build_receipt_payload(payment):
    account = payment.student_account
    student = account.student
    return {
        "receipt_number": payment.receipt_number,
        "student": student.admission_no,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "operating_amount": str(payment.amount_in_operating),
        "method": payment.payment_method,
        "payment_date": payment.payment_date.isoformat(),
        "outstanding_balance": str(account.outstanding_balance),
    }


def issue_receipt(payment, reprinted_by=None):
    setting = FinanceSetting.objects.first()
    latest = (
        Receipt.objects.filter(receipt_number=payment.receipt_number)
        .order_by("-version")
        .first()
    )
    version = 1 if latest is None else latest.version + 1
    payload = build_receipt_payload(payment)
    receipt = Receipt.objects.create(
        payment=payment,
        receipt_number=payment.receipt_number,
        version=version,
        reprinted_at=timezone.now() if latest else None,
        reprinted_by=reprinted_by if latest else None,
        qr_code_payload=str(payload),
        electronic_stamp=(
            setting.receipt_stamp_label if setting else "Electronic School Stamp"
        ),
    )
    log_finance_action(
        "Receipt reprint" if latest else "Receipt generation",
        transaction_number=payment.receipt_number,
        user=reprinted_by or payment.received_by,
        new_value=payload,
    )
    return receipt


def allocate_payment(payment):
    account = payment.student_account
    remaining = payment.amount_in_operating
    setting = FinanceSetting.objects.first()
    policy = (
        setting.payment_allocation_policy
        if setting
        else "OLDEST_ARREARS_FIRST"
    )

    if policy == "OLDEST_ARREARS_FIRST" and account.arrears > Decimal("0.00"):
        arrears_allocation = min(account.arrears, remaining)
        if arrears_allocation > Decimal("0.00"):
            PaymentAllocation.objects.create(
                payment=payment,
                student_account=account,
                allocation_type="ARREARS",
                amount=arrears_allocation,
            )
            remaining -= arrears_allocation

    if remaining > Decimal("0.00"):
        allocation_type = (
            "CREDIT"
            if remaining > max(account.total_charges - account.amount_paid, Decimal("0.00"))
            else "CURRENT_CHARGES"
        )
        PaymentAllocation.objects.create(
            payment=payment,
            student_account=account,
            allocation_type=allocation_type,
            amount=remaining,
        )


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

        allocate_payment(payment)
        issue_receipt(payment)

        log_finance_action(
            "Payment receipt generation",
            transaction_number=receipt_num,
            user=cashier,
            new_value={
                "amount": str(amount),
                "currency": currency,
                "amount_in_operating": str(amount_in_operating),
                "method": payment_method,
                "reference": transaction_reference,
            },
        )

    return payment


def reverse_payment(payment, user, reason):
    if payment.is_reversed:
        raise ValidationError("This payment has already been reversed.")
    if not reason:
        raise ValidationError("A reversal reason is required.")

    with transaction.atomic():
        previous_value = {
            "amount_in_operating": str(payment.amount_in_operating),
            "receipt_number": payment.receipt_number,
        }
        payment.is_reversed = True
        payment.reversed_by = user
        payment.reversed_at = timezone.now()
        payment.reversal_reason = reason
        payment.save()

        account = payment.student_account
        account.amount_paid -= payment.amount_in_operating
        if account.amount_paid < Decimal("0.00"):
            account.amount_paid = Decimal("0.00")
        account.save()

        log_finance_action(
            "Payment reversal",
            transaction_number=payment.receipt_number,
            user=user,
            previous_value=previous_value,
            new_value={"is_reversed": True},
            reason=reason,
        )

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
            approved_at=timezone.now(),
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

        log_finance_action(
            "Sponsorship approval",
            transaction_number=student_account.student.admission_no,
            new_value={
                "sponsor": sponsor_name,
                "type": sponsorship_type,
                "deduction": str(deduction),
            },
        )

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
            original_fee_amount=student_account.total_charges,
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

        log_finance_action(
            "Discount approval",
            transaction_number=student_account.student.admission_no,
            user=approved_by,
            new_value={
                "type": discount_type,
                "deduction": str(deduction),
            },
            reason=reason,
        )

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
            "matched_transactions": payments.count() if status == "RECONCILED" else 0,
            "unmatched_transactions": 0 if status == "RECONCILED" else payments.count(),
            "overpayments": discrepancy if discrepancy > Decimal("0.00") else Decimal("0.00"),
            "underpayments": abs(discrepancy) if discrepancy < Decimal("0.00") else Decimal("0.00"),
        },
    )

    record.items.all().delete()
    for payment in payments:
        ReconciliationItem.objects.create(
            reconciliation=record,
            payment=payment,
            transaction_reference=payment.transaction_reference,
            expected_amount=payment.amount,
            actual_amount=payment.amount if status == "RECONCILED" else Decimal("0.00"),
            status="MATCHED" if status == "RECONCILED" else "UNMATCHED",
        )

    log_finance_action(
        "Reconciliation activity",
        transaction_number=f"{payment_method}-{reconciliation_date}",
        user=resolved_by,
        new_value={
            "system_total": str(system_total),
            "actual_total": str(actual_total),
            "discrepancy": str(discrepancy),
            "status": status,
        },
    )

    return record
