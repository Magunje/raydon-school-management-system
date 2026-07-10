from django.contrib import admin

from inventory_management.models import (
    InventoryAuditLog,
    InventoryCategory,
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


admin.site.register(InventoryCategory)
admin.site.register(Store)
admin.site.register(InventoryItem)
admin.site.register(StoreStock)
admin.site.register(StockBatch)
admin.site.register(StockMovement)
admin.site.register(StockTransfer)
admin.site.register(StockAdjustment)
admin.site.register(StockCount)
admin.site.register(StockCountLine)
admin.site.register(ReorderAlert)
admin.site.register(InventoryAuditLog)
