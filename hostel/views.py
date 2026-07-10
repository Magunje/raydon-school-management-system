import os
from decimal import Decimal
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponse, FileResponse, Http404, JsonResponse
import qrcode

from accounts.permissions import permission_required, user_has_permission, normalized_role
from student_registry.models import Student
from human_resources.models import EmployeeProfile
from hostel.models import (
    Hostel,
    HostelRoom,
    HostelBed,
    HostelAllocation,
    HostelTransfer,
    HostelAttendance,
    HostelDiscipline,
    HostelVisitor,
    HostelInventory,
    HostelFeeRecord,
    HostelMaintenance,
    HostelNotice
)
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


# Helper to sync room occupancy numbers and statuses
def sync_room_occupancy(room_id):
    room = HostelRoom.objects.filter(pk=room_id).first()
    if not room:
        return
        
    occupied_count = HostelBed.objects.filter(room_id=room_id, status="Occupied").count()
    room.current_occupancy = occupied_count
    
    if occupied_count >= room.capacity:
        room.status = "Full"
    elif room.status == "Full":
        room.status = "Available"
        
    room.save()
    
    # Also sync parent hostel capacity sum
    hostel = room.hostel
    total_capacity = HostelRoom.objects.filter(hostel=hostel).exclude(status="Closed").sum_total_capacity()
    # Or just sum capacity
    cap_sum = sum(r.capacity for r in HostelRoom.objects.filter(hostel=hostel).exclude(status="Closed"))
    hostel.capacity = cap_sum
    hostel.save()


# Helper to generate visitor QR Code pass
def generate_visitor_qr(visitor_id, visitor_name, pupil_no):
    try:
        qr_data = f"VISITOR-{visitor_id}-{pupil_no}"
        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        abs_dir = os.path.join(settings.MEDIA_ROOT, "visitor_passes")
        os.makedirs(abs_dir, exist_ok=True)
        
        file_path = os.path.join(abs_dir, f"visitor_{visitor_id}.png")
        img.save(file_path)
        return f"visitor_passes/visitor_{visitor_id}.png"
    except Exception:
        return ""


