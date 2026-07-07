import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from academic_structure.models import (
    AcademicClass,
    AcademicTerm,
    AcademicYear,
    Form,
    Stream,
)
from document_factory.models import (
    DocumentReprintLog,
    DocumentStatus,
    DocumentSubjectResultSnapshot,
    DocumentType,
    GeneratedDocument,
)
from results_centre.models import Assessment, AssessmentComponent, StudentResult
from student_registry.models import Student
from subject_management.models import StudentSubjectRegistration, Subject


User = get_user_model()


class DocumentFactoryTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="records_officer",
            password="password123",
            is_staff=True,
        )
        self.year_2027 = AcademicYear.objects.create(year=2027, is_active=True)
        self.term_1 = AcademicTerm.objects.create(
            academic_year=self.year_2027,
            term_number=1,
            is_active=True,
        )
        self.term_2 = AcademicTerm.objects.create(
            academic_year=self.year_2027,
            term_number=2,
            is_active=False,
        )
        self.form_3 = Form.objects.create(form_number=3, name="Form 3")
        self.stream_a = Stream.objects.create(name="A")
        self.academic_class = AcademicClass.objects.create(
            academic_year=self.year_2027,
            form=self.form_3,
            stream=self.stream_a,
        )
        self.student = Student.objects.create(
            first_name="Rutendo",
            surname="Zhou",
            gender="Female",
            date_of_birth=datetime.date(2011, 3, 15),
            admission_date=datetime.date(2027, 1, 10),
            academic_class=self.academic_class,
            status="Active Student",
        )
        self.math = Subject.objects.create(
            code="OL_MAT",
            name="Mathematics",
            level="O_LEVEL",
        )
        self.science = Subject.objects.create(
            code="OL_SCI",
            name="Combined Science",
            level="O_LEVEL",
        )
        StudentSubjectRegistration.objects.create(
            student=self.student,
            subject=self.math,
            academic_year=self.year_2027,
            academic_term=self.term_1,
        )
        StudentSubjectRegistration.objects.create(
            student=self.student,
            subject=self.science,
            academic_year=self.year_2027,
            academic_term=self.term_2,
        )

        self.math_component = AssessmentComponent.objects.create(
            subject=self.math,
            academic_class=self.academic_class,
            component_type="TERMINAL_EXAM",
            weighting_percentage=Decimal("100.00"),
            max_score=100,
        )
        self.math_assessment = Assessment.objects.create(
            component=self.math_component,
            name="Term 1 Final",
            academic_year=self.year_2027,
            academic_term=self.term_1,
            status="Open",
        )
        self.math_result = StudentResult.objects.create(
            assessment=self.math_assessment,
            student=self.student,
            score=Decimal("82.00"),
        )

        self.science_component = AssessmentComponent.objects.create(
            subject=self.science,
            academic_class=self.academic_class,
            component_type="TERMINAL_EXAM",
            weighting_percentage=Decimal("100.00"),
            max_score=100,
        )
        self.science_assessment = Assessment.objects.create(
            component=self.science_component,
            name="Term 2 Final",
            academic_year=self.year_2027,
            academic_term=self.term_2,
            status="Open",
        )
        self.science_result = StudentResult.objects.create(
            assessment=self.science_assessment,
            student=self.student,
            score=Decimal("76.00"),
        )

    def test_document_numbers_are_type_scoped_year_scoped_and_sequential(self):
        report_1 = GeneratedDocument.create_report_card(
            student=self.student,
            academic_year=self.year_2027,
            academic_term=self.term_1,
            generated_by=self.user,
        )
        transcript_1 = GeneratedDocument.create_transcript(
            student=self.student,
            academic_year=self.year_2027,
            generated_by=self.user,
        )
        report_2 = GeneratedDocument.create_report_card(
            student=self.student,
            academic_year=self.year_2027,
            academic_term=self.term_1,
            generated_by=self.user,
        )

        self.assertEqual(report_1.document_number, "REP-2027-000001")
        self.assertEqual(transcript_1.document_number, "TRANS-2027-000001")
        self.assertEqual(report_2.document_number, "REP-2027-000002")

    def test_generated_document_has_hash_and_electronic_stamp_payload(self):
        document = GeneratedDocument.create_report_card(
            student=self.student,
            academic_year=self.year_2027,
            academic_term=self.term_1,
            generated_by=self.user,
        )

        self.assertEqual(len(document.data_verification_hash), 64)
        self.assertTrue(document.verify_hash())
        self.assertEqual(
            document.electronic_stamp_payload["status"],
            "Electronically Generated",
        )
        self.assertEqual(
            document.electronic_stamp_payload["school_name"],
            "Raydon School",
        )
        self.assertIn("timestamp", document.electronic_stamp_payload)

    def test_photo_and_image_references_are_rejected_at_model_validation(self):
        with self.assertRaises(ValidationError):
            GeneratedDocument.objects.create(
                document_type=DocumentType.TRANSCRIPT,
                document_title="Academic Transcript",
                student=self.student,
                academic_year=self.year_2027,
                source_data_snapshot={
                    "student": {
                        "admission_no": self.student.admission_no,
                        "profile_photo": "uploads/student_photos/a26001.png",
                    }
                },
                generated_by=self.user,
            )

    def test_report_card_filters_rows_to_registered_subjects_for_exact_term(self):
        document = GeneratedDocument.create_report_card(
            student=self.student,
            academic_year=self.year_2027,
            academic_term=self.term_1,
            generated_by=self.user,
        )
        subject_names = [
            row["subject_name"]
            for row in document.source_data_snapshot["subject_results"]
        ]

        self.assertEqual(subject_names, ["Mathematics"])
        self.assertNotIn("Combined Science", subject_names)
        self.assertEqual(document.subject_result_snapshots.count(), 1)
        self.assertEqual(
            document.subject_result_snapshots.first().subject,
            self.math,
        )

    def test_report_card_payload_with_unregistered_exact_term_subject_is_rejected(self):
        with self.assertRaises(ValidationError):
            GeneratedDocument.objects.create(
                document_type=DocumentType.REPORT_CARD,
                document_title="Terminal Report Card",
                student=self.student,
                academic_year=self.year_2027,
                academic_term=self.term_1,
                source_data_snapshot={
                    "subject_results": [
                        {
                            "subject_id": self.science.id,
                            "subject_name": "Combined Science",
                            "percentage": "76.00",
                        }
                    ]
                },
                generated_by=self.user,
            )

    def test_subject_result_snapshot_rejects_unregistered_exact_term_subject(self):
        document = GeneratedDocument.create_report_card(
            student=self.student,
            academic_year=self.year_2027,
            academic_term=self.term_1,
            generated_by=self.user,
        )

        with self.assertRaises(ValidationError):
            DocumentSubjectResultSnapshot.objects.create(
                document=document,
                student=self.student,
                academic_year=self.year_2027,
                academic_term=self.term_1,
                subject=self.science,
                subject_code_snapshot="OL_SCI",
                subject_name_snapshot="Combined Science",
                assessment_name="Term 1 Final",
                component_type="TERMINAL_EXAM",
                score=Decimal("76.00"),
                percentage=Decimal("76.00"),
                alpha_grade="B",
            )

    def test_archived_students_remain_searchable_and_reprintable(self):
        self.student.status = "Archived"
        self.student.save()

        transcript = GeneratedDocument.create_transcript(
            student=self.student,
            academic_year=self.year_2027,
            generated_by=self.user,
            source_data_snapshot={
                "academic_history": [
                    {
                        "year": 2027,
                        "term": 1,
                        "status": "Completed",
                    }
                ]
            },
        )
        reprint = transcript.create_reprint(
            reason="Parent requested a certified historical copy.",
            generated_by=self.user,
        )
        log = DocumentReprintLog.objects.get(reprinted_document=reprint)

        self.assertEqual(transcript.student_status_at_generation, "Archived")
        self.assertEqual(reprint.status, DocumentStatus.REPRINTED)
        self.assertEqual(reprint.version_number, 2)
        self.assertEqual(log.version_number, 2)
        self.assertEqual(log.student_status_snapshot, "Archived")
        self.assertTrue(
            GeneratedDocument.objects.for_student_identity(
                self.student.admission_no
            ).transcripts().exists()
        )
