from django.db import connection
from django.test import TestCase

from .services import admission_no_for_user_save, ensure_existing_staff_admission_numbers, next_staff_admission_no


class StaffAdmissionNumberTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username varchar(150) UNIQUE NOT NULL,
                    password_hash text NOT NULL,
                    role varchar(80),
                    full_name varchar(180),
                    status varchar(30),
                    created_at text,
                    admission_no varchar(20) UNIQUE
                )
                """
            )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users")

    def row(self, username):
        with connection.cursor() as cursor:
            cursor.execute("SELECT user_id, admission_no, username, role FROM users WHERE username = %s", [username])
            result = cursor.fetchone()
        if result is None:
            return None
        return {
            "user_id": result[0],
            "admission_no": result[1],
            "username": result[2],
            "role": result[3],
        }

    def test_backfills_existing_staff_in_sequence(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (user_id, username, password_hash, role, full_name, status)
                VALUES
                    (1, 'admin', 'x', 'Administrator', 'Admin', 'Active'),
                    (2, 'parent', 'x', 'Parent', 'Parent', 'Active'),
                    (3, 'teacher', 'x', 'Teacher', 'Teacher', 'Active')
                """
            )

        assigned = ensure_existing_staff_admission_numbers()

        self.assertEqual(assigned, 2)
        self.assertEqual(self.row("admin")["admission_no"], "AS001")
        self.assertIsNone(self.row("parent")["admission_no"])
        self.assertEqual(self.row("teacher")["admission_no"], "AS002")
        self.assertEqual(next_staff_admission_no(), "AS003")

    def test_new_staff_number_keeps_existing_numbers(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (user_id, username, password_hash, role, full_name, status, admission_no)
                VALUES (1, 'teacher', 'x', 'Teacher', 'Teacher', 'Active', 'AS009')
                """
            )

        teacher = self.row("teacher")

        self.assertEqual(admission_no_for_user_save(teacher, "Teacher"), "AS009")
        self.assertIsNone(admission_no_for_user_save(teacher, "Parent"))
        self.assertEqual(next_staff_admission_no(), "AS010")
