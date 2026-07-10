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
from assets.models import (
    AssetCategory,
    Asset,
    AssetAssignment,
    AssetTransfer,
    AssetMaintenance,
    AssetDepreciationLog,
    AssetDisposal,
    AssetVerification,
    AssetInsurance
)
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


@permission_required("asset.manage")
def asset_dashboard(request):
    # Stats
    total_assets = Asset.objects.exclude(status="Disposed").count()
    total_val = Decimal("0.00")
    for a in Asset.objects.exclude(status="Disposed"):
        total_val += a.current_value
        
    under_maintenance = Asset.objects.filter(status="Under Maintenance").count()
    
    # Upcoming prevention service
    upcoming_service = AssetMaintenance.objects.filter(
        next_service_date__gte=datetime.date.today(),
        next_service_date__lte=datetime.date.today() + datetime.timedelta(days=30)
    ).select_related("asset")
    
    # Depreciation summary
    depr_total = Decimal("0.00")
    recent_logs = AssetDepreciationLog.objects.all().select_related("asset").order_by("-depreciation_date")[:5]
    for log in AssetDepreciationLog.objects.all():
        depr_total += log.amount
        
    stats = [
        ("Total Assets Active", total_assets),
        ("Current Registry Value", f"${total_val}"),
        ("Under Maintenance", under_maintenance),
        ("Accumulated Depreciation", f"${depr_total}"),
    ]
    
    context = {
        "title": "Assets Control Center",
        "stats": stats,
        "upcoming_service": upcoming_service,
        "recent_logs": recent_logs,
        "school_settings": school_settings(),
    }
    return render(request, "assets/dashboard.html", context)


@permission_required("asset.manage")
def asset_list(request):
    assets = Asset.objects.all().select_related("category", "custodian")
    context = {
        "title": "Fixed Asset Register",
        "assets": assets,
        "school_settings": school_settings(),
    }
    return render(request, "assets/asset_list.html", context)


@permission_required("asset.manage")
def asset_new(request):
    if request.method == "POST":
        code = request.POST.get("asset_code", "").strip()
        name = request.POST.get("asset_name", "").strip()
        cat_id = request.POST.get("category_id")
        serial = request.POST.get("serial_number", "").strip()
        desc = request.POST.get("description", "").strip()
        acq_date = request.POST.get("acquisition_date")
        price = request.POST.get("purchase_price", "0.00")
        supp = request.POST.get("supplier", "").strip()
        wstart = request.POST.get("warranty_start")
        wend = request.POST.get("warranty_end")
        life = request.POST.get("useful_life", 5)
        method = request.POST.get("depreciation_method", "Straight-Line")
        rate = request.POST.get("depreciation_rate", "0.00")
        salvage = request.POST.get("salvage_value", "0.00")
        loc = request.POST.get("location_name", "").strip()
        cust_id = request.POST.get("custodian_id")
        
        try:
            category = get_object_or_404(AssetCategory, pk=cat_id)
            custodian = EmployeeProfile.objects.get(pk=cust_id) if cust_id else None
            
            asset = Asset.objects.create(
                asset_code=code,
                asset_name=name,
                category=category,
                serial_number=serial,
                barcode=code,
                qr_code=code,
                description=desc,
                acquisition_date=acq_date,
                purchase_price=Decimal(price),
                supplier=supp,
                warranty_start=wstart if wstart else None,
                warranty_end=wend if wend else None,
                useful_life=int(life),
                depreciation_method=method,
                depreciation_rate=Decimal(rate) if rate else Decimal("0.00"),
                salvage_value=Decimal(salvage) if salvage else Decimal("0.00"),
                current_value=Decimal(price),
                status="Active",
                location_name=loc,
                custodian=custodian,
            )
            audit_action(request, "Asset Registered", f"Created asset {code} - {name}")
            messages.success(request, f"Asset '{name}' registered successfully.")
            return redirect("asset_list")
        except Exception as e:
            messages.error(request, f"Error registering asset: {e}")
            
    categories = AssetCategory.objects.all()
    custodians = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": "Register New Asset",
        "categories": categories,
        "custodians": custodians,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "assets/asset_form.html", context)


