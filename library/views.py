import os
from decimal import Decimal
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponse, FileResponse, Http404, JsonResponse

from accounts.permissions import permission_required, user_has_permission, normalized_role
from student_registry.models import Student
from human_resources.models import EmployeeProfile
from library.models import LibraryBook, LibraryMember, LibraryIssue, LibraryReservation, LibraryDigitalResource
from fees_management.models import StudentFeeAccount, Invoice, InvoiceItem, FeeCategory, ReceiptControl
from school_system_django.native import (
    dict_rows,
    one_row,
    insert_record,
    update_record,
    delete_record,
    today_text,
    now_text,
    school_settings,
    audit_action,
    table_exists
)

# Helper to load library settings
def get_library_settings():
    row = one_row("SELECT * FROM library_settings WHERE setting_id = 1")
    if not row:
        insert_record(None, "library_settings", {
            "daily_overdue_fine": Decimal("0.50"),
            "damaged_book_penalty": Decimal("5.00"),
            "lost_book_penalty": Decimal("15.00"),
            "max_books_allowed": 3,
            "borrow_duration_days": 14
        })
        row = one_row("SELECT * FROM library_settings WHERE setting_id = 1")
    return row


# Helper to update book available copies
def update_book_availability(book_id):
    book = LibraryBook.objects.filter(pk=book_id).first()
    if not book:
        return
    
    # Active issues (Borrowed status)
    active_issues = one_row(
        "SELECT COUNT(*) AS total FROM library_issues WHERE book_id = %s AND status = 'Borrowed'",
        [book_id]
    )
    issued_count = active_issues["total"] if active_issues else 0
    
    # Active textbook loans
    active_loans = 0
    if table_exists("textbook_loans"):
        res = one_row(
            "SELECT COUNT(*) AS total FROM textbook_loans WHERE book_id = %s AND status = 'Borrowed'",
            [book_id]
        )
        active_loans = res["total"] if res else 0
        
    total_issued = issued_count + active_loans
    available = max(book.total_copies - total_issued, 0)
    
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE library_books SET available_copies = %s WHERE book_id = %s",
            [available, book_id]
        )


# Helper to post library fine/penalty to fees_management
def post_library_fine(request, student, amount, notes):
    if amount <= Decimal("0.00"):
        return None
        
    with transaction.atomic():
        # Get or create Fee Account
        account = getattr(student, "fee_account", None)
        if not account:
            account = StudentFeeAccount.objects.filter(student=student).first()
            
        if not account:
            # Create default if missing
            from academic_structure.models import AcademicYear, AcademicTerm
            year = student.academic_class.academic_year if student.academic_class else None
            term = AcademicTerm.objects.filter(is_active=True).first() or AcademicTerm.objects.first()
            if not year or not term:
                raise ValueError("Student has no assigned class or active term structure.")
            account = StudentFeeAccount.objects.create(
                student=student,
                academic_year=year,
                academic_term=term,
                total_charges=Decimal("0.00"),
                amount_paid=Decimal("0.00"),
                arrears=Decimal("0.00"),
            )
            
        # Get or create Library Fine Category
        category, _ = FeeCategory.objects.get_or_create(
            name="Library Fines", defaults={"is_active": True}
        )
        
        # Get ReceiptControl for sequence
        control, _ = ReceiptControl.objects.get_or_create(
            pk=1,
            defaults={
                "receipt_prefix": "REC",
                "invoice_prefix": "INV",
                "last_receipt_no": 0,
                "last_invoice_no": 0,
            },
        )
        control.last_invoice_no += 1
        control.save()
        
        year_val = datetime.date.today().year
        inv_num = f"{control.invoice_prefix}-{year_val}-{control.last_invoice_no:05d}"
        
        # Create Invoice
        invoice = Invoice.objects.create(
            invoice_number=inv_num,
            student_account=account,
            due_date=datetime.date.today() + datetime.timedelta(days=14),
            previous_balance=account.outstanding_balance,
            current_charges=amount,
            discounts=Decimal("0.00"),
            scholarships=Decimal("0.00"),
        )
        
        # Create Invoice Item
        InvoiceItem.objects.create(
            invoice=invoice, category=category, amount=amount
        )
        
        # Update Student Account total charges and trigger recalculation
        account.total_charges += amount
        account.save()
        
        # Audit
        if request:
            audit_action(
                request, 
                "Library Fine Posted", 
                f"Posted invoice {inv_num} for library fine amount ${amount} to student {student.admission_no}."
            )
        
        # Also post into generic balance_adjustments table if exists for compatibility
        if request and table_exists("balance_adjustments"):
            try:
                settings_map = school_settings()
                term_val = settings_map.get("current_term") or "Term 1"
                year_val = settings_map.get("current_year") or datetime.date.today().year
                insert_record(
                    request,
                    "balance_adjustments",
                    {
                        "pupil_id": student.pk,
                        "term": term_val,
                        "year": year_val,
                        "entry_type": "Debit",
                        "amount": amount,
                        "notes": f"Library fine: {notes}",
                        "recorded_by": request.user.id if request.user.is_authenticated else None,
                        "created_at": now_text(),
                    }
                )
            except Exception:
                pass
                
        return invoice


