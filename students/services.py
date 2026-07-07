import hashlib
import io
import os
import re
import uuid
from datetime import date

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection
from django.utils import timezone

from school_system_django.native import dict_rows, now_text, one_row, school_settings, table_columns, table_exists, today_text


O_LEVEL_FINAL_GRADE = 4
A_LEVEL_START_GRADE = 5
A_LEVEL_FINAL_GRADE = 6
O_LEVEL_COMPLETED_GRADE = 7
A_LEVEL_COMPLETED_GRADE = 8
FINAL_GRADE = A_LEVEL_COMPLETED_GRADE
PENDING_ZIMSEC_STATUS = "Pending ZIMSEC Analysis"
PERMANENT_ARCHIVE_STATUS = "Permanently Archived"
REACTIVATED_A_LEVEL_REASON = "Reactivated for A Level"
PHOTO_DIR = "student_photos"
PASSPORT_PHOTO_SIZE = (413, 531)
MAX_PHOTO_SIZE_BYTES = 3 * 1024 * 1024
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_PHOTO_FORMATS = {"JPEG", "PNG"}


def parse_iso_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except (TypeError, ValueError):
        return None


def student_age_text(dob, on_date=None):
    born = parse_iso_date(dob)
    if not born:
        return ""
    today = on_date or timezone.localdate()
    if born > today:
        return ""

    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day
    if days < 0:
        previous_month = today.month - 1 or 12
        previous_year = today.year if today.month > 1 else today.year - 1
        days_in_previous_month = (date(today.year, today.month, 1) - date(previous_year, previous_month, 1)).days
        days += days_in_previous_month
        months -= 1
    if months < 0:
        months += 12
        years -= 1

    def part(value, singular, plural):
        return f"{value} {singular if value == 1 else plural}"

    return " ".join(
        [
            part(years, "Year", "Years"),
            part(months, "Month", "Months"),
            part(days, "Day", "Days"),
        ]
    )


def student_photo_url(photo_path):
    path = str(photo_path or "").strip()
    if not path:
        return ""
    if path.startswith(("http://", "https://", "/")):
        return path
    return f"{django_settings.MEDIA_URL}{path}"


def _student_photo_file_name(admission_no, extension=".jpg"):
    safe_admission = re.sub(r"[^A-Za-z0-9_-]+", "-", str(admission_no or "student")).strip("-") or "student"
    return f"{safe_admission}-{uuid.uuid4().hex[:10]}{extension}"


def _validate_photo_upload(uploaded_file):
    extension = os.path.splitext(uploaded_file.name or "")[1].lower()
    if extension not in ALLOWED_PHOTO_EXTENSIONS:
        raise ValidationError("Student photo must be a JPG, JPEG, or PNG image.")
    if uploaded_file.size and uploaded_file.size > MAX_PHOTO_SIZE_BYTES:
        raise ValidationError("Student photo must be 3MB or smaller.")


def _passport_photo_content(uploaded_file):
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise ValidationError("Pillow is required to process student photos.") from exc

    _validate_photo_upload(uploaded_file)
    try:
        image = Image.open(uploaded_file)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Upload a valid JPG, JPEG, or PNG student photo.") from exc

    if image.format not in ALLOWED_PHOTO_FORMATS:
        raise ValidationError("Student photo must be a JPG, JPEG, or PNG image.")

    image = ImageOps.exif_transpose(image)
    image = ImageOps.fit(image, PASSPORT_PHOTO_SIZE, method=Image.Resampling.LANCZOS)
    if image.mode not in {"RGB", "L"}:
        background = Image.new("RGB", image.size, "white")
        alpha = image.getchannel("A") if "A" in image.getbands() else None
        background.paste(image, mask=alpha)
        image = background
    else:
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return ContentFile(output.getvalue())


def save_student_photo(uploaded_file, admission_no):
    return ""


def delete_student_photo(photo_path):
    pass


def generate_student_portrait(pupil):
    return ""


def ensure_student_photo(pupil):
    return ""


def backfill_student_portraits(limit=None):
    return 0


def generate_realistic_student_photo(pupil):
    return ""


def backfill_realistic_student_photos(limit=None, force=False):
    return 0



def grade_number(value):
    text = str(value or "").strip()
    lowered = text.lower()
    if "completed o" in lowered or "o level" in lowered and "completed" in lowered:
        return O_LEVEL_COMPLETED_GRADE
    if "completed a" in lowered or "a level" in lowered and "completed" in lowered:
        return A_LEVEL_COMPLETED_GRADE
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def grade_label_for_number(number, previous_label=""):
    number = int(number or 0)
    if 1 <= number <= A_LEVEL_FINAL_GRADE:
        return f"Form {number}"
    if number == O_LEVEL_COMPLETED_GRADE:
        return "Completed O Level"
    if number == A_LEVEL_COMPLETED_GRADE:
        return "Completed A Level"
    row = one_row("SELECT grade_name FROM grades WHERE grade_name = %s", [f"Form {number}"]) if table_exists("grades") else None
    if row:
        return row["grade_name"]
    label = str(previous_label or "").strip()
    if label:
        return re.sub(r"\d+", str(number), label, count=1)
    return f"Form {number}"


