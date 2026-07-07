from django.contrib import admin

from .models import Expense, FeeStructure, MasterReceipt, OnlinePaymentRequest, Payment, Receipt


class ReadOnlyLegacyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(ReadOnlyLegacyAdmin):
    list_display = ("receipt_no", "pupil_id", "amount_paid", "payment_date", "payment_method", "term", "year")
    list_filter = ("payment_method", "term", "year")
    search_fields = ("receipt_no", "reference_no")


admin.site.register(FeeStructure, ReadOnlyLegacyAdmin)
admin.site.register(Receipt, ReadOnlyLegacyAdmin)
admin.site.register(MasterReceipt, ReadOnlyLegacyAdmin)
admin.site.register(Expense, ReadOnlyLegacyAdmin)
admin.site.register(OnlinePaymentRequest, ReadOnlyLegacyAdmin)

# Register your models here.
