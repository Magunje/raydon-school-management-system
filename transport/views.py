import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.conf import settings

from accounts.permissions import permission_required, user_has_permission
from student_registry.models import Student
from human_resources.models import EmployeeProfile
from transport.models import (
    TransportVehicle,
    TransportDriver,
    TransportRoute,
    TransportPickupPoint,
    TransportRegistration,
    TransportAttendance,
    TransportMaintenance,
    TransportFuelLog,
    TransportIncident
)
from fees_management.models import StudentFeeAccount, Invoice, InvoiceItem, FeeCategory
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


@permission_required("transport.manage")
def transport_dashboard(request):
    # Stats
    total_vehicles = TransportVehicle.objects.count()
    active_routes = TransportRoute.objects.filter(status="Active").count()
    total_students = TransportRegistration.objects.filter(status="Active").count()
    
    # Capacity statistics
    vehicles = TransportVehicle.objects.all()
    avg_utilisation = 0
    if vehicles.exists():
        total_cap = sum(v.capacity for v in vehicles)
        allocated = sum(TransportRegistration.objects.filter(assigned_vehicle=v, status="Active").count() for v in vehicles)
        if total_cap > 0:
            avg_utilisation = int((allocated / total_cap) * 100)
            
    # Maintenance reminders: vehicles due for service (next service within 30 days)
    upcoming_service = TransportMaintenance.objects.filter(
        next_service_date__gte=datetime.date.today(),
        next_service_date__lte=datetime.date.today() + datetime.timedelta(days=30)
    ).select_related("vehicle")
    
    # Recent incidents
    incidents = TransportIncident.objects.all().order_by("-incident_date")[:5]
    
    # Total transport fee collection / outstanding balance
    outstanding_fees = Decimal("0.00")
    if table_exists("invoices"):
        row = one_row("SELECT SUM(outstanding_balance) as outstanding FROM student_fee_accounts")
        if row and row.get("outstanding"):
            outstanding_fees = Decimal(row["outstanding"]) * Decimal("0.15") # Transport estimation share
            
    stats = [
        ("Total Vehicles", total_vehicles),
        ("Active Routes", active_routes),
        ("Transport Boarders", total_students),
        ("Capacity Utilisation", f"{avg_utilisation}%"),
    ]
    
    context = {
        "title": "Transport Hub Operations",
        "stats": stats,
        "upcoming_service": upcoming_service,
        "incidents": incidents,
        "outstanding_fees": outstanding_fees,
        "school_settings": school_settings(),
    }
    return render(request, "transport/dashboard.html", context)


@permission_required("transport.manage")
def vehicle_list(request):
    vehicles = TransportVehicle.objects.all()
    context = {
        "title": "Vehicle Registry",
        "vehicles": vehicles,
        "school_settings": school_settings(),
    }
    return render(request, "transport/vehicle_list.html", context)


@permission_required("transport.manage")
def vehicle_new(request):
    if request.method == "POST":
        reg = request.POST.get("registration_number", "").strip()
        name = request.POST.get("vehicle_name", "").strip()
        vtype = request.POST.get("vehicle_type", "").strip()
        make = request.POST.get("make", "").strip()
        model = request.POST.get("model", "").strip()
        year = request.POST.get("year")
        capacity = request.POST.get("capacity")
        fuel = request.POST.get("fuel_type", "").strip()
        pdate = request.POST.get("purchase_date")
        mileage = request.POST.get("current_mileage", 0)
        
        try:
            vehicle = TransportVehicle.objects.create(
                registration_number=reg,
                vehicle_name=name,
                vehicle_type=vtype,
                make=make,
                model=model,
                year=int(year) if year else None,
                capacity=int(capacity) if capacity else 15,
                fuel_type=fuel,
                purchase_date=pdate if pdate else None,
                current_mileage=int(mileage) if mileage else 0,
                status="Active",
            )
            audit_action(request, "Vehicle Created", f"Registered vehicle {reg} - {name}")
            messages.success(request, f"Vehicle '{name}' registered successfully.")
            return redirect("vehicle_list")
        except Exception as e:
            messages.error(request, f"Error registering vehicle: {e}")
            
    context = {
        "title": "Register Vehicle",
        "school_settings": school_settings(),
    }
    return render(request, "transport/vehicle_form.html", context)


