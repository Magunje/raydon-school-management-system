from django.contrib import admin

from .models import (
    BankTransferFile,
    BankTransferLine,
    EmployeePayrollProfile,
    OvertimeRecord,
    PayrollAdjustment,
    PayrollApproval,
    PayrollAccountingPosting,
    PayrollAuditLog,
    PayrollComponentDefinition,
    PayrollExportLog,
    PayrollFormula,
    PayrollItem,
    PayrollPeriod,
    PayrollRun,
    Payslip,
    SalaryStructure,
    StaffLoan,
)


@admin.register(EmployeePayrollProfile)
class EmployeePayrollProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "employee_number", "job_title", "department", "basic_salary", "payment_method", "employment_status")
    list_filter = ("department", "payment_method", "employment_status")
    search_fields = ("full_name", "employee_number", "job_title", "bank_name")


class PayrollAdjustmentInline(admin.TabularInline):
    model = PayrollAdjustment
    extra = 0


class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0
    readonly_fields = ("item_type", "code", "label", "amount", "source", "sort_order", "created_at")
    can_delete = False


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("period_code", "status", "locked", "created_by", "created_at")
    list_filter = ("status", "locked", "year", "month")
    search_fields = ("year", "month")


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("employee_name", "employee_number", "period", "department", "gross_salary", "total_deductions", "net_salary", "status", "locked")
    list_filter = ("period", "department", "status", "locked", "payment_method")
    search_fields = ("employee_name", "employee_number", "department", "bank_name", "account_number")
    readonly_fields = ("gross_salary", "total_deductions", "net_salary", "created_at", "updated_at")
    inlines = [PayrollAdjustmentInline, PayrollItemInline]


@admin.register(PayrollApproval)
class PayrollApprovalAdmin(admin.ModelAdmin):
    list_display = ("period", "from_status", "to_status", "action", "approved_by", "created_at")
    list_filter = ("to_status", "action", "created_at")
    search_fields = ("period__year", "period__month", "notes")


@admin.register(PayrollExportLog)
class PayrollExportLogAdmin(admin.ModelAdmin):
    list_display = ("period", "file_name", "total_records", "total_net", "exported_by", "created_at")
    list_filter = ("period", "created_at")
    search_fields = ("file_name",)


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("slip_number", "run", "generated_by", "generated_at")
    search_fields = ("slip_number", "run__employee_name", "run__employee_number")


@admin.register(PayrollAuditLog)
class PayrollAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "period", "run", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("details", "run__employee_name", "run__employee_number")


admin.site.register(SalaryStructure)
admin.site.register(PayrollComponentDefinition)
admin.site.register(PayrollFormula)
admin.site.register(OvertimeRecord)
admin.site.register(StaffLoan)
admin.site.register(PayrollAccountingPosting)
admin.site.register(BankTransferFile)
admin.site.register(BankTransferLine)

# Register your models here.
