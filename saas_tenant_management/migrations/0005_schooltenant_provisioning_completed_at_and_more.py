from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("saas_tenant_management", "0004_tenant_schooltenant_custom_domain_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="schooltenant",
            name="provisioning_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="schooltenant",
            name="provisioning_error",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="schooltenant",
            name="provisioning_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="schooltenant",
            name="provisioning_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("PROVISIONING", "Provisioning"),
                    ("ACTIVE", "Active"),
                    ("FAILED", "Failed"),
                    ("SUSPENDED", "Suspended"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
