import hashlib
import json
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils import timezone


class DocumentType(models.TextChoices):
    REPORT_CARD = "REPORT_CARD", "Report Card"
    TRANSCRIPT = "TRANSCRIPT", "Academic Transcript"
    ENROLMENT_LETTER = "ENROLMENT_LETTER", "Enrolment Letter"


class DocumentStatus(models.TextChoices):
    GENERATED = "GENERATED", "Generated"
    REPRINTED = "REPRINTED", "Reprinted"
    VOID = "VOID", "Void"


DOCUMENT_PREFIXES = {
    DocumentType.REPORT_CARD: "REP",
    DocumentType.TRANSCRIPT: "TRANS",
    DocumentType.ENROLMENT_LETTER: "ENR",
}

HASH_VALIDATOR = RegexValidator(
    regex=r"^[a-f0-9]{64}$",
    message="Data verification hash must be a lowercase SHA-256 hexadecimal digest.",
)

FORBIDDEN_STUDENT_MEDIA_KEYS = {
    "avatar",
    "graphic",
    "graphics",
    "headshot",
    "image",
    "images",
    "photo",
    "photo_path",
    "photograph",
    "picture",
    "portrait",
    "profile_image",
    "profile_photo",
    "profile_photograph",
    "student_graphic",
    "student_image",
    "student_photo",
    "thumbnail",
}

FORBIDDEN_STUDENT_MEDIA_VALUE_RE = re.compile(
    r"(\bavatar\b|\bheadshot\b|\bphoto(?:graph)?\b|\bportrait\b|"
    r"\bstudent\s+(?:graphic|image|photo)\b|\bprofile\s+(?:image|photo)\b|"
    r"\bphoto\s*box\b|\bimage\s*container\b|"
    r"\.(?:bmp|gif|jpe?g|png|svg|webp)\b)",
    re.IGNORECASE,
)


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _assert_photo_free(value, path="payload"):
    if value is None:
        return

    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).strip().lower()
            if key_text in FORBIDDEN_STUDENT_MEDIA_KEYS:
                raise ValidationError(
                    f"Student graphics and profile photographs are prohibited; "
                    f"blocked media key '{key}' at {path}."
                )
            if FORBIDDEN_STUDENT_MEDIA_VALUE_RE.search(str(key)):
                raise ValidationError(
                    f"Student graphics and profile photographs are prohibited; "
                    f"blocked media reference '{key}' at {path}."
                )
            _assert_photo_free(item, f"{path}.{key}")
        return

    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            _assert_photo_free(item, f"{path}[{index}]")
        return

    if isinstance(value, str) and FORBIDDEN_STUDENT_MEDIA_VALUE_RE.search(value):
        raise ValidationError(
            f"Student graphics and profile photographs are prohibited; "
            f"blocked media reference at {path}."
        )


class DocumentNumberSequence(models.Model):
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "document_factory_number_sequences"
        unique_together = ("document_type", "year")
        ordering = ["document_type", "year"]

    def __str__(self):
        return f"{self.document_type}-{self.year}: {self.last_number}"

    @classmethod
    def next_number(cls, document_type, year):
        prefix = DOCUMENT_PREFIXES.get(document_type)
        if not prefix:
            raise ValidationError(f"Unsupported document type '{document_type}'.")

        with transaction.atomic():
            sequence, _created = (
                cls.objects.select_for_update()
                .get_or_create(
                    document_type=document_type,
                    year=year,
                    defaults={"last_number": 0},
                )
            )
            sequence.last_number += 1
            sequence.save(update_fields=["last_number", "updated_at"])
            return f"{prefix}-{year}-{sequence.last_number:06d}"


