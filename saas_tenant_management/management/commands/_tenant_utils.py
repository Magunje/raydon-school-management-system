from saas_tenant_management.services import install_tenant_connection


def tenant_database_alias(tenant):
    return install_tenant_connection(tenant)
