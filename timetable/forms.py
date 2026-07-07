from django import forms
from timetable.models import Room, SubjectAllocation, TeacherAvailability, TimetablePeriodConfig
from accounts.models import UserProfile
from students.models import SchoolClass
from academics.models import Subject

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['room_name', 'room_type', 'capacity']
        widgets = {
            'room_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Science Lab 1'}),
            'room_type': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class SubjectAllocationForm(forms.ModelForm):
    class Meta:
        model = SubjectAllocation
        fields = [
            'school_class', 'subject', 'teacher', 'periods_per_week',
            'preferred_days', 'preferred_sessions', 'is_practical', 'required_room_type'
        ]
        widgets = {
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'periods_per_week': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 20}),
            'preferred_days': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Monday, Wednesday'}),
            'preferred_sessions': forms.Select(attrs={'class': 'form-select'}),
            'is_practical': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'required_room_type': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active teachers in selection list
        self.fields['teacher'].queryset = UserProfile.objects.filter(role='Teacher', status='Active')
        # Filter active classes
        self.fields['school_class'].queryset = SchoolClass.objects.all().order_by('class_name')
        # Filter active subjects
        self.fields['subject'].queryset = Subject.objects.filter(status='Active').order_by('subject_name')

    def save(self, commit=True):
        instance = super().save(commit=commit)
        try:
            from timetable.views import sync_subject_allocation_to_registry
            sync_subject_allocation_to_registry(instance)
        except Exception as e:
            print(f"Error syncing subject allocation to registry: {e}")
        return instance


class TeacherAvailabilityForm(forms.ModelForm):
    class Meta:
        model = TeacherAvailability
        fields = ['teacher', 'max_periods_per_day', 'max_periods_per_week', 'available_days', 'available_periods']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'max_periods_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'max_periods_per_week': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 50}),
            'available_days': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Monday, Tuesday, Wednesday, Thursday, Friday'}),
            'available_periods': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1, 2, 3, 4, 5, 6, 7, 8'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = UserProfile.objects.filter(role='Teacher', status='Active')


class TimetablePeriodConfigForm(forms.ModelForm):
    class Meta:
        model = TimetablePeriodConfig
        fields = ['period_no', 'period_type', 'start_time', 'end_time', 'label']
        widgets = {
            'period_no': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'period_type': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM'}),
            'end_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM'}),
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Period 1, Break, Lunch'}),
        }