class GeneratedDocumentQuerySet(models.QuerySet):
    def report_cards(self):
        return self.filter(document_type=DocumentType.REPORT_CARD)

    def transcripts(self):
        return self.filter(document_type=DocumentType.TRANSCRIPT)

    def enrolment_letters(self):
        return self.filter(document_type=DocumentType.ENROLMENT_LETTER)

    def for_student_identity(self, admission_no):
        return self.filter(student_admission_no=admission_no)

    def regenerable(self):
        return self.filter(is_regenerable=True)


class GeneratedDocument(models.Model):
    document_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        db_index=True,
    )
    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        db_index=True,
    )
    document_title = models.CharField(max_length=180)

    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.PROTECT,
        related_name="generated_documents",
    )
    student_admission_no = models.CharField(max_length=50, db_index=True)
    student_first_name = models.CharField(max_length=100)
    student_surname = models.CharField(max_length=100, db_index=True)
    student_status_at_generation = models.CharField(max_length=50, db_index=True)

    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear",
        on_delete=models.PROTECT,
        related_name="generated_documents",
        blank=True,
        null=True,
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm",
        on_delete=models.PROTECT,
        related_name="generated_documents",
        blank=True,
        null=True,
    )
    document_year = models.PositiveIntegerField(db_index=True)

    pdf_storage_path = models.CharField(max_length=500, blank=True)
    source_data_snapshot = models.JSONField(default=dict, blank=True)
    verification_payload = models.TextField()
    data_verification_hash = models.CharField(
        max_length=64,
        validators=[HASH_VALIDATOR],
        editable=False,
    )
    electronic_stamp_payload = models.JSONField(default=dict, blank=True)

    original_document = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reprint_versions",
        blank=True,
        null=True,
    )
    version_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.GENERATED,
        db_index=True,
    )
    is_regenerable = models.BooleanField(default=True)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="generated_documents",
        blank=True,
        null=True,
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    objects = GeneratedDocumentQuerySet.as_manager()

    class Meta:
        db_table = "document_factory_generated_documents"
        ordering = ["-generated_at", "-id"]
        indexes = [
            models.Index(fields=["document_type", "document_year"]),
            models.Index(fields=["student_admission_no", "document_type"]),
            models.Index(fields=["student_surname", "student_first_name"]),
            models.Index(fields=["status", "is_regenerable"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["original_document", "version_number"],
                name="unique_reprint_version_per_original_document",
            )
        ]

    def __str__(self):
        return f"{self.document_number} - {self.document_title}"

    @property
    def reprint_count(self):
        root = self.original_document or self
        return DocumentReprintLog.objects.filter(source_document=root).count()

    def clean(self):
        super().clean()

        prefix = DOCUMENT_PREFIXES.get(self.document_type)
        if not prefix:
            raise ValidationError({"document_type": "Unsupported document type."})

        if self.document_number:
            expected = rf"^{prefix}-{self.document_year}-\d{{6}}$"
            if not re.match(expected, self.document_number):
                raise ValidationError(
                    {
                        "document_number": (
                            "Document number must match the strict "
                            f"{prefix}-{self.document_year}-000001 format."
                        )
                    }
                )

        if self.document_type == DocumentType.REPORT_CARD:
            if not self.academic_year or not self.academic_term:
                raise ValidationError(
                    "Report Cards must be bound to one exact academic year and term."
                )
            self._validate_report_card_subject_payload()

        _assert_photo_free(self.source_data_snapshot, "source_data_snapshot")
        _assert_photo_free(self.electronic_stamp_payload, "electronic_stamp_payload")
        _assert_photo_free(self.verification_payload, "verification_payload")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self._hydrate_identity_snapshot()
            self._hydrate_document_year()
            self._hydrate_stamp_payload()
            self._hydrate_verification_payload()
            self.data_verification_hash = self.calculate_data_verification_hash()

            if not self.document_number:
                self.document_number = DocumentNumberSequence.next_number(
                    self.document_type,
                    self.document_year,
                )
                self._hydrate_verification_payload()
                self.data_verification_hash = self.calculate_data_verification_hash()

            self.full_clean()
            super().save(*args, **kwargs)

    def _hydrate_identity_snapshot(self):
        if not self.student_id:
            return
        self.student_admission_no = self.student.admission_no
        self.student_first_name = self.student.first_name
        self.student_surname = self.student.surname
        self.student_status_at_generation = self.student.status

    def _hydrate_document_year(self):
        if self.document_year:
            return
        if self.academic_year_id:
            self.document_year = self.academic_year.year
        else:
            self.document_year = timezone.localdate().year

    def _hydrate_stamp_payload(self):
        if self.electronic_stamp_payload:
            return
        self.electronic_stamp_payload = {
            "school_name": os.environ.get("SCHOOL_NAME", "Raydon School"),
            "timestamp": timezone.now().isoformat(),
            "status": "Electronically Generated",
        }

    def _hydrate_verification_payload(self):
        payload = {
            "document_number": self.document_number or "PENDING",
            "document_type": self.document_type,
            "document_title": self.document_title,
            "student": {
                "admission_no": self.student_admission_no,
                "first_name": self.student_first_name,
                "surname": self.student_surname,
                "status": self.student_status_at_generation,
            },
            "academic_year": self.academic_year.year if self.academic_year_id else None,
            "academic_term": (
                self.academic_term.term_number if self.academic_term_id else None
            ),
            "document_year": self.document_year,
            "version_number": self.version_number,
            "source_data_snapshot": self.source_data_snapshot,
            "electronic_stamp": self.electronic_stamp_payload,
        }
        self.verification_payload = _canonical_json(payload)

    def calculate_data_verification_hash(self):
        return hashlib.sha256(self.verification_payload.encode("utf-8")).hexdigest()

    def verify_hash(self):
        return self.data_verification_hash == self.calculate_data_verification_hash()

    def _validate_report_card_subject_payload(self):
        rows = self.source_data_snapshot.get("subject_results", [])
        if not rows:
            return

        registered_subject_ids = set(
            StudentSubjectRegistration.objects.filter(
                student=self.student,
                academic_year=self.academic_year,
                academic_term=self.academic_term,
            ).values_list("subject_id", flat=True)
        )
        row_subject_ids = {
            int(row["subject_id"])
            for row in rows
            if isinstance(row, dict) and row.get("subject_id") is not None
        }
        unregistered = row_subject_ids - registered_subject_ids
        if unregistered:
            raise ValidationError(
                "Report Card payload contains subjects not registered by the "
                "student for the exact academic year and term cycle."
            )

    @classmethod
    def report_card_subject_rows(cls, student, academic_year, academic_term):
        registrations = StudentSubjectRegistration.objects.filter(
            student=student,
            academic_year=academic_year,
            academic_term=academic_term,
        ).select_related("subject")
        registered_subject_ids = registrations.values_list("subject_id", flat=True)

        results = (
            StudentResult.objects.filter(
                student=student,
                assessment__academic_year=academic_year,
                assessment__academic_term=academic_term,
                assessment__component__subject_id__in=registered_subject_ids,
            )
            .select_related(
                "assessment",
                "assessment__component",
                "assessment__component__subject",
            )
            .order_by("assessment__component__subject__name", "assessment__name")
        )

        rows = []
        for result in results:
            subject = result.assessment.component.subject
            rows.append(
                {
                    "subject_id": subject.id,
                    "subject_code": subject.code,
                    "subject_name": subject.name,
                    "assessment_id": result.assessment_id,
                    "assessment_name": result.assessment.name,
                    "component_type": result.assessment.component.component_type,
                    "score": str(result.score),
                    "percentage": str(result.percentage),
                    "alpha_grade": result.alpha_grade,
                    "class_rank": result.class_rank,
                    "class_average": (
                        str(result.class_average)
                        if result.class_average is not None
                        else None
                    ),
                }
            )
        return rows

    @classmethod
    def build_report_card_snapshot(cls, student, academic_year, academic_term):
        rows = cls.report_card_subject_rows(student, academic_year, academic_term)
        percentages = [
            float(row["percentage"])
            for row in rows
            if row.get("percentage") not in (None, "")
        ]
        return {
            "student_admission_no": student.admission_no,
            "academic_year": academic_year.year,
            "academic_term": academic_term.term_number,
            "registered_subject_ids": list(
                StudentSubjectRegistration.objects.filter(
                    student=student,
                    academic_year=academic_year,
                    academic_term=academic_term,
                ).values_list("subject_id", flat=True)
            ),
            "subject_results": rows,
            "aggregate": {
                "subject_count": len(rows),
                "total_percentage": round(sum(percentages), 2),
                "average_percentage": (
                    round(sum(percentages) / len(percentages), 2)
                    if percentages
                    else None
                ),
            },
        }

    @classmethod
    def create_report_card(
        cls,
        *,
        student,
        academic_year,
        academic_term,
        generated_by=None,
        pdf_storage_path="",
        document_title="Terminal Report Card",
    ):
        snapshot = cls.build_report_card_snapshot(
            student=student,
            academic_year=academic_year,
            academic_term=academic_term,
        )
        document = cls.objects.create(
            document_type=DocumentType.REPORT_CARD,
            document_title=document_title,
            student=student,
            academic_year=academic_year,
            academic_term=academic_term,
            pdf_storage_path=pdf_storage_path,
            source_data_snapshot=snapshot,
            generated_by=generated_by,
        )
        for row in snapshot["subject_results"]:
            DocumentSubjectResultSnapshot.objects.create(
                document=document,
                student=student,
                academic_year=academic_year,
                academic_term=academic_term,
                subject_id=row["subject_id"],
                subject_code_snapshot=row["subject_code"],
                subject_name_snapshot=row["subject_name"],
                assessment_name=row["assessment_name"],
                component_type=row["component_type"],
                score=row["score"],
                percentage=row["percentage"],
                alpha_grade=row["alpha_grade"],
                class_rank=row["class_rank"],
                class_average=row["class_average"],
            )
        return document

    @classmethod
    def create_transcript(
        cls,
        *,
        student,
        academic_year=None,
        generated_by=None,
        pdf_storage_path="",
        source_data_snapshot=None,
        document_title="Academic Transcript",
    ):
        return cls.objects.create(
            document_type=DocumentType.TRANSCRIPT,
            document_title=document_title,
            student=student,
            academic_year=academic_year,
            pdf_storage_path=pdf_storage_path,
            source_data_snapshot=source_data_snapshot or {},
            generated_by=generated_by,
        )

    @classmethod
    def create_enrolment_letter(
        cls,
        *,
        student,
        academic_year=None,
        academic_term=None,
        generated_by=None,
        pdf_storage_path="",
        source_data_snapshot=None,
        document_title="Enrolment Letter",
    ):
        return cls.objects.create(
            document_type=DocumentType.ENROLMENT_LETTER,
            document_title=document_title,
            student=student,
            academic_year=academic_year,
            academic_term=academic_term,
            pdf_storage_path=pdf_storage_path,
            source_data_snapshot=source_data_snapshot or {},
            generated_by=generated_by,
        )

    def create_reprint(self, *, reason, generated_by=None, pdf_storage_path=""):
        if not reason or not reason.strip():
            raise ValidationError("A written reprint reason is required.")

        root = self.original_document or self
        next_version = (
            DocumentReprintLog.objects.filter(source_document=root).count() + 2
        )
        reprinted = GeneratedDocument.objects.create(
            document_type=root.document_type,
            document_title=root.document_title,
            student=root.student,
            academic_year=root.academic_year,
            academic_term=root.academic_term,
            pdf_storage_path=pdf_storage_path,
            source_data_snapshot=root.source_data_snapshot,
            original_document=root,
            version_number=next_version,
            status=DocumentStatus.REPRINTED,
            generated_by=generated_by,
        )
        DocumentReprintLog.objects.create(
            source_document=root,
            reprinted_document=reprinted,
            version_number=next_version,
            reason=reason,
            requested_by=generated_by,
            student_status_snapshot=reprinted.student_status_at_generation,
        )
        return reprinted


class DocumentSubjectResultSnapshot(models.Model):
    document = models.ForeignKey(
        GeneratedDocument,
        on_delete=models.CASCADE,
        related_name="subject_result_snapshots",
    )
    student = models.ForeignKey(
        "student_registry.Student",
        on_delete=models.PROTECT,
        related_name="document_subject_result_snapshots",
    )
    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear",
        on_delete=models.PROTECT,
        related_name="document_subject_result_snapshots",
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm",
        on_delete=models.PROTECT,
        related_name="document_subject_result_snapshots",
    )
    subject = models.ForeignKey(
        "subject_management.Subject",
        on_delete=models.PROTECT,
        related_name="document_result_snapshots",
    )
    subject_code_snapshot = models.CharField(max_length=50)
    subject_name_snapshot = models.CharField(max_length=150)
    assessment_name = models.CharField(max_length=150)
    component_type = models.CharField(max_length=20)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    alpha_grade = models.CharField(max_length=5, blank=True)
    class_rank = models.IntegerField(blank=True, null=True)
    class_average = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_factory_subject_result_snapshots"
        ordering = ["subject_name_snapshot", "assessment_name"]
        indexes = [
            models.Index(fields=["student", "academic_year", "academic_term"]),
            models.Index(fields=["subject_code_snapshot"]),
        ]

    def __str__(self):
        return f"{self.document.document_number}: {self.subject_name_snapshot}"

    def clean(self):
        super().clean()
        if self.document.document_type != DocumentType.REPORT_CARD:
            raise ValidationError(
                "Subject result snapshots may only be attached to Report Cards."
            )

        is_registered = StudentSubjectRegistration.objects.filter(
            student=self.student,
            subject=self.subject,
            academic_year=self.academic_year,
            academic_term=self.academic_term,
        ).exists()
        if not is_registered:
            raise ValidationError(
                "Report Card rows must reference only subjects registered by the "
                "student in the exact academic year and term cycle."
            )

        _assert_photo_free(
            {
                "subject_code_snapshot": self.subject_code_snapshot,
                "subject_name_snapshot": self.subject_name_snapshot,
                "assessment_name": self.assessment_name,
                "component_type": self.component_type,
            },
            "document_subject_result_snapshot",
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class DocumentReprintLog(models.Model):
    source_document = models.ForeignKey(
        GeneratedDocument,
        on_delete=models.PROTECT,
        related_name="reprint_logs",
    )
    reprinted_document = models.OneToOneField(
        GeneratedDocument,
        on_delete=models.PROTECT,
        related_name="reprint_log",
    )
    version_number = models.PositiveIntegerField()
    reason = models.TextField()
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="document_reprint_requests",
        blank=True,
        null=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    student_status_snapshot = models.CharField(max_length=50, db_index=True)

    class Meta:
        db_table = "document_factory_reprint_logs"
        unique_together = ("source_document", "version_number")
        ordering = ["source_document", "version_number"]

    def __str__(self):
        return (
            f"{self.source_document.document_number} reprint v{self.version_number}"
        )

    def clean(self):
        super().clean()
        if not self.reason or not self.reason.strip():
            raise ValidationError({"reason": "A written reprint reason is required."})
        if self.version_number < 2:
            raise ValidationError(
                {"version_number": "Reprint version counts start at version 2."}
            )
        if self.reprinted_document.original_document_id != self.source_document_id:
            raise ValidationError(
                "The reprinted document must point back to the same source document."
            )
        _assert_photo_free(self.reason, "reprint_reason")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


from results_centre.models import StudentResult
from subject_management.models import StudentSubjectRegistration
