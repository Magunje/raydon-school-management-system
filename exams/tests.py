from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import connection
from exams.models import ResultSheet, ResultEntry, ExamSession
from students.models import Pupil
from school_system_django.native import insert_record, now_text
from exams.views import calculate_grade, recalculate_positions

class ExamsTestCase(TestCase):
    def setUp(self):
        # Create user
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='admin', password='admin123')
        
        # Create teacher user
        self.teacher = User.objects.create_user(username='teacher', password='teacher123')
        from accounts.models import UserProfile
        self.teacher_profile = UserProfile.objects.create(user=self.teacher, role='Teacher', full_name='ERINA MANEGI')
        
        # Log in client
        self.client = Client()
        self.client.login(username='admin', password='admin123')
        
        # Insert test pupils directly using SQL as they are unmanaged
        with connection.cursor() as cursor:
            # Insert grades first in case they are not in the test DB
            cursor.execute("INSERT OR IGNORE INTO grades (grade_id, grade_name) VALUES (7, 'Completed O Level')")
            
            # Insert class
            cursor.execute(
                """
                INSERT INTO classes (class_name, grade_id, academic_year, class_teacher)
                VALUES ('A', 7, 2026, 'ERINA MANEGI')
                """
            )
            cursor.execute("SELECT class_id FROM classes WHERE class_name = 'A'")
            self.class_id = cursor.fetchone()[0]
            
            cursor.execute(
                """
                INSERT INTO pupils (admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, guardian_name, guardian_phone, address, admission_date, status, class_id)
                VALUES 
                ('A26001', 'Alice', 'Smith', 'Female', '2015-01-01', 'Completed O Level', 'A', 'John Smith', '12345', 'Street 1', '2026-01-01', 'Active', %s),
                ('A26002', 'Bob', 'Jones', 'Male', '2015-02-02', 'Completed O Level', 'A', 'Mark Jones', '67890', 'Street 2', '2026-01-01', 'Active', %s),
                ('A26003', 'Charlie', 'Brown', 'Male', '2015-03-03', 'Completed O Level', 'A', 'Lucy Brown', '11111', 'Street 3', '2026-01-01', 'Active', %s)
                """,
                [self.class_id, self.class_id, self.class_id]
            )
            
            # Fetch pupil IDs
            cursor.execute("SELECT pupil_id, admission_no FROM pupils")
            self.pupils = {row[1]: row[0] for row in cursor.fetchall()}
            
            # Insert subjects
            cursor.execute(
                """
                INSERT INTO subjects (subject_code, subject_name, grade, display_order, status)
                VALUES 
                ('ENG', 'English', 'All Forms', 1, 'Active'),
                ('MATH', 'Mathematics', 'All Forms', 2, 'Active')
                """
            )
            cursor.execute("SELECT subject_id, subject_code FROM subjects")
            self.subjects = {row[1]: row[0] for row in cursor.fetchall()}
            
            # Register pupils for both subjects
            for p_id in self.pupils.values():
                for s_id in self.subjects.values():
                    cursor.execute(
                        """
                        INSERT INTO student_subjects (pupil_id, subject_id, academic_year, form, stream)
                        VALUES (%s, %s, 2026, 'Completed O Level', 'A')
                        """,
                        [p_id, s_id]
                    )
            
            # Allocate teacher to both subjects in Class A
            for s_id in self.subjects.values():
                cursor.execute(
                    """
                    INSERT INTO timetable_subjectallocation (teacher_id, class_id, subject_id, periods_per_week, preferred_sessions, is_practical, required_room_type)
                    VALUES (%s, %s, %s, 4, 'Any', 0, 'Classroom')
                    """,
                    [self.teacher_profile.id, self.class_id, s_id]
                )

    def test_calculate_grade(self):
        self.assertEqual(calculate_grade(85), "A")
        self.assertEqual(calculate_grade(70), "B")
        self.assertEqual(calculate_grade(65), "C")
        self.assertEqual(calculate_grade(55), "D")
        self.assertEqual(calculate_grade(45), "E")
        self.assertEqual(calculate_grade(35), "U")
        self.assertEqual(calculate_grade("invalid"), "U")

    def test_result_sheet_creation_and_grading(self):
        self.client.login(username='teacher', password='teacher123')
        # 1. Create a result sheet for Alice
        response = self.client.post("/results/new", {
            "pupil_id": self.pupils["A26001"],
            "term": "Term 1",
            "year": "2026",
            "teacher_comment": "Excellent"
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify result sheet exists
        sheet = ResultSheet.objects.filter(pupil_id=self.pupils["A26001"], term="Term 1", year=2026).first()
        self.assertIsNotNone(sheet)
        self.assertEqual(sheet.grade_snapshot, "Completed O Level")
        self.assertEqual(sheet.class_stream_snapshot, "A")
        
        # 2. Enter subject marks for Alice
        result_id = sheet.result_id
        response = self.client.post(f"/results/{result_id}/edit", {
            "teacher_comment": "Superb job",
            f"subject_{self.subjects['ENG']}": "82",
            f"subject_{self.subjects['MATH']}": "78"
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify entries & auto-grading
        eng_entry = ResultEntry.objects.filter(result_id=result_id, subject_id=self.subjects['ENG']).first()
        self.assertIsNotNone(eng_entry)
        self.assertEqual(float(eng_entry.mark), 82.0)
        self.assertEqual(eng_entry.grade, "A")
        
        math_entry = ResultEntry.objects.filter(result_id=result_id, subject_id=self.subjects['MATH']).first()
        self.assertIsNotNone(math_entry)
        self.assertEqual(float(math_entry.mark), 78.0)
        self.assertEqual(math_entry.grade, "B")
        
        # Verify result sheet totals and averages are calculated
        sheet.refresh_from_db()
        self.assertEqual(float(sheet.total_marks), 160.0)
        self.assertEqual(float(sheet.average_mark), 80.0)

    def test_position_rankings(self):
        # Create sheets for Alice, Bob, and Charlie
        alice_sheet = ResultSheet.objects.create(pupil_id=self.pupils["A26001"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=180, average_mark=90, created_at=now_text(), updated_at=now_text())
        bob_sheet = ResultSheet.objects.create(pupil_id=self.pupils["A26002"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=160, average_mark=80, created_at=now_text(), updated_at=now_text())
        charlie_sheet = ResultSheet.objects.create(pupil_id=self.pupils["A26003"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=160, average_mark=80, created_at=now_text(), updated_at=now_text())
        
        # Run recalculation
        recalculate_positions("Term 1", 2026, "Completed O Level")
        
        # Verify positions (Alice is 1st, Bob and Charlie tie for 2nd)
        alice_sheet.refresh_from_db()
        bob_sheet.refresh_from_db()
        charlie_sheet.refresh_from_db()
        
        self.assertEqual(alice_sheet.class_position, 1)
        self.assertEqual(alice_sheet.grade_position, 1)
        self.assertEqual(bob_sheet.class_position, 2)
        self.assertEqual(charlie_sheet.class_position, 2)

    def test_result_slip_pdf(self):
        # Create a result sheet and some marks
        sheet = ResultSheet.objects.create(pupil_id=self.pupils["A26001"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=180, average_mark=90, created_at=now_text(), updated_at=now_text())
        ResultEntry.objects.create(result_id=sheet.result_id, subject_id=self.subjects['ENG'], mark=92, grade='A', created_at=now_text(), updated_at=now_text())
        
        # Fetch PDF
        response = self.client.get(f"/results/{sheet.result_id}/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_result_class_entry(self):
        self.client.login(username='teacher', password='teacher123')
        # Record marks for whole class
        response = self.client.post("/results/class-entry", {
            "class_id": self.class_id,
            "subject_id": self.subjects['ENG'],
            "term": "Term 1",
            "year": "2026",
            f"mark_{self.pupils['A26001']}": "85.5",
            f"mark_{self.pupils['A26002']}": "90.0",
            f"mark_{self.pupils['A26003']}": "75.0"
        })
        self.assertEqual(response.status_code, 302)

        # Verify sheets created and marks saved
        sheet1 = ResultSheet.objects.filter(pupil_id=self.pupils["A26001"], term="Term 1", year=2026).first()
        self.assertIsNotNone(sheet1)
        self.assertEqual(float(sheet1.average_mark), 85.5)

        eng_entry1 = ResultEntry.objects.filter(result_id=sheet1.result_id, subject_id=self.subjects['ENG']).first()
        self.assertIsNotNone(eng_entry1)
        self.assertEqual(float(eng_entry1.mark), 85.5)

    def test_result_bulk_publish(self):
        # Create draft sheet
        sheet = ResultSheet.objects.create(pupil_id=self.pupils["A26001"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=180, average_mark=90, status="Draft", created_at=now_text(), updated_at=now_text())
        
        response = self.client.post("/results/bulk-publish", {
            "class_id": self.class_id,
            "term": "Term 1",
            "year": "2026"
        })
        self.assertEqual(response.status_code, 302)

        # Verify published
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, "Published")

    def test_class_attendance_register(self):
        response = self.client.post("/attendance/register", {
            "class_id": self.class_id,
            "date": "2026-06-15",
            f"status_{self.pupils['A26001']}": "Present",
            f"status_{self.pupils['A26002']}": "Absent",
            f"status_{self.pupils['A26003']}": "Late",
            f"notes_{self.pupils['A26002']}": "Sick leave"
        })
        self.assertEqual(response.status_code, 302)

        # Verify attendance records in DB
        with connection.cursor() as cursor:
            cursor.execute("SELECT pupil_id, status, notes FROM attendance_records WHERE class_id = %s AND attendance_date = '2026-06-15'", [self.class_id])
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 3)
            attendance_map = {r[0]: (r[1], r[2]) for r in rows}
            self.assertEqual(attendance_map[self.pupils['A26001']], ('Present', ''))
            self.assertEqual(attendance_map[self.pupils['A26002']], ('Absent', 'Sick leave'))
            self.assertEqual(attendance_map[self.pupils['A26003']], ('Late', ''))

    def test_results_list_sorting(self):
        # Create sheets for Alice, Bob, and Charlie with different average marks (and therefore positions)
        ResultSheet.objects.create(pupil_id=self.pupils["A26001"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=180, average_mark=90, class_position=1, grade_position=1, created_at=now_text(), updated_at=now_text())
        ResultSheet.objects.create(pupil_id=self.pupils["A26002"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=160, average_mark=80, class_position=2, grade_position=2, created_at=now_text(), updated_at=now_text())
        
        # Test class position sorting
        response = self.client.get("/results?tab=sheets&order_by=class_position")
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_by", response.context)
        self.assertEqual(response.context["order_by"], "class_position")
        
        # Test grade position sorting
        response = self.client.get("/results?tab=sheets&order_by=grade_position")
        self.assertEqual(response.status_code, 200)
        self.assertIn("order_by", response.context)
        self.assertEqual(response.context["order_by"], "grade_position")

    def test_results_export_pdf(self):
        # Create sheet
        ResultSheet.objects.create(pupil_id=self.pupils["A26001"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=180, average_mark=90, class_position=1, grade_position=1, created_at=now_text(), updated_at=now_text())
        
        # Export default
        response = self.client.get("/results/export/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Export with sorting and filters
        response = self.client.get(f"/results/export/pdf?class_id={self.class_id}&term=Term 1&year=2026&order_by=class_position")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_published_result_lockout(self):
        sheet = ResultSheet.objects.create(pupil_id=self.pupils["A26001"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=180, average_mark=90, status="Published", created_at=now_text(), updated_at=now_text())
        
        self.client.login(username='teacher', password='teacher123')
        response = self.client.post(f"/results/{sheet.result_id}/edit", {
            "teacher_comment": "Trying to modify",
            f"subject_{self.subjects['ENG']}": "95"
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"/results/{sheet.result_id}")
        
        response = self.client.post(f"/results/{sheet.result_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"/results/{sheet.result_id}")
        
        sheet.refresh_from_db()
        self.assertEqual(float(sheet.average_mark), 90.0)

    def test_results_verify_public(self):
        sheet = ResultSheet.objects.create(pupil_id=self.pupils["A26001"], term="Term 1", year=2026, grade_snapshot="Completed O Level", class_stream_snapshot="A", total_marks=180, average_mark=90, status="Published", created_at=now_text(), updated_at=now_text())
        
        self.client.logout()
        
        response = self.client.get(f"/results/verify/{sheet.result_id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verified Authentic")
        self.assertContains(response, "Alice")
        
        response = self.client.get("/results/verify/99999")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verification Unsuccessful")


