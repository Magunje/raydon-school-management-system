from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("academic_structure", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="academicyear",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="is_current",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="name",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="status",
            field=models.CharField(default="upcoming", max_length=20),
        ),
        migrations.AddField(
            model_name="academicyear",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name="academicterm",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="academicterm",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="academicterm",
            name="is_current",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="academicterm",
            name="name",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="academicterm",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="academicterm",
            name="status",
            field=models.CharField(default="upcoming", max_length=20),
        ),
        migrations.AddField(
            model_name="academicterm",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="academicyear",
            constraint=models.UniqueConstraint(
                fields=("is_current",),
                condition=Q(is_current=True),
                name="single_current_academic_year",
            ),
        ),
        migrations.AddConstraint(
            model_name="academicterm",
            constraint=models.UniqueConstraint(
                fields=("is_current",),
                condition=Q(is_current=True),
                name="single_current_academic_term",
            ),
        ),
    ]