@permission_required("transport.manage")
def vehicle_edit(request, vehicle_id):
    vehicle = get_object_or_404(TransportVehicle, pk=vehicle_id)
    if request.method == "POST":
        vehicle.vehicle_name = request.POST.get("vehicle_name", "").strip()
        vehicle.vehicle_type = request.POST.get("vehicle_type", "").strip()
        vehicle.make = request.POST.get("make", "").strip()
        vehicle.model = request.POST.get("model", "").strip()
        year = request.POST.get("year")
        vehicle.year = int(year) if year else None
        capacity = request.POST.get("capacity")
        vehicle.capacity = int(capacity) if capacity else vehicle.capacity
        vehicle.fuel_type = request.POST.get("fuel_type", "").strip()
        pdate = request.POST.get("purchase_date")
        vehicle.purchase_date = pdate if pdate else None
        mileage = request.POST.get("current_mileage")
        vehicle.current_mileage = int(mileage) if mileage else vehicle.current_mileage
        vehicle.status = request.POST.get("status", vehicle.status)
        
        try:
            vehicle.save()
            audit_action(request, "Vehicle Updated", f"Updated vehicle {vehicle.registration_number}")
            messages.success(request, f"Vehicle '{vehicle.vehicle_name}' updated successfully.")
            return redirect("vehicle_list")
        except Exception as e:
            messages.error(request, f"Error saving vehicle: {e}")
            
    context = {
        "title": f"Edit Vehicle: {vehicle.registration_number}",
        "vehicle": vehicle,
        "school_settings": school_settings(),
    }
    return render(request, "transport/vehicle_form.html", context)


@permission_required("transport.manage")
def driver_list(request):
    drivers = TransportDriver.objects.all().select_related("employee", "assigned_vehicle")
    
    # Calculate licence expiry notifications
    today = datetime.date.today()
    for d in drivers:
        d.licence_expiry_soon = d.licence_expiry <= today + datetime.timedelta(days=30)
        d.medical_expiry_soon = d.medical_expiry <= today + datetime.timedelta(days=30)
        
    context = {
        "title": "Driver Rosters",
        "drivers": drivers,
        "school_settings": school_settings(),
    }
    return render(request, "transport/driver_list.html", context)


@permission_required("transport.manage")
def driver_new(request):
    if request.method == "POST":
        emp_id = request.POST.get("employee_id")
        lic = request.POST.get("licence_number", "").strip()
        lexp = request.POST.get("licence_expiry")
        mexp = request.POST.get("medical_expiry")
        veh_id = request.POST.get("assigned_vehicle_id")
        
        try:
            emp = get_object_or_404(EmployeeProfile, pk=emp_id)
            veh = TransportVehicle.objects.get(pk=veh_id) if veh_id else None
            
            driver = TransportDriver.objects.create(
                employee=emp,
                licence_number=lic,
                licence_expiry=lexp,
                medical_expiry=mexp,
                assigned_vehicle=veh,
                status="Active",
            )
            audit_action(request, "Driver Created", f"Registered driver {emp.full_name}")
            messages.success(request, f"Driver profile for '{emp.full_name}' created successfully.")
            return redirect("driver_list")
        except Exception as e:
            messages.error(request, f"Error creating driver profile: {e}")
            
    employees = EmployeeProfile.objects.filter(status="ACTIVE")
    vehicles = TransportVehicle.objects.filter(status="Active")
    context = {
        "title": "Add Driver",
        "employees": employees,
        "vehicles": vehicles,
        "school_settings": school_settings(),
    }
    return render(request, "transport/driver_form.html", context)


@permission_required("transport.manage")
def route_list(request):
    routes = TransportRoute.objects.all().select_related("assigned_vehicle", "assigned_driver")
    
    # Calculate occupancies
    for r in routes:
        r.occupancy = TransportRegistration.objects.filter(route=r, status="Active").count()
        r.capacity = r.assigned_vehicle.capacity if r.assigned_vehicle else 0
        r.is_overloaded = r.occupancy > r.capacity if r.capacity > 0 else False
        
    context = {
        "title": "Logistics Routes",
        "routes": routes,
        "school_settings": school_settings(),
    }
    return render(request, "transport/route_list.html", context)