# Helper to log communication / notice details
def log_library_notification(request, pupil_id, channel, msg_type, message, status="Sent"):
    if table_exists("communication_log"):
        try:
            insert_record(
                request,
                "communication_log",
                {
                    "pupil_id": pupil_id,
                    "channel": channel,
                    "message_type": msg_type,
                    "status": status,
                    "created_at": now_text(),
                    "notes": message,
                    "subject": f"Library {msg_type}"
                }
            )
        except Exception:
            pass


@permission_required("library.manage")
def library_dashboard(request):
    settings_val = get_library_settings()
    
    # Telemetry
    total_books_row = one_row("SELECT SUM(total_copies) AS total FROM library_books")
    total_books = total_books_row["total"] if total_books_row and total_books_row["total"] else 0
    
    issued_books_row = one_row("SELECT COUNT(*) AS total FROM library_issues WHERE status = 'Borrowed'")
    issued_books = issued_books_row["total"] if issued_books_row else 0
    
    overdue_books_row = one_row(
        "SELECT COUNT(*) AS total FROM library_issues WHERE status = 'Borrowed' AND due_date < %s",
        [today_text()]
    )
    overdue_books = overdue_books_row["total"] if overdue_books_row else 0
    
    reserved_books_row = one_row("SELECT COUNT(*) AS total FROM library_reservations WHERE status = 'Pending'")
    reserved_books = reserved_books_row["total"] if reserved_books_row else 0
    
    fine_collected_row = one_row("SELECT SUM(fine_amount) AS total FROM library_issues WHERE fine_paid = 1")
    fine_collections = fine_collected_row["total"] if fine_collected_row and fine_collected_row["total"] else Decimal("0.00")
    
    digital_resources_count = one_row("SELECT COUNT(*) AS total FROM library_digital_resources")
    digital_resources = digital_resources_count["total"] if digital_resources_count else 0
    
    # Carousels / Popular books
    popular_books = dict_rows(
        """
        SELECT b.book_id, b.title, b.author, b.category, COUNT(i.issue_id) AS issue_count
        FROM library_books b
        LEFT JOIN library_issues i ON i.book_id = b.book_id
        GROUP BY b.book_id, b.title, b.author, b.category
        ORDER BY issue_count DESC
        LIMIT 5
        """
    )
    
    recently_added = dict_rows(
        "SELECT book_id, title, author, category, total_copies, shelf_location FROM library_books ORDER BY book_id DESC LIMIT 5"
    )
    
    context = {
        "title": "Library Dashboard",
        "settings": settings_val,
        "stats": [
            ("Total Copies", total_books),
            ("Issued Books", issued_books),
            ("Overdue Books", overdue_books),
            ("Reservations", reserved_books),
        ],
        "fine_collections": fine_collections,
        "digital_resources": digital_resources,
        "popular_books": popular_books,
        "recently_added": recently_added,
        "school_settings": school_settings(),
    }
    return render(request, "library/dashboard.html", context)


@permission_required("library.manage")
def book_list(request):
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    
    where_clauses = ["status != 'Archived'"]
    params = []
    
    if q:
        where_clauses.append("(title LIKE %s OR author LIKE %s OR isbn LIKE %s OR subject LIKE %s)")
        params.extend([f"%{q}%"] * 4)
        
    if category:
        where_clauses.append("category = %s")
        params.append(category)
        
    where = " AND ".join(where_clauses)
    
    books = dict_rows(
        f"""
        SELECT book_id, title, author, isbn, category, total_copies, available_copies, fine_per_day, subject, shelf_location
        FROM library_books
        WHERE {where}
        ORDER BY title
        """,
        params
    )
    
    categories = dict_rows("SELECT DISTINCT category FROM library_books WHERE category IS NOT NULL AND category != ''")
    
    context = {
        "title": "Book Catalogue",
        "books": books,
        "categories": [c["category"] for c in categories],
        "q": q,
        "selected_category": category,
        "school_settings": school_settings(),
    }
    return render(request, "library/book_list.html", context)


