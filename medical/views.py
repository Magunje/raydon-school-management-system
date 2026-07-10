from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from medical.models import MedicalProfile, ClinicVisit, Medication

@login_required
def medical_list(request):
    profiles = MedicalProfile.objects.all()
    visits = ClinicVisit.objects.all().order_by("-visit_date", "-visit_time")
    medications = Medication.objects.all()
    
    # Telemetry
    total_patients = profiles.count()
    total_visits = visits.count()
    active_meds = medications.filter(is_active=True).count()
    low_stock = 0
    for med in medications:
        if med.quantity_available <= med.reorder_level:
            low_stock += 1
            
    context = {
        "profiles": profiles,
        "visits": visits,
        "medications": medications,
        "total_patients": total_patients,
        "total_visits": total_visits,
        "active_meds": active_meds,
        "low_stock": low_stock,
    }
    return render(request, "medical/profile_list.html", context)
