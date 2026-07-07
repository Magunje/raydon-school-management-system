from django.apps import AppConfig


class FeesManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fees_management'
    verbose_name = 'Fees Management'

    def ready(self):
        import fees_management.signals  # noqa: F401