@permission_required("library.manage")
def book_new(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        author = request.POST.get("author", "").strip()
        isbn = request.POST.get("isbn", "").strip()
        category = request.POST.get("category", "").strip()
        subject = request.POST.get("subject", "").strip()
        publisher = request.POST.get("publisher", "").strip()
        publication_year = request.POST.get("publication_year") or None
        edition = request.POST.get("edition", "").strip()
        shelf_location = request.POST.get("shelf_location", "").strip()
        total_copies = int(request.POST.get("total_copies", 1))
        fine_per_day = Decimal(request.POST.get("fine_per_day", "0.50"))
        
        if not title:
            messages.error(request, "Book Title is required.")
        else:
            try:
                book_id = insert_record(
                    request,
                    "library_books",
                    {
                        "title": title,
                        "author": author,
                        "isbn": isbn,
                        "category": category,
                        "subject": subject,
                        "publisher": publisher,
                        "publication_year": publication_year,
                        "edition": edition,
                        "shelf_location": shelf_location,
                        "total_copies": total_copies,
                        "available_copies": total_copies,
                        "fine_per_day": fine_per_day,
                        "status": "Active",
                    }
                )
                audit_action(request, "Create Book", f"Registered new book '{title}' (ID: {book_id})")
                messages.success(request, "Book added to catalogue successfully.")
                return redirect("library_books")
            except Exception as e:
                messages.error(request, f"Error adding book: {e}")
                
    categories = dict_rows("SELECT DISTINCT category FROM library_books WHERE category IS NOT NULL AND category != ''")
    context = {
        "title": "Register New Book",
        "categories": [c["category"] for c in categories],
        "school_settings": school_settings(),
    }
    return render(request, "library/book_form.html", context)


@permission_required("library.manage")
def book_edit(request, book_id):
    book = get_object_or_404(LibraryBook, pk=book_id)
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        author = request.POST.get("author", "").strip()
        isbn = request.POST.get("isbn", "").strip()
        category = request.POST.get("category", "").strip()
        subject = request.POST.get("subject", "").strip()
        publisher = request.POST.get("publisher", "").strip()
        publication_year = request.POST.get("publication_year") or None
        edition = request.POST.get("edition", "").strip()
        shelf_location = request.POST.get("shelf_location", "").strip()
        total_copies = int(request.POST.get("total_copies", 1))
        fine_per_day = Decimal(request.POST.get("fine_per_day", "0.50"))
        
        if not title:
            messages.error(request, "Book Title is required.")
        else:
            try:
                # Recalculate available copies based on new total
                active_issues = one_row(
                    "SELECT COUNT(*) AS total FROM library_issues WHERE book_id = %s AND status = 'Borrowed'",
                    [book_id]
                )
                issued_count = active_issues["total"] if active_issues else 0
                available = max(total_copies - issued_count, 0)
                
                update_record(
                    request,
                    "library_books",
                    "book_id",
                    book_id,
                    {
                        "title": title,
                        "author": author,
                        "isbn": isbn,
                        "category": category,
                        "subject": subject,
                        "publisher": publisher,
                        "publication_year": publication_year,
                        "edition": edition,
                        "shelf_location": shelf_location,
                        "total_copies": total_copies,
                        "available_copies": available,
                        "fine_per_day": fine_per_day,
                    }
                )
                audit_action(request, "Update Book", f"Updated book '{title}' (ID: {book_id})")
                messages.success(request, "Book details updated successfully.")
                return redirect("library_books")
            except Exception as e:
                messages.error(request, f"Error updating book: {e}")
                
    categories = dict_rows("SELECT DISTINCT category FROM library_books WHERE category IS NOT NULL AND category != ''")
    context = {
        "title": "Edit Book details",
        "book": book,
        "categories": [c["category"] for c in categories],
        "school_settings": school_settings(),
    }
    return render(request, "library/book_form.html", context)


@permission_required("library.manage")
def book_delete(request, book_id):
    book = get_object_or_404(LibraryBook, pk=book_id)
    # Check if there are active loans
    active_loans = one_row("SELECT COUNT(*) AS total FROM library_issues WHERE book_id = %s AND status = 'Borrowed'", [book_id])
    if active_loans and active_loans["total"] > 0:
        messages.error(request, f"Cannot delete book '{book.title}' because {active_loans['total']} copies are currently issued.")
        return redirect("library_books")
        
    try:
        update_record(request, "library_books", "book_id", book_id, {"status": "Archived"})
        audit_action(request, "Delete Book", f"Archived/Soft-deleted book '{book.title}' (ID: {book_id})")
        messages.success(request, "Book soft-deleted from catalogue successfully.")
    except Exception as e:
        messages.error(request, f"Could not delete book: {e}")
    return redirect("library_books")


@permission_required("library.manage")
def book_qrcode(request, book_id):
    book = get_object_or_404(LibraryBook, pk=book_id)
    qr_data = f"BOOK-{book.book_id}"
    
    # Generate QR Code image path
    abs_dir = os.path.join(settings.MEDIA_ROOT, "book_qrcodes")
    os.makedirs(abs_dir, exist_ok=True)
    file_path = os.path.join(abs_dir, f"book_{book_id}.png")
    
    if not os.path.exists(file_path):
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(file_path)
        
    qr_url = f"/media/book_qrcodes/book_{book_id}.png"
    
    context = {
        "title": "Book Label & QR Code",
        "book": book,
        "qr_url": qr_url,
        "qr_data": qr_data,
        "school_settings": school_settings(),
    }
    return render(request, "library/book_qrcode.html", context)


@permission_required("library.manage")
def issue_list(request):
    status_filter = (request.GET.get("status") or "Borrowed").strip()
    
    where = "1=1"
    params = []
    if status_filter:
        where = "i.status = %s"
        params.append(status_filter)
        
    issues = dict_rows(
        f"""
        SELECT i.issue_id, b.title, b.isbn, i.issue_date, i.due_date, i.return_date, i.status, i.fine_amount,
               p.first_name || ' ' || p.surname AS student_name, p.admission_no,
               e.first_name || ' ' || e.surname AS staff_name, e.employee_number
        FROM library_issues i
        JOIN library_books b ON b.book_id = i.book_id
        LEFT JOIN pupils p ON p.pupil_id = i.pupil_id
        LEFT JOIN hr_employee_profiles e ON e.id = i.staff_id
        WHERE {where}
        ORDER BY i.due_date ASC
        """,
        params
    )
    
    # Highlight overdues
    today = today_text()
    for issue in issues:
        issue["is_overdue"] = issue["status"] == "Borrowed" and issue["due_date"] < today
        
    context = {
        "title": "Lending Activities",
        "issues": issues,
        "selected_status": status_filter,
        "school_settings": school_settings(),
    }
    return render(request, "library/issue_list.html", context)


@permission_required("library.manage")
def issue_new(request):
    lib_settings = get_library_settings()
    
    if request.method == "POST":
        borrower_type = request.POST.get("borrower_type", "Student")
        borrower_id = request.POST.get("borrower_id")
        book_id = request.POST.get("book_id")
        due_date = request.POST.get("due_date") or None
        
        try:
            # Validate Book
            book = get_object_or_404(LibraryBook, pk=book_id)
            if book.available_copies <= 0:
                raise ValueError(f"Cannot issue: '{book.title}' has no copies available.")
                
            # Validate Borrower and limit check
            pupil_pk = None
            staff_pk = None
            borrower_name = ""
            
            if borrower_type == "Student":
                student = get_object_or_404(Student, pk=borrower_id)
                pupil_pk = student.pk
                borrower_name = f"Student {student.first_name} {student.surname} ({student.admission_no})"
                
                # Check active issues count
                active = one_row(
                    "SELECT COUNT(*) AS total FROM library_issues WHERE pupil_id = %s AND status = 'Borrowed'",
                    [pupil_pk]
                )
                active_count = active["total"] if active else 0
                if active_count >= lib_settings["max_books_allowed"]:
                    raise ValueError(f"Borrower exceeds allocation limit of {lib_settings['max_books_allowed']} books.")
            else:
                staff = get_object_or_404(EmployeeProfile, pk=borrower_id)
                staff_pk = staff.pk
                borrower_name = f"Staff {staff.first_name} {staff.surname} ({staff.employee_number})"
                
                # Check active issues count
                active = one_row(
                    "SELECT COUNT(*) AS total FROM library_issues WHERE staff_id = %s AND status = 'Borrowed'",
                    [staff_pk]
                )
                active_count = active["total"] if active else 0
                if active_count >= lib_settings["max_books_allowed"]:
                    raise ValueError(f"Borrower exceeds allocation limit of {lib_settings['max_books_allowed']} books.")
            
            # Due date generation
            if not due_date:
                duration = int(lib_settings["borrow_duration_days"])
                due_date = (datetime.date.today() + datetime.timedelta(days=duration)).isoformat()
                
            # Create Issue
            issue_id = insert_record(
                request,
                "library_issues",
                {
                    "book_id": book_id,
                    "pupil_id": pupil_pk,
                    "staff_id": staff_pk,
                    "issue_date": today_text(),
                    "due_date": due_date,
                    "status": "Borrowed",
                    "librarian_id": request.user.id if request.user.is_authenticated else None,
                }
            )
            
            # Decrement availability
            update_book_availability(book_id)
            
            # Audit
            audit_action(request, "Issue Book", f"Issued '{book.title}' to {borrower_name} (Issue ID: {issue_id})")
            
            messages.success(request, f"Book issued successfully to {borrower_name}.")
            return redirect("library_issues")
            
        except Exception as e:
            messages.error(request, f"Could not issue book: {e}")
            
    # Load listings for dropdown autocomplete
    books = dict_rows("SELECT book_id, title, author, available_copies FROM library_books WHERE status = 'Active' AND available_copies > 0")
    students = Student.objects.filter(status="Active Student")
    staff = EmployeeProfile.objects.filter(status="ACTIVE")
    
    context = {
        "title": "New Book Issuing",
        "books": books,
        "students": students,
        "staff": staff,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "library/issue_form.html", context)


@permission_required("library.manage")
def return_library_book(request, issue_id):
    issue = one_row(
        """
        SELECT i.*, b.title, b.fine_per_day,
               p.first_name || ' ' || p.surname AS student_name, p.admission_no,
               e.first_name || ' ' || e.surname AS staff_name, e.employee_number
        FROM library_issues i
        JOIN library_books b ON b.book_id = i.book_id
        LEFT JOIN pupils p ON p.pupil_id = i.pupil_id
        LEFT JOIN hr_employee_profiles e ON e.id = i.staff_id
        WHERE i.issue_id = %s
        """,
        [issue_id]
    )
    
    if not issue:
        raise Http404("Lending record not found.")
        
    lib_settings = get_library_settings()
    
    # Pre-calculate overdue fine if applicable
    due_date = datetime.date.fromisoformat(issue["due_date"])
    today = datetime.date.today()
    overdue_days = max((today - due_date).days, 0)
    
    rate = Decimal(str(issue.get("fine_per_day") or lib_settings["daily_overdue_fine"]))
    overdue_fine = Decimal(overdue_days) * rate
    
    if request.method == "POST":
        condition = request.POST.get("condition", "Good")
        custom_fine = Decimal(request.POST.get("fine_amount", "0.00"))
        fine_action = request.POST.get("fine_action", "Ignore") # Posted / Paid / Ignore
        
        try:
            # Set book status return
            status = "Returned"
            if condition == "Damaged":
                status = "Damaged"
                custom_fine += Decimal(str(lib_settings["damaged_book_penalty"]))
            elif condition == "Lost":
                status = "Lost"
                custom_fine += Decimal(str(lib_settings["lost_book_penalty"]))
                
            # If Lost, reduce total copies of the book by 1
            if condition == "Lost":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE library_books SET total_copies = MAX(total_copies - 1, 0) WHERE book_id = %s",
                        [issue["book_id"]]
                    )
            
            fine_paid = 1 if fine_action == "Paid" else 0
            
            # Update Lending record
            update_record(
                request,
                "library_issues",
                "issue_id",
                issue_id,
                {
                    "return_date": today_text(),
                    "status": status,
                    "book_condition": condition,
                    "fine_amount": custom_fine,
                    "fine_paid": fine_paid,
                    "return_librarian_id": request.user.id if request.user.is_authenticated else None,
                }
            )
            
            # Sync copies
            update_book_availability(issue["book_id"])
            
            # Integrate with Fees Management if learner and has fine
            borrower_name = issue["student_name"] or issue["staff_name"] or "Member"
            if issue["pupil_id"] and custom_fine > 0 and fine_action == "Posted":
                student = Student.objects.get(pk=issue["pupil_id"])
                post_library_fine(
                    request, 
                    student, 
                    custom_fine, 
                    f"Book '{issue['title']}' returned in stage '{condition}'. Fines: ${custom_fine}."
                )
                
            # Audit
            audit_action(request, "Return Book", f"Book '{issue['title']}' returned by {borrower_name} as '{condition}'. Fine: ${custom_fine} ({fine_action}).")
            
            # Check Reservations waiting list
            check_reservations_queue(request, issue["book_id"])
            
            messages.success(request, "Book marked as returned successfully.")
            return redirect("library_issues")
            
        except Exception as e:
            messages.error(request, f"Error processing return: {e}")
            
    context = {
        "title": "Return Book Copy",
        "issue": issue,
        "overdue_days": overdue_days,
        "overdue_fine": overdue_fine,
        "damaged_penalty": lib_settings["damaged_book_penalty"],
        "lost_penalty": lib_settings["lost_book_penalty"],
        "school_settings": school_settings(),
    }
    return render(request, "library/return_form.html", context)