@permission_required("transport.manage")
def route_new(request):
    if request.method == "POST":
        code = request.POST.get("route_code", "").strip()
        name = request.POST.get("route_name", "").strip()
        start = request.POST.get("starting_point", "").strip()
        dest = request.POST.get("destination", "").strip()
        dist = request.POST.get("distance", 0)
        duration = request.POST.get("estimated_duration", "").strip()
        veh_id = request.POST.get("assigned_vehicle_id")
        drv_id = request.POST.get("assigned_driver_id")
        
        try:
            veh = TransportVehicle.objects.get(pk=veh_id) if veh_id else None
            drv = TransportDriver.objects.get(pk=drv_id) if drv_id else None
            
            route = TransportRoute.objects.create(
                route_code=code,
                route_name=name,
                starting_point=start,
                destination=dest,
                distance=Decimal(dist) if dist else Decimal("0.00"),
                estimated_duration=duration,
                assigned_vehicle=veh,
                assigned_driver=drv,
                status="Active",
            )
            audit_action(request, "Route Created", f"Created route {code} - {name}")
            messages.success(request, f"Route '{name}' created successfully.")
            return redirect("route_list")
        except Exception as e:
            messages.error(request, f"Error saving route: {e}")
            
    vehicles = TransportVehicle.objects.filter(status="Active")
    drivers = TransportDriver.objects.filter(status="Active")
    context = {
        "title": "Create Route",
        "vehicles": vehicles,
        "drivers": drivers,
        "school_settings": school_settings(),
    }
    return render(request, "transport/route_form.html", context)


@permission_required("transport.manage")
def route_edit(request, route_id):
    route = get_object_or_404(TransportRoute, pk=route_id)
    if request.method == "POST":
        route.route_name = request.POST.get("route_name", "").strip()
        route.starting_point = request.POST.get("starting_point", "").strip()
        route.destination = request.POST.get("destination", "").strip()
        dist = request.POST.get("distance")
        route.distance = Decimal(dist) if dist else Decimal("0.00")
        route.estimated_duration = request.POST.get("estimated_duration", "").strip()
        veh_id = request.POST.get("assigned_vehicle_id")
        drv_id = request.POST.get("assigned_driver_id")
        route.status = request.POST.get("status", route.status)
        
        try:
            route.assigned_vehicle = TransportVehicle.objects.get(pk=veh_id) if veh_id else None
            route.assigned_driver = TransportDriver.objects.get(pk=drv_id) if drv_id else None
            route.save()
            audit_action(request, "Route Updated", f"Updated route {route.route_code}")
            messages.success(request, f"Route '{route.route_name}' updated successfully.")
            return redirect("route_list")
        except Exception as e:
            messages.error(request, f"Error saving route: {e}")
            
    vehicles = TransportVehicle.objects.filter(status="Active")
    drivers = TransportDriver.objects.filter(status="Active")
    context = {
        "title": f"Edit Route: {route.route_code}",
        "route": route,
        "vehicles": vehicles,
        "drivers": drivers,
        "school_settings": school_settings(),
    }
    return render(request, "transport/route_form.html", context)


@permission_required("transport.manage")
def pickup_point_list(request, route_id):
    route = get_object_or_404(TransportRoute, pk=route_id)
    stops = TransportPickupPoint.objects.filter(route=route)
    context = {
        "title": f"Stops: {route.route_name}",
        "route": route,
        "stops": stops,
        "school_settings": school_settings(),
    }
    return render(request, "transport/pickup_point_list.html", context)


@permission_required("transport.manage")
def pickup_point_new(request, route_id):
    route = get_object_or_404(TransportRoute, pk=route_id)
    if request.method == "POST":
        loc = request.POST.get("location_name", "").strip()
        time_val = request.POST.get("pickup_time")
        
        try:
            TransportPickupPoint.objects.create(
                route=route,
                location_name=loc,
                pickup_time=time_val,
                status="Active",
            )
            audit_action(request, "Pickup Point Created", f"Added stop {loc} to route {route.route_code}")
            messages.success(request, f"Pickup stop '{loc}' added successfully.")
            return redirect("pickup_point_list", route_id=route.pk)
        except Exception as e:
            messages.error(request, f"Error saving pickup point: {e}")
            
    context = {
        "title": f"Add Stop: {route.route_name}",
        "route": route,
        "school_settings": school_settings(),
    }
    return render(request, "transport/pickup_point_form.html", context)


