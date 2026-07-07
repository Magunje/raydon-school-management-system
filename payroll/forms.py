from datetime import date

from django import forms

from .models import (
    EmployeePayrollProfile,
    PayrollAdjustment,
    PayrollItemType,
    PayrollRun,
)


class EmployeePayrollProfileForm(forms.ModelForm):
    class Meta:
        model = EmployeePayrollProfile
        fields = [
            "user",
            "full_name",
            "employee_number",
            "job_title",
            "department",
            "basic_salary",
            "account_number",
            "bank_name",
            "branch_name",
            "payment_method",
            "employment_status",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        payment_method = cleaned.get("payment_method")
        if payment_method == "Bank transfer":
            if not cleaned.get("account_number"):
                self.add_error("account_number", "Account number is required for bank transfer.")
            if not cleaned.get("bank_name"):
                self.add_error("bank_name", "Bank name is required for bank transfer.")
        return cleaned


class PayrollProcessForm(forms.Form):
    period = forms.CharField(
        label="Payroll month",
        initial=lambda: date.today().strftime("%Y-%m"),
        widget=forms.TextInput(attrs={"type": "month"}),
    )
    copy_previous = forms.BooleanField(required=False, label="Copy previous month adjustments")

    def clean_period(self):
        value = (self.cleaned_data["period"] or "").strip()
        try:
            year_text, month_text = value.split("-", 1)
            year = int(year_text)
            month = int(month_text)
        except (TypeError, ValueError):
            raise forms.ValidationError("Enter a payroll month in YYYY-MM format.")
        if month < 1 or month > 12:
            raise forms.ValidationError("Select a valid month.")
        return {"year": year, "month": month, "code": f"{year:04d}-{month:02d}"}


class PayrollRunForm(forms.ModelForm):
    class Meta:
        model = PayrollRun
        fields = [
            "housing_allowance",
            "transport_allowance",
            "bonus",
            "overtime",
            "other_allowance",
            "tax",
            "nssa",
            "pension",
            "loan",
            "advance",
            "unpaid_leave",
            "other_deductions",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            if field_name != "notes":
                self.fields[field_name].widget.attrs.update({"step": "0.01", "min": "0"})


class PayrollAdjustmentForm(forms.ModelForm):
    class Meta:
        model = PayrollAdjustment
        fields = ["adjustment_type", "code", "description", "amount", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Adjustment amount must be greater than zero.")
        return amount

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class PayrollFilterForm(forms.Form):
    q = forms.CharField(required=False)
    department = forms.CharField(required=False)
    status = forms.CharField(required=False)


class PayrollReportForm(forms.Form):
    REPORT_CHOICES = [
        ("monthly", "Monthly payroll summary"),
        ("department", "Department payroll summary"),
        ("employee", "Employee payroll history"),
        ("cost", "Total salary cost report"),
        ("bank", "Bank payment report"),
    ]

    report = forms.ChoiceField(choices=REPORT_CHOICES, required=False, initial="monthly")
    employee_number = forms.CharField(required=False)


ADJUSTMENT_TYPE_LABELS = dict(PayrollItemType.choices)
