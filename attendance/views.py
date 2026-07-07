from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages

from accounts.permissions import normalized_role, permission_required, assigned_classes_for_teacher
from school_system_django.native import (
    delete_record,
    render_record_form_page,
    render_table_page,
    export_rows,
    school_settings,
    one_row,
    dict_rows,
    today_text,
    now_text,
    legacy_user_id,
    hydrate_class_labels,
    active_pupils_for_class,
)


ATTENDANCE_FIELDS = ["pupil_id", "class_id", "attendance_date", "status", "notes"]


def _active_students_for_class_id(class_id, fields="pupil_id, admission_no, first_name, surname, gender"):
    selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [class_id])
    if not selected_class:
        return []
    grade = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class.get("grade_id")])
    return active_pupils_for_class(selected_class, (grade or {}).get("grade_name") or "", fields)


@permission_required("attendance.manage")
def student_attendance(request):
    tab = request.GET.get("tab") or "register"
    tabs = [
        {"label": "Mark Daily Register", "href": "/attendance?tab=register", "active": tab == "register"},
        {"label": "Daily Log History", "href": "/attendance?tab=log", "active": tab == "log"},
        {"label": "Weekly Grid", "href": "/attendance?tab=weekly", "active": tab == "weekly"},
        {"label": "Monthly Attendance", "href": "/attendance?tab=monthly", "active": tab == "monthly"},
    ]

    if tab == "register":
        from django.db import connection
        allowed_class_ids = assigned_classes_for_teacher(request.user)

        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            classes = dict_rows(
                f"SELECT class_id, class_name, grade_id, academic_year FROM classes WHERE class_id IN ({placeholders}) ORDER BY academic_year DESC, class_name",
                allowed_class_ids
            )
        else:
            classes = []
        classes = hydrate_class_labels(classes)

        selected_class_id = request.GET.get("class_id") or request.POST.get("class_id")
        selected_date = request.GET.get("date") or request.POST.get("date") or today_text()
        if request.method == "POST" and selected_date > today_text():
            messages.error(request, "Attendance cannot be marked for a future date.")
            return redirect("/attendance?tab=register")

        students_with_attendance = []

        if selected_class_id:
            if allowed_class_ids and int(selected_class_id) not in allowed_class_ids:
                messages.error(request, "You are not assigned to manage attendance for this class.")
                return redirect("/attendance?tab=register")

            students = _active_students_for_class_id(selected_class_id)

            for s in students:
                record = one_row(
                    "SELECT status, notes FROM attendance_records WHERE pupil_id = %s AND attendance_date = %s",
                    [s["pupil_id"], selected_date]
                )
                students_with_attendance.append({
                    "pupil_id": s["pupil_id"],
                    "admission_no": s["admission_no"],
                    "first_name": s["first_name"],
                    "surname": s["surname"],
                    "gender": s["gender"],
                    "status": record["status"] if record else "Present",
                    "notes": record["notes"] if record else ""
                })

        if request.GET.get("export") == "pdf" and selected_class_id:
            rows = [
                {
                    "admission_no": item["admission_no"],
                    "student_name": f"{item['first_name']} {item['surname']}",
                    "gender": item["gender"],
                    "status": item["status"],
                    "notes": item["notes"],
                }
                for item in students_with_attendance
            ]
            return export_rows(
                f"Attendance Register {selected_date}",
                rows,
                ["admission_no", "student_name", "gender", "status", "notes"],
                "pdf",
            )

        if request.method == "POST" and selected_class_id:
            marked_count = 0
            with connection.cursor() as cursor:
                for item in students_with_attendance:
                    status_val = request.POST.get(f"status_{item['pupil_id']}") or "Present"
                    notes_val = (request.POST.get(f"notes_{item['pupil_id']}") or "").strip()

                    exists = one_row(
                        "SELECT attendance_id FROM attendance_records WHERE pupil_id = %s AND attendance_date = %s",
                        [item["pupil_id"], selected_date]
                    )

                    if exists:
                        cursor.execute(
                            """
                            UPDATE attendance_records
                            SET status = %s, notes = %s, marked_by = %s, updated_at = %s
                            WHERE attendance_id = %s
                            """,
                            [status_val, notes_val, legacy_user_id(request), now_text(), exists["attendance_id"]]
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO attendance_records (pupil_id, class_id, attendance_date, status, notes, marked_by, marked_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [item["pupil_id"], int(selected_class_id), selected_date, status_val, notes_val, legacy_user_id(request), now_text(), now_text()]
                        )
                    marked_count += 1

            from school_system_django.native import audit_action
            audit_action(request, "Mark Daily Attendance", f"Marked attendance for class ID {selected_class_id} on {selected_date}")
            messages.success(request, f"Attendance register saved for {marked_count} student(s).")
            return redirect(f"/attendance?tab=register&class_id={selected_class_id}&date={selected_date}")

        context = {
            "classes": classes,
            "selected_class_id": selected_class_id,
            "selected_date": selected_date,
            "students_with_attendance": students_with_attendance,
            "settings": school_settings(),
            "tabs": tabs,
            "active_tab": "register",
        }
        return render(request, "attendance/class_register_form.html", context)

    elif tab == "log":
        log_where = None
        log_params = None
        if normalized_role(request.user) == "Teacher":
            allowed_class_ids = assigned_classes_for_teacher(request.user)
            if allowed_class_ids:
                placeholders = ", ".join(["%s"] * len(allowed_class_ids))
                log_where = f"class_id IN ({placeholders})"
                log_params = allowed_class_ids
            else:
                log_where = "1 = 0"
                log_params = []
        return render_table_page(
            request,
            "Attendance Log",
            "attendance_records",
            ["attendance_id", "pupil_id", "class_id", "attendance_date", "status", "notes", "marked_by"],
            "Daily learner attendance records.",
            order_by="attendance_date DESC",
            search_columns=["status", "notes"],
            where=log_where,
            params=log_params,
            pk_column="attendance_id",
            row_actions=[
                {"label": "Edit", "href": "/attendance/{attendance_id}/edit?next_tab=log", "icon": "bi-pencil", "class": "btn-outline-secondary"},
                {"label": "Delete", "href": "/attendance/{attendance_id}/delete?next_tab=log", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this attendance record?"},
            ],
            extra_context={"tabs": tabs, "active_tab": "log"}
        )

    elif tab == "weekly":
        from datetime import datetime, timedelta
        from django.db import connection

        selected_date_str = request.GET.get("date") or today_text()
        try:
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d")
        except ValueError:
            selected_date = datetime.strptime(today_text(), "%Y-%m-%d")

        monday = selected_date - timedelta(days=selected_date.weekday())
        week_dates = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
        week_days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        allowed_class_ids = assigned_classes_for_teacher(request.user)
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            classes = dict_rows(
                f"SELECT class_id, class_name, grade_id, academic_year FROM classes WHERE class_id IN ({placeholders}) ORDER BY academic_year DESC, class_name",
                allowed_class_ids
            )
        else:
            classes = []
        classes = hydrate_class_labels(classes)

        selected_class_id = request.GET.get("class_id") or (str(classes[0]["class_id"]) if classes else "")

        students_grid = []
        if selected_class_id:
            students = _active_students_for_class_id(selected_class_id)

            placeholders_dates = ", ".join(["%s"] * len(week_dates))
            records = dict_rows(
                f"""
                SELECT pupil_id, attendance_date, status
                FROM attendance_records
                WHERE class_id = %s AND attendance_date IN ({placeholders_dates})
                """,
                [int(selected_class_id)] + week_dates
            )

            att_map = {}
            for r in records:
                p_id = r["pupil_id"]
                d_str = str(r["attendance_date"])
                if len(d_str) > 10:
                    d_str = d_str[:10]
                status = r["status"]

                if p_id not in att_map:
                    att_map[p_id] = {}
                if status in ("Present", "Late"):
                    att_map[p_id][d_str] = "1"
                elif status == "Absent":
                    att_map[p_id][d_str] = "a"
                else:
                    att_map[p_id][d_str] = status

            for s in students:
                p_id = s["pupil_id"]
                daily_status = []
                present_count = 0
                absent_count = 0

                s_map = att_map.get(p_id, {})
                for d_str in week_dates:
                    val = s_map.get(d_str, ".")
                    daily_status.append(val)
                    if val == "1":
                        present_count += 1
                    elif val == "a":
                        absent_count += 1

                total = present_count + absent_count
                percentage = (present_count / total * 100) if total > 0 else 0.0

                students_grid.append({
                    "admission_no": s["admission_no"],
                    "name": f"{s['first_name']} {s['surname']}",
                    "gender": s["gender"],
                    "daily_status": daily_status,
                    "present_count": present_count,
                    "absent_count": absent_count,
                    "percentage": f"{percentage:.1f}%",
                })

        prev_week_date = (selected_date - timedelta(days=7)).strftime("%Y-%m-%d")
        next_week_date = (selected_date + timedelta(days=7)).strftime("%Y-%m-%d")
        week_days = [{"name": n, "date": d} for n, d in zip(week_days_names, week_dates)]

        context = {
            "classes": classes,
            "selected_class_id": selected_class_id,
            "selected_date": selected_date_str,
            "week_days": week_days,
            "students_grid": students_grid,
            "prev_week_date": prev_week_date,
            "next_week_date": next_week_date,
            "tabs": tabs,
            "active_tab": "weekly",
            "settings": school_settings(),
        }
        if request.GET.get("export") == "pdf" and selected_class_id:
            rows = []
            for row in students_grid:
                item = {key: row.get(key) for key in ["admission_no", "name", "gender", "present_count", "absent_count", "percentage"]}
                for idx, day in enumerate(week_days):
                    item[day["name"]] = row["daily_status"][idx]
                rows.append(item)
            return export_rows(
                f"Weekly Attendance {week_dates[0]} to {week_dates[-1]}",
                rows,
                ["admission_no", "name", "gender"] + [day["name"] for day in week_days] + ["present_count", "absent_count", "percentage"],
                "pdf",
            )
        return render(request, "attendance/weekly_grid.html", context)

    elif tab == "monthly":
        import calendar
        from datetime import datetime
        from django.db import connection

        allowed_class_ids = assigned_classes_for_teacher(request.user)
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            classes = dict_rows(
                f"SELECT class_id, class_name, grade_id, academic_year FROM classes WHERE class_id IN ({placeholders}) ORDER BY academic_year DESC, class_name",
                allowed_class_ids
            )
        else:
            classes = []
        classes = hydrate_class_labels(classes)

        selected_class_id = request.GET.get("class_id") or (str(classes[0]["class_id"]) if classes else "")
        
        now = datetime.now()
        selected_month = int(request.GET.get("month") or now.month)
        selected_year = int(request.GET.get("year") or now.year)

        months_list = [
            {"value": i, "name": calendar.month_name[i]} for i in range(1, 13)
        ]
        years_list = [selected_year - 1, selected_year, selected_year + 1]

        days_in_month = calendar.monthrange(selected_year, selected_month)[1]
        days = list(range(1, days_in_month + 1))

        students_grid = []
        if selected_class_id:
            students = _active_students_for_class_id(selected_class_id)

            is_postgres = connection.vendor == 'postgresql'
            if is_postgres:
                month_expr = "EXTRACT(MONTH FROM CAST(attendance_date AS DATE))"
                year_expr = "EXTRACT(YEAR FROM CAST(attendance_date AS DATE))"
                day_expr = "EXTRACT(DAY FROM CAST(attendance_date AS DATE))"
            else:
                month_expr = "CAST(strftime('%%m', attendance_date) AS INTEGER)"
                year_expr = "CAST(strftime('%%Y', attendance_date) AS INTEGER)"
                day_expr = "CAST(strftime('%%d', attendance_date) AS INTEGER)"

            records = dict_rows(
                f"""
                SELECT pupil_id, {day_expr} AS day_of_month, status
                FROM attendance_records
                WHERE class_id = %s AND {month_expr} = %s AND {year_expr} = %s
                """,
                [int(selected_class_id), selected_month, selected_year]
            )

            # Map records: pupil_id -> day -> status
            att_map = {}
            for r in records:
                p_id = r["pupil_id"]
                day = int(r["day_of_month"])
                status = r["status"]
                if p_id not in att_map:
                    att_map[p_id] = {}
                # Map Present/Late to 1, Absent to a
                if status in ("Present", "Late"):
                    att_map[p_id][day] = "1"
                elif status == "Absent":
                    att_map[p_id][day] = "a"
                else:
                    att_map[p_id][day] = status

            for s in students:
                p_id = s["pupil_id"]
                daily_status = []
                present_count = 0
                absent_count = 0
                
                s_map = att_map.get(p_id, {})
                for d in days:
                    val = s_map.get(d, ".")
                    daily_status.append(val)
                    if val == "1":
                        present_count += 1
                    elif val == "a":
                        absent_count += 1
                
                total = present_count + absent_count
                percentage = (present_count / total * 100) if total > 0 else 0.0

                students_grid.append({
                    "admission_no": s["admission_no"],
                    "name": f"{s['first_name']} {s['surname']}",
                    "gender": s["gender"],
                    "daily_status": daily_status,
                    "present_count": present_count,
                    "absent_count": absent_count,
                    "percentage": f"{percentage:.1f}%",
                })

        context = {
            "classes": classes,
            "selected_class_id": selected_class_id,
            "selected_month": selected_month,
            "selected_year": selected_year,
            "months_list": months_list,
            "years_list": years_list,
            "days": days,
            "students_grid": students_grid,
            "tabs": tabs,
            "active_tab": "monthly",
            "settings": school_settings(),
        }
        if request.GET.get("export") == "pdf" and selected_class_id:
            rows = []
            day_columns = [str(day) for day in days]
            for row in students_grid:
                item = {key: row.get(key) for key in ["admission_no", "name", "gender", "present_count", "absent_count", "percentage"]}
                for idx, day in enumerate(day_columns):
                    item[day] = row["daily_status"][idx]
                rows.append(item)
            return export_rows(
                f"Monthly Attendance {selected_month}-{selected_year}",
                rows,
                ["admission_no", "name", "gender"] + day_columns + ["present_count", "absent_count", "percentage"],
                "pdf",
            )
        return render(request, "attendance/monthly_grid.html", context)


@permission_required("attendance.manage")
def monthly(request):
    return redirect("/attendance?tab=monthly")


@permission_required("attendance.manage")
def new(request):
    next_tab = request.GET.get("next_tab", "log")
    return render_record_form_page(request, "Mark Student Attendance", "attendance_records", ATTENDANCE_FIELDS, redirect_to=f"/attendance?tab={next_tab}")


@permission_required("attendance.manage")
def edit(request, attendance_id):
    next_tab = request.GET.get("next_tab", "log")
    row = one_row("SELECT class_id FROM attendance_records WHERE attendance_id = %s", [attendance_id])
    if normalized_role(request.user) == "Teacher":
        allowed_class_ids = assigned_classes_for_teacher(request.user)
        if not row or row.get("class_id") not in allowed_class_ids:
            messages.error(request, "You are not assigned to manage this attendance record.")
            return redirect(f"/attendance?tab={next_tab}")
    return render_record_form_page(
        request,
        "Edit Student Attendance",
        "attendance_records",
        ATTENDANCE_FIELDS,
        pk_column="attendance_id",
        pk_value=attendance_id,
        redirect_to=f"/attendance?tab={next_tab}",
    )


@permission_required("attendance.manage")
def delete(request, attendance_id):
    next_tab = request.GET.get("next_tab", "log")
    row = one_row("SELECT class_id FROM attendance_records WHERE attendance_id = %s", [attendance_id])
    if normalized_role(request.user) == "Teacher":
        allowed_class_ids = assigned_classes_for_teacher(request.user)
        if not row or row.get("class_id") not in allowed_class_ids:
            messages.error(request, "You are not assigned to delete this attendance record.")
            return redirect(f"/attendance?tab={next_tab}")
    return delete_record(request, "Student Attendance", "attendance_records", "attendance_id", attendance_id, f"/attendance?tab={next_tab}")


@permission_required("attendance.manage")
def class_attendance_register(request):
    if request.method == "POST":
        return student_attendance(request)
    selected_class_id = request.GET.get("class_id") or ""
    selected_date = request.GET.get("date") or ""
    url = "/attendance?tab=register"
    if selected_class_id:
        url += f"&class_id={selected_class_id}"
    if selected_date:
        url += f"&date={selected_date}"
    return redirect(url)