def grade_row_for_number(number):
    if not table_exists("grades"):
        return None
    number = int(number or 0)
    row = one_row("SELECT grade_id, grade_name FROM grades WHERE grade_id = %s", [number])
    if row:
        return row
    labels = [grade_label_for_number(number), f"Grade {number}", f"Form {number}"]
    for label in labels:
        row = one_row("SELECT grade_id, grade_name FROM grades WHERE grade_name = %s", [label])
        if row:
            return row
    row = one_row("SELECT grade_id, grade_name FROM grades WHERE grade_name = %s", [f"Grade {number}"])
    if row:
        return row
    return one_row(
        "SELECT grade_id, grade_name FROM grades WHERE grade_name LIKE %s ORDER BY grade_id LIMIT 1",
        [f"%{number}%"],
    )


def display_grade_label(grade=None, grade_id=None):
    number = grade_number(grade_id) or grade_number(grade)
    if number:
        return grade_label_for_number(number, grade)
    return str(grade or "").strip()


def academic_level_for_number(number):
    number = int(number or 0)
    if number in range(1, O_LEVEL_FINAL_GRADE + 1) or number == O_LEVEL_COMPLETED_GRADE:
        return "O Level"
    if number in range(A_LEVEL_START_GRADE, A_LEVEL_FINAL_GRADE + 1) or number == A_LEVEL_COMPLETED_GRADE:
        return "A Level"
    return ""


def academic_level_for_pupil(pupil):
    number = grade_number((pupil or {}).get("grade_id")) or grade_number((pupil or {}).get("grade"))
    return academic_level_for_number(number)


def is_pending_zimsec(pupil):
    return str((pupil or {}).get("status") or "").strip() == PENDING_ZIMSEC_STATUS


def zimsec_release_date(pupil):
    completed = parse_iso_date((pupil or {}).get("completed_on"))
    if not completed:
        return None
    return date(completed.year + 1, 3, 1)


def pending_zimsec_is_mature(pupil, on_date=None):
    release_date = zimsec_release_date(pupil)
    return bool(release_date and (on_date or timezone.localdate()) >= release_date)


def class_id_for(grade_id, stream, academic_year):
    if not grade_id or not stream or not table_exists("classes"):
        return None
    row = one_row(
        """
        SELECT class_id
        FROM classes
        WHERE grade_id = %s AND academic_year = %s AND UPPER(TRIM(class_name)) = %s
        LIMIT 1
        """,
        [grade_id, academic_year, str(stream).strip().upper()],
    )
    return row["class_id"] if row else None


def school_finish_date(pupil, current_year=None):
    if pupil.get("completed_on"):
        return pupil["completed_on"]
    current_year = int(current_year or (school_settings().get("current_year") or timezone.localdate().year))
    number = grade_number(pupil.get("grade") or pupil.get("grade_id"))
    if not number:
        return ""
    if number <= O_LEVEL_FINAL_GRADE:
        finish_year = current_year + max(0, O_LEVEL_FINAL_GRADE - number)
    elif number <= A_LEVEL_FINAL_GRADE:
        finish_year = current_year + max(0, A_LEVEL_FINAL_GRADE - number)
    else:
        finish_year = current_year
    return f"{finish_year}-12-31"


def set_last_promotion_year(year):
    if not table_exists("school_settings") or "last_promotion_year" not in table_columns("school_settings"):
        return
    with connection.cursor() as cursor:
        cursor.execute("UPDATE school_settings SET last_promotion_year = %s WHERE setting_id = 1", [year])


