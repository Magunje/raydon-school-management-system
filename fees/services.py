import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction
from django.utils import timezone

from accounts.decorators import user_role
from school_system_django.native import (
    audit_action,
    compact_class_label,
    dict_rows,
    insert_record,
    legacy_user_id,
    now_text,
    one_row,
    school_settings,
    table_exists,
    today_text,
)


MONEY_ZERO = Decimal("0.00")
O_LEVEL_FEE_AMOUNT = Decimal("100.00")
A_LEVEL_FEE_AMOUNT = Decimal("150.00")
STANDARD_CLASS_NUMBERS = range(1, 7)
STANDARD_CLASS_FEE_NOTE = "Default fee by level: O Level USD 100 per term, A Level USD 150 per term. Amounts remain configurable."
FINANCE_EDIT_ROLES = {"Super Admin", "Administrator", "Admin"}
FINANCE_RECORD_ROLES = FINANCE_EDIT_ROLES | {"Bursar / Accounts Clerk", "Accountant"}
PAYMENT_ALLOWED_STATUSES = {"", "Active"}


def money(value):
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return MONEY_ZERO


def money_float(value):
    return float(money(value))


def term_number(term):
    match = re.search(r"\d+", str(term or ""))
    return int(match.group(0)) if match else 0


def next_term_period(term, year):
    number = term_number(term)
    year = int(year or timezone.localdate().year)
    if number <= 0:
        return "Term 1", year
    if number >= 3:
        return "Term 1", year + 1
    return f"Term {number + 1}", year


def term_key(year, term):
    return (int(year or 0), term_number(term), str(term or ""))


def is_before_period(item, term, year):
    return term_key(item.get("year"), item.get("term")) < term_key(year, term)


def current_period():
    settings = school_settings()
    return settings.get("current_term") or "Term 1", int(settings.get("current_year") or timezone.localdate().year)


def can_record_payments(user):
    return user.is_superuser or user_role(user) in FINANCE_RECORD_ROLES


def can_edit_receipts(user):
    return user.is_superuser or user_role(user) in FINANCE_EDIT_ROLES


def can_delete_receipts(user):
    return user.is_superuser or user_role(user) == "Super Admin"


def student_status(pupil):
    return str((pupil or {}).get("status") or "Active").strip()


def can_receive_payment(pupil):
    return student_status(pupil) in PAYMENT_ALLOWED_STATUSES


def assert_can_receive_payment(pupil):
    if not can_receive_payment(pupil):
        raise ValueError(f"Cannot record payment for archived student {pupil.get('admission_no')}: status is {student_status(pupil)}.")


def pupil_by_admission(admission_no):
    return one_row("SELECT * FROM pupils WHERE UPPER(admission_no) = %s", [str(admission_no or "").strip().upper()])


def pupil_by_identifier(identifier):
    value = str(identifier or "").strip()
    if not value:
        return None

    # 1) Internal id
    if value.isdigit():
        return one_row("SELECT * FROM pupils WHERE pupil_id = %s", [value])

    upper = value.upper()

    # 2) Admission number-like inputs
    # e.g. A26001, ADM-A26001 etc.
    if any(ch.isdigit() for ch in value) or upper.startswith("A") or upper.startswith("ADM"):
        # Try admission first.
        pupil = pupil_by_admission(value)
        if pupil:
            return pupil

    # 3) Name lookup (picker posts full name into pupil_query)
    # We try full first_name+surname first; then fallback to partial surname.
    parts = [p for p in re.split(r"\s+", value) if p]
    if len(parts) >= 2:
        # Assume last part is surname.
        first = parts[0]
        surname = parts[-1]
        pupil = one_row(
            "SELECT * FROM pupils WHERE UPPER(first_name) = %s AND UPPER(surname) = %s LIMIT 2",
            [first.upper(), surname.upper()],
        )
        if pupil:
            return pupil

        pupil = one_row(
            "SELECT * FROM pupils WHERE UPPER(surname) = %s AND UPPER(first_name) LIKE %s LIMIT 2",
            [surname.upper(), f"{first.upper()}%"],
        )
        if pupil:
            return pupil

    compact_match = re.fullmatch(r"(\d+)\s*([A-Za-z]+)", value)
    if compact_match:
        grade_part, stream_part = compact_match.groups()
        pupil = one_row(
            """
            SELECT *
            FROM pupils
            WHERE (grade LIKE %s OR CAST(grade_id AS TEXT) = %s)
              AND UPPER(class_stream) = %s
            ORDER BY surname, first_name
            LIMIT 1
            """,
            [f"%{grade_part}%", grade_part, stream_part.upper()],
        )
        if pupil:
            return pupil

    # Last resort: admission/name/class/guardian contains match.
    return one_row(
        """
        SELECT *
        FROM pupils
        WHERE UPPER(admission_no) LIKE %s
           OR UPPER(first_name) LIKE %s
           OR UPPER(surname) LIKE %s
           OR UPPER(guardian_name) LIKE %s
           OR UPPER(grade) LIKE %s
           OR UPPER(class_stream) LIKE %s
        ORDER BY
            CASE
                WHEN UPPER(admission_no) = %s THEN 0
                WHEN UPPER(first_name || ' ' || surname) = %s THEN 1
                ELSE 2
            END,
            surname,
            first_name
        LIMIT 1
        """,
        [f"%{value.upper()}%"] * 6 + [value.upper(), value.upper()],
    )



def admission_number_year(value=None):
    if not value:
        return timezone.localdate().year
    text = str(value)
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return int(value)


