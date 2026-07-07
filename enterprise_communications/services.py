from django.core.exceptions import ValidationError
from enterprise_communications.models import AccountPortalMapping, NotificationQueue
from student_registry.models import Student


def query_linked_children_profiles(parent_user):
    """Retrieves all linked children profiles for a parent portal user context."""
    mappings = AccountPortalMapping.objects.filter(
        user=parent_user, portal_role="PARENT"
    )
    return Student.objects.filter(portal_mappings__in=mappings).distinct()


def enforce_portal_readonly(user, target_model, action="mutate"):
    """Validates and enforces portal read-only policies.

    Blocks mutations (adds, updates, deletions) on administrative, academic,
    or billing tables.
    """
    if not user or user.is_staff or user.is_superuser:
        return

    # Check if user is mapped to a portal
    is_portal = AccountPortalMapping.objects.filter(user=user).exists()
    if is_portal:
        raise ValidationError(
            f"Portal users are strictly restricted to read-only access. "
            f"Mutation action '{action}' is blocked on model '{target_model.__name__}'."
        )


def enqueue_system_notification(event_name, recipient_user, message_body):
    """Adds automated delivery assignments to the Notification Queue."""
    return NotificationQueue.objects.create(
        event_name=event_name,
        recipient=recipient_user,
        message_body=message_body,
        status="PENDING",
    )
