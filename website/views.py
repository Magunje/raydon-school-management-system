from django.contrib import messages
from django.shortcuts import redirect, render

from school_system_django.native import count_table, insert_record, now_text, one_row, school_settings, dict_rows, table_exists


def count_sql(sql, params=None):
    row = one_row(sql, params or [])
    return int(row["total"] or 0) if row else 0


def optional_rows(table_name, sql, params=None):
    if not table_exists(table_name):
        return []
    return dict_rows(sql, params or [])


def home(request):
    is_saas_portal = False
    if hasattr(request, "tenant") and request.tenant is None:
        is_saas_portal = True

    if is_saas_portal:
        return render(request, "website/saas_landing.html")

    settings = school_settings()
    stats = [
        ("Students", count_sql("SELECT COUNT(*) AS total FROM pupils WHERE COALESCE(status, 'Active') = 'Active'")),
        ("Teachers", count_sql("SELECT COUNT(*) AS total FROM users WHERE role = 'Teacher' AND COALESCE(status, 'Active') = 'Active'")),
        ("Classes", count_table("classes")),
        ("Subjects", count_table("subjects")),
    ]
    announcements = optional_rows(
        "website_announcements",
        "SELECT * FROM website_announcements WHERE status = 'Published' ORDER BY created_at DESC LIMIT 6",
    )
    return render(request, "website/home.html", {"settings": settings, "stats": stats, "announcements": announcements})


PUBLIC_PAGES = {
    "about-us": ("About Us", "School profile, mission, vision, and leadership."),
    "admissions": ("Admissions", "Admission requirements, process, and enquiry information."),
    "academics": ("Academics", "Curriculum, classes, subjects, and academic support."),
    "departments": ("Departments & Staff", "School departments and active staff directory."),
    "gallery": ("Gallery", "School life, sports, and events gallery."),
    "events": ("Events Calendar", "Upcoming school events and term activities."),
    "news": ("Latest News", "Latest school notices and announcements."),
    "contact-us": ("Contact Us", "Contact details and location information."),
}


def page(request, slug):
    title, subtitle = PUBLIC_PAGES.get(slug, ("School Website", "Public school information."))
    context = {
        "settings": school_settings(),
        "title": title,
        "subtitle": subtitle,
        "slug": slug,
    }
    
    if slug == "academics":
        context["subjects"] = dict_rows("SELECT subject_code, subject_name, grade FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name LIMIT 30")
        
    elif slug in ["departments", "about-us"]:
        context["teachers"] = dict_rows("SELECT user_id, full_name, username FROM users WHERE role = 'Teacher' AND status = 'Active' ORDER BY full_name")
        
    elif slug in ["news", "events"]:
        context["announcements"] = optional_rows(
            "website_announcements",
            "SELECT * FROM website_announcements WHERE status = 'Published' ORDER BY created_at DESC",
        )
        
    return render(request, "website/page.html", context)


def enquiry(request):
    if request.method == "POST":
        name = request.POST.get("name") or "Website visitor"
        phone = request.POST.get("phone") or ""
        email = request.POST.get("email") or ""
        message = request.POST.get("message") or ""
        insert_record(
            request,
            "communication_log",
            {
                "guardian_phone": phone,
                "channel": "Website",
                "message_type": "Online Enquiry",
                "status": "New",
                "message_body": f"Name: {name}\nEmail: {email}\nPhone: {phone}\n\n{message}",
                "created_at": now_text(),
            },
        )
        messages.success(request, "Your enquiry has been submitted.")
        return redirect("website")
    return render(request, "website/enquiry.html", {"settings": school_settings()})

# Create your views here.
