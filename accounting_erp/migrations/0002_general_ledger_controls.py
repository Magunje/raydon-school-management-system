# Generated manually for Accounting Module 3.18 implementation.

from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting_erp", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="financialyear",
            name="status",
            field=models.CharField(
                choices=[
                    ("OPEN", "Open"),
                    ("CLOSED", "Closed"),
                    ("LOCKED", "Locked"),
                    ("REOPENED", "Reopened"),
                ],
                default="OPEN",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="accountportal",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="accountportal",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accounts_created", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="accountportal",
            name="currency",
            field=models.CharField(default="USD", max_length=10),
        ),
        migrations.AddField(
            model_name="accountportal",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accountportal",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="accountportal",
            name="parent_account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="child_accounts", to="accounting_erp.accountportal"),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="posted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="prepared_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="prepared_journals", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="reference_number",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="reviewed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_journals", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="reversed_entry",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reversal_entries", to="accounting_erp.journalentry"),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="source_module",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AlterField(
            model_name="journalentry",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("SUBMITTED", "Submitted"),
                    ("APPROVED", "Approved"),
                    ("POSTED", "Posted"),
                    ("REJECTED", "Rejected"),
                    ("REVERSED", "Reversed"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="journalline",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bankaccount",
            name="account_name",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name="bankaccount",
            name="ledger_account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bank_accounts", to="accounting_erp.accountportal"),
        ),
        migrations.AddField(
            model_name="bankreconciliation",
            name="difference",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
        migrations.AlterField(
            model_name="bankreconciliation",
            name="status",
            field=models.CharField(
                choices=[
                    ("UNRECONCILED", "Unreconciled"),
                    ("MATCHED", "Matched"),
                    ("PARTIALLY_MATCHED", "Partially Matched"),
                    ("DISPUTED", "Disputed"),
                    ("RECONCILED", "Reconciled"),
                    ("DRAFT", "Draft"),
                    ("APPROVED", "Approved"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="schoolbudget",
            name="account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounting_erp.accountportal"),
        ),
        migrations.AddField(
            model_name="schoolbudget",
            name="accounting_period",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name="schoolbudget",
            name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="budgets_approved", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="schoolbudget",
            name="revised_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="schoolbudget",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("SUBMITTED", "Submitted"),
                    ("APPROVED", "Approved"),
                    ("REVISED", "Revised"),
                    ("CLOSED", "Closed"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="GeneralLedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_date", models.DateField()),
                ("posting_date", models.DateField()),
                ("debit_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("credit_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("currency", models.CharField(default="USD", max_length=10)),
                ("exchange_rate", models.DecimalField(decimal_places=4, default=Decimal("1.0000"), max_digits=12)),
                ("source_module", models.CharField(blank=True, max_length=80, null=True)),
                ("reference_number", models.CharField(blank=True, max_length=120, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="accounting_erp.accountportal")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ledger_entries_approved", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ledger_entries_created", to=settings.AUTH_USER_MODEL)),
                ("journal_line", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entry", to="accounting_erp.journalline")),
            ],
            options={
                "db_table": "accounting_general_ledger",
                "ordering": ["-posting_date", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AccountingAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(default="Accounting", max_length=80)),
                ("action", models.CharField(max_length=120)),
                ("transaction_number", models.CharField(blank=True, max_length=120, null=True)),
                ("previous_value", models.JSONField(blank=True, null=True)),
                ("new_value", models.JSONField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("device_identifier", models.CharField(blank=True, max_length=120, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "accounting_audit_logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AccountingPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("CLOSED", "Closed"), ("LOCKED", "Locked"), ("REOPENED", "Reopened")], default="OPEN", max_length=20)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accounting_periods_closed", to=settings.AUTH_USER_MODEL)),
                ("financial_year", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="periods", to="accounting_erp.financialyear")),
            ],
            options={
                "db_table": "accounting_periods",
                "unique_together": {("financial_year", "name")},
            },
        ),
        migrations.CreateModel(
            name="ApprovalWorkflow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_type", models.CharField(max_length=80)),
                ("target_id", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("REQUESTED", "Requested"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="REQUESTED", max_length=20)),
                ("comments", models.TextField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("approver", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accounting_approvals", to=settings.AUTH_USER_MODEL)),
                ("requester", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accounting_approval_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "accounting_approval_workflows",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="NumberSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("prefix", models.CharField(max_length=20)),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
            options={"db_table": "accounting_number_sequences"},
        ),
        migrations.CreateModel(
            name="OfflineAccountingQueue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation", models.CharField(max_length=80)),
                ("payload", models.JSONField()),
                ("device_identifier", models.CharField(blank=True, max_length=120, null=True)),
                ("local_timestamp", models.DateTimeField()),
                ("server_timestamp", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("QUEUED", "Queued"), ("VALIDATED", "Validated"), ("POSTED", "Posted"), ("CONFLICT", "Conflict"), ("FAILED", "Failed")], default="QUEUED", max_length=20)),
                ("validation_errors", models.JSONField(blank=True, null=True)),
            ],
            options={
                "db_table": "accounting_offline_queue",
                "ordering": ["server_timestamp"],
            },
        ),
        migrations.CreateModel(
            name="BankStatementTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_date", models.DateField()),
                ("description", models.TextField(blank=True, null=True)),
                ("reference_number", models.CharField(blank=True, max_length=120, null=True)),
                ("deposit_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("withdrawal_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("match_status", models.CharField(choices=[("UNRECONCILED", "Unreconciled"), ("MATCHED", "Matched"), ("PARTIALLY_MATCHED", "Partially Matched"), ("DISPUTED", "Disputed")], default="UNRECONCILED", max_length=30)),
                ("bank_account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="statement_transactions", to="accounting_erp.bankaccount")),
                ("matched_ledger_entry", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="matched_bank_statement_transactions", to="accounting_erp.generalledgerentry")),
            ],
            options={
                "db_table": "accounting_bank_statement_transactions",
                "ordering": ["-transaction_date"],
            },
        ),
    ]
