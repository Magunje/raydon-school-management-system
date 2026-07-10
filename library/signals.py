import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
import qrcode

from student_registry.models import Student
from human_resources.models import EmployeeProfile
from library.models import LibraryMember
from school_system_django.native import insert_record, today_text, one_row, table_exists


def generate_member_qr_code(card_number):
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(card_number)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        rel_path = f"library_cards/{card_number}.png"
        abs_dir = os.path.join(settings.MEDIA_ROOT, "library_cards")
        os.makedirs(abs_dir, exist_ok=True)
        
        file_path = os.path.join(abs_dir, f"{card_number}.png")
        img.save(file_path)
        return rel_path
    except Exception:
        return ""


@receiver(post_save, sender=Student)
def auto_create_student_library_membership(sender, instance, created, **kwargs):
    if not table_exists("library_members") or not instance.admission_no:
        return

    # Check if membership already exists
    member = one_row("SELECT member_id FROM library_members WHERE pupil_id = %s", [instance.pk])
    if member:
        return

    card_number = f"LIB-S-{instance.admission_no}"
    barcode_path = generate_member_qr_code(card_number)
    
    # Use insert_record to ensure compatibility with tenant-specific DB connection
    insert_record(
        None,
        "library_members",
        {
            "pupil_id": instance.pk,
            "staff_id": None,
            "card_number": card_number,
            "barcode_path": barcode_path,
            "status": "Active",
            "created_at": today_text(),
        }
    )


@receiver(post_save, sender=EmployeeProfile)
def auto_create_staff_library_membership(sender, instance, created, **kwargs):
    if not table_exists("library_members") or not instance.employee_number:
        return

    # Check if membership already exists
    member = one_row("SELECT member_id FROM library_members WHERE staff_id = %s", [instance.pk])
    if member:
        return

    card_number = f"LIB-T-{instance.employee_number}"
    barcode_path = generate_member_qr_code(card_number)
    
    insert_record(
        None,
        "library_members",
        {
            "pupil_id": None,
            "staff_id": instance.pk,
            "card_number": card_number,
            "barcode_path": barcode_path,
            "status": "Active",
            "created_at": today_text(),
        }
    )
