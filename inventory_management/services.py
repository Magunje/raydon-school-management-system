from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from accounting_erp.models import AccountPortal, FinancialYear, JournalEntry, JournalLine
from accounting_erp.services import post_journal_entry
from inventory_management.models import (
    InventoryAuditLog,
    InventoryItem,
    ReorderAlert,
    StockAdjustment,
    StockBatch,
    StockCount,
    StockCountLine,
    StockMovement,
    StockTransfer,
    Store,
    StoreStock,
)


def next_inventory_number(prefix, model, field_name):
    count = model.objects.count() + 1
    return f"{prefix}-{count:05d}"


def log_inventory_action(action, reference_number=None, user=None, new_value=None, reason=None):
    return InventoryAuditLog.objects.create(
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


def post_inventory_journal(txn_date, reference_number, description, debit_account, credit_account, amount, user=None):
    if amount <= Decimal("0.00"):
        return None
    fy = get_open_financial_year(txn_date)
    entry = JournalEntry.objects.create(
        journal_number=f"JV-INV-{reference_number}",
        entry_date=txn_date,
        description=description,
        financial_year=fy,
        approval_status="DRAFT",
        source_module="Inventory",
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


def refresh_item_quantity(item):
    total = sum(stock.quantity for stock in item.store_stock.all())
    item.current_quantity = total
    item.save(update_fields=["current_quantity"])
    return item.current_quantity


def receive_stock(
    item,
    store,
    quantity,
    unit_cost,
    reference_number,
    user=None,
    supplier=None,
    batch_number=None,
    serial_number=None,
    expiry_date=None,
    post_accounting=True,
):
    if quantity <= Decimal("0.00"):
        raise ValidationError("Received quantity must be greater than zero.")

    with transaction.atomic():
        stock, _ = StoreStock.objects.select_for_update().get_or_create(
            store=store, item=item, defaults={"quantity": Decimal("0.00")}
        )
        stock.quantity += quantity
        stock.full_clean()
        stock.save()
        refresh_item_quantity(item)

        movement = StockMovement.objects.create(
            movement_number=next_inventory_number("SM-REC", StockMovement, "movement_number"),
            movement_type="RECEIPT",
            item=item,
            store=store,
            quantity=quantity,
            unit_cost=unit_cost,
            reference_number=reference_number,
            issued_by=user,
            received_by=str(supplier) if supplier else None,
        )
        StockBatch.objects.create(
            item=item,
            store=store,
            batch_number=batch_number,
            serial_number=serial_number,
            expiry_date=expiry_date,
            quantity=quantity,
            unit_cost=unit_cost,
        )

        if post_accounting:
            inventory_account = get_or_create_account("1200", "Inventory", "ASSET")
            ap_account = get_or_create_account("2100", "Accounts Payable", "LIABILITY")
            post_inventory_journal(
                movement.created_at.date(),
                movement.movement_number,
                f"Inventory goods received {reference_number}",
                inventory_account,
                ap_account,
                movement.total_cost,
                user=user,
            )

        log_inventory_action(
            "Stock receipt",
            reference_number=movement.movement_number,
            user=user,
            new_value={"item": item.item_code, "quantity": str(quantity), "store": store.store_code},
        )
        return movement


def issue_stock(item, store, quantity, department, issued_by=None, received_by=None, reference_number=None):
    if quantity <= Decimal("0.00"):
        raise ValidationError("Issued quantity must be greater than zero.")

    with transaction.atomic():
        stock = StoreStock.objects.select_for_update().get(store=store, item=item)
        if stock.quantity < quantity:
            raise ValidationError("Negative stock is prohibited.")
        stock.quantity -= quantity
        stock.full_clean()
        stock.save()
        refresh_item_quantity(item)

        unit_cost = item.purchase_price
        movement = StockMovement.objects.create(
            movement_number=next_inventory_number("SM-ISS", StockMovement, "movement_number"),
            movement_type="ISSUE",
            item=item,
            store=store,
            quantity=quantity,
            unit_cost=unit_cost,
            reference_number=reference_number,
            department=department,
            issued_by=issued_by,
            received_by=received_by,
        )

        expense_account = get_or_create_account("5000", "Inventory Consumption Expense", "EXPENSE")
        inventory_account = get_or_create_account("1200", "Inventory", "ASSET")
        post_inventory_journal(
            movement.created_at.date(),
            movement.movement_number,
            f"Stock issued to {department}",
            expense_account,
            inventory_account,
            movement.total_cost,
            user=issued_by,
        )

        log_inventory_action(
            "Stock issue",
            reference_number=movement.movement_number,
            user=issued_by,
            new_value={"item": item.item_code, "quantity": str(quantity), "department": department},
        )
        return movement


def transfer_stock(item, source_store, destination_store, quantity, approved_by=None):
    if source_store == destination_store:
        raise ValidationError("Source and destination stores must be different.")

    with transaction.atomic():
        source_stock = StoreStock.objects.select_for_update().get(store=source_store, item=item)
        if source_stock.quantity < quantity:
            raise ValidationError("Negative stock is prohibited.")
        destination_stock, _ = StoreStock.objects.select_for_update().get_or_create(
            store=destination_store, item=item, defaults={"quantity": Decimal("0.00")}
        )
        source_stock.quantity -= quantity
        destination_stock.quantity += quantity
        source_stock.full_clean()
        destination_stock.full_clean()
        source_stock.save()
        destination_stock.save()
        refresh_item_quantity(item)

        transfer = StockTransfer.objects.create(
            transfer_number=next_inventory_number("TRF", StockTransfer, "transfer_number"),
            source_store=source_store,
            destination_store=destination_store,
            item=item,
            quantity=quantity,
            approved_by=approved_by,
        )
        StockMovement.objects.create(
            movement_number=f"{transfer.transfer_number}-OUT",
            movement_type="TRANSFER_OUT",
            item=item,
            store=source_store,
            quantity=quantity,
            unit_cost=item.purchase_price,
            reference_number=transfer.transfer_number,
            issued_by=approved_by,
        )
        StockMovement.objects.create(
            movement_number=f"{transfer.transfer_number}-IN",
            movement_type="TRANSFER_IN",
            item=item,
            store=destination_store,
            quantity=quantity,
            unit_cost=item.purchase_price,
            reference_number=transfer.transfer_number,
            issued_by=approved_by,
        )
        log_inventory_action(
            "Stock transfer",
            reference_number=transfer.transfer_number,
            user=approved_by,
            new_value={
                "item": item.item_code,
                "quantity": str(quantity),
                "source": source_store.store_code,
                "destination": destination_store.store_code,
            },
        )
        return transfer


def adjust_stock(item, store, quantity_delta, adjustment_type, reason, approved_by, supporting_notes=None):
    if not reason:
        raise ValidationError("Inventory adjustments require a reason.")

    with transaction.atomic():
        stock, _ = StoreStock.objects.select_for_update().get_or_create(
            store=store, item=item, defaults={"quantity": Decimal("0.00")}
        )
        new_quantity = stock.quantity + quantity_delta
        if new_quantity < Decimal("0.00"):
            raise ValidationError("Negative stock is prohibited.")
        stock.quantity = new_quantity
        stock.full_clean()
        stock.save()
        refresh_item_quantity(item)

        adjustment = StockAdjustment.objects.create(
            adjustment_number=next_inventory_number("ADJ", StockAdjustment, "adjustment_number"),
            item=item,
            store=store,
            adjustment_type=adjustment_type,
            quantity_delta=quantity_delta,
            reason=reason,
            supporting_notes=supporting_notes,
            approved_by=approved_by,
        )
        StockMovement.objects.create(
            movement_number=f"SM-{adjustment.adjustment_number}",
            movement_type="WRITE_OFF" if quantity_delta < 0 else "ADJUSTMENT",
            item=item,
            store=store,
            quantity=abs(quantity_delta),
            unit_cost=item.purchase_price,
            reference_number=adjustment.adjustment_number,
            issued_by=approved_by,
            notes=reason,
        )
        log_inventory_action(
            "Stock adjustment",
            reference_number=adjustment.adjustment_number,
            user=approved_by,
            new_value={"item": item.item_code, "quantity_delta": str(quantity_delta)},
            reason=reason,
        )
        return adjustment


def perform_stock_count(store, count_type, counted_quantities, counted_by=None):
    count = StockCount.objects.create(
        count_number=next_inventory_number("CNT", StockCount, "count_number"),
        store=store,
        count_type=count_type,
        counted_by=counted_by,
    )
    for item, counted_quantity in counted_quantities.items():
        stock, _ = StoreStock.objects.get_or_create(
            store=store, item=item, defaults={"quantity": Decimal("0.00")}
        )
        StockCountLine.objects.create(
            stock_count=count,
            item=item,
            system_quantity=stock.quantity,
            counted_quantity=counted_quantity,
        )
    log_inventory_action("Stock count", reference_number=count.count_number, user=counted_by)
    return count


def generate_reorder_alerts():
    alerts = []
    for item in InventoryItem.objects.filter(status="ACTIVE"):
        for stock in item.store_stock.select_related("store"):
            if stock.quantity <= item.reorder_level:
                recommendation = max(item.maximum_stock_level - stock.quantity, Decimal("0.00"))
                alert, _ = ReorderAlert.objects.update_or_create(
                    item=item,
                    store=stock.store,
                    status="OPEN",
                    defaults={
                        "current_quantity": stock.quantity,
                        "reorder_level": item.reorder_level,
                        "purchase_recommendation": recommendation,
                    },
                )
                alerts.append(alert)
    return alerts


def stock_valuation_report():
    rows = []
    total_value = Decimal("0.00")
    for item in InventoryItem.objects.select_related("category").all():
        unit_cost = item.purchase_price
        value = (item.current_quantity * unit_cost).quantize(Decimal("0.01"))
        rows.append(
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "quantity_on_hand": item.current_quantity,
                "unit_cost": unit_cost,
                "total_value": value,
                "valuation_method": item.valuation_method,
            }
        )
        total_value += value
    return {"rows": rows, "total_value": total_value}
