from django.db import connection

from school_system_django.native import dict_rows, one_row, table_columns, table_exists, today_text


RETURNED_STATUSES = ["Returned", "Cleared", "Cancelled"]


def textbook_has_book_id():
    return table_exists("textbook_loans") and "book_id" in table_columns("textbook_loans")


def backfill_textbook_book_ids():
    if not textbook_has_book_id() or not table_exists("library_books"):
        return
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                """
                UPDATE textbook_loans tl
                SET book_id = lb.book_id
                FROM library_books lb
                WHERE tl.book_id IS NULL
                  AND tl.book_name IS NOT NULL
                  AND UPPER(TRIM(tl.book_name)) = UPPER(TRIM(lb.title))
                """
            )
        else:
            cursor.execute(
                """
                UPDATE textbook_loans
                SET book_id = (
                    SELECT lb.book_id
                    FROM library_books lb
                    WHERE UPPER(TRIM(lb.title)) = UPPER(TRIM(textbook_loans.book_name))
                    ORDER BY lb.book_id
                    LIMIT 1
                )
                WHERE book_id IS NULL
                  AND book_name IS NOT NULL
                  AND TRIM(book_name) != ''
                """
            )


def _not_returned_clause(prefix=""):
    column = f"{prefix}.status" if prefix else "status"
    placeholders = ", ".join(["%s"] * len(RETURNED_STATUSES))
    return f"({column} IS NULL OR {column} = '' OR {column} NOT IN ({placeholders}))", list(RETURNED_STATUSES)


def _book_filter_clause(book_id=None, title=None, prefix="", include_unlinked_title=True):
    table_prefix = f"{prefix}." if prefix else ""
    clauses = []
    params = []
    has_book_id = textbook_has_book_id()
    if has_book_id and book_id not in {None, ""}:
        clauses.append(f"{table_prefix}book_id = %s")
        params.append(book_id)
        if include_unlinked_title and title:
            clauses.append(f"({table_prefix}book_id IS NULL AND UPPER(TRIM({table_prefix}book_name)) = UPPER(TRIM(%s)))")
            params.append(title)
    elif title:
        clauses.append(f"UPPER(TRIM({table_prefix}book_name)) = UPPER(TRIM(%s))")
        params.append(title)
    else:
        clauses.append("1=0")
    return "(" + " OR ".join(clauses) + ")", params


def active_textbook_loan_count(book_id=None, title=None, exclude_loan_id=None):
    if not table_exists("textbook_loans"):
        return 0
    status_clause, params = _not_returned_clause()
    filter_clause, filter_params = _book_filter_clause(book_id=book_id, title=title)
    where = [status_clause, filter_clause]
    params.extend(filter_params)
    if exclude_loan_id:
        where.append("loan_id != %s")
        params.append(exclude_loan_id)
    row = one_row(f"SELECT COUNT(*) AS total FROM textbook_loans WHERE {' AND '.join(where)}", params)
    return int(row["total"] or 0) if row else 0


def overdue_textbook_loan_count(book_id=None, title=None):
    if not table_exists("textbook_loans"):
        return 0
    status_clause, params = _not_returned_clause()
    filter_clause, filter_params = _book_filter_clause(book_id=book_id, title=title)
    params.extend(filter_params)
    params.append(today_text())
    row = one_row(
        f"""
        SELECT COUNT(*) AS total
        FROM textbook_loans
        WHERE {status_clause}
          AND {filter_clause}
          AND return_date IS NOT NULL
          AND return_date != ''
          AND return_date < %s
        """,
        params,
    )
    return int(row["total"] or 0) if row else 0


def active_library_issue_count(book_id):
    if not table_exists("library_issues") or book_id in {None, ""}:
        return 0
    status_clause, params = _not_returned_clause()
    params.append(book_id)
    row = one_row(
        f"SELECT COUNT(*) AS total FROM library_issues WHERE {status_clause} AND book_id = %s",
        params,
    )
    return int(row["total"] or 0) if row else 0


