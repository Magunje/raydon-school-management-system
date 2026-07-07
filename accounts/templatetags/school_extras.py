from django import template

from school_system_django.native import compact_class_label


register = template.Library()


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return ""
    return mapping.get(key, "")


@register.filter
def class_label(mapping):
    if mapping is None:
        return ""
    return mapping.get("class_label") or compact_class_label(
        grade=mapping.get("grade") or mapping.get("grade_snapshot"),
        stream=mapping.get("class_stream") or mapping.get("class_stream_snapshot"),
        grade_id=mapping.get("grade_id"),
        class_name=mapping.get("class_name"),
        grade_name=mapping.get("grade_name"),
    )
