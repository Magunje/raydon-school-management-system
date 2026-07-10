from django.contrib import admin

from medical.models import (
    ClinicVisit,
    ImmunisationRecord,
    MedicalAppointment,
    MedicalAttendanceExcuse,
    MedicalAuditLog,
    MedicalCertificate,
    MedicalCondition,
    MedicalEmergency,
    MedicalNotification,
    MedicalProfile,
    MedicalReferral,
    Medication,
    MedicationDispense,
    SickBayAdmission,
)


admin.site.register(MedicalCondition)
admin.site.register(MedicalProfile)
admin.site.register(ClinicVisit)
admin.site.register(Medication)
admin.site.register(MedicationDispense)
admin.site.register(MedicalEmergency)
admin.site.register(MedicalReferral)
admin.site.register(ImmunisationRecord)
admin.site.register(MedicalAppointment)
admin.site.register(SickBayAdmission)
admin.site.register(MedicalCertificate)
admin.site.register(MedicalAttendanceExcuse)
admin.site.register(MedicalNotification)
admin.site.register(MedicalAuditLog)
