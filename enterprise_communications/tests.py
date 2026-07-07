from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academic_structure.models import AcademicYear, Form, Stream, AcademicClass
from student_registry.models import Student
from timetable_engine.models import Classroom
from enterprise_communications.models import (
    AccountPortalMapping,
    InternalMessage,
    NotificationQueue,
    SystemAuditLog,
)
from enterprise_communications.services import (
    query_linked_children_profiles,
    enforce_portal_readonly,
    enqueue_system_notification,
)
import datetime

User = get_user_model()


class EnterpriseCommunicationsTestCase(TestCase):
    def setUp(self):
        # Users
        self.parent_user = User.objects.create_user(
            username="parent1", password="password123"
        )
        self.teacher_user = User.objects.create_user(
            username="teacher1", password="password123"
        )

        # Academic Context
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.form_1 = Form.objects.create(form_number=1, name="Form 1")
        self.stream_a = Stream.objects.create(name="A")
        self.academic_class = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_1, stream=self.stream_a
        )

        # Students
        self.child_1 = Student.objects.create(
            first_name="Farai",
            surname="Moyo",
            gender="Male",
            date_of_birth=datetime.date(2011, 4, 12),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )
        self.child_2 = Student.objects.create(
            first_name="Chipo",
            surname="Moyo",
            gender="Female",
            date_of_birth=datetime.date(2013, 8, 22),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )

        # Map parent to children
        AccountPortalMapping.objects.create(
            user=self.parent_user, student=self.child_1, portal_role="PARENT"
        )
        AccountPortalMapping.objects.create(
            user=self.parent_user, student=self.child_2, portal_role="PARENT"
        )

    def test_portal_mapping_and_partitioning(self):
        # Query children for parent
        children = query_linked_children_profiles(self.parent_user)
        self.assertEqual(children.count(), 2)
        self.assertIn(self.child_1, children)
        self.assertIn(self.child_2, children)

    def test_portal_readonly_mutation_guards(self):
        # Portal user tries to mutate Classroom model -> should raise ValidationError
        with self.assertRaises(ValidationError):
            enforce_portal_readonly(self.parent_user, Classroom, action="insert")

    def test_unified_messaging_and_notification_queue(self):
        # 1. Internal Message
        msg = InternalMessage.objects.create(
            sender=self.parent_user,
            recipient=self.teacher_user,
            subject="Queries on homework",
            body="Is there any homework for this weekend?",
            priority="MEDIUM",
        )
        self.assertIsNotNone(msg)
        self.assertEqual(self.teacher_user.received_messages.count(), 1)

        # 2. Notification Enqueue
        notif = enqueue_system_notification(
            event_name="CHRONIC_ABSENCE",
            recipient_user=self.parent_user,
            message_body="Your child Farai has registered 3 consecutive absences.",
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.status, "PENDING")
        self.assertEqual(self.parent_user.notifications.count(), 1)

    def test_global_json_audit_ledger(self):
        # Clear existing logs to verify fresh updates
        SystemAuditLog.objects.all().delete()

        # Create a new Classroom (should trigger ADD audit signal)
        room = Classroom.objects.create(name="Lab 3", capacity=25)

        # Verify ADD log
        add_log = SystemAuditLog.objects.filter(
            action="ADD", module="timetable_engine.Classroom"
        ).first()
        self.assertIsNotNone(add_log)
        self.assertEqual(add_log.new_values_json["name"], "Lab 3")

        # Update Classroom (should trigger UPDATE audit signal)
        room.capacity = 30
        room.save()

        # Verify UPDATE log
        update_log = SystemAuditLog.objects.filter(
            action="UPDATE", module="timetable_engine.Classroom"
        ).first()
        self.assertIsNotNone(update_log)
        self.assertEqual(update_log.new_values_json["capacity"], 30)

        # Delete Classroom (should trigger DELETE audit signal)
        room.delete()

        # Verify DELETE log
        delete_log = SystemAuditLog.objects.filter(
            action="DELETE", module="timetable_engine.Classroom"
        ).first()
        self.assertIsNotNone(delete_log)
        self.assertEqual(delete_log.old_values_json["name"], "Lab 3")