# Check reservation waitlists and notify first member
def check_reservations_queue(request, book_id):
    # Retrieve first pending reservation
    reservation = one_row(
        "SELECT * FROM library_reservations WHERE book_id = %s AND status = 'Pending' ORDER BY reservation_id ASC LIMIT 1",
        [book_id]
    )
    if not reservation:
        return
        
    book = LibraryBook.objects.filter(pk=book_id).first()
    if not book or book.available_copies <= 0:
        return
        
    # Mark reservation as Available for collection
    update_record(
        request,
        "library_reservations",
        "reservation_id",
        reservation["reservation_id"],
        {"status": "Available"}
    )
    
    # Notify borrower
    msg = f"Your reserved library book '{book.title}' is now available for collection at the library desk."
    if reservation["pupil_id"]:
        log_library_notification(request, reservation["pupil_id"], "Portal", "Reservation Available", msg)
    # Auditing
    audit_action(request, "Reservation Ready", f"Reservation ID {reservation['reservation_id']} set to 'Available'. Notify borrower.")


@permission_required("library.manage")
def reservation_list(request):
    reservations = dict_rows(
        """
        SELECT r.reservation_id, b.title, r.reserve_date, r.status,
               p.first_name || ' ' || p.surname AS student_name, p.admission_no,
               e.first_name || ' ' || e.surname AS staff_name, e.employee_number
        FROM library_reservations r
        JOIN library_books b ON b.book_id = r.book_id
        LEFT JOIN pupils p ON p.pupil_id = r.pupil_id
        LEFT JOIN hr_employee_profiles e ON e.id = r.staff_id
        ORDER BY r.reservation_id DESC
        """
    )
    
    context = {
        "title": "Book Reservations",
        "reservations": reservations,
        "school_settings": school_settings(),
    }
    return render(request, "library/reservation_list.html", context)


