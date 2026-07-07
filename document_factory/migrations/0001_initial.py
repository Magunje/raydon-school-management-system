# Generated manually for Phase 7 document_factory.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("academic_structure", "0001_initial"),
        ("student_registry", "0002_student_national_id_alter_student_status_and_more"),
        ("subject_management", "0003_subject_department"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentNumberSequence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("REPORT_CARD", "Report Card"),
                            ("TRANSCRIPT", "Academic Transcript"),
                            ("ENROLMENT_LETTER", "Enrolment Letter"),
                        ],
                        max_length=30,
                    ),
                ),
                ("year", models.PositiveIntegerField()),
                ("last_number", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "document_factory_number_sequences",
                "ordering": ["document_type", "year"],
                "unique_together": {("document_type", "year")},
            },
        ),
        migrations.CreateModel(
            name="GeneratedDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "document_number",
                    models.CharField(
                        db_index=True,
                        editable=False,
                        max_length=32,
                        unique=True,
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("REPORT_CARD", "Report Card"),
                            ("TRANSCRIPT", "Academic Transcript"),
                            ("ENROLMENT_LETTER", "Enrolment Letter"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("document_title", models.CharField(max_length=180)),
                ("student_admission_no", models.CharField(db_index=True, max_length=50)),
                ("student_first_name", models.CharField(max_length=100)),
                ("student_surname", models.CharField(db_index=True, max_length=100)),
                (
                    "student_status_at_generation",
                    models.CharField(db_index=True, max_length=50),
                ),
                ("document_year", models.PositiveIntegerField(db_index=True)),
                ("pdf_storage_path", models.CharField(blank=True, max_length=500)),
                ("source_data_snapshot", models.JSONField(blank=True, default=dict)),
                ("verification_payload", models.TextField()),
                (
                    "data_verification_hash",
                    models.CharField(
                        editable=False,
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                message=(
                                    "Data verification hash must be a lowercase "
                                    "SHA-256 hexadecimal digest."
                                ),
                                regex="^[a-f0-9]{64}$",
                            )
                        ],
                    ),
                ),
                ("electronic_stamp_payload", models.JSONField(blank=True, default=dict)),
                ("version_number", models.PositiveIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("GENERATED", "Generated"),
                            ("REPRINTED", "Reprinted"),
                            ("VOID", "Void"),
                        ],
                        db_index=True,
                        default="GENERATED",
                        max_length=20,
                    ),
                ),
                ("is_regenerable", models.BooleanField(default=True)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "academic_term",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="generated_documents",
                        to="academic_structure.academicterm",
                    ),
                ),
                (
                    "academic_year",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="generated_documents",
                        to="academic_structure.academicyear",
                    ),
                ),
                (
                    "generated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generated_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "original_document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reprint_versions",
                        to="document_factory.generateddocument",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="generated_documents",
                        to="student_registry.student",
                    ),
                ),
            ],
            options={
                "db_table": "document_factory_generated_documents",
                "ordering": ["-generated_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="DocumentSubjectResultSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("subject_code_snapshot", models.CharField(max_length=50)),
                ("subject_name_snapshot", models.CharField(max_length=150)),
                ("assessment_name", models.CharField(max_length=150)),
                ("component_type", models.CharField(max_length=20)),
                ("score", models.DecimalField(decimal_places=2, max_digits=5)),
                ("percentage", models.DecimalField(decimal_places=2, max_digits=5)),
                ("alpha_grade", models.CharField(blank=True, max_length=5)),
                ("class_rank", models.IntegerField(blank=True, null=True)),
                (
                    "class_average",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                    ),
                ),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
                (
                    "academic_term",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_subject_result_snapshots",
                        to="academic_structure.academicterm",
                    ),
                ),
                (
                    "academic_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_subject_result_snapshots",
                        to="academic_structure.academicyear",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subject_result_snapshots",
                        to="document_factory.generateddocument",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_subject_result_snapshots",
                        to="student_registry.student",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_result_snapshots",
                        to="subject_management.subject",
                    ),
                ),
            ],
            options={
                "db_table": "document_factory_subject_result_snapshots",
                "ordering": ["subject_name_snapshot", "assessment_name"],
            },
        ),
        migrations.CreateModel(
            name="DocumentReprintLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("version_number", models.PositiveIntegerField()),
                ("reason", models.TextField()),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                (
                    "student_status_snapshot",
                    models.CharField(db_index=True, max_length=50),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="document_reprint_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reprinted_document",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reprint_log",
                        to="document_factory.generateddocument",
                    ),
                ),
                (
                    "source_document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reprint_logs",
                        to="document_factory.generateddocument",
                    ),
                ),
            ],
            options={
                "db_table": "document_factory_reprint_logs",
                "ordering": ["source_document", "version_number"],
                "unique_together": {("source_document", "version_number")},
            },
        ),
        migrations.AddIndex(
            model_name="generateddocument",
            index=models.Index(
                fields=["document_type", "document_year"],
                name="document_fa_documen_8697a8_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="generateddocument",
            index=models.Index(
                fields=["student_admission_no", "document_type"],
                name="document_fa_student_6d6777_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="generateddocument",
            index=models.Index(
                fields=["student_surname", "student_first_name"],
                name="document_fa_student_3264d5_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="generateddocument",
            index=models.Index(
                fields=["status", "is_regenerable"],
                name="document_fa_status_44e56e_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="generateddocument",
            constraint=models.UniqueConstraint(
                fields=("original_document", "version_number"),
                name="unique_reprint_version_per_original_document",
            ),
        ),
        migrations.AddIndex(
            model_name="documentsubjectresultsnapshot",
            index=models.Index(
                fields=["student", "academic_year", "academic_term"],
                name="document_fa_student_f4e3d9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="documentsubjectresultsnapshot",
            index=models.Index(
                fields=["subject_code_snapshot"],
                name="document_fa_subject_656a06_idx",
            ),
        ),
    ]
