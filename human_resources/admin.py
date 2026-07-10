from django.contrib import admin

from human_resources.models import (
    Applicant,
    Department,
    DisciplinaryAction,
    EmployeeQualification,
    EmployeeProfile,
    HRDocumentAccessLog,
    EmployeeTrainingRecord,
    EmploymentContract,
    HRAuditLog,
    Interview,
    LeaveApplication,
    LeaveBalance,
    LeaveType,
    PerformanceReview,
    Position,
    StaffAttendanceRecord,
    StaffDocument,
    TrainingProgram,
    Vacancy,
)


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_number", "full_name", "employee_category", "department", "position", "employment_type", "status")
    list_filter = ("employee_category", "department", "employment_type", "status", "gender")
    search_fields = ("employee_number", "first_name", "middle_name", "surname", "email", "phone_number", "national_id")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department_head", "status")
    list_filter = ("status",)
    search_fields = ("name", "code")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "department", "approved_posts", "status")
    list_filter = ("department", "status")
    search_fields = ("title", "code")


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ("vacancy_number", "title", "department", "number_of_posts", "status", "closing_date")
    list_filter = ("department", "status", "employment_type")
    search_fields = ("vacancy_number", "title")


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ("applicant_number", "full_name", "vacancy", "status", "interview_score")
    list_filter = ("status",)
    search_fields = ("applicant_number", "full_name", "email", "phone_number")


admin.site.register(Interview)
admin.site.register(EmploymentContract)
admin.site.register(LeaveBalance)
admin.site.register(LeaveType)
admin.site.register(LeaveApplication)
admin.site.register(StaffAttendanceRecord)
admin.site.register(PerformanceReview)
admin.site.register(TrainingProgram)
admin.site.register(EmployeeTrainingRecord)
admin.site.register(DisciplinaryAction)
admin.site.register(StaffDocument)
admin.site.register(EmployeeQualification)
admin.site.register(HRDocumentAccessLog)
admin.site.register(HRAuditLog)
