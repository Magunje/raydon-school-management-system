from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting_erp.models import GeneralLedgerEntry
from inventory_management.models import (
    InventoryAuditLog,
    InventoryCategory,
    InventoryItem,
    ReorderAlert,
    Store,
    StoreStock,
)
from inventory_management.services import (
    adjust_stock,
    generate_reorder_alerts,
    issue_stock,
    perform_stock_count,
    receive_stock,
    stock_valuation_report,
    transfer_stock,
)


User = get_user_model()


class InventoryManagementWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="storekeeper", password="password123")
        self.category = InventoryCategory.objects.create(name="Stationery")
        self.main_store = Store.objects.create(store_code="MAIN", store_name="Main Store", storekeeper=self.user)
        self.lab_store = Store.objects.create(store_code="LAB", store_name="Science Laboratory Store")
        self.item = InventoryItem.objects.create(
            item_code="PEN-BLUE",
            item_name="Blue Pens",
            category=self.category,
            unit_of_measure="Box",
            minimum_stock_level=Decimal("5.00"),
            maximum_stock_level=Decimal("100.00"),
            reorder_level=Decimal("10.00"),
            purchase_price=Decimal("2.00"),
            default_store=self.main_store,
            barcode="BAR-PEN-BLUE",
            qr_code="QR-PEN-BLUE",
        )

    def test_stock_receipt_issue_transfer_reorder_and_accounting(self):
        receipt = receive_stock(
            item=self.item,
            store=self.main_store,
            quantity=Decimal("20.00"),
            unit_cost=Decimal("2.00"),
            reference_number="GRN-TEST-1",
            user=self.user,
            batch_number="BATCH-1",
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_quantity, Decimal("20.00"))
        self.assertEqual(receipt.total_cost, Decimal("40.00"))
        self.assertTrue(GeneralLedgerEntry.objects.filter(source_module="Inventory").exists())

        issue_stock(
            item=self.item,
            store=self.main_store,
            quantity=Decimal("8.00"),
            department="Academics",
            issued_by=self.user,
            received_by="HOD Academics",
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_quantity, Decimal("12.00"))

        transfer_stock(
            item=self.item,
            source_store=self.main_store,
            destination_store=self.lab_store,
            quantity=Decimal("4.00"),
            approved_by=self.user,
        )
        self.assertEqual(
            StoreStock.objects.get(store=self.lab_store, item=self.item).quantity,
            Decimal("4.00"),
        )

        adjust_stock(
            item=self.item,
            store=self.main_store,
            quantity_delta=Decimal("-3.00"),
            adjustment_type="DAMAGED",
            reason="Damaged during handling",
            approved_by=self.user,
        )
        alerts = generate_reorder_alerts()
        self.assertTrue(any(alert.item == self.item for alert in alerts))
        self.assertTrue(ReorderAlert.objects.filter(item=self.item, status="OPEN").exists())

        report = stock_valuation_report()
        self.assertGreater(report["total_value"], Decimal("0.00"))
        self.assertTrue(InventoryAuditLog.objects.filter(action="Stock adjustment").exists())

    def test_negative_stock_is_blocked_and_stock_count_records_variance(self):
        receive_stock(
            item=self.item,
            store=self.main_store,
            quantity=Decimal("3.00"),
            unit_cost=Decimal("2.00"),
            reference_number="GRN-TEST-2",
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            issue_stock(
                item=self.item,
                store=self.main_store,
                quantity=Decimal("5.00"),
                department="Sports",
                issued_by=self.user,
            )

        stock_count = perform_stock_count(
            store=self.main_store,
            count_type="SPOT",
            counted_quantities={self.item: Decimal("2.00")},
            counted_by=self.user,
        )
        line = stock_count.lines.get(item=self.item)
        self.assertEqual(line.variance, Decimal("-1.00"))
        self.assertTrue(line.adjustment_recommended)