def complete_pupil(pupil, completed_year):
    current_grade = grade_number(pupil.get("grade") or pupil.get("grade_id"))
    if current_grade and current_grade >= A_LEVEL_FINAL_GRADE:
        completed_grade = A_LEVEL_COMPLETED_GRADE
        level = "A Level"
    else:
        completed_grade = O_LEVEL_COMPLETED_GRADE
        level = "O Level"
    grade_row = grade_row_for_number(completed_grade)
    grade_id = grade_row["grade_id"] if grade_row else completed_grade
    grade_label = grade_label_for_number(completed_grade)
    completed_on = f"{completed_year}-12-31"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE pupils
            SET status = %s,
                grade = %s,
                grade_id = %s,
                class_id = NULL,
                completed_on = %s,
                status_changed_on = %s,
                status_reason = %s
            WHERE pupil_id = %s
            """,
            [
                PENDING_ZIMSEC_STATUS,
                grade_label,
                grade_id,
                completed_on,
                today_text(),
                f"Completed {level} at the end of {completed_year}; pending ZIMSEC analysis until 1 March {completed_year + 1}.",
                pupil["pupil_id"],
            ],
        )


def promote_pupil(pupil, target_year):
    current_grade = grade_number(pupil.get("grade") or pupil.get("grade_id"))
    if not current_grade:
        return False
    if current_grade >= O_LEVEL_COMPLETED_GRADE:
        return False
    next_grade = current_grade + 1
    if next_grade == A_LEVEL_START_GRADE:
        return False
    grade_row = grade_row_for_number(next_grade)
    grade_id = grade_row["grade_id"] if grade_row else None
    grade_label = grade_label_for_number(next_grade, pupil.get("grade"))
    class_id = class_id_for(grade_id, pupil.get("class_stream"), target_year)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE pupils
            SET grade = %s,
                grade_id = %s,
                class_id = %s,
                status_changed_on = %s,
                status_reason = %s
            WHERE pupil_id = %s
            """,
            [grade_label, grade_id, class_id, today_text(), f"Auto-promoted to {grade_label} for {target_year}", pupil["pupil_id"]],
        )
    return True


def archive_pupil(pupil, reason=None):
    level = academic_level_for_pupil(pupil)
    reason_text = reason or f"{level or 'Student'} permanently archived."
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE pupils
            SET status = %s,
                status_changed_on = %s,
                status_reason = %s
            WHERE pupil_id = %s
            """,
            [PERMANENT_ARCHIVE_STATUS, today_text(), reason_text, pupil["pupil_id"]],
        )


def reactivate_for_a_level(pupil, stream="", target_year=None, reason=None):
    grade_row = grade_row_for_number(A_LEVEL_START_GRADE)
    grade_id = grade_row["grade_id"] if grade_row else A_LEVEL_START_GRADE
    stream = stream or pupil.get("class_stream") or "A"
    target_year = int(target_year or (school_settings().get("current_year") or timezone.localdate().year))
    class_id = class_id_for(grade_id, stream, target_year)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE pupils
            SET status = 'Active',
                grade = %s,
                grade_id = %s,
                class_stream = %s,
                class_id = %s,
                status_changed_on = %s,
                status_reason = %s
            WHERE pupil_id = %s
            """,
            [
                grade_label_for_number(A_LEVEL_START_GRADE),
                grade_id,
                stream,
                class_id,
                today_text(),
                reason or REACTIVATED_A_LEVEL_REASON,
                pupil["pupil_id"],
            ],
        )
    return one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil["pupil_id"]])


def archive_mature_pending_students(on_date=None):
    on_date = on_date or timezone.localdate()
    archived = 0
    pupils = dict_rows(
        "SELECT * FROM pupils WHERE status = %s ORDER BY pupil_id",
        [PENDING_ZIMSEC_STATUS],
    )
    for pupil in pupils:
        if pending_zimsec_is_mature(pupil, on_date=on_date):
            level = academic_level_for_pupil(pupil)
            archive_pupil(pupil, f"Completed {level} ZIMSEC analysis period ended; permanently archived.")
            archived += 1
    return archived


def run_yearly_student_progression():
    if not table_exists("school_settings") or not table_exists("pupils"):
        return {"promoted": 0, "completed": 0, "initialized": False, "skipped": True}
    settings = school_settings()
    current_year = int(settings.get("current_year") or timezone.localdate().year)
    last_year = settings.get("last_promotion_year")
    actual_year = timezone.localdate().year
    stats = {
        "from_year": last_year,
        "to_year": current_year,
        "promoted": 0,
        "completed": 0,
        "archived": 0,
        "initialized": False,
        "skipped": False,
    }
    if not last_year:
        if current_year <= actual_year:
            set_last_promotion_year(current_year)
            stats["initialized"] = True
            return stats
        last_year = current_year - 1
    last_year = int(last_year)
    if current_year <= last_year:
        stats["skipped"] = True
        return stats

    for target_year in range(last_year + 1, current_year + 1):
        previous_year = target_year - 1
        pupils = dict_rows("SELECT * FROM pupils WHERE COALESCE(status, 'Active') = 'Active' ORDER BY pupil_id")
        for pupil in pupils:
            number = grade_number(pupil.get("grade") or pupil.get("grade_id"))
            if not number:
                continue
            if number >= A_LEVEL_FINAL_GRADE:
                complete_pupil(pupil, previous_year)
                stats["completed"] += 1
            elif number >= O_LEVEL_FINAL_GRADE:
                complete_pupil(pupil, previous_year)
                stats["completed"] += 1
            else:
                if promote_pupil(pupil, target_year):
                    stats["promoted"] += 1
        set_last_promotion_year(target_year)
    stats["archived"] += archive_mature_pending_students()
    return stats
