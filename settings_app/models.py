from django.db import models


class SchoolSettings(models.Model):
    setting_id = models.IntegerField(primary_key=True)
    school_name = models.CharField(max_length=180)
    school_address = models.TextField(blank=True, null=True)
    school_phone = models.CharField(max_length=80, blank=True, null=True)
    school_logo = models.CharField(max_length=255, blank=True, null=True)
    current_term = models.CharField(max_length=40)
    current_year = models.IntegerField()
    receipt_prefix = models.CharField(max_length=20, default="RCP")
    whatsapp_sender_number = models.CharField(max_length=40, blank=True, null=True)
    whatsapp_phone_number_id = models.CharField(max_length=120, blank=True, null=True)
    whatsapp_access_token = models.TextField(blank=True, null=True)
    whatsapp_api_version = models.CharField(max_length=30, blank=True, null=True)
    last_promotion_year = models.IntegerField(blank=True, null=True)
    cashbook_opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    school_email = models.CharField(max_length=255, blank=True, null=True)
    school_motto = models.TextField(blank=True, null=True)
    school_website = models.CharField(max_length=255, blank=True, null=True)
    headmaster_name = models.CharField(max_length=180, blank=True, null=True)
    school_stamp = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "school_settings"


class AuditLog(models.Model):
    audit_id = models.AutoField(primary_key=True)
    user_id = models.IntegerField(blank=True, null=True)
    action = models.CharField(max_length=120)
    details = models.TextField(blank=True, null=True)
    created_at = models.TextField()
    username = models.CharField(max_length=150, blank=True, null=True)
    user_role = models.CharField(max_length=80, blank=True, null=True)
    ip_address = models.CharField(max_length=80, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    endpoint = models.CharField(max_length=120, blank=True, null=True)
    request_method = models.CharField(max_length=20, blank=True, null=True)
    path = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "audit_log"


class DatabaseBackupLog(models.Model):
    backup_id = models.AutoField(primary_key=True)
    backup_name = models.CharField(max_length=180)
    backup_path = models.CharField(max_length=255)
    file_size = models.IntegerField(default=0)
    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.TextField()

    class Meta:
        managed = False
        db_table = "database_backups_log"

# Create your models here.