@permission_required("asset.manage")
def asset_edit(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == "POST":
        asset.asset_name = request.POST.get("asset_name", "").strip()
        asset.serial_number = request.POST.get("serial_number", "").strip()
        asset.description = request.POST.get("description", "").strip()
        asset.supplier = request.POST.get("supplier", "").strip()
        
        wstart = request.POST.get("warranty_start")
        asset.warranty_start = wstart if wstart else None
        wend = request.POST.get("warranty_end")
        asset.warranty_end = wend if wend else None
        
        life = request.POST.get("useful_life")
        asset.useful_life = int(life) if life else asset.useful_life
        asset.depreciation_method = request.POST.get("depreciation_method", asset.depreciation_method)
        
        rate = request.POST.get("depreciation_rate")
        asset.depreciation_rate = Decimal(rate) if rate else asset.depreciation_rate
        
        salvage = request.POST.get("salvage_value")
        asset.salvage_value = Decimal(salvage) if salvage else asset.salvage_value
        
        asset.location_name = request.POST.get("location_name", "").strip()
        cust_id = request.POST.get("custodian_id")
        asset.status = request.POST.get("status", asset.status)
        
        try:
            asset.custodian = EmployeeProfile.objects.get(pk=cust_id) if cust_id else None
            asset.save()
            audit_action(request, "Asset Updated", f"Updated asset {asset.asset_code}")
            messages.success(request, f"Asset '{asset.asset_name}' updated successfully.")
            return redirect("asset_list")
        except Exception as e:
            messages.error(request, f"Error saving asset: {e}")
            
    custodians = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": f"Edit Asset: {asset.asset_code}",
        "asset": asset,
        "custodians": custodians,
        "school_settings": school_settings(),
    }
    return render(request, "assets/asset_form.html", context)


@permission_required("asset.manage")
def asset_assignment_new(request):
    if request.method == "POST":
        asset_id = request.POST.get("asset_id")
        emp_id = request.POST.get("assigned_employee_id")
        dept = request.POST.get("assigned_department", "").strip()
        loc = request.POST.get("assigned_location", "").strip()
        adate = request.POST.get("date_assigned")
        cond = request.POST.get("condition", "Good")
        notes = request.POST.get("notes", "").strip()
        
        try:
            asset = get_object_or_404(Asset, pk=asset_id)
            emp = EmployeeProfile.objects.get(pk=emp_id) if emp_id else None
            
            # Record assignment
            AssetAssignment.objects.create(
                asset=asset,
                assigned_employee=emp,
                assigned_department=dept,
                assigned_location=loc,
                date_assigned=adate if adate else today_text(),
                condition=cond,
                notes=notes,
            )
            
            # Update asset location & status
            asset.location_name = loc if loc else asset.location_name
            asset.status = "In Use"
            if emp:
                asset.custodian = emp
            asset.save()
            
            audit_action(request, "Asset Assigned", f"Assigned asset {asset.asset_code} to custodian")
            messages.success(request, f"Asset assigned successfully.")
            return redirect("asset_list")
        except Exception as e:
            messages.error(request, f"Error assigning asset: {e}")
            
    assets = Asset.objects.exclude(status="Disposed")
    employees = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": "Assign Asset Custody",
        "assets": assets,
        "employees": employees,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "assets/assignment_form.html", context)


@permission_required("asset.manage")
def asset_transfer_new(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == "POST":
        prev = asset.location_name or "Unknown"
        new_loc = request.POST.get("new_location", "").strip()
        reason = request.POST.get("reason", "").strip()
        tdate = request.POST.get("transfer_date")
        approved_id = request.POST.get("approved_by_id")
        
        try:
            approver = EmployeeProfile.objects.get(pk=approved_id) if approved_id else None
            
            # Record transfer log
            AssetTransfer.objects.create(
                asset=asset,
                previous_location=prev,
                new_location=new_loc,
                transfer_date=tdate if tdate else today_text(),
                approved_by=approver,
                reason=reason,
            )
            
            # Update location
            asset.location_name = new_loc
            asset.save()
            
            audit_action(request, "Asset Transferred", f"Transferred asset {asset.asset_code} from {prev} to {new_loc}")
            messages.success(request, f"Location transfer for '{asset.asset_name}' logged.")
            return redirect("asset_list")
        except Exception as e:
            messages.error(request, f"Error saving asset transfer: {e}")
            
    approvers = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": f"Transfer Asset: {asset.asset_name}",
        "asset": asset,
        "approvers": approvers,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "assets/transfer_form.html", context)


