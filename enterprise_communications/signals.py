from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.forms.models import model_to_dict
from enterprise_communications.models import SystemAuditLog

EXCLUDED_MODELS = [
    "systemauditlog",
    "session",
    "contenttype",
    "logentry",
    "migration",
]


def serialize_model_instance(instance):
    try:
        data = model_to_dict(instance)
        # Clean any non-JSON serializable fields safely
        return json.loads(json.dumps(data, cls=DjangoJSONEncoder))
    except Exception:
        pk_val = getattr(instance, "pk", None)
        return {"id": str(pk_val) if pk_val is not None else None}


@receiver(post_save)
def global_post_save_logger(sender, instance, created, **kwargs):
    model_name = sender._meta.model_name
    app_label = sender._meta.app_label

    if model_name in EXCLUDED_MODELS or app_label == "enterprise_communications":
        return

    action = "ADD" if created else "UPDATE"
    module = f"{app_label}.{sender.__name__}"

    new_values = serialize_model_instance(instance)
    old_values = {}  # Optional: track old state if cached earlier

    try:
        SystemAuditLog.objects.create(
            user=None,  # Thread local user integration can be plugged in here
            module=module,
            action=action,
            old_values_json=old_values,
            new_values_json=new_values,
        )
    except Exception:
        # Ignore audit log failures during migrations/tests when table is not ready
        pass


@receiver(post_delete)
def global_post_delete_logger(sender, instance, **kwargs):
    model_name = sender._meta.model_name
    app_label = sender._meta.app_label

    if model_name in EXCLUDED_MODELS or app_label == "enterprise_communications":
        return

    module = f"{app_label}.{sender.__name__}"
    old_values = serialize_model_instance(instance)

    try:
        SystemAuditLog.objects.create(
            user=None,
            module=module,
            action="DELETE",
            old_values_json=old_values,
            new_values_json={},
        )
    except Exception:
        pass
