from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounting_erp.models import AccountPortal, FinancialYear, JournalEntry, JournalLine, SchoolBudget
from accounting_erp.services import post_journal_entry
from procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    ProcurementApproval,
    ProcurementAuditLog,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    Supplier,
    SupplierInvoice,
    SupplierPayment,
    SupplierQuotation,
)


def next_procurement_number(prefix, model):
    return f"{prefix}-{model.objects.count() + 1:05d}"


def log_procurement_action(action, reference_number=None, user=None, new_value=None, reason=None):
    return ProcurementAuditLog.objects.create(
        action=action,
        reference_number=reference_number,
        user=user,
        new_value=new_value,
        reason=reason,
    )


def get_open_financial_year(txn_date):
    fy = FinancialYear.objects.filter(
        start_date__lte=txn_date,
        end_date__gte=txn_date,
        is_closed=False,
    ).exclude(status__in=["CLOSED", "LOCKED"]).first()
    if fy:
        return fy
    return FinancialYear.objects.create(
        name=f"FY {txn_date.year}",
        start_date=txn_date.replace(month=1, day=1),
        end_date=txn_date.replace(month=12, day=31),
        status="OPEN",
        is_closed=False,
    )


def get_or_create_account(code, name, account_type):
    account, _ = AccountPortal.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "account_type": account_type,
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
        },
    )
    return account


def post_procurement_journal(txn_date, reference_number, description, debit_account, credit_account, amount, user=None):
    if amount <= Decimal("0.00"):
        return None
    fy = get_open_financial_year(txn_date)
    entry = JournalEntry.objects.create(
        journal_number=f"JV-PROC-{reference_number}",
        entry_date=txn_date,
        description=description,
        financial_year=fy,
        approval_status="DRAFT",
        source_module="Procurement",
        reference_number=reference_number,
        prepared_by=user,
    )
    JournalLine.objects.create(
        journal_entry=entry,
        account=debit_account,
        debit_amount=amount,
        credit_amount=Decimal("0.00"),
    )
    JournalLine.objects.create(
        journal_entry=entry,
        account=credit_account,
        debit_amount=Decimal("0.00"),
        credit_amount=amount,
    )
    entry.approval_status = "APPROVED"
    entry.approved_by = user
    entry.save()
    return post_journal_entry(entry, user=user)


def create_requisition(
    department,
    requested_by,
    item_description,
    quantity,
    estimated_cost,
    priority,
    justification,
    required_date,
):
    requisition = PurchaseRequisition.objects.create(
        requisition_number=next_procurement_number("REQ", PurchaseRequisition),
        department=department,
        requested_by=requested_by,
        item_description=item_description,
        quantity=quantity,
        estimated_cost=estimated_cost,
        priority=priority,
        justification=justification,
        required_date=required_date,
        approval_status="SUBMITTED",
    )
    log_procurement_action(
        "Requisition creation",
        reference_number=requisition.requisition_number,
        user=requested_by,
        new_value={"department": department, "estimated_total": str(requisition.estimated_total)},
    )
    return requisition


def verify_budget(requisition):
    budgets = SchoolBudget.objects.filter(
        department=requisition.department,
        status__in=["APPROVED", "REVISED"],
    )
    remaining = sum(budget.variance for budget in budgets)
    requisition.budget_checked = True
    requisition.budget_available = remaining >= requisition.estimated_total
    requisition.budget_override_required = not requisition.budget_available
    if requisition.budget_available:
        requisition.approval_status = "BUDGET_APPROVED"
    requisition.save(
        update_fields=[
            "budget_checked",
            "budget_available",
            "budget_override_required",
            "approval_status",
        ]
    )
    return requisition.budget_available, remaining


