from decimal import Decimal
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting_erp.models import GeneralLedgerEntry, SchoolBudget, FinancialYear
from inventory_management.models import InventoryCategory, InventoryItem, Store
from procurement.models import ProcurementAuditLog, Supplier, SupplierCategory
from procurement.services import (
    add_supplier_quotation,
    approve_requisition,
    create_requisition,
    create_supplier_invoice,
    generate_purchase_order,
    pay_supplier_invoice,
    receive_goods,
    select_best_quotation,
)


User = get_user_model()


class ProcurementWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="procurement", password="password123")
        self.admin = User.objects.create_superuser(username="head", password="password123")
        self.finance = User.objects.create_user(username="finance", password="password123")
        self.fy = FinancialYear.objects.create(
            name="FY 2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            status="OPEN",
        )
        SchoolBudget.objects.create(
            name="Academics Budget",
            financial_year=self.fy,
            department="Academics",
            budget_amount=Decimal("1000.00"),
            actual_expenditure=Decimal("200.00"),
            status="APPROVED",
        )
        self.supplier_category = SupplierCategory.objects.create(name="Stationery")
        self.supplier = Supplier.objects.create(
            supplier_code="SUP-001",
            supplier_name="ABC Stationers",
            category=self.supplier_category,
            preferred=True,
            performance_score=Decimal("95.00"),
        )
        self.store = Store.objects.create(store_code="MAIN", store_name="Main Store")
        self.inventory_category = InventoryCategory.objects.create(name="Stationery")
        self.item = InventoryItem.objects.create(
            item_code="EXB-001",
            item_name="Exercise Book",
            category=self.inventory_category,
            purchase_price=Decimal("1.50"),
            reorder_level=Decimal("20.00"),
            maximum_stock_level=Decimal("500.00"),
        )

    def test_requisition_to_payment_updates_inventory_and_accounting(self):
        requisition = create_requisition(
            department="Academics",
            requested_by=self.user,
            item_description="Exercise Book",
            quantity=Decimal("100.00"),
            estimated_cost=Decimal("1.50"),
            priority="NORMAL",
            justification="Books for Form 1 classes",
            required_date=datetime.date(2026, 2, 1),
        )
        approve_requisition(requisition, "DEPARTMENT_HEAD", self.admin)
        approve_requisition(requisition, "FINANCE_VERIFICATION", self.finance)
        approve_requisition(requisition, "SCHOOL_ADMIN", self.admin)

        add_supplier_quotation(requisition, self.supplier, Decimal("1.40"), delivery_period="3 days")
        quotation = select_best_quotation(requisition)
        self.assertEqual(quotation.supplier, self.supplier)

        po = generate_purchase_order(
            requisition,
            supplier=self.supplier,
            delivery_address="Raydon High School",
            delivery_date=datetime.date(2026, 2, 1),
            approved_by=self.admin,
            inventory_item=self.item,
        )
        receipt = receive_goods(po, self.store, received_by=self.user)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_quantity, Decimal("100.00"))

        invoice = create_supplier_invoice(
            supplier=self.supplier,
            purchase_order=po,
            goods_receipt=receipt,
            invoice_number="INV-ABC-001",
            invoice_date=datetime.date(2026, 2, 2),
            due_date=datetime.date(2026, 2, 15),
            amount=Decimal("140.00"),
        )
        self.assertEqual(invoice.status, "MATCHED")

        payment = pay_supplier_invoice(
            invoice,
            amount=Decimal("140.00"),
            payment_method="BANK_TRANSFER",
            payment_date=datetime.date(2026, 2, 3),
            authorised_by=self.finance,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "PAID")
        self.assertTrue(payment.payment_voucher_number.startswith("PV-"))
        self.assertTrue(GeneralLedgerEntry.objects.filter(source_module="Procurement").exists())
        self.assertTrue(ProcurementAuditLog.objects.filter(action="Supplier payment").exists())

    def test_budget_override_and_three_way_match_are_enforced(self):
        requisition = create_requisition(
            department="Academics",
            requested_by=self.user,
            item_description="Projectors",
            quantity=Decimal("10.00"),
            estimated_cost=Decimal("200.00"),
            priority="HIGH",
            justification="ICT lab expansion",
            required_date=datetime.date(2026, 3, 1),
        )
        with self.assertRaises(ValidationError):
            approve_requisition(requisition, "FINANCE_VERIFICATION", self.finance)

        approve_requisition(requisition, "FINANCE_VERIFICATION", self.finance, allow_budget_override=True)
        approve_requisition(requisition, "SCHOOL_ADMIN", self.admin, allow_budget_override=True)
        add_supplier_quotation(requisition, self.supplier, Decimal("200.00"))
        select_best_quotation(requisition)
        po = generate_purchase_order(
            requisition,
            supplier=self.supplier,
            delivery_address="Raydon High School",
            delivery_date=datetime.date(2026, 3, 1),
            approved_by=self.admin,
            inventory_item=self.item,
        )
        receipt = receive_goods(po, self.store, received_by=self.user)
        with self.assertRaises(ValidationError):
            create_supplier_invoice(
                supplier=self.supplier,
                purchase_order=po,
                goods_receipt=receipt,
                invoice_number="INV-ABC-OVER",
                invoice_date=datetime.date(2026, 3, 2),
                due_date=datetime.date(2026, 3, 15),
                amount=Decimal("2500.00"),
            )
