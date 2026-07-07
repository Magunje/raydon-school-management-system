from decimal import Decimal
from io import BytesIO
import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    EmployeePayrollProfile,
    PayrollAdjustment,
    PayrollApproval,
    PayrollAuditAction,
    PayrollAuditLog,
    PayrollExportLog,
    PayrollItem,
    PayrollItemType,
    PayrollPeriod,
    PayrollRun,
    PayrollStatus,
    Payslip,
)


EARNING_FIELDS = [
    ("basic_salary", "Basic salary", "profile"),
    ("housing_allowance", "Housing allowance", "run"),
    ("transport_allowance", "Transport allowance", "run"),
    ("bonus", "Bonus", "run"),
    ("overtime", "Overtime", "run"),
    ("other_allowance", "Other allowance", "run"),
]

DEDUCTION_FIELDS = [
    ("tax", "Tax", "run"),
    ("nssa", "NSSA", "run"),
    ("pension", "Pension", "run"),
    ("loan", "Loan", "run"),
    ("advance", "Advance", "run"),
    ("unpaid_leave", "Unpaid leave", "run"),
    ("other_deductions", "Other deductions", "run"),
]

COPY_ADJUSTMENT_FIELDS = [
    "housing_allowance",
    "transport_allowance",
    "bonus",
    "overtime",
    "other_allowance",
    "tax",
    "nssa",
    "pension",
    "loan",
    "advance",
    "unpaid_leave",
    "other_deductions",
]


def create_audit(action, *, actor=None, period=None, run=None, details=""):
    return PayrollAuditLog.objects.create(
        action=action,
        actor=actor,
        period=period,
        run=run,
        details=details,
    )


def previous_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def latest_previous_run(profile, year, month):
    previous_year, previous_period_month = previous_month(year, month)
    return (
        PayrollRun.objects.filter(
            employee_profile=profile,
            period__year=previous_year,
            period__month=previous_period_month,
        )
        .select_related("period")
        .first()
    )


def run_defaults_from_profile(profile, period, user, previous_run=None, copy_previous=False):
    defaults = {
        "period": period,
        "employee_profile": profile,
        "employee_name": profile.full_name,
        "employee_number": profile.employee_number,
        "job_title": profile.job_title,
        "department": profile.department,
        "payment_method": profile.payment_method,
        "account_number": profile.account_number,
        "bank_name": profile.bank_name,
        "branch_name": profile.branch_name,
        "basic_salary": profile.basic_salary,
        "created_by": user,
        "updated_by": user,
        "copied_from": previous_run if copy_previous else None,
    }
    if copy_previous and previous_run:
        for field_name in COPY_ADJUSTMENT_FIELDS:
            defaults[field_name] = getattr(previous_run, field_name)
    return defaults


def rebuild_payroll_items(run):
    PayrollItem.objects.filter(run=run).delete()
    items = []
    sort_order = 1
    for field_name, label, source in EARNING_FIELDS:
        amount = getattr(run, field_name) or Decimal("0.00")
        if amount:
            items.append(
                PayrollItem(
                    run=run,
                    item_type=PayrollItemType.EARNING,
                    code=field_name.upper(),
                    label=label,
                    amount=amount,
                    source=source,
                    sort_order=sort_order,
                )
            )
            sort_order += 1
    for adjustment in run.adjustments.filter(adjustment_type=PayrollItemType.EARNING):
        items.append(
            PayrollItem(
                run=run,
                item_type=PayrollItemType.EARNING,
                code=adjustment.code,
                label=adjustment.description,
                amount=adjustment.amount,
                source="adjustment",
                sort_order=sort_order,
            )
        )
        sort_order += 1

    sort_order = 1
    for field_name, label, source in DEDUCTION_FIELDS:
        amount = getattr(run, field_name) or Decimal("0.00")
        if amount:
            items.append(
                PayrollItem(
                    run=run,
                    item_type=PayrollItemType.DEDUCTION,
                    code=field_name.upper(),
                    label=label,
                    amount=amount,
                    source=source,
                    sort_order=sort_order,
                )
            )
            sort_order += 1
    for adjustment in run.adjustments.filter(adjustment_type=PayrollItemType.DEDUCTION):
        items.append(
            PayrollItem(
                run=run,
                item_type=PayrollItemType.DEDUCTION,
                code=adjustment.code,
                label=adjustment.description,
                amount=adjustment.amount,
                source="adjustment",
                sort_order=sort_order,
            )
        )
        sort_order += 1

    if items:
        PayrollItem.objects.bulk_create(items)