def approve_requisition(requisition, stage, approved_by, comments=None, allow_budget_override=False):
    if stage == "FINANCE_VERIFICATION":
        available, _remaining = verify_budget(requisition)
        if not available and not allow_budget_override:
            raise ValidationError("Budget override requires higher-level approval.")
        requisition.approval_status = "FINANCE_VERIFIED"
    elif stage == "DEPARTMENT_HEAD":
        requisition.approval_status = "DEPARTMENT_APPROVED"
    elif stage == "SCHOOL_ADMIN":
        if requisition.budget_override_required and not allow_budget_override:
            raise ValidationError("School Administrator approval must explicitly allow the budget override.")
        requisition.approval_status = "ADMIN_APPROVED"
    else:
        raise ValidationError("Unsupported procurement approval stage.")

    requisition.save(update_fields=["approval_status"])
    ProcurementApproval.objects.create(
        requisition=requisition,
        stage=stage,
        approved_by=approved_by,
        comments=comments,
    )
    log_procurement_action(
        "Approval action",
        reference_number=requisition.requisition_number,
        user=approved_by,
        new_value={"stage": stage, "status": requisition.approval_status},
        reason=comments,
    )
    return requisition


def add_supplier_quotation(requisition, supplier, unit_price, delivery_period=None, warranty=None, validity_period=None):
    quotation = SupplierQuotation.objects.create(
        requisition=requisition,
        supplier=supplier,
        item=requisition.item_description[:180],
        unit_price=unit_price,
        total_price=(unit_price * requisition.quantity).quantize(Decimal("0.01")),
        delivery_period=delivery_period,
        warranty=warranty,
        validity_period=validity_period,
    )
    return quotation


def select_best_quotation(requisition):
    quotation = requisition.quotations.order_by("total_price", "-supplier__performance_score").first()
    if not quotation:
        raise ValidationError("At least one supplier quotation is required.")
    requisition.quotations.update(is_selected=False)
    quotation.is_selected = True
    quotation.save(update_fields=["is_selected"])
    return quotation


def generate_purchase_order(requisition, supplier=None, delivery_address="", delivery_date=None, approved_by=None, inventory_item=None):
    if requisition.approval_status != "ADMIN_APPROVED":
        raise ValidationError("Purchase Orders are generated only after final approval.")

    quotation = requisition.quotations.filter(is_selected=True).first()
    if not supplier:
        supplier = quotation.supplier if quotation else Supplier.objects.filter(status="ACTIVE").first()
    if not supplier:
        raise ValidationError("A supplier is required to create a Purchase Order.")
    unit_price = quotation.unit_price if quotation else requisition.estimated_cost
    total_amount = (unit_price * requisition.quantity).quantize(Decimal("0.01"))

    with transaction.atomic():
        po = PurchaseOrder.objects.create(
            purchase_order_number=next_procurement_number("PO", PurchaseOrder),
            requisition=requisition,
            supplier=supplier,
            delivery_address=delivery_address,
            delivery_date=delivery_date or requisition.required_date,
            total_amount=total_amount,
            payment_terms=supplier.payment_terms,
            approved_by=approved_by,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            inventory_item=inventory_item,
            description=requisition.item_description[:180],
            quantity=requisition.quantity,
            unit_price=unit_price,
        )
        requisition.approval_status = "PO_CREATED"
        requisition.save(update_fields=["approval_status"])
        log_procurement_action(
            "Purchase Order generation",
            reference_number=po.purchase_order_number,
            user=approved_by,
            new_value={"supplier": supplier.supplier_code, "total_amount": str(total_amount)},
        )
        return po


