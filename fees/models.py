from django.db import models


class FeeStructure(models.Model):
    fee_id = models.AutoField(primary_key=True)
    grade = models.CharField(max_length=80)
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    amount_required = models.DecimalField(max_digits=12, decimal_places=2)
    grade_id = models.IntegerField(blank=True, null=True)
    payment_deadline = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "fees_structure"

    def __str__(self):
        return f"{self.grade} {self.term} {self.year}"


class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    pupil = models.ForeignKey('students.Pupil', on_delete=models.CASCADE, db_column='pupil_id')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.TextField()
    payment_method = models.CharField(max_length=80)
    receipt_no = models.CharField(max_length=80, unique=True)
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    fee_id = models.IntegerField(blank=True, null=True)
    recorded_by = models.IntegerField(blank=True, null=True)
    master_receipt_id = models.IntegerField(blank=True, null=True)
    reference_no = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "payments"

    def __str__(self):
        return self.receipt_no


class PaymentAllocation(models.Model):
    allocation_id = models.AutoField(primary_key=True)
    payment_id = models.IntegerField()
    pupil_id = models.IntegerField()
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    amount_allocated = models.DecimalField(max_digits=12, decimal_places=2)
    fee_id = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = "payment_allocations"


class Receipt(models.Model):
    receipt_id = models.AutoField(primary_key=True)
    payment_id = models.IntegerField(unique=True)
    receipt_no = models.CharField(max_length=80, unique=True)
    issued_date = models.TextField()

    class Meta:
        managed = False
        db_table = "receipts"

    def __str__(self):
        return self.receipt_no


class MasterReceipt(models.Model):
    master_receipt_id = models.AutoField(primary_key=True)
    master_receipt_no = models.CharField(max_length=80, unique=True)
    batch_date = models.TextField()
    generated_at = models.TextField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    receipt_count = models.IntegerField()
    notes = models.TextField(blank=True, null=True)
    generated_by = models.IntegerField(blank=True, null=True)
    receipt_type = models.CharField(max_length=80, default="Fees")

    class Meta:
        managed = False
        db_table = "master_receipts"


class Expense(models.Model):
    expense_id = models.AutoField(primary_key=True)
    expense_date = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=120)
    description = models.TextField()
    payment_method = models.CharField(max_length=80)
    reference_no = models.CharField(max_length=120, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = "expenses"


class OnlinePaymentRequest(models.Model):
    request_id = models.AutoField(primary_key=True)
    pupil_id = models.IntegerField()
    reference_no = models.CharField(max_length=120, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=80)
    phone_number = models.CharField(max_length=40, blank=True, null=True)
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    status = models.CharField(max_length=40, default="Pending")
    payment_id = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()
    updated_at = models.TextField()
    bank_reference_no = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "online_payment_requests"


class TermBill(models.Model):
    bill_id = models.AutoField(primary_key=True)
    pupil_id = models.IntegerField()
    fee_id = models.IntegerField(blank=True, null=True)
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    amount_billed = models.DecimalField(max_digits=12, decimal_places=2)
    billed_on = models.TextField()
    due_date = models.TextField()
    status = models.CharField(max_length=40, default='Billed')

    class Meta:
        managed = False
        db_table = 'term_bills'


# Alias for compatibility with tests
FeesStructure = FeeStructure


class BalanceAdjustment(models.Model):
    adjustment_id = models.AutoField(primary_key=True)
    pupil_id = models.IntegerField()
    term = models.CharField(max_length=40)
    year = models.IntegerField()
    entry_type = models.CharField(max_length=80, default="Balance B/D")
    source_term = models.CharField(max_length=40, blank=True, null=True)
    source_year = models.IntegerField(blank=True, null=True)
    entry_date = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = "balance_adjustments"

