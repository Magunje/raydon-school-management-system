from django.apps import AppConfig


class AttendanceLedgerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance_ledger'
    verbose_name = 'Attendance Ledger'

    def ready(self):
        import attendance_ledger.signals  # noqa: F401