def refresh_run_totals(run):
    run.calculate_totals(include_adjustments=True)
    run.save()
    rebuild_payroll_items(run)
    return run


@transaction.atomic
def process_period(*, year, month, user, copy_previous=False):
    period, _created = PayrollPeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"created_by": user},
    )
    if period.locked:
        raise ValidationError("Approved or paid payroll periods cannot be processed again.")

    created_count = 0
    active_profiles = EmployeePayrollProfile.objects.filter(employment_status="Active").order_by("full_name")
    for profile in active_profiles:
        previous_run = latest_previous_run(profile, year, month)
        defaults = run_defaults_from_profile(profile, period, user, previous_run, copy_previous)
        run, created = PayrollRun.objects.get_or_create(
            period=period,
            employee_profile=profile,
            defaults=defaults,
        )
        if created:
            created_count += 1
            run.calculate_totals(include_adjustments=False)
            run.save()
            if copy_previous and previous_run:
                for adjustment in previous_run.adjustments.all():
                    PayrollAdjustment.objects.create(
                        run=run,
                        adjustment_type=adjustment.adjustment_type,
                        code=adjustment.code,
                        description=adjustment.description,
                        amount=adjustment.amount,
                        notes=adjustment.notes,
                        created_by=user,
                    )
            refresh_run_totals(run)

    create_audit(
        PayrollAuditAction.PERIOD_PROCESSED,
        actor=user,
        period=period,
        details=f"{created_count} payroll run(s) created for {period.period_code}. Copy previous: {copy_previous}",
    )
    return period, created_count


@transaction.atomic
def update_run_adjustments(run, *, user):
    if run.period.locked or run.locked:
        raise ValidationError("Approved or paid payroll runs are locked.")
    run.updated_by = user
    run.save()
    refresh_run_totals(run)
    create_audit(PayrollAuditAction.RUN_UPDATED, actor=user, period=run.period, run=run, details="Payroll adjustments updated.")
    return run


@transaction.atomic
def add_adjustment(run, form, *, user):
    if run.period.locked or run.locked:
        raise ValidationError("Approved or paid payroll runs are locked.")
    adjustment = form.save(commit=False)
    adjustment.run = run
    adjustment.created_by = user
    adjustment.save()
    refresh_run_totals(run)
    create_audit(
        PayrollAuditAction.RUN_UPDATED,
        actor=user,
        period=run.period,
        run=run,
        details=f"Adjustment {adjustment.code} {adjustment.amount} added.",
    )
    return adjustment


@transaction.atomic
def delete_adjustment(adjustment, *, user):
    run = adjustment.run
    if run.period.locked or run.locked:
        raise ValidationError("Approved or paid payroll runs are locked.")
    details = f"Adjustment {adjustment.code} {adjustment.amount} removed."
    adjustment.delete()
    refresh_run_totals(run)
    create_audit(PayrollAuditAction.RUN_UPDATED, actor=user, period=run.period, run=run, details=details)