# Helper: Posts transport invoice and records to general ledger
def post_transport_invoice(request, student, amount, notes):
    account = StudentFeeAccount.objects.filter(student=student).first()
    if not account:
        return None
        
    inv_num = f"INV-TR-{datetime.date.today().strftime('%y%m%d%H%M%S')}"
    
    # Get or create Transport Fee Category
    category, _ = FeeCategory.objects.get_or_create(
        name="Transport Fees", defaults={"is_active": True}
    )
            
    invoice = Invoice.objects.create(
        invoice_number=inv_num,
        student_account=account,
        due_date=datetime.date.today() + datetime.timedelta(days=14),
        previous_balance=account.outstanding_balance,
        current_charges=amount,
        discounts=Decimal("0.00"),
        scholarships=Decimal("0.00"),
        total_amount_due=amount,
    )
    InvoiceItem.objects.create(
        invoice=invoice, category=category, amount=amount
    )
    account.total_charges += amount
    account.save()
    
    if request:
        audit_action(request, "Transport Fine Posted", f"Generated invoice {inv_num} for transport fee ${amount}")
    return invoice


@permission_required("transport.manage")
def student_registration_new(request):
    if request.method == "POST":
        stud_id = request.POST.get("student_id")
        route_id = request.POST.get("route_id")
        stop_id = request.POST.get("pickup_point_id")
        trip = request.POST.get("trip_type", "Return Trip")
        eff_date = request.POST.get("effective_date")
        fee_amt = request.POST.get("transport_fee", "45.00")
        
        try:
            student = get_object_or_404(Student, pk=stud_id)
            route = get_object_or_404(TransportRoute, pk=route_id)
            stop = get_object_or_404(TransportPickupPoint, pk=stop_id)
            
            # Check Vehicle Capacity
            veh = route.assigned_vehicle
            if veh:
                active_count = TransportRegistration.objects.filter(route=route, status="Active").count()
                if active_count >= veh.capacity:
                    messages.error(request, f"Error: Vehicle {veh.vehicle_name} capacity limit reached ({veh.capacity} seats).")
                    return redirect("student_registration_new")
                    
            reg = TransportRegistration.objects.create(
                pupil=student,
                route=route,
                pickup_point=stop,
                trip_type=trip,
                effective_date=eff_date if eff_date else today_text(),
                status="Active",
            )
            
            # Billing invoice
            post_transport_invoice(request, student, Decimal(fee_amt), f"Transport Route: {route.route_name}")
            
            audit_action(request, "Student Transport Registered", f"Allocated student {student.admission_no} to route {route.route_code}")
            messages.success(request, f"Student '{student.first_name}' allocated to route successfully.")
            return redirect("registration_list")
            
        except Exception as e:
            messages.error(request, f"Error allocating student: {e}")
            
    students = Student.objects.filter(status="Active Student")
    routes = TransportRoute.objects.filter(status="Active").select_related("assigned_vehicle")
    stops = TransportPickupPoint.objects.filter(status="Active")
    context = {
        "title": "Allocate Transport Space",
        "students": students,
        "routes": routes,
        "stops": stops,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "transport/registration_form.html", context)


@permission_required("transport.manage")
def registration_list(request):
    registrations = TransportRegistration.objects.filter(status="Active").select_related("pupil", "route", "pickup_point")
    context = {
        "title": "Boarders & Commuters",
        "registrations": registrations,
        "school_settings": school_settings(),
    }
    return render(request, "transport/registration_list.html", context)


@permission_required("transport.manage")
def registration_cancel(request, registration_id):
    reg = get_object_or_404(TransportRegistration, pk=registration_id)
    reg.status = "Cancelled"
    reg.save()
    audit_action(request, "Transport Registration Cancelled", f"Cancelled transport for {reg.pupil.admission_no}")
    messages.success(request, "Student transport registration cancelled.")
    return redirect("registration_list")