@permission_required("library.manage")
def reservation_action(request, reservation_id, action):
    res = one_row("SELECT * FROM library_reservations WHERE reservation_id = %s", [reservation_id])
    if not res:
        raise Http404("Reservation not found.")
        
    try:
        if action == "collect":
            # Issue the reserved book directly to the member
            book = LibraryBook.objects.get(pk=res["book_id"])
            if book.available_copies <= 0:
                raise ValueError("No available copies of this book to collect.")
                
            due_days = get_library_settings()["borrow_duration_days"]
            due_date = (datetime.date.today() + datetime.timedelta(days=int(due_days))).isoformat()
            
            issue_id = insert_record(
                request,
                "library_issues",
                {
                    "book_id": res["book_id"],
                    "pupil_id": res["pupil_id"],
                    "staff_id": res["staff_id"],
                    "issue_date": today_text(),
                    "due_date": due_date,
                    "status": "Borrowed",
                    "librarian_id": request.user.id if request.user.is_authenticated else None,
                }
            )
            update_book_availability(res["book_id"])
            
            # Close reservation
            update_record(request, "library_reservations", "reservation_id", reservation_id, {"status": "Collected"})
            audit_action(request, "Reservation Collected", f"Reserved book '{book.title}' collected. Issued ID: {issue_id}")
            messages.success(request, "Reserved book collected and issued successfully.")
            
        elif action == "cancel":
            update_record(request, "library_reservations", "reservation_id", reservation_id, {"status": "Cancelled"})
            # Check availability if this was set to Available so another borrower gets notified
            if res["status"] == "Available":
                check_reservations_queue(request, res["book_id"])
            audit_action(request, "Reservation Cancelled", f"Cancelled reservation ID: {reservation_id}")
            messages.success(request, "Reservation cancelled successfully.")
            
    except Exception as e:
        messages.error(request, f"Error processing action: {e}")
        
    return redirect("library_reservations")


