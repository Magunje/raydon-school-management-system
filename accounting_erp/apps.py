from django.apps import AppConfig


class AccountingErpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounting_erp'
    verbose_name = 'Accounting ERP'

    def ready(self):
        import accounting_erp.signals  # noqa: F401