@permission_required("hostel.manage")
def hostel_dashboard(request):
    total_boarders = HostelAllocation.objects.filter(status="Active").count()
    total_hostels = Hostel.objects.filter(status="Active").count()
    
    total_beds = HostelBed.objects.exclude(room__status="Closed").count()
    available_beds = HostelBed.objects.filter(status="Available").exclude(room__status="Closed").count()
    
    occupancy_rate = round((total_boarders / total_beds) * 100, 1) if total_beds > 0 else 0.0
    
    pending_maintenance = HostelMaintenance.objects.filter(status__in=["Pending", "In Progress"]).count()
    visitors_today = HostelVisitor.objects.filter(visit_date=today_text()).count()
    
    unpaid_fees_row = one_row("SELECT SUM(amount) AS total FROM hostel_fee_records WHERE status = 'Unpaid'")
    unpaid_fees = unpaid_fees_row["total"] if unpaid_fees_row and unpaid_fees_row["total"] else Decimal("0.00")
    
    # Active notices
    notices = HostelNotice.objects.filter(is_active=1).order_by("-notice_id")[:5]
    
    # Recents
    recent_allocations = HostelAllocation.objects.filter(status="Active").order_by("-allocation_id")[:5]
    recent_discipline = HostelDiscipline.objects.all().order_by("-discipline_id")[:5]
    
    context = {
        "title": "Hostel Operations Command Center",
        "stats": [
            ("Active Boarders", total_boarders),
            ("Total Hostels", total_hostels),
            ("Beds Vacant", available_beds),
            ("Occupancy Rate", f"{occupancy_rate}%"),
        ],
        "pending_maintenance": pending_maintenance,
        "visitors_today": visitors_today,
        "unpaid_fees": unpaid_fees,
        "notices": notices,
        "recent_allocations": recent_allocations,
        "recent_discipline": recent_discipline,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/dashboard.html", context)


@permission_required("hostel.manage")
def hostel_list(request):
    hostels = Hostel.objects.filter(status="Active")
    context = {
        "title": "Hostel Infrastructure",
        "hostels": hostels,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/hostel_list.html", context)


@permission_required("hostel.manage")
def hostel_new(request):
    if request.method == "POST":
        code = request.POST.get("hostel_code", "").strip()
        name = request.POST.get("hostel_name", "").strip()
        hostel_type = request.POST.get("hostel_type", "MIXED")
        warden_id = request.POST.get("warden_id") or None
        
        if not code or not name:
            messages.error(request, "Hostel Code and Name are mandatory.")
        else:
            try:
                hostel = Hostel.objects.create(
                    hostel_code=code,
                    hostel_name=name,
                    hostel_type=hostel_type,
                    warden_id=warden_id,
                    status="Active",
                )
                audit_action(request, "Create Hostel", f"Created hostel '{name}' ({code})")
                messages.success(request, "Hostel structure created successfully.")
                return redirect("hostel_list")
            except Exception as e:
                messages.error(request, f"Error building hostel: {e}")
                
    wardens = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": "Build New Hostel",
        "wardens": wardens,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/hostel_form.html", context)


@permission_required("hostel.manage")
def hostel_edit(request, hostel_id):
    hostel = get_object_or_404(Hostel, pk=hostel_id)
    if request.method == "POST":
        name = request.POST.get("hostel_name", "").strip()
        hostel_type = request.POST.get("hostel_type", "MIXED")
        warden_id = request.POST.get("warden_id") or None
        
        if not name:
            messages.error(request, "Hostel Name is required.")
        else:
            try:
                hostel.hostel_name = name
                hostel.hostel_type = hostel_type
                hostel.warden_id = warden_id
                hostel.save()
                audit_action(request, "Edit Hostel", f"Modified hostel details of '{name}'")
                messages.success(request, "Hostel details updated successfully.")
                return redirect("hostel_list")
            except Exception as e:
                messages.error(request, f"Error updating: {e}")
                
    wardens = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": "Modify Hostel Infrastructure",
        "hostel": hostel,
        "wardens": wardens,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/hostel_form.html", context)


@permission_required("hostel.manage")
def hostel_delete(request, hostel_id):
    hostel = get_object_or_404(Hostel, pk=hostel_id)
    # Verify active residents
    residents = HostelAllocation.objects.filter(hostel=hostel, status="Active").count()
    if residents > 0:
        messages.error(request, f"Cannot delete hostel '{hostel.hostel_name}' because it contains {residents} active boarders.")
        return redirect("hostel_list")
        
    hostel.status = "Deactivated"
    hostel.save()
    audit_action(request, "Deactivate Hostel", f"Soft-deleted/Deactivated hostel '{hostel.hostel_name}'")
    messages.success(request, "Hostel deactivated successfully.")
    return redirect("hostel_list")


@permission_required("hostel.manage")
def room_list(request, hostel_id):
    hostel = get_object_or_404(Hostel, pk=hostel_id)
    rooms = hostel.rooms.exclude(status="Closed")
    
    context = {
        "title": f"Rooms Catalogue: {hostel.hostel_name}",
        "hostel": hostel,
        "rooms": rooms,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/room_list.html", context)


@permission_required("hostel.manage")
def room_new(request, hostel_id):
    hostel = get_object_or_404(Hostel, pk=hostel_id)
    if request.method == "POST":
        num = request.POST.get("room_number", "").strip()
        floor = int(request.POST.get("floor", 0))
        capacity = int(request.POST.get("capacity", 4))
        
        if not num:
            messages.error(request, "Room number is required.")
        else:
            try:
                room = HostelRoom.objects.create(
                    room_number=num,
                    hostel=hostel,
                    floor=floor,
                    capacity=capacity,
                    current_occupancy=0,
                    status="Available",
                )
                
                # Auto generate beds
                for i in range(1, capacity + 1):
                    HostelBed.objects.create(
                        bed_number=f"{num}-{i}",
                        room=room,
                        status="Available",
                    )
                    
                sync_room_occupancy(room.pk)
                audit_action(request, "Create Room", f"Created room {num} and beds in hostel '{hostel.hostel_name}'")
                messages.success(request, f"Room {num} with {capacity} beds generated successfully.")
                return redirect("room_list", hostel_id=hostel_id)
            except Exception as e:
                messages.error(request, f"Error creating room: {e}")
                
    context = {
        "title": "Configure New Room",
        "hostel": hostel,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/room_form.html", context)


@permission_required("hostel.manage")
def bed_map_grid(request, room_id):
    room = get_object_or_404(HostelRoom, pk=room_id)
    beds = room.beds.all().order_by("bed_number")
    
    context = {
        "title": f"Bed Layout Grid: Room {room.room_number}",
        "room": room,
        "beds": beds,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/bed_grid.html", context)


@permission_required("hostel.manage")
def allocation_list(request):
    allocations = HostelAllocation.objects.filter(status="Active")
    context = {
        "title": "Boarders Ledger",
        "allocations": allocations,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/allocation_list.html", context)


@permission_required("hostel.manage")
def allocation_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        hostel_id = request.POST.get("hostel_id")
        room_id = request.POST.get("room_id")
        bed_id = request.POST.get("bed_id")
        boarding_fee = Decimal(request.POST.get("boarding_fee", "120.00"))
        
        try:
            student = get_object_or_404(Student, pk=student_id)
            hostel = get_object_or_404(Hostel, pk=hostel_id)
            room = get_object_or_404(HostelRoom, pk=room_id)
            bed = get_object_or_404(HostelBed, pk=bed_id)
            
            # 1. Gender Enforcements
            student_gender = (student.gender or "Male").upper()
            hostel_type = hostel.hostel_type.upper()
            
            if hostel_type == "BOYS" and student_gender != "MALE":
                raise ValueError("Cannot assign a female student to a Boys Hostel.")
            elif hostel_type == "GIRLS" and student_gender == "MALE":
                raise ValueError("Cannot assign a male student to a Girls Hostel.")
                
            # 2. Availability Checks
            if bed.status != "Available":
                raise ValueError(f"Bed {bed.bed_number} is not available (Status: {bed.status}).")
                
            # Check if student already has active allocation
            active_alloc = HostelAllocation.objects.filter(pupil=student, status="Active").first()
            if active_alloc:
                raise ValueError(f"Student {student.admission_no} already holds active bed allocation in room {active_alloc.room.room_number}.")
                
            with transaction.atomic():
                # Allocate
                alloc = HostelAllocation.objects.create(
                    pupil=student,
                    hostel=hostel,
                    room=room,
                    bed=bed,
                    boarding_date=today_text(),
                    status="Active",
                    guardian_notified=1,
                    fee_posted=1,
                    created_at=now_text(),
                )
                
                # Update bed status
                bed.status = "Occupied"
                bed.current_occupant = student
                bed.save()
                
                sync_room_occupancy(room.pk)
                
                # Generate Fee record and invoice
                HostelFeeRecord.objects.create(
                    pupil=student,
                    charge_type="Boarding Fees",
                    amount=boarding_fee,
                    date_charged=today_text(),
                    status="Unpaid",
                )
                
                # Integration with fees_management
                from library.views import post_library_fine # reuse invoice post helper
                post_library_fine(
                    request,
                    student,
                    boarding_fee,
                    f"Hostel Boarding Fees. Hostel: {hostel.hostel_name}, Room: {room.room_number}"
                )
                
                # Notification
                parent_msg = f"Parent notification: Your child {student.first_name} {student.surname} has been allocated room {room.room_number}, Bed {bed.bed_number} in {hostel.hostel_name} today."
                if table_exists("communication_log"):
                    insert_record(
                        request,
                        "communication_log",
                        {
                            "pupil_id": student.pk,
                            "channel": "SMS",
                            "message_type": "Hostel Allocation",
                            "status": "Sent",
                            "created_at": now_text(),
                            "notes": parent_msg,
                            "subject": "Hostel Bed Allocation"
                        }
                    )
                
                audit_action(request, "Boarder Allocation", f"Allocated student {student.admission_no} to {bed.bed_number} (Allocation ID: {alloc.pk})")
                messages.success(request, f"Student {student.full_name} assigned to bed {bed.bed_number} successfully.")
                return redirect("allocation_list")
                
        except Exception as e:
            messages.error(request, f"Allocation failed: {e}")
            
    students = Student.objects.filter(status="Active Student")
    hostels = Hostel.objects.filter(status="Active")
    rooms = HostelRoom.objects.filter(status="Available")
    beds = HostelBed.objects.filter(status="Available")
    
    context = {
        "title": "Allocate Bed Space",
        "students": students,
        "hostels": hostels,
        "rooms": rooms,
        "beds": beds,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/allocation_form.html", context)


@permission_required("hostel.manage")
def allocation_transfer(request, allocation_id):
    alloc = get_object_or_404(HostelAllocation, pk=allocation_id)
    student = alloc.pupil
    
    if request.method == "POST":
        new_hostel_id = request.POST.get("hostel_id")
        new_room_id = request.POST.get("room_id")
        new_bed_id = request.POST.get("bed_id")
        reason = request.POST.get("reason", "").strip()
        
        try:
            new_hostel = get_object_or_404(Hostel, pk=new_hostel_id)
            new_room = get_object_or_404(HostelRoom, pk=new_room_id)
            new_bed = get_object_or_404(HostelBed, pk=new_bed_id)
            
            # Enforce gender matching on new hostel
            student_gender = (student.gender or "Male").upper()
            hostel_type = new_hostel.hostel_type.upper()
            if hostel_type == "BOYS" and student_gender != "MALE":
                raise ValueError("New hostel is boys only.")
            elif hostel_type == "GIRLS" and student_gender == "MALE":
                raise ValueError("New hostel is girls only.")
                
            if new_bed.status != "Available":
                raise ValueError("Target bed is not vacant.")
                
            with transaction.atomic():
                # Log transfer
                warden_profile = EmployeeProfile.objects.filter(user=request.user).first()
                if not warden_profile:
                    # Fallback to first active staff or self
                    warden_profile = EmployeeProfile.objects.filter(status="ACTIVE").first()
                    
                HostelTransfer.objects.create(
                    pupil=student,
                    previous_allocation_id=allocation_id,
                    new_hostel=new_hostel,
                    new_room=new_room,
                    new_bed=new_bed,
                    reason=reason,
                    transfer_date=today_text(),
                    approved_by=warden_profile,
                )
                
                # Free old bed
                old_bed = alloc.bed
                old_bed.status = "Available"
                old_bed.current_occupant = None
                old_bed.save()
                sync_room_occupancy(alloc.room.pk)
                
                # Update old allocation
                alloc.status = "Transferred"
                alloc.save()
                
                # Create new allocation
                new_alloc = HostelAllocation.objects.create(
                    pupil=student,
                    hostel=new_hostel,
                    room=new_room,
                    bed=new_bed,
                    boarding_date=today_text(),
                    status="Active",
                    guardian_notified=1,
                    fee_posted=0,
                    created_at=now_text(),
                )
                
                # Fill target bed
                new_bed.status = "Occupied"
                new_bed.current_occupant = student
                new_bed.save()
                sync_room_occupancy(new_room.pk)
                
                audit_action(request, "Boarder Transfer", f"Transferred student {student.admission_no} to bed {new_bed.bed_number}")
                messages.success(request, f"Student {student.full_name} transferred to room {new_room.room_number} successfully.")
                return redirect("allocation_list")
                
        except Exception as e:
            messages.error(request, f"Transfer aborted: {e}")
            
    hostels = Hostel.objects.filter(status="Active")
    context = {
        "title": f"Transfer Boarder: {student.full_name}",
        "alloc": alloc,
        "hostels": hostels,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/transfer_form.html", context)


@permission_required("hostel.manage")
def allocation_vacate(request, allocation_id):
    alloc = get_object_or_404(HostelAllocation, pk=allocation_id)
    try:
        with transaction.atomic():
            # Release bed
            bed = alloc.bed
            bed.status = "Available"
            bed.current_occupant = None
            bed.save()
            
            # Vacate allocation
            alloc.status = "Vacated"
            alloc.save()
            
            sync_room_occupancy(alloc.room.pk)
            
            audit_action(request, "Boarder Vacated", f"Marked student {alloc.pupil.admission_no} as vacated from room {alloc.room.room_number}")
            messages.success(request, "Student marked as vacated from hostel room.")
    except Exception as e:
        messages.error(request, f"Could not process vacate request: {e}")
    return redirect("allocation_list")


@permission_required("hostel.manage")
def attendance_mark(request):
    selected_date = request.GET.get("date") or today_text()
    selected_slot = request.GET.get("time_slot") or "Evening"
    
    boarders = HostelAllocation.objects.filter(status="Active")
    
    if request.method == "POST":
        try:
            with transaction.atomic():
                staff_profile = EmployeeProfile.objects.filter(user=request.user).first() or EmployeeProfile.objects.filter(status="ACTIVE").first()
                
                for boarder in boarders:
                    student_pk = boarder.pupil.pk
                    status_val = request.POST.get(f"status_{student_pk}", "Present")
                    remarks = request.POST.get(f"remarks_{student_pk}", "").strip()
                    
                    # Check existing record
                    record = HostelAttendance.objects.filter(
                        pupil_id=student_pk, date=selected_date, time_slot=selected_slot
                    ).first()
                    
                    if record:
                        record.status = status_val
                        record.remarks = remarks
                        record.recorded_by = staff_profile
                        record.save()
                    else:
                        HostelAttendance.objects.create(
                            pupil_id=student_pk,
                            date=selected_date,
                            time_slot=selected_slot,
                            status=status_val,
                            remarks=remarks,
                            recorded_by=staff_profile,
                        )
                
                # Check chronic absences alerts (over 3 absences consecutively or high rate)
                check_attendance_anomalies(request, selected_date)
                
                audit_action(request, "Record Hostel Attendance", f"Recorded attendance for {selected_date} ({selected_slot})")
                messages.success(request, f"Hostel attendance checklist saved successfully.")
                return redirect(f"/hostels/attendance/?date={selected_date}&time_slot={selected_slot}")
        except Exception as e:
            messages.error(request, f"Error saving roll call: {e}")
            
    # Load marked values mapped by student PK
    marked_db = HostelAttendance.objects.filter(date=selected_date, time_slot=selected_slot)
    marked_map = {att.pupil_id: (att.status, att.remarks) for att in marked_db}
    
    boarders_list = []
    for b in boarders:
        s_pk = b.pupil.pk
        status_val, remark_val = marked_map.get(s_pk, ("Present", ""))
        boarders_list.append({
            "pupil": b.pupil,
            "hostel": b.hostel,
            "room": b.room,
            "bed": b.bed,
            "status": status_val,
            "remarks": remark_val
        })
        
    context = {
        "title": "Roll Call Attendance sheet",
        "boarders": boarders_list,
        "selected_date": selected_date,
        "selected_slot": selected_slot,
        "slots": ["Morning", "Evening", "Weekend"],
        "school_settings": school_settings(),
    }
    return render(request, "hostel/attendance_sheet.html", context)


# Check consecutive absence alarms
def check_attendance_anomalies(request, date_val):
    # Retrieve recent attendance ordered
    # Trigger alert if consecutive absences >= 3
    active_boarders = HostelAllocation.objects.filter(status="Active")
    for boarder in active_boarders:
        student = boarder.pupil
        recent = HostelAttendance.objects.filter(pupil=student).order_by("-date", "-attendance_id")[:3]
        absent_count = sum(1 for r in recent if r.status == "Absent")
        
        if absent_count >= 3:
            # Issue alarm trigger / notify parent
            msg = f"Hostel Alert: Pupil {student.first_name} {student.surname} has been marked ABSENT consecutively from roll call logs in {boarder.hostel.hostel_name}."
            if table_exists("communication_log"):
                insert_record(
                    request,
                    "communication_log",
                    {
                        "pupil_id": student.pk,
                        "channel": "SMS",
                        "message_type": "Hostel Absence Alert",
                        "status": "Sent",
                        "created_at": now_text(),
                        "notes": msg,
                        "subject": "Chronic Hostel Absence Alert"
                    }
                )


@permission_required("hostel.manage")
def discipline_list(request):
    records = HostelDiscipline.objects.all().order_by("-incident_date")
    context = {
        "title": "Incident & Discipline Ledger",
        "records": records,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/discipline_list.html", context)


@permission_required("hostel.manage")
def discipline_new(request):
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        desc = request.POST.get("description", "").strip()
        action = request.POST.get("action_taken", "").strip()
        incident_date = request.POST.get("incident_date") or today_text()
        
        try:
            student = get_object_or_404(Student, pk=student_id)
            staff_profile = EmployeeProfile.objects.filter(user=request.user).first() or EmployeeProfile.objects.filter(status="ACTIVE").first()
            
            with transaction.atomic():
                record = HostelDiscipline.objects.create(
                    pupil=student,
                    incident_date=incident_date,
                    incident_description=desc,
                    action_taken=action,
                    staff=staff_profile,
                    parent_notified=1,
                )
                
                # Notify parent
                msg = f"Incident Alert: A discipline incident was recorded for {student.first_name} {student.surname} in the hostel on {incident_date}. Details: {desc}. Action: {action}."
                if table_exists("communication_log"):
                    insert_record(
                        request,
                        "communication_log",
                        {
                            "pupil_id": student.pk,
                            "channel": "SMS",
                            "message_type": "Discipline Incident",
                            "status": "Sent",
                            "created_at": now_text(),
                            "notes": msg,
                            "subject": "Hostel Incident Notification"
                        }
                    )
                
                audit_action(request, "Hostel Incident", f"Recorded discipline record for {student.admission_no} (Record ID: {record.pk})")
                messages.success(request, f"Discipline incident log posted successfully.")
                return redirect("hostel_discipline")
                
        except Exception as e:
            messages.error(request, f"Incident log failed: {e}")
            
    students = Student.objects.filter(status="Active Student")
    context = {
        "title": "Log Discipline Incident",
        "students": students,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "hostel/discipline_form.html", context)


@permission_required("hostel.manage")
def visitor_list(request):
    visitors = HostelVisitor.objects.all().order_by("-visit_date", "-visitor_id")
    context = {
        "title": "Visitor Approvals & Logs",
        "visitors": visitors,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/visitor_list.html", context)


@permission_required("hostel.manage")
def visitor_new(request):
    if request.method == "POST":
        v_name = request.POST.get("visitor_name", "").strip()
        rel = request.POST.get("relationship", "").strip()
        student_id = request.POST.get("student_id")
        phone = request.POST.get("contact_number", "").strip()
        
        try:
            student = get_object_or_404(Student, pk=student_id)
            staff_profile = EmployeeProfile.objects.filter(user=request.user).first() or EmployeeProfile.objects.filter(status="ACTIVE").first()
            
            with transaction.atomic():
                visitor = HostelVisitor.objects.create(
                    visitor_name=v_name,
                    relationship=rel,
                    pupil=student,
                    visit_date=today_text(),
                    time_in=datetime.datetime.now().strftime("%H:%M:%S"),
                    contact_number=phone,
                    approval_status="Approved",
                    approved_by=staff_profile,
                )
                
                # Generate QR Pass URL
                qr_path = generate_visitor_qr(visitor.visitor_id, v_name, student.admission_no)
                
                audit_action(request, "Log Visitor", f"Visitor {v_name} approved for student {student.admission_no}")
                messages.success(request, "Visitor check-in logged and gate pass generated.")
                return redirect("hostel_visitors")
                
        except Exception as e:
            messages.error(request, f"Visitor check-in failed: {e}")
            
    students = Student.objects.filter(status="Active Student")
    context = {
        "title": "Log Hostel Visitor Check-in",
        "students": students,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/visitor_form.html", context)


@permission_required("hostel.manage")
def visitor_checkout(request, visitor_id):
    visitor = get_object_or_404(HostelVisitor, pk=visitor_id)
    visitor.time_out = datetime.datetime.now().strftime("%H:%M:%S")
    visitor.approval_status = "Completed"
    visitor.save()
    
    audit_action(request, "Visitor Checkout", f"Checked out visitor {visitor.visitor_name} (ID: {visitor_id})")
    messages.success(request, "Visitor check-out logged successfully.")
    return redirect("hostel_visitors")


@permission_required("hostel.manage")
def visitor_pass_detail(request, visitor_id):
    visitor = get_object_or_404(HostelVisitor, pk=visitor_id)
    qr_url = f"/media/visitor_passes/visitor_{visitor_id}.png"
    
    context = {
        "title": "Visitor Gate Pass",
        "visitor": visitor,
        "qr_url": qr_url,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/visitor_pass.html", context)


@permission_required("hostel.manage")
def maintenance_list(request):
    requests = HostelMaintenance.objects.all().order_by("-reported_date")
    context = {
        "title": "Facility Maintenance Tickets",
        "requests": requests,
        "school_settings": school_settings(),
    }
    return render(request, "hostel/maintenance_list.html", context)


@permission_required("hostel.manage")
def maintenance_status_update(request, maintenance_id, status_val):
    ticket = get_object_or_404(HostelMaintenance, pk=maintenance_id)
    ticket.status = status_val
    ticket.save()
    
    audit_action(request, "Maintenance Ticket Status", f"Updated ticket {maintenance_id} status to '{status_val}'")
    messages.success(request, f"Maintenance status updated to '{status_val}'.")
    return redirect("hostel_maintenance")


# ================= STUDENT PORTAL HOSTEL VIEWS =================

from portals.views import student_portal_required

@student_portal_required
def student_portal_hostel(request, pupil):
    pupil_id = pupil["pupil_id"]
    student = Student.objects.get(pk=pupil_id)
    
    # Active allocation
    alloc = HostelAllocation.objects.filter(pupil=student, status="Active").first()
    
    # Medical context (linked student profile notes)
    allergies = student.allergies if hasattr(student, "allergies") else ""
    medical_notes = student.medical_notes if hasattr(student, "medical_notes") else "No chronic conditions logged."
    
    # Maintenance tickets reported by this student
    tickets = HostelMaintenance.objects.filter(reported_by=student).order_by("-reported_date")
    
    # Notices
    notices = HostelNotice.objects.filter(is_active=1).order_by("-notice_id")[:5]
    
    if request.method == "POST" and "report_maintenance" in request.POST:
        desc = request.POST.get("issue_description", "").strip()
        if not desc or not alloc:
            messages.error(request, "Issue description is required and you must reside in a hostel room.")
        else:
            try:
                HostelMaintenance.objects.create(
                    hostel=alloc.hostel,
                    room=alloc.room,
                    bed=alloc.bed,
                    issue_description=desc,
                    reported_by=student,
                    status="Pending",
                    reported_date=today_text(),
                )
                messages.success(request, "Maintenance issue reported successfully to warden.")
                return redirect("student_portal_hostel")
            except Exception as e:
                messages.error(request, f"Error saving maintenance request: {e}")
                
    context = {
        "title": "My Hostel Residency",
        "student": student,
        "alloc": alloc,
        "allergies": allergies,
        "medical_notes": medical_notes,
        "tickets": tickets,
        "notices": notices,
        "school_settings": school_settings(),
    }
    return render(request, "portals/student_hostel.html", context)
