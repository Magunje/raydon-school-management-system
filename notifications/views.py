from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
import os

from accounts.permissions import permission_required
from school_system_django.native import render_detail_page, render_table_page, school_settings, one_row, delete_record, insert_record, now_text


@permission_required("notifications.manage")
def notifications(request):
    return render_table_page(
        request,
        "Notifications",
        "communication_log",
        ["communication_id", "pupil_id", "channel", "message_type", "status", "created_at"],
        "SMS, WhatsApp, meeting, attendance, fees, result, and announcement logs.",
        order_by="created_at DESC",
        search_columns=["channel", "message_type", "status"],
        pk_column="communication_id",
        row_actions=[
            {"label": "View", "href": "/notifications/{communication_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
        ],
    )


@permission_required("notifications.manage")
def detail(request, communication_id):
    return render_detail_page(request, "Notification", "communication_log", "communication_id", communication_id)


@permission_required("notifications.manage")
def announcements(request):
    from school_system_django.native import dict_rows
    rows = dict_rows("SELECT * FROM website_announcements ORDER BY created_at DESC")
    return render(
        request,
        "notifications/announcements.html",
        {
            "title": "Website Announcements",
            "announcements": rows,
            "settings": school_settings(),
        }
    )


@permission_required("notifications.manage")
def announcement_new(request):
    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")
        status = request.POST.get("status") or "Published"
        
        image_path = None
        if request.FILES.get("picture"):
            try:
                uploaded_file = request.FILES["picture"]
                import uuid
                from datetime import datetime
                
                base_dir = "uploads"
                target_dir = os.path.join(base_dir, "website")
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                    
                ext = os.path.splitext(uploaded_file.name)[1]
                unique_name = f"announcement-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{ext}"
                target_path = os.path.join(target_dir, unique_name)
                
                with open(target_path, "wb+") as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                        
                image_path = os.path.join("website", unique_name).replace("\\", "/")
            except Exception as exc:
                messages.error(request, f"Failed to upload image: {exc}")
                
        data = {
            "title": title,
            "content": content,
            "status": status,
            "image_path": image_path,
            "created_at": now_text(),
            "updated_at": now_text(),
        }
        
        try:
            insert_record(request, "website_announcements", data)
            messages.success(request, "Announcement created successfully.")
            return redirect("/django/notifications/announcements/")
        except Exception as exc:
            messages.error(request, f"Could not create announcement: {exc}")
            
    context = {
        "title": "New Announcement",
        "settings": school_settings(),
    }
    return render(request, "notifications/announcement_form.html", context)


@permission_required("notifications.manage")
def announcement_delete(request, announcement_id):
    announcement = one_row("SELECT * FROM website_announcements WHERE announcement_id = %s", [announcement_id])
    if announcement and announcement.get("image_path"):
        try:
            path = os.path.join("uploads", announcement["image_path"])
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    return delete_record(request, "Announcement", "website_announcements", "announcement_id", announcement_id, "/django/notifications/announcements/")
