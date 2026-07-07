from django.apps import AppConfig


class EnterpriseCommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'enterprise_communications'
    verbose_name = 'Enterprise Communications'

    def ready(self):
        import enterprise_communications.signals  # noqa: F401