def next_admission_no(year=None):
    year = admission_number_year(year)
    prefix = f"A{year % 100:02d}"
    rows = dict_rows(
        "SELECT admission_no FROM pupils WHERE admission_no LIKE %s ORDER BY admission_no DESC LIMIT 100",
        [f"{prefix}%"],
    )
    highest = 0
    for row in rows:
        match = re.fullmatch(rf"{prefix}(\d+)", str(row.get("admission_no") or ""), flags=re.IGNORECASE)
        if match:
            highest = max(highest, int(match.group(1)))
    while True:
        highest += 1
        candidate = f"{prefix}{highest:03d}"
        if not one_row("SELECT pupil_id FROM pupils WHERE UPPER(admission_no) = %s", [candidate]):
            return candidate


def next_receipt_no(year=None):
    year = int(year or timezone.localdate().year)
    prefix = f"RCT{year}"
    rows = dict_rows(
        "SELECT receipt_no FROM payments WHERE receipt_no LIKE %s ORDER BY receipt_no DESC LIMIT 100",
        [f"{prefix}%"],
    )
    highest = 0
    for row in rows:
        match = re.fullmatch(rf"{prefix}(\d+)", str(row.get("receipt_no") or ""))
        if match:
            highest = max(highest, int(match.group(1)))
    while True:
        highest += 1
        candidate = f"{prefix}{highest:05d}"
        if not one_row("SELECT payment_id FROM payments WHERE receipt_no = %s", [candidate]):
            return candidate


def standard_class_number(grade=None, grade_id=None):
    for value in (grade_id, grade):
        text = str(value or "").strip()
        if not text:
            continue
        if text.isdigit():
            number = int(text)
        else:
            match = re.search(r"\d+", text)
            number = int(match.group(0)) if match else 0
        if number in STANDARD_CLASS_NUMBERS:
            return number
    return None


def academic_level_for_class_number(number):
    number = int(number or 0)
    if 1 <= number <= 4:
        return "O Level"
    if 5 <= number <= 6:
        return "A Level"
    return ""


def default_fee_amount_for_class_number(number):
    return A_LEVEL_FEE_AMOUNT if academic_level_for_class_number(number) == "A Level" else O_LEVEL_FEE_AMOUNT


def fee_grade_label(number):
    number = int(number or 0)
    if 1 <= number <= 6:
        return f"Form {number}"
    return f"Form {number}"


def fee_row_class_number(row):
    return standard_class_number(row.get("grade"), row.get("grade_id"))


def standard_fee_rows(grade_number, term, year):
    return [
        row
        for row in dict_rows(
            """
            SELECT *
            FROM fees_structure
            WHERE term = %s AND year = %s
            ORDER BY fee_id
            """,
            [term, year],
        )
        if fee_row_class_number(row) == grade_number
    ]


def normalize_standard_fee_row(row, grade_number):
    if not row:
        return None
    updates = {}
    if not row.get("grade_id"):
        updates["grade_id"] = grade_number
    if updates:
        assignments = ", ".join(f"{key} = %s" for key in updates)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE fees_structure SET {assignments} WHERE fee_id = %s",
                list(updates.values()) + [row["fee_id"]],
            )
        return one_row("SELECT * FROM fees_structure WHERE fee_id = %s", [row["fee_id"]])
    return row


def ensure_standard_fee_structure(term, year, grade_number):
    if not table_exists("fees_structure") or grade_number not in STANDARD_CLASS_NUMBERS:
        return None
    rows = standard_fee_rows(grade_number, term, year)
    if rows:
        normalized_rows = [normalize_standard_fee_row(row, grade_number) for row in rows]
        return normalized_rows[0]
    fee_id = insert_record(
        None,
            "fees_structure",
        {
            "grade": fee_grade_label(grade_number),
            "grade_id": grade_number,
            "term": term,
            "year": year,
            "amount_required": default_fee_amount_for_class_number(grade_number),
            "payment_deadline": today_text(),
            "notes": f"{academic_level_for_class_number(grade_number)}. {STANDARD_CLASS_FEE_NOTE}",
        },
    )
    if fee_id:
        return one_row("SELECT * FROM fees_structure WHERE fee_id = %s", [fee_id])
    return one_row(
        """
        SELECT *
        FROM fees_structure
        WHERE grade_id = %s AND term = %s AND year = %s
        ORDER BY fee_id
        LIMIT 1
        """,
        [grade_number, term, year],
    )


def ensure_standard_fee_structures(term, year):
    return {
        grade_number: ensure_standard_fee_structure(term, year, grade_number)
        for grade_number in STANDARD_CLASS_NUMBERS
    }


def fee_structure_for(pupil, term, year):
    grade_number = standard_class_number(pupil.get("grade"), pupil.get("grade_id"))
    if grade_number:
        ensure_standard_fee_structures(term, year)

    if grade_number:
        row = one_row(
            """
            SELECT * FROM fees_structure
            WHERE grade_id = %s AND term = %s AND year = %s
            LIMIT 1
            """,
            [grade_number, term, year],
        )
        if row:
            return normalize_standard_fee_row(row, grade_number)
    row = one_row(
        """
        SELECT * FROM fees_structure
        WHERE grade = %s AND term = %s AND year = %s
        LIMIT 1
        """,
        [pupil.get("grade"), term, year],
    )
    if row:
        return normalize_standard_fee_row(row, grade_number) if grade_number else row
    row = one_row(
        """
        SELECT * FROM fees_structure
        WHERE grade_id = %s AND term = %s AND year = %s
        LIMIT 1
        """,
        [pupil.get("grade_id"), term, year],
    ) if pupil.get("grade_id") else None
    if row:
        return normalize_standard_fee_row(row, grade_number) if grade_number else row
    if grade_number:
        return ensure_standard_fee_structure(term, year, grade_number)
    return None


