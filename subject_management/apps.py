from django.apps import AppConfig


class SubjectManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'subject_management'
    verbose_name = 'Subject Management'

    def ready(self):
        import subject_management.signals  # noqa: F401
