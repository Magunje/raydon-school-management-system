from django.test import TestCase
from django.db import connection
from django.contrib.auth import get_user_model
from decimal import Decimal
import datetime

from human_resources.models import EmployeeProfile
from assets.models import (
    AssetCategory,
    Asset,
    AssetAssignment,
    AssetTransfer,
    AssetMaintenance,
    AssetDepreciationLog,
    AssetDisposal,
    AssetVerification
)
from saas_tenant_management.schema import ensure_schema_with_cursor

User = get_user_model()


class AssetManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Build required SQLite schema in test DB
        with connection.cursor() as cursor:
            ensure_schema_with_cursor(cursor, vendor="sqlite")
            
        # Register Category
        cls.category = AssetCategory.objects.create(
            name="ICT Equipment",
            description="School computers, laptops and servers"
        )
        
        # Register custodian Employee
        cls.employee = EmployeeProfile.objects.create(
            employee_number="EMP-ASSET-01",
            first_name="Alice",
            surname="Admin",
            gender="Female",
            date_of_birth="1988-10-10",
            national_id="NID-ASSET-01",
            phone_number="0771122334",
            email="alice@school.com",
            employment_date="2021-06-01",
            department="IT Department",
            position="IT Administrator",
            employee_category="ADMIN",
            next_of_kin="Bob Admin",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="0772244668",
            status="ACTIVE",
        )
        
    def test_asset_registration_and_custody(self):
        # Register a Laptop
        asset = Asset.objects.create(
            asset_code="AST-ICT-001",
            asset_name="Staff Laptop Dell",
            category=self.category,
            acquisition_date=datetime.date.today(),
            purchase_price=Decimal("800.00"),
            current_value=Decimal("800.00"),
            useful_life=5,
            depreciation_method="Straight-Line",
            status="Active",
        )
        self.assertEqual(asset.asset_code, "AST-ICT-001")
        self.assertEqual(asset.current_value, Decimal("800.00"))
        
        # Assign Custody
        assign = AssetAssignment.objects.create(
            asset=asset,
            assigned_employee=self.employee,
            assigned_location="Admin Room 2",
            date_assigned=datetime.date.today(),
            condition="Good",
        )
        self.assertEqual(assign.asset, asset)
        self.assertEqual(assign.assigned_employee, self.employee)
        
    def test_asset_transfers_and_audit(self):
        asset = Asset.objects.create(
            asset_code="AST-ICT-002",
            asset_name="Server Router Switch",
            category=self.category,
            acquisition_date=datetime.date.today(),
            purchase_price=Decimal("450.00"),
            current_value=Decimal("450.00"),
            location_name="Server Room A",
            status="Active",
        )
        
        # Record location transfer
        transfer = AssetTransfer.objects.create(
            asset=asset,
            previous_location="Server Room A",
            new_location="Server Room B",
            transfer_date=datetime.date.today(),
            reason="Expansion upgrades",
        )
        self.assertEqual(transfer.previous_location, "Server Room A")
        self.assertEqual(transfer.new_location, "Server Room B")
        
    def test_straight_line_depreciation(self):
        # Cost: 1000, Salvage: 200, Useful Life: 5 Years -> Depr per year = (1000 - 200) / 5 = 160
        asset = Asset.objects.create(
            asset_code="AST-ICT-003",
            asset_name="Projector Class 1",
            category=self.category,
            acquisition_date=datetime.date.today(),
            purchase_price=Decimal("1000.00"),
            current_value=Decimal("1000.00"),
            salvage_value=Decimal("200.00"),
            useful_life=5,
            depreciation_method="Straight-Line",
            status="Active",
        )
        
        # Run Depreciation manually (representing 1 year cycle)
        depr_amt = (asset.purchase_price - asset.salvage_value) / asset.useful_life
        asset.current_value -= depr_amt
        asset.save()
        
        AssetDepreciationLog.objects.create(
            asset=asset,
            depreciation_date=datetime.date.today(),
            amount=depr_amt,
            book_value=asset.current_value,
        )
        
        asset.refresh_from_db()
        self.assertEqual(asset.current_value, Decimal("840.00")) # 1000 - 160
        self.assertEqual(asset.depreciation_logs.count(), 1)
        
    def test_reducing_balance_depreciation(self):
        # Cost: 1200, Rate: 10% -> Depr per run = 1200 * 0.10 = 120
        asset = Asset.objects.create(
            asset_code="AST-ICT-004",
            asset_name="Lab Desktop Unit 1",
            category=self.category,
            acquisition_date=datetime.date.today(),
            purchase_price=Decimal("1200.00"),
            current_value=Decimal("1200.00"),
            depreciation_rate=Decimal("10.00"),
            depreciation_method="Reducing Balance",
            status="Active",
        )
        
        depr_amt = asset.current_value * (asset.depreciation_rate / Decimal("100.00"))
        asset.current_value -= depr_amt
        asset.save()
        
        asset.refresh_from_db()
        self.assertEqual(asset.current_value, Decimal("1080.00")) # 1200 - 120
        
    def test_asset_disposal(self):
        asset = Asset.objects.create(
            asset_code="AST-ICT-005",
            asset_name="Broken Monitor",
            category=self.category,
            acquisition_date=datetime.date.today(),
            purchase_price=Decimal("200.00"),
            current_value=Decimal("50.00"),
            status="Damaged",
        )
        
        # Dispose scrap
        disp = AssetDisposal.objects.create(
            asset=asset,
            disposal_date=datetime.date.today(),
            method="Scrap",
            value=Decimal("10.00"),
            reason="Damaged beyond repair",
        )
        asset.status = "Disposed"
        asset.current_value = Decimal("0.00")
        asset.save()
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, "Disposed")
        self.assertEqual(asset.current_value, Decimal("0.00"))