@permission_required("asset.manage")
def asset_maintenance_list(request):
    if request.method == "POST":
        asset_id = request.POST.get("asset_id")
        mtype = request.POST.get("maintenance_type")
        mdate = request.POST.get("maintenance_date")
        cost = request.POST.get("cost", "0.00")
        provider = request.POST.get("provider", "").strip()
        notes = request.POST.get("notes", "").strip()
        ndate = request.POST.get("next_service_date")
        
        try:
            asset = get_object_or_404(Asset, pk=asset_id)
            AssetMaintenance.objects.create(
                asset=asset,
                maintenance_type=mtype,
                maintenance_date=mdate,
                cost=Decimal(cost),
                provider=provider,
                notes=notes,
                next_service_date=ndate if ndate else None,
            )
            
            # Set asset status to Under Maintenance
            asset.status = "Under Maintenance"
            asset.save()
            
            audit_action(request, "Asset Maintenance Logged", f"Logged {mtype} maintenance cost ${cost} for asset {asset.asset_code}")
            messages.success(request, "Asset maintenance log saved successfully.")
            return redirect("asset_maintenance")
        except Exception as e:
            messages.error(request, f"Error saving maintenance log: {e}")
            
    logs = AssetMaintenance.objects.all().select_related("asset")
    assets = Asset.objects.exclude(status="Disposed")
    context = {
        "title": "Preventative Services",
        "requests": logs,
        "assets": assets,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "assets/maintenance_list.html", context)


@permission_required("asset.manage")
def calculate_depreciation_trigger(request):
    if request.method == "POST":
        # Process all active assets that support depreciation
        assets = Asset.objects.exclude(status="Disposed").exclude(depreciation_method="None")
        count = 0
        total_depr = Decimal("0.00")
        
        for a in assets:
            depr_amt = Decimal("0.00")
            if a.depreciation_method == "Straight-Line":
                if a.useful_life > 0:
                    depr_amt = (a.purchase_price - a.salvage_value) / a.useful_life
            elif a.depreciation_method == "Reducing Balance":
                depr_amt = a.current_value * (a.depreciation_rate / Decimal("100.00"))
                
            if depr_amt > 0:
                if a.current_value - depr_amt >= a.salvage_value:
                    a.current_value -= depr_amt
                else:
                    depr_amt = a.current_value - a.salvage_value
                    a.current_value = a.salvage_value
                    
                a.save()
                
                # Log depreciation
                AssetDepreciationLog.objects.create(
                    asset=a,
                    depreciation_date=datetime.date.today(),
                    amount=depr_amt,
                    book_value=a.current_value,
                )
                count += 1
                total_depr += depr_amt
                
        audit_action(request, "Depreciation Run Triggered", f"Calculated depreciation for {count} assets. Total depreciation: ${total_depr}")
        messages.success(request, f"Depreciation calculations completed. Processed {count} assets. Total value adjusted: ${total_depr}")
        return redirect("asset_dashboard")
        
    logs = AssetDepreciationLog.objects.all().select_related("asset")
    context = {
        "title": "Depreciation Logs History",
        "logs": logs,
        "school_settings": school_settings(),
    }
    return render(request, "assets/depreciation_logs.html", context)


@permission_required("asset.manage")
def asset_disposal_new(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == "POST":
        ddate = request.POST.get("disposal_date")
        method = request.POST.get("method")
        val = request.POST.get("value", "0.00")
        reason = request.POST.get("reason", "").strip()
        approved_id = request.POST.get("approved_by_id")
        
        try:
            approver = EmployeeProfile.objects.get(pk=approved_id) if approved_id else None
            
            AssetDisposal.objects.create(
                asset=asset,
                disposal_date=ddate if ddate else today_text(),
                method=method,
                value=Decimal(val) if val else Decimal("0.00"),
                reason=reason,
                approved_by=approver,
            )
            
            # Update status
            asset.status = "Disposed"
            asset.current_value = Decimal("0.00")
            asset.save()
            
            audit_action(request, "Asset Disposed", f"Disposed asset {asset.asset_code} via {method}")
            messages.success(request, f"Asset '{asset.asset_name}' marked as disposed.")
            return redirect("asset_list")
        except Exception as e:
            messages.error(request, f"Error saving asset disposal: {e}")
            
    approvers = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": f"Dispose Asset: {asset.asset_name}",
        "asset": asset,
        "approvers": approvers,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "assets/disposal_form.html", context)