def overdue_library_issue_count(book_id):
    if not table_exists("library_issues") or book_id in {None, ""}:
        return 0
    status_clause, params = _not_returned_clause()
    params.extend([book_id, today_text()])
    row = one_row(
        f"""
        SELECT COUNT(*) AS total
        FROM library_issues
        WHERE {status_clause}
          AND book_id = %s
          AND due_date IS NOT NULL
          AND due_date != ''
          AND due_date < %s
        """,
        params,
    )
    return int(row["total"] or 0) if row else 0


def book_from_loan(loan):
    if not loan or not table_exists("library_books"):
        return None
    if textbook_has_book_id() and loan.get("book_id"):
        book = one_row("SELECT * FROM library_books WHERE book_id = %s", [loan["book_id"]])
        if book:
            return book
    title = loan.get("book_name")
    if title:
        return one_row(
            "SELECT * FROM library_books WHERE UPPER(TRIM(title)) = UPPER(TRIM(%s)) ORDER BY book_id LIMIT 1",
            [title],
        )
    return None


def available_copies_for_issue(book_id, exclude_loan_id=None):
    if not table_exists("library_books") or book_id in {None, ""}:
        return 0
    book = one_row("SELECT * FROM library_books WHERE book_id = %s", [book_id])
    if not book:
        return 0
    total = int(book.get("total_copies") or 0)
    issued = active_textbook_loan_count(book_id=book_id, title=book.get("title"), exclude_loan_id=exclude_loan_id)
    issued += active_library_issue_count(book_id)
    return max(total - issued, 0)


def sync_book_availability(book_id):
    if not table_exists("library_books") or book_id in {None, ""}:
        return None
    book = one_row("SELECT * FROM library_books WHERE book_id = %s", [book_id])
    if not book:
        return None
    available = available_copies_for_issue(book_id)
    if "available_copies" in table_columns("library_books"):
        with connection.cursor() as cursor:
            cursor.execute("UPDATE library_books SET available_copies = %s WHERE book_id = %s", [available, book_id])
    book["available_copies"] = available
    book["issued_count"] = active_textbook_loan_count(book_id=book_id, title=book.get("title")) + active_library_issue_count(book_id)
    book["overdue_count"] = overdue_textbook_loan_count(book_id=book_id, title=book.get("title")) + overdue_library_issue_count(book_id)
    return book


def sync_all_library_availability():
    if not table_exists("library_books"):
        return []
    backfill_textbook_book_ids()
    rows = dict_rows("SELECT book_id FROM library_books ORDER BY title")
    return [sync_book_availability(row["book_id"]) for row in rows]


def library_book_rows(q=""):
    if not table_exists("library_books"):
        return []
    sync_all_library_availability()
    params = []
    where = ""
    if q:
        where = "WHERE title LIKE %s OR author LIKE %s OR isbn LIKE %s OR category LIKE %s OR status LIKE %s"
        params = [f"%{q}%"] * 5
    rows = dict_rows(
        f"""
        SELECT book_id, title, author, isbn, category, total_copies, available_copies, fine_per_day, status
        FROM library_books
        {where}
        ORDER BY title
        """,
        params,
    )
    for row in rows:
        row["issued_count"] = active_textbook_loan_count(book_id=row.get("book_id"), title=row.get("title")) + active_library_issue_count(row.get("book_id"))
        row["overdue_count"] = overdue_textbook_loan_count(book_id=row.get("book_id"), title=row.get("title")) + overdue_library_issue_count(row.get("book_id"))
        row["stock_status"] = "Out of stock" if int(row.get("available_copies") or 0) <= 0 else "Available"
    return rows


def book_options(include_book_id=None):
    if not table_exists("library_books"):
        return []
    sync_all_library_availability()
    params = []
    where = "WHERE status = 'Active'"
    if include_book_id:
        where = "WHERE status = 'Active' OR book_id = %s"
        params.append(include_book_id)
    return dict_rows(
        f"""
        SELECT book_id, title, author, available_copies, total_copies, status
        FROM library_books
        {where}
        ORDER BY title
        """,
        params,
    )
