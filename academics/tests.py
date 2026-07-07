from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.utils import timezone

from academics.library_services import available_copies_for_issue, sync_book_availability
from school_system_django.native import compact_class_label
from .views import active_academic_year


class ClassModuleYearTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS classes (
                    class_id INTEGER PRIMARY KEY,
                    class_name varchar(80),
                    grade_id integer,
                    academic_year integer,
                    class_teacher varchar(180),
                    class_teacher_id integer
                )
                """
            )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM classes")
        User = get_user_model()
        self.user = User.objects.create_superuser(username="admin", password="admin123")
        self.client = Client()
        self.client.force_login(self.user)

    def test_classes_page_only_shows_active_year(self):
        current_year = active_academic_year()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO classes (class_name, grade_id, academic_year, class_teacher)
                VALUES ('CURRENTONLY', 1, %s, ''), ('FUTUREONLY', 1, %s, '')
                """,
                [current_year, current_year + 1],
            )

        response = self.client.get("/classes")
        body = response.content.decode("utf-8", errors="ignore")

        self.assertEqual(response.status_code, 200)
        self.assertIn("CURRENTONLY", body)
        self.assertNotIn("FUTUREONLY", body)
        self.assertNotIn(str(timezone.localdate().year + 1), body)

    def test_new_class_rejects_future_academic_year(self):
        current_year = active_academic_year()
        response = self.client.post(
            "/classes/new",
            {
                "class_name": "Z",
                "grade_id": "1",
                "academic_year": str(current_year + 1),
                "class_teacher": "",
                "class_teacher_id": "",
            },
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM classes WHERE class_name = 'Z'")
            count = cursor.fetchone()[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(count, 0)

    def test_new_class_saves_current_academic_year(self):
        current_year = active_academic_year()
        response = self.client.post(
            "/classes/new",
            {
                "class_name": "D",
                "grade_id": "1",
                "academic_year": str(current_year),
                "class_teacher": "Teacher One",
                "class_teacher_id": "",
            },
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT academic_year FROM classes WHERE class_name = 'D' AND grade_id = 1")
            row = cursor.fetchone()

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(row)
        self.assertEqual(row[0], current_year)

    def test_compact_class_label_uses_grade_and_stream(self):
        self.assertEqual(compact_class_label(grade_name="Grade 1", class_name="A"), "Form 1 A")
        self.assertEqual(compact_class_label(grade="Grade 7", stream="B"), "Completed O Level")
        self.assertEqual(compact_class_label(class_name="2 c"), "2C")


class LibraryInventoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS library_books (
                    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title varchar(180),
                    author varchar(180),
                    isbn varchar(80),
                    category varchar(80),
                    total_copies integer,
                    available_copies integer,
                    fine_per_day numeric,
                    status varchar(40)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS textbook_loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pupil_id integer,
                    book_id integer,
                    book_name varchar(180),
                    borrowed_date text,
                    return_date text,
                    status varchar(40),
                    notes text,
                    cleared_date text,
                    recorded_by integer,
                    cleared_by integer,
                    created_at text,
                    updated_at text
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS library_issues (
                    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id integer,
                    status varchar(40),
                    due_date text,
                    return_date text
                )
                """
            )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM textbook_loans")
            cursor.execute("DELETE FROM library_issues")
            cursor.execute("DELETE FROM library_books")

    def create_book(self, total=2):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO library_books (title, author, isbn, category, total_copies, available_copies, fine_per_day, status)
                VALUES ('Math One', 'Raydon', 'M1', 'Textbook', %s, %s, 0, 'Active')
                """,
                [total, total],
            )
            cursor.execute("SELECT book_id FROM library_books WHERE title = 'Math One'")
            return cursor.fetchone()[0]

    def create_loan(self, book_id, status="Borrowed"):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO textbook_loans (pupil_id, book_id, book_name, borrowed_date, return_date, status)
                VALUES (1, %s, 'Math One', '2026-01-01', '2026-01-31', %s)
                """,
                [book_id, status],
            )
            cursor.execute("SELECT loan_id FROM textbook_loans WHERE book_id = %s", [book_id])
            return cursor.fetchone()[0]

    def test_sync_book_availability_counts_active_loans(self):
        book_id = self.create_book(total=2)
        self.create_loan(book_id, status="Borrowed")

        book = sync_book_availability(book_id)

        self.assertEqual(book["issued_count"], 1)
        self.assertEqual(book["available_copies"], 1)

    def test_returned_loans_release_stock(self):
        book_id = self.create_book(total=1)
        self.create_loan(book_id, status="Returned")

        book = sync_book_availability(book_id)

        self.assertEqual(book["issued_count"], 0)
        self.assertEqual(book["available_copies"], 1)

    def test_editing_current_active_loan_can_keep_its_copy(self):
        book_id = self.create_book(total=1)
        loan_id = self.create_loan(book_id, status="Borrowed")

        self.assertEqual(available_copies_for_issue(book_id), 0)
        self.assertEqual(available_copies_for_issue(book_id, exclude_loan_id=loan_id), 1)