@permission_required("transport.manage")
def transport_attendance(request):
    selected_date = request.GET.get("date", today_text())
    
    # Load all registered transport students
    boarders = TransportRegistration.objects.filter(status="Active").select_related("pupil", "route", "pickup_point")
    
    # Load existing attendance logs
    logs = {
        item.pupil_id: item 
        for item in TransportAttendance.objects.filter(date=selected_date)
    }
    
    sheet = []
    for b in boarders:
        log = logs.get(b.pupil_id)
        sheet.append({
            "pupil": b.pupil,
            "route": b.route,
            "pickup_point": b.pickup_point,
            "status_morning": log.status_morning if log else "Present",
            "status_afternoon": log.status_afternoon if log else "Present",
            "remarks": log.remarks if log else "",
        })
        
    if request.method == "POST":
        for b in boarders:
            morning = request.POST.get(f"morning_{b.pupil_id}", "Present")
            afternoon = request.POST.get(f"afternoon_{b.pupil_id}", "Present")
            rem = request.POST.get(f"remarks_{b.pupil_id}", "")
            
            TransportAttendance.objects.update_or_create(
                pupil=b.pupil,
                route=b.route,
                date=selected_date,
                defaults={
                    "status_morning": morning,
                    "status_afternoon": afternoon,
                    "remarks": rem,
                }
            )
        audit_action(request, "Transport Attendance Checked", f"Recorded attendance checklist for date {selected_date}")
        messages.success(request, f"Attendance saved successfully for {selected_date}.")
        return redirect(f"/transport/attendance?date={selected_date}")
        
    context = {
        "title": "Daily Roll Call Sheet",
        "selected_date": selected_date,
        "sheet": sheet,
        "school_settings": school_settings(),
    }
    return render(request, "transport/attendance_sheet.html", context)


@permission_required("transport.manage")
def maintenance_list(request):
    if request.method == "POST":
        veh_id = request.POST.get("vehicle_id")
        mtype = request.POST.get("maintenance_type")
        sdate = request.POST.get("service_date")
        cost = request.POST.get("cost", "0.00")
        desc = request.POST.get("description", "").strip()
        ndate = request.POST.get("next_service_date")
        
        try:
            veh = get_object_or_404(TransportVehicle, pk=veh_id)
            TransportMaintenance.objects.create(
                vehicle=veh,
                maintenance_type=mtype,
                service_date=sdate,
                cost=Decimal(cost),
                description=desc,
                next_service_date=ndate if ndate else None,
            )
            
            # If repair log cost, update mileage details if wanted
            audit_action(request, "Maintenance Logged", f"Logged {mtype} maintenance cost ${cost} for vehicle {veh.registration_number}")
            messages.success(request, "Maintenance service recorded successfully.")
            return redirect("transport_maintenance")
        except Exception as e:
            messages.error(request, f"Error saving maintenance log: {e}")
            
    logs = TransportMaintenance.objects.all().select_related("vehicle")
    vehicles = TransportVehicle.objects.filter(status="Active")
    context = {
        "title": "Facility Maintenance logs",
        "requests": logs,
        "vehicles": vehicles,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "transport/maintenance_list.html", context)


@permission_required("transport.manage")
def fuel_list(request):
    if request.method == "POST":
        veh_id = request.POST.get("vehicle_id")
        fdate = request.POST.get("fuel_date")
        qty = request.POST.get("quantity")
        cost = request.POST.get("cost")
        mil = request.POST.get("mileage")
        supp = request.POST.get("supplier", "").strip()
        
        try:
            veh = get_object_or_404(TransportVehicle, pk=veh_id)
            
            # Update mileage
            veh.current_mileage = int(mil)
            veh.save()
            
            TransportFuelLog.objects.create(
                vehicle=veh,
                fuel_date=fdate,
                quantity=Decimal(qty),
                cost=Decimal(cost),
                mileage=int(mil),
                supplier=supp,
            )
            audit_action(request, "Fuel Logged", f"Logged fuel log cost ${cost} for vehicle {veh.registration_number}")
            messages.success(request, "Fuel log transaction recorded.")
            return redirect("transport_fuel")
        except Exception as e:
            messages.error(request, f"Error saving fuel log: {e}")
            
    logs = TransportFuelLog.objects.all().select_related("vehicle")
    vehicles = TransportVehicle.objects.filter(status="Active")
    context = {
        "title": "Fuel Logs Analysis",
        "logs": logs,
        "vehicles": vehicles,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "transport/fuel_list.html", context)


