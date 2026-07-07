from django import forms
from django.contrib.auth import get_user_model
from subject_management.models import Subject, TeacherSubjectAllocation
from academic_structure.models import AcademicYear, AcademicTerm, Form, Stream

User = get_user_model()


class TeacherSubjectAllocationForm(forms.ModelForm):
    class Meta:
        model = TeacherSubjectAllocation
        fields = ["teacher", "subject", "academic_year", "academic_term", "form", "stream"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter teachers to staff/teachers (exclude students and parents)
        self.fields["teacher"].queryset = User.objects.select_related("profile").exclude(profile__role__in=["Student", "Parent"]).order_by("username")
        self.fields["teacher"].label_from_instance = lambda obj: f"{obj.profile.full_name} ({obj.username})" if hasattr(obj, "profile") and obj.profile.full_name else obj.username
        
        # Filter to active subjects
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True).order_by("name")
        
        # Apply bootstrap CSS classes to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-select"
