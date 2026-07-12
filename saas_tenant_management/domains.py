from urllib.parse import urlsplit

from django.conf import settings


def saas_base_domain():
    return getattr(settings, "SAAS_BASE_DOMAIN", "raydonsystems.co.zw").strip().lower().rstrip(".")


def normalize_hostname(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    host = parsed.netloc or parsed.path
    host = host.split("@")[-1].split(":")[0].strip().rstrip(".")
    return host


def normalize_subdomain_label(value):
    host = normalize_hostname(value)
    base_domain = saas_base_domain()
    if not host:
        return ""
    if host == base_domain:
        return ""
    suffix = f".{base_domain}"
    while host.endswith(suffix):
        host = host[: -len(suffix)]
    return host.strip(". ").lower()


def normalize_custom_domain(value):
    host = normalize_hostname(value)
    base_domain = saas_base_domain()
    if not host:
        return None
    if host == base_domain or host.endswith(f".{base_domain}"):
        return None
    return host


def build_full_hostname(subdomain):
    label = normalize_subdomain_label(subdomain)
    if not label:
        return ""
    return f"{label}.{saas_base_domain()}"