@permission_required("asset.manage")
def asset_verification_list(request):
    if request.method == "POST":
        asset_id = request.POST.get("asset_id")
        vdate = request.POST.get("verification_date")
        vby = request.POST.get("verified_by_id")
        found = request.POST.get("status_found")
        notes = request.POST.get("variance_notes", "").strip()
        
        try:
            asset = get_object_or_404(Asset, pk=asset_id)
            verifier = EmployeeProfile.objects.get(pk=vby) if vby else None
            
            AssetVerification.objects.create(
                asset=asset,
                verification_date=vdate if vdate else today_text(),
                verified_by=verifier,
                status_found=found,
                variance_notes=notes,
            )
            
            # Update status
            asset.status = found if found != "Present" else asset.status
            asset.save()
            
            audit_action(request, "Asset Verified", f"Verified asset {asset.asset_code} status: {found}")
            messages.success(request, "Physical count verification saved.")
            return redirect("asset_verification")
        except Exception as e:
            messages.error(request, f"Error saving verification: {e}")
            
    verifications = AssetVerification.objects.all().select_related("asset", "verified_by")
    assets = Asset.objects.exclude(status="Disposed")
    employees = EmployeeProfile.objects.filter(status="ACTIVE")
    context = {
        "title": "Spot Check Verifications",
        "verifications": verifications,
        "assets": assets,
        "employees": employees,
        "today": today_text(),
        "school_settings": school_settings(),
    }
    return render(request, "assets/verification_list.html", context)


@permission_required("asset.manage")
def asset_reports(request):
    report_type = request.GET.get("type", "registry")
    fmt = request.GET.get("format")
    
    headers = []
    rows = []
    title_label = ""
    
    if report_type == "registry":
        title_label = "Fixed Asset Master Registry"
        headers = ["Asset Code", "Asset Name", "Category", "Acquisition Date", "Purchase Price", "Book Value", "Status"]
        assets = Asset.objects.all().select_related("category")
        rows = [[a.asset_code, a.asset_name, a.category.name, str(a.acquisition_date), f"${a.purchase_price}", f"${a.current_value}", a.status] for a in assets]
    elif report_type == "maintenance":
        title_label = "Facility Maintenance Report"
        headers = ["Asset Code", "Asset Name", "Service Date", "Cost (USD)", "Provider", "Next Service Date"]
        logs = AssetMaintenance.objects.all().select_related("asset")
        rows = [[l.asset.asset_code, l.asset.asset_name, str(l.maintenance_date), f"${l.cost}", l.provider, str(l.next_service_date or "-")] for l in logs]
    elif report_type == "disposals":
        title_label = "Asset Disposals Registry"
        headers = ["Asset Code", "Asset Name", "Disposal Date", "Method", "Salvage Value (USD)", "Reason"]
        disps = AssetDisposal.objects.all().select_related("asset")
        rows = [[d.asset.asset_code, d.asset.asset_name, str(d.disposal_date), d.method, f"${d.value}", d.reason] for d in disps]
        
    if fmt == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="asset_report_{report_type}.csv"'
        import csv
        writer = csv.writer(response)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(r)
        return response
        
    context = {
        "title": "Facility Asset Reporting",
        "report_type": report_type,
        "title_label": title_label,
        "headers": headers,
        "rows": rows,
        "school_settings": school_settings(),
    }
    return render(request, "assets/reports.html", context)


# ================= STUDENT PORTAL VIEW =================
from portals.views import student_portal_required

@student_portal_required
def student_portal_assets(request, pupil):
    pupil_id = pupil["pupil_id"]
    student = Student.objects.get(pk=pupil_id)
    
    # In student registry context, check-out devices/desks are represented as assignments.
    # To track this dynamically: we can query the AssetAssignment table to see what assets are checked out to this pupil
    # If the student name matches or linked via custom assignments.
    # To implement this cleanly: we query assets where the custodian name matches the student's name, or link assignments.
    # Since AssetAssignment fields are assigned_employee (EmployeeProfile) only, let's also support looking up
    # assets located in student's class name, or custodian matches.
    # We can query all AssetAssignments where the description or notes mention the student's admission number!
    import django.db.models as django_models
    assigned_assets = Asset.objects.filter(
        description__icontains=student.admission_no
    )
    
    context = {
        "title": "My Checked-out Devices & Assets",
        "student": student,
        "assets": assigned_assets,
        "school_settings": school_settings(),
    }
    return render(request, "portals/student_assets.html", context)