@transaction.atomic
def transition_period(period, action, *, user, notes=""):
    status_before = period.status
    now = timezone.now()
    if action == "review" and period.status == PayrollStatus.DRAFT:
        period.status = PayrollStatus.REVIEWED
        period.reviewed_by = user
        period.reviewed_at = now
    elif action == "approve" and period.status in {PayrollStatus.DRAFT, PayrollStatus.REVIEWED}:
        if not period.runs.exists():
            raise ValidationError("Payroll cannot be approved before employees are loaded.")
        period.status = PayrollStatus.APPROVED
        period.locked = True
        period.approved_by = user
        period.approved_at = now
    elif action == "mark_paid" and period.status == PayrollStatus.APPROVED:
        period.status = PayrollStatus.PAID
        period.locked = True
        period.paid_by = user
        period.paid_at = now
    elif action == "reopen" and period.status in {PayrollStatus.DRAFT, PayrollStatus.REVIEWED}:
        period.status = PayrollStatus.DRAFT
        period.locked = False
    else:
        raise ValidationError("That payroll workflow action is not allowed for the current status.")

    period.save()
    period.runs.update(status=period.status, locked=period.locked, updated_at=now)
    PayrollApproval.objects.create(
        period=period,
        from_status=status_before,
        to_status=period.status,
        action=action,
        notes=notes,
        approved_by=user,
    )
    create_audit(
        PayrollAuditAction.STATUS_CHANGED,
        actor=user,
        period=period,
        details=f"Payroll changed from {status_before} to {period.status}. {notes}",
    )
    return period


def payroll_summary(period):
    return period.runs.aggregate(
        employees=Count("id"),
        gross=Sum("gross_salary"),
        deductions=Sum("total_deductions"),
        net=Sum("net_salary"),
    )


def build_bank_export(period, *, user):
    if period.status not in {PayrollStatus.APPROVED, PayrollStatus.PAID}:
        raise ValidationError("Only approved payroll can be exported for bank payment.")
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for bank Excel export.") from exc

    runs = list(period.runs.order_by("employee_name"))
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bank Payment"
    headers = [
        "Full Name",
        "Account Number",
        "Bank Name",
    ]
    sheet.append(headers)

    for run in runs:
        sheet.append(
            [
                run.employee_name,
                run.account_number,
                run.bank_name,
            ]
        )

    for column_cells in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column_cells) + 2
        sheet.column_dimensions[column_cells[0].column_letter].width = min(width, 32)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    total_net = sum((run.net_salary for run in runs), Decimal("0.00"))
    file_name = f"bank-payroll-{period.period_code}.xlsx"
    PayrollExportLog.objects.create(
        period=period,
        file_name=file_name,
        total_records=len(runs),
        total_net=total_net,
        exported_by=user,
    )
    create_audit(PayrollAuditAction.EXPORTED, actor=user, period=period, details=f"{file_name} exported.")
    return file_name, buffer


def payslip_lines(run):
    if not run.items.exists():
        rebuild_payroll_items(run)
    earnings = run.items.filter(item_type=PayrollItemType.EARNING)
    deductions = run.items.filter(item_type=PayrollItemType.DEDUCTION)
    return earnings, deductions


def get_or_create_payslip(run, *, user):
    slip_number = f"PAY-{run.period.period_code}-{run.employee_number}"
    payslip, _created = Payslip.objects.get_or_create(
        run=run,
        defaults={"slip_number": slip_number, "generated_by": user},
    )
    create_audit(
        PayrollAuditAction.PAYSLIP_GENERATED,
        actor=user,
        period=run.period,
        run=run,
        details=f"Payslip {payslip.slip_number} opened.",
    )
    return payslip


def payslip_auth_payload(run, payslip):
    raw = f"{payslip.slip_number}|{run.employee_number}|{run.period.period_code}|{run.net_salary}"
    signature = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    return (
        f"Raydon School System Payslip Verification\n"
        f"Slip: {payslip.slip_number}\n"
        f"Employee: {run.employee_name} ({run.employee_number})\n"
        f"Period: {run.period.period_code}\n"
        f"Net: USD {run.net_salary:,.2f}\n"
        f"Code: {signature}"
    )


def payslip_qr_image(payload, size_mm):
    import qrcode
    from reportlab.lib.units import mm
    from reportlab.platypus import Image

    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return Image(buffer, width=size_mm * mm, height=size_mm * mm)