@permission_required("transport.manage")
def incident_list(request):
    if request.method == "POST":
        idate = request.POST.get("incident_date")
        desc = request.POST.get("description", "").strip()
        veh_id = request.POST.get("vehicle_id")
        drv_id = request.POST.get("driver_id")
        action = request.POST.get("action_taken", "").strip()
        
        try:
            veh = TransportVehicle.objects.get(pk=veh_id) if veh_id else None
            drv = TransportDriver.objects.get(pk=drv_id) if drv_id else None
            
            TransportIncident.objects.create(
                incident_date=idate,
                description=desc,
                vehicle=veh,
                driver=drv,
                action_taken=action,
            )
            audit_action(request, "Incident Reported", "Logged transport accident/delay reports.")
            messages.success(request, "Log event report successfully registered.")
            return redirect("transport_incidents")
        except Exception as e:
            messages.error(request, f"Error logging incident: {e}")
            
    incidents = TransportIncident.objects.all().select_related("vehicle", "driver__employee")
    vehicles = TransportVehicle.objects.filter(status="Active")
    drivers = TransportDriver.objects.filter(status="Active")
    context = {
        "title": "Incident Logs",
        "incidents": incidents,
        "vehicles": vehicles,
        "drivers": drivers,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "transport/incident_list.html", context)


@permission_required("transport.manage")
def transport_reports(request):
    report_type = request.GET.get("type", "routes")
    fmt = request.GET.get("format")
    
    headers = []
    rows = []
    title_label = ""
    
    if report_type == "routes":
        title_label = "Active Transport Routes"
        headers = ["Route Code", "Route Name", "Start Point", "Destination", "Distance (KM)", "Vehicle"]
        routes = TransportRoute.objects.all().select_related("assigned_vehicle")
        rows = [[r.route_code, r.route_name, r.starting_point, r.destination, f"{r.distance} km", r.assigned_vehicle.vehicle_name if r.assigned_vehicle else "Unassigned"] for r in routes]
    elif report_type == "students":
        title_label = "Student Transport Allocations"
        headers = ["Student Name", "Adm No", "Class", "Route", "Pickup Stop", "Trip Type"]
        regs = TransportRegistration.objects.filter(status="Active").select_related("pupil__academic_class", "route", "pickup_point")
        rows = [[f"{r.pupil.first_name} {r.pupil.surname}", r.pupil.admission_no, r.pupil.academic_class.class_name if r.pupil.academic_class else "-", r.route.route_name, r.pickup_point.location_name, r.trip_type] for r in regs]
    elif report_type == "fuel":
        title_label = "Fuel Consumption Audit logs"
        headers = ["Date", "Vehicle", "Quantity (L)", "Cost (USD)", "Mileage (KM)", "Supplier"]
        logs = TransportFuelLog.objects.all().select_related("vehicle")
        rows = [[str(l.fuel_date), l.vehicle.vehicle_name, f"{l.quantity} L", f"${l.cost}", f"{l.mileage} KM", l.supplier or "-"] for l in logs]
        
    if fmt == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="transport_report_{report_type}.csv"'
        import csv
        writer = csv.writer(response)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(r)
        return response
        
    context = {
        "title": "Logistics Reporting Desk",
        "report_type": report_type,
        "title_label": title_label,
        "headers": headers,
        "rows": rows,
        "school_settings": school_settings(),
    }
    return render(request, "transport/reports.html", context)


# ================= STUDENT PORTAL VIEW =================
from portals.views import student_portal_required

@student_portal_required
def student_portal_transport(request, pupil):
    pupil_id = pupil["pupil_id"]
    student = Student.objects.get(pk=pupil_id)
    
    # Fetch student transport allocations
    allocation = TransportRegistration.objects.filter(pupil=student, status="Active").select_related("route__assigned_driver__employee", "route__assigned_vehicle", "pickup_point").first()
    
    # Notifications list
    notices = TransportIncident.objects.all().order_by("-incident_date")[:4]
    
    context = {
        "title": "My Transport Route Details",
        "student": student,
        "alloc": allocation,
        "notices": notices,
        "school_settings": school_settings(),
    }
    return render(request, "portals/student_transport.html", context)