@permission_required("library.manage")
def digital_library(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        category = request.POST.get("category", "eBook")
        allowed_roles = ",".join(request.POST.getlist("allowed_roles")) or "Teacher,Student"
        
        if not title or "file" not in request.FILES:
            messages.error(request, "Title and Digital resource file are mandatory.")
        else:
            try:
                uploaded_file = request.FILES["file"]
                
                # Setup safe file upload path
                abs_dir = os.path.join(settings.MEDIA_ROOT, "digital_library")
                os.makedirs(abs_dir, exist_ok=True)
                
                ext = os.path.splitext(uploaded_file.name)[1]
                filename = f"res_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                dest_path = os.path.join(abs_dir, filename)
                
                with open(dest_path, "wb+") as f:
                    for chunk in uploaded_file.chunks():
                        f.write(chunk)
                        
                file_rel_path = f"digital_library/{filename}"
                
                insert_record(
                    request,
                    "library_digital_resources",
                    {
                        "title": title,
                        "category": category,
                        "file_path": file_rel_path,
                        "original_filename": uploaded_file.name,
                        "uploaded_by": request.user.id if request.user.is_authenticated else None,
                        "uploaded_at": today_text(),
                        "allowed_roles": allowed_roles,
                    }
                )
                audit_action(request, "Upload Resource", f"Uploaded digital resource '{title}' ({category})")
                messages.success(request, "Digital resource uploaded successfully.")
                return redirect("digital_library")
                
            except Exception as e:
                messages.error(request, f"Failed to save upload: {e}")
                
    resources = dict_rows("SELECT * FROM library_digital_resources ORDER BY resource_id DESC")
    context = {
        "title": "Digital Resource Center",
        "resources": resources,
        "school_settings": school_settings(),
    }
    return render(request, "library/digital_library.html", context)


@login_required
def download_digital_resource(request, resource_id):
    res = one_row("SELECT * FROM library_digital_resources WHERE resource_id = %s", [resource_id])
    if not res:
        raise Http404("Digital resource not found.")
        
    # Check permissions
    role = normalized_role(request.user)
    # If student, session student_pupil_id is active
    if request.session.get("student_pupil_id"):
        role = "Student"
        
    allowed = [r.strip() for r in (res["allowed_roles"] or "Teacher,Student").split(",")]
    if role != "Super Admin" and role not in allowed:
        messages.error(request, "You do not have download permissions for this resource.")
        return redirect("portal_dashboard" if role == "Student" else "library_dashboard")
        
    abs_path = os.path.join(settings.MEDIA_ROOT, res["file_path"].replace("/", os.sep))
    if not os.path.exists(abs_path):
        raise Http404("Resource file is missing from the server.")
        
    audit_action(request, "Download Resource", f"Downloaded digital resource '{res['title']}' (ID: {resource_id})")
    return FileResponse(open(abs_path, "rb"), as_attachment=True, filename=res["original_filename"] or os.path.basename(abs_path))


@permission_required("library.manage")
def fine_management(request):
    lib_settings = get_library_settings()
    
    if request.method == "POST" and "update_settings" in request.POST:
        fine = request.POST.get("daily_overdue_fine", "0.50")
        damaged = request.POST.get("damaged_book_penalty", "5.00")
        lost = request.POST.get("lost_book_penalty", "15.00")
        max_books = request.POST.get("max_books_allowed", "3")
        duration = request.POST.get("borrow_duration_days", "14")
        
        try:
            update_record(
                request,
                "library_settings",
                "setting_id",
                1,
                {
                    "daily_overdue_fine": Decimal(fine),
                    "damaged_book_penalty": Decimal(damaged),
                    "lost_book_penalty": Decimal(lost),
                    "max_books_allowed": int(max_books),
                    "borrow_duration_days": int(duration),
                }
            )
            audit_action(request, "Update Library Settings", "Updated fine configurations and limits.")
            messages.success(request, "Library configurations saved successfully.")
            return redirect("library_fines")
        except Exception as e:
            messages.error(request, f"Error updating settings: {e}")
            
    fines = dict_rows(
        """
        SELECT i.issue_id, b.title, i.fine_amount, i.fine_paid, i.return_date, i.book_condition,
               p.first_name || ' ' || p.surname AS student_name, p.admission_no
        FROM library_issues i
        JOIN library_books b ON b.book_id = i.book_id
        JOIN pupils p ON p.pupil_id = i.pupil_id
        WHERE i.fine_amount > 0
        ORDER BY i.return_date DESC
        """
    )
    
    context = {
        "title": "Fines & Penalty Manager",
        "settings": lib_settings,
        "fines": fines,
        "school_settings": school_settings(),
    }
    return render(request, "library/fine_management.html", context)


@permission_required("library.manage")
def library_reports(request):
    report_type = request.GET.get("type", "catalogue")
    export_format = request.GET.get("format", "")
    
    title_label = "Library Catalogue Report"
    headers = []
    rows = []
    
    if report_type == "catalogue":
        title_label = "Library Resource Catalogue"
        headers = ["Title", "Author", "ISBN", "Category", "Copies", "Available", "Location", "Status"]
        db_rows = dict_rows("SELECT title, author, isbn, category, total_copies, available_copies, shelf_location, status FROM library_books WHERE status != 'Archived' ORDER BY title")
        rows = [[r["title"], r["author"], r["isbn"], r["category"], r["total_copies"], r["available_copies"], r["shelf_location"], r["status"]] for r in db_rows]
        
    elif report_type == "borrowed":
        title_label = "Borrowed Books Report"
        headers = ["Book Title", "Borrower", "Card Number", "Issued Date", "Due Date", "Status"]
        db_rows = dict_rows(
            """
            SELECT b.title, i.issue_date, i.due_date, i.status,
                   COALESCE(p.first_name || ' ' || p.surname, e.first_name || ' ' || e.surname) AS borrower_name,
                   COALESCE(m.card_number, 'N/A') AS card_no
            FROM library_issues i
            JOIN library_books b ON b.book_id = i.book_id
            LEFT JOIN pupils p ON p.pupil_id = i.pupil_id
            LEFT JOIN hr_employee_profiles e ON e.id = i.staff_id
            LEFT JOIN library_members m ON m.pupil_id = i.pupil_id OR m.staff_id = i.staff_id
            WHERE i.status = 'Borrowed'
            ORDER BY i.due_date ASC
            """
        )
        rows = [[r["title"], r["borrower_name"], r["card_no"], r["issue_date"], r["due_date"], r["status"]] for r in db_rows]
        
    elif report_type == "overdue":
        title_label = "Overdue Books Registry"
        headers = ["Book Title", "Borrower", "Due Date", "Days Late", "Fine Accrued", "Status"]
        db_rows = dict_rows(
            """
            SELECT b.title, i.due_date, i.status, b.fine_per_day,
                   COALESCE(p.first_name || ' ' || p.surname, e.first_name || ' ' || e.surname) AS borrower_name
            FROM library_issues i
            JOIN library_books b ON b.book_id = i.book_id
            LEFT JOIN pupils p ON p.pupil_id = i.pupil_id
            LEFT JOIN hr_employee_profiles e ON e.id = i.staff_id
            WHERE i.status = 'Borrowed' AND i.due_date < %s
            ORDER BY i.due_date ASC
            """,
            [today_text()]
        )
        today = datetime.date.today()
        rows = []
        for r in db_rows:
            due = datetime.date.fromisoformat(r["due_date"])
            days = (today - due).days
            accrued = Decimal(days) * Decimal(str(r["fine_per_day"] or 0.50))
            rows.append([r["title"], r["borrower_name"], r["due_date"], days, f"${accrued}", r["status"]])
            
    elif report_type == "fines":
        title_label = "Fines Collections & Outstanding"
        headers = ["Borrower", "Book", "Returned Date", "Condition", "Amount", "Receipt status"]
        db_rows = dict_rows(
            """
            SELECT b.title, i.fine_amount, i.fine_paid, i.return_date, i.book_condition,
                   p.first_name || ' ' || p.surname AS borrower_name
            FROM library_issues i
            JOIN library_books b ON b.book_id = i.book_id
            JOIN pupils p ON p.pupil_id = i.pupil_id
            WHERE i.fine_amount > 0
            ORDER BY i.return_date DESC
            """
        )
        rows = [[r["borrower_name"], r["title"], r["return_date"], r["book_condition"], f"${r['fine_amount']}", "Paid" if r["fine_paid"] == 1 else "Unpaid/Invoiced"] for r in db_rows]

    # Handle Exports
    if export_format == "csv":
        import csv
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={report_type}_report.csv"
        writer = csv.writer(response)
        writer.writerow([title_label])
        writer.writerow([])
        writer.writerow(headers)
        writer.writerows(rows)
        return response
        
    elif export_format == "excel":
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report_type.capitalize()
        ws.append([title_label])
        ws.append([])
        ws.append(headers)
        for r in rows:
            ws.append(r)
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename={report_type}_report.xlsx"
        wb.save(response)
        return response
        
    elif export_format == "pdf":
        from school_system_django.native import simple_pdf
        return simple_pdf(request, title_label, headers, rows)

    context = {
        "title": "Library Reporting Desk",
        "report_type": report_type,
        "title_label": title_label,
        "headers": headers,
        "rows": rows,
        "school_settings": school_settings(),
    }
    return render(request, "library/reports.html", context)


# ================= STUDENT PORTAL LIBRARY VIEWS =================

from portals.views import student_portal_required

@student_portal_required
def student_portal_library(request, pupil):
    pupil_id = pupil["pupil_id"]
    pupil_model = Student.objects.get(pk=pupil_id)
    pupil = pupil_model
    
    # Member card info
    member = one_row("SELECT * FROM library_members WHERE pupil_id = %s", [pupil_id])
    
    # Active textbook loans & library issues
    loans = dict_rows(
        """
        SELECT b.title, i.issue_date, i.due_date, i.status, i.fine_amount
        FROM library_issues i
        JOIN library_books b ON b.book_id = i.book_id
        WHERE i.pupil_id = %s AND i.status = 'Borrowed'
        ORDER BY i.due_date ASC
        """,
        [pupil_id]
    )
    
    history = dict_rows(
        """
        SELECT b.title, i.issue_date, i.return_date, i.status, i.fine_amount, i.book_condition
        FROM library_issues i
        JOIN library_books b ON b.book_id = i.book_id
        WHERE i.pupil_id = %s AND i.status != 'Borrowed'
        ORDER BY i.return_date DESC
        LIMIT 10
        """,
        [pupil_id]
    )
    
    # Check textbook loans compatibility
    textbook_loans = []
    if table_exists("textbook_loans"):
        textbook_loans = dict_rows(
            "SELECT book_name, borrowed_date, return_date, status, notes FROM textbook_loans WHERE pupil_id = %s ORDER BY borrowed_date DESC",
            [pupil_id]
        )
        
    # Digital books recommendations
    digital_resources = dict_rows(
        "SELECT resource_id, title, category, uploaded_at, allowed_roles FROM library_digital_resources ORDER BY resource_id DESC LIMIT 6"
    )
    
    # Filter digital resources by user role (Student)
    filtered_digital = []
    for r in digital_resources:
        roles = [role.strip() for role in (r["allowed_roles"] or "Teacher,Student").split(",")]
        if "Student" in roles:
            filtered_digital.append(r)
            
    # Check overdue count
    today = today_text()
    overdue_count = sum(1 for loan in loans if loan["due_date"] < today)
    
    context = {
        "title": "Digital Book Shelves",
        "pupil": pupil,
        "member": member,
        "loans": loans,
        "history": history,
        "textbook_loans": textbook_loans,
        "digital_resources": filtered_digital,
        "overdue_count": overdue_count,
        "today": today,
        "school_settings": school_settings(),
    }
    return render(request, "portals/student_library.html", context)


def student_portal_reserve_book(request, book_id):
    pupil_id = request.session.get("student_pupil_id")
    if not pupil_id:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)
        
    try:
        book = get_object_or_404(LibraryBook, pk=book_id)
        if book.available_copies > 0:
            return JsonResponse({"status": "error", "message": "Copies are currently available in library. No need to reserve."})
            
        # Check active reservation
        exists = one_row(
            "SELECT 1 FROM library_reservations WHERE pupil_id = %s AND book_id = %s AND status = 'Pending'",
            [pupil_id, book_id]
        )
        if exists:
            return JsonResponse({"status": "error", "message": "You already have a pending reservation for this book."})
            
        # Create reservation waitlist
        insert_record(
            request,
            "library_reservations",
            {
                "book_id": book_id,
                "pupil_id": pupil_id,
                "staff_id": None,
                "reserve_date": today_text(),
                "status": "Pending",
                "notification_sent": 0,
            }
        )
        audit_action(request, "Student Reserve Book", f"Student reserved book '{book.title}' (Book ID: {book_id})")
        return JsonResponse({"status": "success", "message": f"Successfully joined waitlist for '{book.title}'."})
        
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})