def electronic_stamp_table(settings, styles):
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle

    school_name = settings.get("school_name") or "Raydon School System"
    table = Table(
        [[Paragraph("<b>ELECTRONICALLY STAMPED</b>", styles["Normal"])], [Paragraph(school_name, styles["Normal"])]],
        colWidths=[58 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#0f766e")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#7dd3fc")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f766e")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ecfeff")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def payslip_story(run, *, user, styles, settings):
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    generated_at = timezone.localtime().strftime("%Y-%m-%d %H:%M")
    payslip = get_or_create_payslip(run, user=user)
    earnings, deductions = payslip_lines(run)
    story = [
        Paragraph(f"Payslip {payslip.slip_number}", styles["Heading2"]),
        Paragraph(f"{run.employee_name} | {run.employee_number} | {run.department}", styles["Normal"]),
        Paragraph(f"Payroll month: {run.period.period_code}", styles["Normal"]),
        Paragraph(f"Generation date: {generated_at}", styles["Normal"]),
        Spacer(1, 10),
    ]

    max_rows = max(earnings.count(), deductions.count())
    rows = [["Earnings", "Amount", "Deductions", "Amount"]]
    earning_list = list(earnings)
    deduction_list = list(deductions)
    for index in range(max_rows):
        earning = earning_list[index] if index < len(earning_list) else None
        deduction = deduction_list[index] if index < len(deduction_list) else None
        rows.append(
            [
                earning.label if earning else "",
                f"{earning.amount:,.2f}" if earning else "",
                deduction.label if deduction else "",
                f"{deduction.amount:,.2f}" if deduction else "",
            ]
        )
    rows.extend(
        [
            ["Gross salary", f"{run.gross_salary:,.2f}", "Total deductions", f"{run.total_deductions:,.2f}"],
            ["", "", "Net salary", f"{run.net_salary:,.2f}"],
        ]
    )
    table = Table(rows, colWidths=[55 * mm, 34 * mm, 55 * mm, 34 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ("BACKGROUND", (0, -2), (-1, -1), colors.HexColor("#f8fafc")),
            ]
        )
    )
    story.append(table)
    story.extend(
        [
            Spacer(1, 18),
            Paragraph(f"Payment method: {run.payment_method}", styles["Normal"]),
            Paragraph(f"Bank: {run.bank_name or '-'} | Account: {run.account_number or '-'}", styles["Normal"]),
            Spacer(1, 16),
        ]
    )
    qr = payslip_qr_image(payslip_auth_payload(run, payslip), 31)
    stamp = electronic_stamp_table(settings, styles)
    auth_table = Table(
        [
            [
                stamp,
                qr,
                Paragraph(
                    "Scan the QR code to compare the slip number, employee, period, net amount, and verification code on the printed payslip.",
                    styles["Normal"],
                ),
            ]
        ],
        colWidths=[62 * mm, 34 * mm, 82 * mm],
    )
    auth_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.extend(
        [
            auth_table,
            Spacer(1, 24),
            Paragraph("Employee signature: ____________________________", styles["Normal"]),
            Spacer(1, 12),
            Paragraph("Authorised signature: __________________________", styles["Normal"]),
        ]
    )
    return story


def build_payslip_pdf(run, *, user):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    from school_system_django.native import get_pdf_header, school_settings

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=18 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    settings = school_settings()
    story = [get_pdf_header(settings, 178 * mm)] + payslip_story(run, user=user, styles=styles, settings=settings)
    doc.build(story)
    buffer.seek(0)
    return f"payslip-{run.employee_number}-{run.period.period_code}.pdf", buffer


def build_period_payslips_pdf(period, *, user):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, SimpleDocTemplate
    from school_system_django.native import get_pdf_header, school_settings

    runs = list(period.runs.select_related("employee_profile").order_by("employee_name"))
    if not runs:
        raise ValidationError("No payroll runs are available for this period.")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=18 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    settings = school_settings()
    story = []
    for index, run in enumerate(runs):
        if index:
            story.append(PageBreak())
        story.append(get_pdf_header(settings, 178 * mm))
        story.extend(payslip_story(run, user=user, styles=styles, settings=settings))
    doc.build(story)
    buffer.seek(0)
    return f"bulk-payslips-{period.period_code}.pdf", buffer
