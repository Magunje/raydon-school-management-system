from django.apps import AppConfig


class StudentRegistryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'student_registry'
    verbose_name = 'Student Registry'

    def ready(self):
        import student_registry.signals  # noqa: F401
