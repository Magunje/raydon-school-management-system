from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class AccountPortalMapping(models.Model):
    PORTAL_ROLE_CHOICES = [
        ("PARENT", "Parent Portal"),
        ("STUDENT", "Student Portal"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portal_mappings",
    )
    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="portal_mappings",
    )
    portal_role = models.CharField(max_length=20, choices=PORTAL_ROLE_CHOICES)

    class Meta:
        db_table = "account_portal_mappings"
        unique_together = ("user", "student", "portal_role")

    def __str__(self):
        return f"{self.user.username} -> {self.student.full_name} ({self.portal_role})"

    def clean(self):
        super().clean()
        # Enforce read-only constraint policies blocking portals from mutating structural rows
        # Standard users mapped here must not have staff/superuser access
        if self.user.is_staff or self.user.is_superuser:
            raise ValidationError(
                "Staff or administrative users cannot be bound to read-only portal mappings."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class InternalMessage(models.Model):
    PRIORITY_CHOICES = [
        ("LOW", "Low Priority"),
        ("MEDIUM", "Medium Priority"),
        ("HIGH", "High Priority"),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="MEDIUM"
    )
    read_receipt = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "internal_messages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Msg from {self.sender.username} to {self.recipient.username} - {self.subject}"


class NotificationQueue(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Delivery"),
        ("SENT", "Delivered Successfully"),
        ("FAILED", "Delivery Failed"),
    ]

    event_name = models.CharField(max_length=100)  # e.g., 'CHRONIC_ABSENCE'
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message_body = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_queue"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification {self.event_name} to {self.recipient.username} ({self.status})"


class SystemAuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_audit_logs",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    module = models.CharField(max_length=100)
    action = models.CharField(max_length=50)  # ADD, UPDATE, DELETE
    old_values_json = models.JSONField(null=True, blank=True)
    new_values_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "system_audit_ledger"
        ordering = ["-timestamp"]

    def __str__(self):
        actor = self.user.username if self.user else "System"
        return f"[{self.timestamp}] {actor} - {self.action} on {self.module}"