def ensure_term_bill(pupil, term, year):
    existing = one_row(
        "SELECT * FROM term_bills WHERE pupil_id = %s AND term = %s AND year = %s",
        [pupil["pupil_id"], term, year],
    )
    if existing:
        return existing
    fee = fee_structure_for(pupil, term, year)
    if not fee:
        return None
    bill_id = insert_record(
        None,
        "term_bills",
        {
            "pupil_id": pupil["pupil_id"],
            "fee_id": fee.get("fee_id"),
            "term": term,
            "year": year,
            "amount_billed": fee.get("amount_required"),
            "billed_on": today_text(),
            "due_date": fee.get("payment_deadline") or today_text(),
            "status": "Billed",
        },
    )
    bill = one_row("SELECT * FROM term_bills WHERE bill_id = %s", [bill_id])
    if bill:
        # Check for unallocated payments (credit balance)
        unallocated_payments = dict_rows(
            """
            SELECT p.payment_id, p.amount_paid, p.fee_id, p.term, p.year,
                   COALESCE(SUM(pa.amount_allocated), 0) AS total_allocated
            FROM payments p
            LEFT JOIN payment_allocations pa ON pa.payment_id = p.payment_id
            WHERE p.pupil_id = %s
            GROUP BY p.payment_id, p.amount_paid, p.fee_id, p.term, p.year
            HAVING COALESCE(SUM(pa.amount_allocated), 0) < p.amount_paid
            ORDER BY p.payment_date ASC, p.payment_id ASC
            """,
            [pupil["pupil_id"]]
        )
        if unallocated_payments:
            bill_amount = money(bill["amount_billed"])
            adjustments_row = one_row(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM balance_adjustments WHERE pupil_id = %s AND term = %s AND year = %s",
                [pupil["pupil_id"], term, year]
            )
            adjustments_amount = money(adjustments_row["total"] if adjustments_row else 0)
            allocations_row = one_row(
                "SELECT COALESCE(SUM(amount_allocated), 0) AS total FROM payment_allocations WHERE pupil_id = %s AND term = %s AND year = %s",
                [pupil["pupil_id"], term, year]
            )
            allocated_already = money(allocations_row["total"] if allocations_row else 0)
            
            remaining_bill_balance = bill_amount + adjustments_amount - allocated_already
            
            for payment in unallocated_payments:
                if remaining_bill_balance <= 0:
                    break
                payment_id = payment["payment_id"]
                amount_paid = money(payment["amount_paid"])
                total_allocated = money(payment["total_allocated"])
                credit_available = amount_paid - total_allocated
                if credit_available <= 0:
                    continue
                
                to_allocate = min(credit_available, remaining_bill_balance)
                if to_allocate > 0:
                    insert_record(
                        None,
                        "payment_allocations",
                        {
                            "payment_id": payment_id,
                            "pupil_id": pupil["pupil_id"],
                            "term": term,
                            "year": year,
                            "amount_allocated": to_allocate,
                            "fee_id": fee.get("fee_id") or bill.get("fee_id"),
                            "created_at": now_text(),
                        },
                    )
                    remaining_bill_balance -= to_allocate

    return bill


def auto_bill_student_for_current_term(pupil):
    term, year = current_period()
    bill = ensure_term_bill(pupil, term, year)
    return {
        "term": term,
        "year": year,
        "bill": bill,
        "created": bool(bill),
        "amount": money_float(bill.get("amount_billed")) if bill else 0,
        "has_fee_structure": bool(fee_structure_for(pupil, term, year)),
    }


def ensure_current_term_bills_for_active_students():
    term, year = current_period()
    pupils = dict_rows("SELECT * FROM pupils WHERE COALESCE(status, 'Active') = 'Active'")
    stats = {
        "term": term,
        "year": year,
        "active_students": len(pupils),
        "created": 0,
        "existing": 0,
        "missing_fee_structure": 0,
    }
    for pupil in pupils:
        existing = one_row(
            "SELECT bill_id FROM term_bills WHERE pupil_id = %s AND term = %s AND year = %s",
            [pupil["pupil_id"], term, year],
        )
        if existing:
            stats["existing"] += 1
            continue
        bill = ensure_term_bill(pupil, term, year)
        if bill:
            stats["created"] += 1
        else:
            stats["missing_fee_structure"] += 1
    return stats


def ensure_term_bill_without_credit_sweep(pupil, term, year):
    existing = one_row(
        "SELECT * FROM term_bills WHERE pupil_id = %s AND term = %s AND year = %s",
        [pupil["pupil_id"], term, year],
    )
    if existing:
        return existing
    fee = fee_structure_for(pupil, term, year)
    if not fee:
        return None
    bill_id = insert_record(
        None,
        "term_bills",
        {
            "pupil_id": pupil["pupil_id"],
            "fee_id": fee.get("fee_id"),
            "term": term,
            "year": year,
            "amount_billed": fee.get("amount_required"),
            "billed_on": today_text(),
            "due_date": fee.get("payment_deadline") or today_text(),
            "status": "Billed",
        },
    )
    return one_row("SELECT * FROM term_bills WHERE bill_id = %s", [bill_id])


def period_balance(pupil_id, term, year):
    for row in period_summaries(pupil_id):
        if str(row["term"]) == str(term) and int(row["year"]) == int(year):
            return row
    return None


