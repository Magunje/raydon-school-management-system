# Generated manually for Finance Module 3.17 implementation.

from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fees_management", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="feecategory",
            name="ledger_account_code",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="financesetting",
            name="payment_allocation_policy",
            field=models.CharField(
                choices=[
                    ("OLDEST_ARREARS_FIRST", "Oldest arrears first"),
                    ("CURRENT_CHARGES_FIRST", "Current charges first"),
                ],
                default="OLDEST_ARREARS_FIRST",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="financesetting",
            name="receipt_stamp_label",
            field=models.CharField(default="Electronic School Stamp", max_length=120),
        ),
        migrations.AddField(
            model_name="studentfeeaccount",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="studentfeeaccount",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="generated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fee_invoices_generated",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("ISSUED", "Issued"),
                    ("PART_PAID", "Part Paid"),
                    ("PAID", "Paid"),
                    ("VOID", "Void"),
                ],
                default="ISSUED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="payment",
            name="reversal_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="reversed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="reversed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fee_payments_reversed",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("CASH", "Cash"),
                    ("BANK_TRANSFER", "Bank Transfer"),
                    ("POS", "POS"),
                    ("MOBILE_MONEY", "Mobile Money"),
                    ("ONLINE", "Online Payment"),
                    ("OTHER", "Other"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="paymentplan",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_plans_approved",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="paymentplan",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="paymentplan",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_plans_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="sponsorship",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sponsorship",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sponsorships_approved",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="sponsorship",
            name="is_approved",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="sponsorship",
            name="supporting_document",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="finance/sponsorships/",
            ),
        ),
        migrations.AddField(
            model_name="discount",
            name="is_approved",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="discount",
            name="original_fee_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="reconciliationrecord",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reconciliationrecord",
            name="matched_transactions",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="reconciliationrecord",
            name="overpayments",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="reconciliationrecord",
            name="underpayments",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="reconciliationrecord",
            name="unmatched_transactions",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reconciliationrecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("RECONCILED", "Reconciled"),
                    ("DISCREPANCY", "Discrepancy"),
                    ("CLOSED", "Closed"),
                ],
                default="RECONCILED",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="FinanceAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(default="Fees Management", max_length=80)),
                ("action", models.CharField(max_length=120)),
                ("transaction_number", models.CharField(blank=True, max_length=120, null=True)),
                ("school_tenant", models.CharField(blank=True, max_length=255, null=True)),
                ("previous_value", models.JSONField(blank=True, null=True)),
                ("new_value", models.JSONField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "fees_mgt_audit_logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="OfflineFinanceQueue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation", models.CharField(max_length=80)),
                ("payload", models.JSONField()),
                ("device_identifier", models.CharField(blank=True, max_length=120, null=True)),
                ("local_timestamp", models.DateTimeField()),
                ("server_timestamp", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("QUEUED", "Queued"), ("SYNCED", "Synced"), ("CONFLICT", "Conflict"), ("FAILED", "Failed")], default="QUEUED", max_length=20)),
                ("conflict_reason", models.TextField(blank=True, null=True)),
            ],
            options={
                "db_table": "fees_mgt_offline_queue",
                "ordering": ["server_timestamp"],
            },
        ),
        migrations.CreateModel(
            name="Receipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("receipt_number", models.CharField(max_length=50)),
                ("version", models.PositiveIntegerField(default=1)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("reprinted_at", models.DateTimeField(blank=True, null=True)),
                ("qr_code_payload", models.TextField()),
                ("electronic_stamp", models.CharField(default="Electronic School Stamp", max_length=120)),
                ("pdf_file", models.FileField(blank=True, null=True, upload_to="finance/receipts/")),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receipts", to="fees_management.payment")),
                ("reprinted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="fee_receipts_reprinted", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "fees_mgt_receipts",
                "ordering": ["-issued_at"],
                "unique_together": {("receipt_number", "version")},
            },
        ),
        migrations.CreateModel(
            name="PaymentAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("allocation_type", models.CharField(choices=[("ARREARS", "Arrears"), ("CURRENT_CHARGES", "Current Charges"), ("CREDIT", "Credit Balance")], max_length=30)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("allocated_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payment_allocations", to="fees_management.invoice")),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="fees_management.payment")),
                ("student_account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_allocations", to="fees_management.studentfeeaccount")),
            ],
            options={"db_table": "fees_mgt_payment_allocations"},
        ),
        migrations.CreateModel(
            name="ReconciliationItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_reference", models.CharField(blank=True, max_length=150, null=True)),
                ("expected_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("actual_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("status", models.CharField(choices=[("MATCHED", "Matched"), ("UNMATCHED", "Unmatched"), ("OVERPAYMENT", "Overpayment"), ("UNDERPAYMENT", "Underpayment"), ("REVERSAL", "Reversal")], max_length=30)),
                ("notes", models.TextField(blank=True, null=True)),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reconciliation_items", to="fees_management.payment")),
                ("reconciliation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="fees_management.reconciliationrecord")),
            ],
            options={"db_table": "fees_mgt_reconciliation_items"},
        ),
    ]