def receive_goods(purchase_order, store, received_by=None, inspection_notes=None):
    from inventory_management.services import receive_stock

    with transaction.atomic():
        receipt = GoodsReceipt.objects.create(
            goods_receipt_number=next_procurement_number("GRN", GoodsReceipt),
            purchase_order=purchase_order,
            supplier=purchase_order.supplier,
            delivery_date=purchase_order.delivery_date,
            store=store,
            received_by=received_by,
            inspection_notes=inspection_notes,
        )
        qty_received = Decimal("0.00")
        qty_rejected = Decimal("0.00")
        for po_item in purchase_order.items.all():
            GoodsReceiptItem.objects.create(
                goods_receipt=receipt,
                purchase_order_item=po_item,
                quantity_received=po_item.quantity,
                quantity_rejected=Decimal("0.00"),
                unit_cost=po_item.unit_price,
            )
            qty_received += po_item.quantity
            if po_item.inventory_item:
                receive_stock(
                    item=po_item.inventory_item,
                    store=store,
                    quantity=po_item.quantity,
                    unit_cost=po_item.unit_price,
                    reference_number=receipt.goods_receipt_number,
                    user=received_by,
                    supplier=purchase_order.supplier,
                )
        receipt.quantity_received = qty_received
        receipt.quantity_rejected = qty_rejected
        receipt.save(update_fields=["quantity_received", "quantity_rejected"])
        purchase_order.status = "RECEIVED"
        purchase_order.save(update_fields=["status"])
        log_procurement_action(
            "Goods receipt",
            reference_number=receipt.goods_receipt_number,
            user=received_by,
            new_value={"purchase_order": purchase_order.purchase_order_number, "quantity_received": str(qty_received)},
        )
        return receipt


def create_supplier_invoice(supplier, purchase_order, goods_receipt, invoice_number, invoice_date, due_date, amount, tax=Decimal("0.00"), override_reason=None):
    expected_total = sum(
        item.quantity_received * item.unit_cost for item in goods_receipt.items.all()
    ).quantize(Decimal("0.01"))
    invoice_total = (amount + tax).quantize(Decimal("0.01"))
    status = "MATCHED"
    if invoice_total > expected_total:
        if not override_reason:
            raise ValidationError("Supplier invoice must match Purchase Order and Goods Receipt before payment.")
        status = "OVERRIDE_APPROVED"

    invoice = SupplierInvoice.objects.create(
        invoice_number=invoice_number,
        supplier=supplier,
        purchase_order=purchase_order,
        goods_receipt=goods_receipt,
        invoice_date=invoice_date,
        due_date=due_date,
        amount=amount,
        tax=tax,
        status=status,
        override_reason=override_reason,
    )
    purchase_order.status = "INVOICED"
    purchase_order.save(update_fields=["status"])
    log_procurement_action(
        "Invoice processing",
        reference_number=invoice.invoice_number,
        new_value={"status": status, "amount": str(amount), "tax": str(tax)},
        reason=override_reason,
    )
    return invoice


def pay_supplier_invoice(invoice, amount, payment_method, payment_date, authorised_by=None, bank_account=None):
    if invoice.status not in ["MATCHED", "OVERRIDE_APPROVED", "APPROVED_FOR_PAYMENT"]:
        raise ValidationError("Only matched or authorised supplier invoices can be paid.")
    if amount <= Decimal("0.00"):
        raise ValidationError("Supplier payment amount must be greater than zero.")

    with transaction.atomic():
        payment = SupplierPayment.objects.create(
            payment_voucher_number=next_procurement_number("PV", SupplierPayment),
            supplier=invoice.supplier,
            invoice=invoice,
            payment_date=payment_date,
            payment_method=payment_method,
            amount=amount,
            bank_account=bank_account,
            authorised_by=authorised_by,
        )
        ap_account = get_or_create_account("2100", "Accounts Payable", "LIABILITY")
        bank_ledger = bank_account.ledger_account if bank_account and bank_account.ledger_account else None
        cash_account = bank_ledger or get_or_create_account("1010", "Cash at Bank", "ASSET")
        post_procurement_journal(
            payment_date,
            payment.payment_voucher_number,
            f"Supplier payment {invoice.invoice_number}",
            ap_account,
            cash_account,
            amount,
            user=authorised_by,
        )
        invoice.status = "PAID"
        invoice.save(update_fields=["status"])
        log_procurement_action(
            "Supplier payment",
            reference_number=payment.payment_voucher_number,
            user=authorised_by,
            new_value={"supplier": invoice.supplier.supplier_code, "amount": str(amount)},
        )
        return payment