def advance_payment_term_for(pupil, term, year, ensure_bill=False):
    next_term, next_year = next_term_period(term, year)
    if term_key(next_year, next_term) <= term_key(year, term):
        return None
    bill = ensure_term_bill_without_credit_sweep(pupil, next_term, next_year) if ensure_bill else one_row(
        "SELECT * FROM term_bills WHERE pupil_id = %s AND term = %s AND year = %s",
        [pupil["pupil_id"], next_term, next_year],
    )
    balance_row = period_balance(pupil["pupil_id"], next_term, next_year) if bill else None
    if balance_row:
        if money(balance_row["balance"]) <= 0:
            return None
        return {
            "term": next_term,
            "year": next_year,
            "label": f"{next_term} {next_year}",
            "balance": money_float(balance_row["balance"]),
            "fee_id": balance_row.get("fee_id") or bill.get("fee_id"),
        }
    fee = fee_structure_for(pupil, next_term, next_year)
    if not fee:
        return None
    amount = money(fee.get("amount_required"))
    if amount <= 0:
        return None
    return {
        "term": next_term,
        "year": next_year,
        "label": f"{next_term} {next_year}",
        "balance": money_float(amount),
        "fee_id": fee.get("fee_id"),
    }


def allocate_period(payment_id, pupil, item, remaining):
    allocated = min(remaining, money(item["balance"]))
    if allocated <= 0:
        return MONEY_ZERO, None
    existing = one_row(
        """
        SELECT allocation_id, amount_allocated
        FROM payment_allocations
        WHERE payment_id = %s AND term = %s AND year = %s
        """,
        [payment_id, item["term"], item["year"]],
    )
    if existing:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE payment_allocations
                SET amount_allocated = amount_allocated + %s,
                    fee_id = COALESCE(fee_id, %s)
                WHERE allocation_id = %s
                """,
                [allocated, item.get("fee_id"), existing["allocation_id"]],
            )
        return allocated, {**item, "amount_allocated": allocated}
    insert_record(
        None,
        "payment_allocations",
        {
            "payment_id": payment_id,
            "pupil_id": pupil["pupil_id"],
            "term": item["term"],
            "year": item["year"],
            "amount_allocated": allocated,
            "fee_id": item.get("fee_id"),
            "created_at": now_text(),
        },
    )
    return allocated, {**item, "amount_allocated": allocated}


def period_summaries(pupil_id):
    summaries = defaultdict(
        lambda: {
            "term": "",
            "year": 0,
            "fees_charged": MONEY_ZERO,
            "adjustments": MONEY_ZERO,
            "paid_allocated": MONEY_ZERO,
            "fee_id": None,
        }
    )
    for row in dict_rows(
        """
        SELECT term, year, fee_id, COALESCE(SUM(amount_billed), 0) AS amount
        FROM term_bills
        WHERE pupil_id = %s
        GROUP BY term, year, fee_id
        """,
        [pupil_id],
    ):
        item = summaries[(row["year"], row["term"])]
        item.update({"term": row["term"], "year": row["year"], "fee_id": row.get("fee_id")})
        item["fees_charged"] += money(row.get("amount"))
    for row in dict_rows(
        """
        SELECT term, year, COALESCE(SUM(amount), 0) AS amount
        FROM balance_adjustments
        WHERE pupil_id = %s
        GROUP BY term, year
        """,
        [pupil_id],
    ):
        item = summaries[(row["year"], row["term"])]
        item.update({"term": row["term"], "year": row["year"]})
        item["adjustments"] += money(row.get("amount"))
    for row in dict_rows(
        """
        SELECT term, year, fee_id, COALESCE(SUM(amount_allocated), 0) AS amount
        FROM payment_allocations
        WHERE pupil_id = %s
        GROUP BY term, year, fee_id
        """,
        [pupil_id],
    ):
        item = summaries[(row["year"], row["term"])]
        item.update({"term": row["term"], "year": row["year"]})
        item["fee_id"] = item.get("fee_id") or row.get("fee_id")
        item["paid_allocated"] += money(row.get("amount"))
    rows = []
    for item in summaries.values():
        required = item["fees_charged"] + item["adjustments"]
        balance = required - item["paid_allocated"]
        rows.append(
            {
                **item,
                "amount_required": required,
                "balance": balance,
                "fees_charged": item["fees_charged"],
                "adjustments": item["adjustments"],
                "paid_allocated": item["paid_allocated"],
                "label": f"{item['term']} {item['year']}",
            }
        )
    return sorted(rows, key=lambda row: term_key(row["year"], row["term"]))


def payment_history(pupil_id, limit=20):
    return dict_rows(
        """
        SELECT payment_id, receipt_no, amount_paid, payment_date, payment_method, term, year, reference_no
        FROM payments
        WHERE pupil_id = %s
        ORDER BY payment_date DESC, payment_id DESC
        LIMIT %s
        """,
        [pupil_id, limit],
    )


def statement_payment_rows(pupil_id, limit=500):
    payments = payment_history(pupil_id, limit=limit)
    if not payments:
        return []
    payment_ids = [row["payment_id"] for row in payments if row.get("payment_id")]
    placeholders = ", ".join(["%s"] * len(payment_ids))
    allocations = dict_rows(
        f"""
        SELECT payment_id, term, year, amount_allocated
        FROM payment_allocations
        WHERE payment_id IN ({placeholders})
        ORDER BY year, term
        """,
        payment_ids,
    ) if payment_ids else []
    allocations_by_payment = defaultdict(list)
    for allocation in allocations:
        allocations_by_payment[allocation["payment_id"]].append(allocation)
    rows = []
    for payment in payments:
        arrears_paid = MONEY_ZERO
        current_paid = MONEY_ZERO
        allocated_total = MONEY_ZERO
        for allocation in allocations_by_payment.get(payment["payment_id"], []):
            amount = money(allocation.get("amount_allocated"))
            allocated_total += amount
            if is_before_period(allocation, payment.get("term"), payment.get("year")):
                arrears_paid += amount
            else:
                current_paid += amount
        credit = money(payment.get("amount_paid")) - allocated_total
        rows.append(
            {
                **payment,
                "arrears_paid": money_float(arrears_paid),
                "current_paid": money_float(current_paid),
                "credit_balance": money_float(credit if credit > 0 else MONEY_ZERO),
            }
        )
    return rows


def student_financial_summary(pupil=None, admission_no=None, pupil_id=None, term=None, year=None, ensure_bill=False):
    if pupil is None:
        pupil = pupil_by_admission(admission_no) if admission_no else one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil_id])
    if not pupil:
        return None
    term, year = term or current_period()[0], int(year or current_period()[1])
    if ensure_bill:
        ensure_term_bill(pupil, term, year)
    summaries = period_summaries(pupil["pupil_id"])
    current = next((row for row in summaries if str(row["term"]) == str(term) and int(row["year"]) == int(year)), None)
    if current is None:
        fee = fee_structure_for(pupil, term, year)
        current = {
            "term": term,
            "year": year,
            "fees_charged": money(fee.get("amount_required") if fee else 0),
            "adjustments": MONEY_ZERO,
            "paid_allocated": MONEY_ZERO,
            "amount_required": money(fee.get("amount_required") if fee else 0),
            "balance": money(fee.get("amount_required") if fee else 0),
            "fee_id": fee.get("fee_id") if fee else None,
            "label": f"{term} {year}",
        }
        summaries.append(current)
        summaries = sorted(summaries, key=lambda row: term_key(row["year"], row["term"]))
    total_charged = sum((row["fees_charged"] for row in summaries), MONEY_ZERO)
    manual_adjustments = sum((row["adjustments"] for row in summaries), MONEY_ZERO)
    total_paid_row = one_row("SELECT COALESCE(SUM(amount_paid), 0) AS total FROM payments WHERE pupil_id = %s", [pupil["pupil_id"]])
    total_paid = money(total_paid_row.get("total") if total_paid_row else 0)
    overall_balance = total_charged + manual_adjustments - total_paid
    current_balance = current["fees_charged"] + current["adjustments"] - current["paid_allocated"]
    previous_arrears = sum(
        (row["balance"] for row in summaries if is_before_period(row, term, year) and row["balance"] > 0),
        MONEY_ZERO,
    )
    outstanding_terms = [
        {
            "term": row["term"],
            "year": row["year"],
            "label": row["label"],
            "balance": money_float(row["balance"]),
            "fee_id": row.get("fee_id"),
        }
        for row in summaries
        if row["balance"] > 0 and term_key(row["year"], row["term"]) <= term_key(year, term)
    ]
    return {
        "pupil": {
            "pupil_id": pupil["pupil_id"],
            "admission_no": pupil["admission_no"],
            "name": f"{pupil.get('first_name', '')} {pupil.get('surname', '')}".strip(),
            "first_name": pupil.get("first_name"),
            "surname": pupil.get("surname"),
            "grade": pupil.get("grade"),
            "class_stream": pupil.get("class_stream"),
            "class_label": compact_class_label(grade=pupil.get("grade"), stream=pupil.get("class_stream"), grade_id=pupil.get("grade_id")),
            "guardian_name": pupil.get("guardian_name"),
            "guardian_phone": pupil.get("guardian_phone"),
            "status": pupil.get("status"),
        },
        "term": term,
        "year": year,
        "current_fees": money_float(current["fees_charged"]),
        "opening_balance": money_float(previous_arrears),
        "previous_arrears": money_float(previous_arrears),
        "manual_adjustments": money_float(manual_adjustments),
        "amount_required": money_float(current["amount_required"]),
        "total_fees_charged": money_float(total_charged),
        "total_paid": money_float(total_paid),
        "balance": money_float(current_balance),
        "other_terms_balance": money_float(previous_arrears),
        "overall_balance": money_float(overall_balance),
        "credit_balance": money_float(abs(overall_balance) if overall_balance < 0 else 0),
        "amount_due": money_float(overall_balance if overall_balance > 0 else 0),
        "outstanding_terms": outstanding_terms,
        "required_payment_term": outstanding_terms[0] if outstanding_terms else None,
        "advance_payment_term": advance_payment_term_for(pupil, term, year, ensure_bill=False),
        "payment_history": payment_history(pupil["pupil_id"], limit=10),
        "periods": summaries,
    }


def create_allocations(payment_id, pupil, amount, term, year):
    summary = student_financial_summary(pupil=pupil, term=term, year=year, ensure_bill=True)
    remaining = money(amount)
    allocations = []
    for item in summary["outstanding_terms"]:
        if remaining <= 0:
            break
        allocated, allocation = allocate_period(payment_id, pupil, item, remaining)
        if allocation:
            allocations.append(allocation)
        remaining -= allocated

    if remaining > 0:
        all_periods = period_summaries(pupil["pupil_id"])
        future_outstanding = [
            {
                "term": row["term"],
                "year": row["year"],
                "label": row["label"],
                "balance": money_float(row["balance"]),
                "fee_id": row.get("fee_id"),
            }
            for row in all_periods
            if row["balance"] > 0 and term_key(row["year"], row["term"]) > term_key(year, term)
        ]
        future_outstanding = sorted(future_outstanding, key=lambda row: term_key(row["year"], row["term"]))
        for item in future_outstanding:
            if remaining <= 0:
                break
            allocated, allocation = allocate_period(payment_id, pupil, item, remaining)
            if allocation:
                allocations.append(allocation)
            remaining -= allocated

    if remaining > 0:
        advance_term = advance_payment_term_for(pupil, term, year, ensure_bill=True)
        if advance_term:
            allocated, allocation = allocate_period(payment_id, pupil, advance_term, remaining)
            if allocation:
                allocations.append(allocation)
            remaining -= allocated

    if remaining > 0:
        next_term, next_year = next_term_period(term, year)
        forward_credit = {
            "term": next_term,
            "year": next_year,
            "label": f"{next_term} {next_year}",
            "balance": money_float(remaining),
            "fee_id": None,
        }
        allocated, allocation = allocate_period(payment_id, pupil, forward_credit, remaining)
        if allocation:
            allocations.append(allocation)
        remaining -= allocated

    return allocations, remaining


def sweep_existing_credit_balances():
    if not table_exists("payment_allocations"):
        return {"payments_checked": 0, "allocations_created": 0, "credit_remaining": money_float(MONEY_ZERO)}
    rows = dict_rows(
        """
        SELECT p.payment_id, p.pupil_id, p.amount_paid, p.term, p.year,
               COALESCE(SUM(pa.amount_allocated), 0) AS total_allocated
        FROM payments p
        LEFT JOIN payment_allocations pa ON pa.payment_id = p.payment_id
        GROUP BY p.payment_id, p.pupil_id, p.amount_paid, p.term, p.year
        HAVING COALESCE(SUM(pa.amount_allocated), 0) < p.amount_paid
        ORDER BY p.payment_date ASC, p.payment_id ASC
        """
    )
    allocations_created = 0
    credit_remaining = MONEY_ZERO
    for row in rows:
        pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [row["pupil_id"]])
        if not pupil:
            continue
        available = money(row["amount_paid"]) - money(row["total_allocated"])
        if available <= 0:
            continue
        allocations, remaining = create_allocations(row["payment_id"], pupil, available, row["term"], int(row["year"]))
        allocations_created += len(allocations)
        credit_remaining += remaining
    return {
        "payments_checked": len(rows),
        "allocations_created": allocations_created,
        "credit_remaining": money_float(credit_remaining),
    }


def save_payment(request, pupil, amount, payment_date, payment_method, term, year, reference_no=None):
    assert_can_receive_payment(pupil)
    amount_value = money(amount)
    if amount_value <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    if reference_no and one_row("SELECT payment_id FROM payments WHERE reference_no = %s", [reference_no]):
        raise ValueError(f"Payment reference {reference_no} has already been receipted.")
    with transaction.atomic():
        ensure_term_bill(pupil, term, year)
        receipt_no = next_receipt_no(int(str(payment_date or today_text())[:4]))
        payment_id = insert_record(
            request,
            "payments",
            {
                "pupil_id": pupil["pupil_id"],
                "amount_paid": amount_value,
                "payment_date": payment_date or today_text(),
                "payment_method": payment_method or "Cash",
                "receipt_no": receipt_no,
                "term": term,
                "year": year,
                "fee_id": (fee_structure_for(pupil, term, year) or {}).get("fee_id"),
                "recorded_by": legacy_user_id(request),
                "reference_no": reference_no or None,
            },
        )
        if not payment_id:
            row = one_row("SELECT payment_id FROM payments WHERE receipt_no = %s", [receipt_no])
            payment_id = row["payment_id"] if row else None
        insert_record(request, "receipts", {"payment_id": payment_id, "receipt_no": receipt_no, "issued_date": now_text()})
        allocations, credit = create_allocations(payment_id, pupil, amount_value, term, year)
        audit_action(
            request,
            "Create receipt",
            f"Receipt {receipt_no} for {pupil['admission_no']} amount {amount_value}; credit {credit}",
        )
    return payment_id, receipt_no, allocations, credit


def receipt_by_number(receipt_no):
    return one_row(
        """
        SELECT p.*, r.issued_date, pu.admission_no, pu.first_name, pu.surname, pu.grade, pu.class_stream,
               pu.guardian_name, pu.guardian_phone
        FROM payments p
        LEFT JOIN receipts r ON r.payment_id = p.payment_id
        LEFT JOIN pupils pu ON pu.pupil_id = p.pupil_id
        WHERE p.receipt_no = %s
        """,
        [receipt_no],
    )


def receipt_by_payment_id(payment_id):
    row = one_row("SELECT receipt_no FROM payments WHERE payment_id = %s", [payment_id])
    return receipt_by_number(row["receipt_no"]) if row else None


def receipt_allocations(payment_id):
    return dict_rows(
        """
        SELECT term, year, amount_allocated
        FROM payment_allocations
        WHERE payment_id = %s
        ORDER BY year, term
        """,
        [payment_id],
    )


def receipt_context(receipt_no=None, payment_id=None, admission_no=None):
    payment = None
    if receipt_no:
        payment = receipt_by_number(receipt_no)
    elif payment_id:
        payment = receipt_by_payment_id(payment_id)

    pupil = None
    if admission_no:
        pupil = pupil_by_admission(admission_no)
    elif payment and payment.get("pupil_id"):
        pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [payment["pupil_id"]])

    if not payment and not pupil:
        return None

    # If payment is not found but pupil is, try to find a recent payment for the pupil
    if not payment and pupil:
        payment = one_row("SELECT p.*, r.issued_date, pu.admission_no, pu.first_name, pu.surname, pu.grade, pu.class_stream," \
               "pu.guardian_name, pu.guardian_phone " \
        "FROM payments p " \
        "LEFT JOIN receipts r ON r.payment_id = p.payment_id " \
        "LEFT JOIN pupils pu ON pu.pupil_id = p.pupil_id " \
        "WHERE p.pupil_id = %s " \
        "ORDER BY p.payment_date DESC, p.payment_id DESC LIMIT 1", [pupil["pupil_id"]])
    if not payment:
            return None

    if not pupil:
        # This case should ideally not be reached if payment is found and linked to a pupil
        return None

    summary = student_financial_summary(pupil=pupil, term=payment["term"], year=payment["year"])
    allocations = receipt_allocations(payment["payment_id"])
    payment_period = term_key(payment["year"], payment["term"])
    arrears_paid = sum(
        (money(row["amount_allocated"]) for row in allocations if term_key(row["year"], row["term"]) < payment_period),
        MONEY_ZERO,
    )
    current_paid = sum(
        (money(row["amount_allocated"]) for row in allocations if term_key(row["year"], row["term"]) == payment_period),
        MONEY_ZERO,
    )
    advance_paid = sum(
        (money(row["amount_allocated"]) for row in allocations if term_key(row["year"], row["term"]) > payment_period),
        MONEY_ZERO,
    )
    allocated_total = sum((money(row["amount_allocated"]) for row in allocations), MONEY_ZERO)
    credit = money(payment["amount_paid"]) - allocated_total
    return {
        "payment": payment,
        "pupil": pupil,
        "summary": summary,
        "allocations": allocations,
        "arrears_paid": arrears_paid,
        "current_paid": current_paid,
        "advance_paid": advance_paid,
        "credit": credit if credit > 0 else MONEY_ZERO,
        "settings": school_settings(),
    }


def update_payment_with_audit(request, payment_id, data, reason):
    if not reason:
        raise ValueError("An edit reason is required.")
    old = one_row("SELECT * FROM payments WHERE payment_id = %s", [payment_id])
    if not old:
        raise ValueError("Payment was not found.")
    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [old["pupil_id"]])
    allowed = {"amount_paid", "payment_date", "payment_method", "term", "year", "reference_no"}
    usable = {key: value for key, value in data.items() if key in allowed}
    if not usable:
        raise ValueError("No editable payment fields were submitted.")
    with transaction.atomic():
        assignments = ", ".join(f"{key} = %s" for key in usable)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE payments SET {assignments} WHERE payment_id = %s", list(usable.values()) + [payment_id])
            cursor.execute("DELETE FROM payment_allocations WHERE payment_id = %s", [payment_id])
        updated = one_row("SELECT * FROM payments WHERE payment_id = %s", [payment_id])
        create_allocations(payment_id, pupil, updated["amount_paid"], updated["term"], updated["year"])
        audit_action(
            request,
            "Edit receipt",
            f"Receipt {old['receipt_no']} edited by {request.user.username}. Reason: {reason}. Before: {old}. After: {updated}",
        )
    return updated


def delete_payment_with_audit(request, payment_id, reason="Super Admin deletion"):
    payment = one_row("SELECT * FROM payments WHERE payment_id = %s", [payment_id])
    if not payment:
        raise ValueError("Payment was not found.")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM receipts WHERE payment_id = %s", [payment_id])
            cursor.execute("DELETE FROM payment_allocations WHERE payment_id = %s", [payment_id])
            cursor.execute("DELETE FROM payments WHERE payment_id = %s", [payment_id])
        audit_action(request, "Delete receipt", f"Receipt {payment['receipt_no']} deleted. Reason: {reason}")


def student_balance_rows(q="", grade="", term="", year="", status="", academic_level="", limit=25, offset=0):
    params = []
    clauses = []
    if q:
        clauses.append(
            "(p.admission_no LIKE %s OR p.first_name LIKE %s OR p.surname LIKE %s OR p.guardian_name LIKE %s OR p.grade LIKE %s)"
        )
        params.extend([f"%{q}%"] * 5)
    if grade:
        clauses.append("p.grade = %s")
        params.append(grade)
    if academic_level == "O Level":
        clauses.append("(p.grade_id BETWEEN 1 AND 4 OR p.grade_id = 7 OR p.grade LIKE %s OR p.grade LIKE %s)")
        params.extend(["%Completed O%", "%O Level%"])
    elif academic_level == "A Level":
        clauses.append("(p.grade_id BETWEEN 5 AND 6 OR p.grade_id = 8 OR p.grade LIKE %s OR p.grade LIKE %s)")
        params.extend(["%Completed A%", "%A Level%"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    where_filter = ""
    if status == "arrears":
        where_filter = "WHERE current_balance > 0"
    elif status == "paid":
        where_filter = "WHERE current_balance = 0"
    elif status == "credit":
        where_filter = "WHERE credit_balance > 0"
    sql = f"""
        SELECT * FROM (
            SELECT p.admission_no,
                   p.first_name || ' ' || p.surname AS student_name,
                   p.grade,
                   p.grade_id,
                   p.class_stream,
                   CASE
                     WHEN p.grade_id BETWEEN 1 AND 4 OR p.grade_id = 7 OR p.grade LIKE '%%Completed O%%' OR p.grade LIKE '%%O Level%%' THEN 'O Level'
                     WHEN p.grade_id BETWEEN 5 AND 6 OR p.grade_id = 8 OR p.grade LIKE '%%Completed A%%' OR p.grade LIKE '%%A Level%%' THEN 'A Level'
                     ELSE ''
                   END AS academic_level,
                   COALESCE(charges.total, 0) AS total_fees_charged,
                   COALESCE(payments.total, 0) AS total_paid,
                   CASE WHEN COALESCE(charges.total, 0) + COALESCE(adjustments.total, 0) - COALESCE(payments.total, 0) > 0
                        THEN COALESCE(charges.total, 0) + COALESCE(adjustments.total, 0) - COALESCE(payments.total, 0)
                        ELSE 0 END AS current_balance,
                   CASE WHEN COALESCE(payments.total, 0) - COALESCE(charges.total, 0) - COALESCE(adjustments.total, 0) > 0
                        THEN COALESCE(payments.total, 0) - COALESCE(charges.total, 0) - COALESCE(adjustments.total, 0)
                        ELSE 0 END AS credit_balance,
                   CASE WHEN COALESCE(charges.total, 0) + COALESCE(adjustments.total, 0) - COALESCE(payments.total, 0) > 0
                        THEN COALESCE(charges.total, 0) + COALESCE(adjustments.total, 0) - COALESCE(payments.total, 0)
                        ELSE 0 END AS arrears
            FROM pupils p
            LEFT JOIN (SELECT pupil_id, SUM(amount_billed) AS total FROM term_bills GROUP BY pupil_id) charges ON charges.pupil_id = p.pupil_id
            LEFT JOIN (SELECT pupil_id, SUM(amount) AS total FROM balance_adjustments GROUP BY pupil_id) adjustments ON adjustments.pupil_id = p.pupil_id
            LEFT JOIN (SELECT pupil_id, SUM(amount_paid) AS total FROM payments GROUP BY pupil_id) payments ON payments.pupil_id = p.pupil_id
            {where}
        ) sub
        {where_filter}
        ORDER BY current_balance DESC, student_name
        LIMIT %s OFFSET %s
    """
    count_sql = f"SELECT COUNT(*) AS total FROM ({sql.replace('LIMIT %s OFFSET %s', '')}) balance_rows"
    rows = dict_rows(sql, params + [limit, offset])
    count = one_row(count_sql, params)
    return rows, int(count["total"] or 0)


def dashboard_metrics():
    today = today_text()
    month_prefix = today[:7] + "%"
    payments_today = one_row("SELECT COALESCE(SUM(amount_paid), 0) AS total FROM payments WHERE payment_date = %s", [today])
    payments_month = one_row("SELECT COALESCE(SUM(amount_paid), 0) AS total FROM payments WHERE payment_date LIKE %s", [month_prefix])
    expected = one_row("SELECT COALESCE(SUM(amount_billed), 0) AS total FROM term_bills")
    collected = one_row("SELECT COALESCE(SUM(amount_paid), 0) AS total FROM payments")
    rows, total_students = student_balance_rows(limit=100000, offset=0)
    arrears_total = sum((money(row["current_balance"]) for row in rows if money(row["current_balance"]) > 0), MONEY_ZERO)
    students_with_arrears = sum(1 for row in rows if money(row["current_balance"]) > 0)
    fully_paid = sum(1 for row in rows if money(row["current_balance"]) == 0 and money(row["credit_balance"]) == 0)
    expected_total = money(expected.get("total") if expected else 0)
    collected_total = money(collected.get("total") if collected else 0)
    percentage = (collected_total / expected_total * 100).quantize(Decimal("0.01")) if expected_total > 0 else MONEY_ZERO
    class_totals = defaultdict(Decimal)
    level_totals = defaultdict(lambda: {"students": 0, "arrears": MONEY_ZERO})
    for row in rows:
        class_totals[f"{row.get('grade') or '-'} {row.get('class_stream') or ''}".strip()] += money(row["current_balance"])
        level = row.get("academic_level") or "Unclassified"
        level_totals[level]["students"] += 1
        level_totals[level]["arrears"] += money(row["current_balance"])
    top_classes = sorted(
        [{"class_name": key, "arrears": value} for key, value in class_totals.items() if value > 0],
        key=lambda item: item["arrears"],
        reverse=True,
    )[:5]
    recent_payments = dict_rows(
        """
        SELECT p.receipt_no, p.amount_paid, p.payment_date, pu.admission_no,
               pu.first_name || ' ' || pu.surname AS student_name
        FROM payments p
        JOIN pupils pu ON pu.pupil_id = p.pupil_id
        ORDER BY p.payment_date DESC, p.payment_id DESC
        LIMIT 8
        """
    )
    highest_arrears = [row for row in rows if money(row["current_balance"]) > 0][:8]
    return {
        "payments_today": money(payments_today.get("total") if payments_today else 0),
        "payments_month": money(payments_month.get("total") if payments_month else 0),
        "total_arrears": arrears_total,
        "students_with_arrears": students_with_arrears,
        "fully_paid_students": fully_paid,
        "total_expected": expected_total,
        "total_collected": collected_total,
        "collection_percentage": percentage,
        "total_students": total_students,
        "top_classes": top_classes,
        "level_totals": [
            {"level": level, "students": values["students"], "arrears": values["arrears"]}
            for level, values in sorted(level_totals.items())
        ],
        "recent_payments": recent_payments,
        "highest_arrears": highest_arrears,
    }


def ensure_finance_indexes():
    if not table_exists("payments"):
        return
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_pupils_admission_no_search ON pupils (admission_no)",
        "CREATE INDEX IF NOT EXISTS idx_pupils_guardian_name_search ON pupils (guardian_name)",
        "CREATE INDEX IF NOT EXISTS idx_payments_receipt_date ON payments (receipt_no, payment_date)",
        "CREATE INDEX IF NOT EXISTS idx_receipts_receipt_no ON receipts (receipt_no)",
        "CREATE INDEX IF NOT EXISTS idx_allocations_payment_period ON payment_allocations (payment_id, year, term)",
    ]
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
