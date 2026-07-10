from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from business_intelligence.models import DashboardDefinition, DashboardWidget, ReportTemplate, SavedReport

@login_required
def bi_dashboard_list(request):
    dashboards = DashboardDefinition.objects.all()
    templates = ReportTemplate.objects.all()
    saved_reports = SavedReport.objects.all()
    
    # Telemetry
    total_dashboards = dashboards.count()
    active_widgets = DashboardWidget.objects.filter(is_active=True).count()
    system_templates = templates.filter(is_active=True).count() if hasattr(ReportTemplate, 'is_active') else templates.count()
    total_saved = saved_reports.count()
    
    context = {
        "dashboards": dashboards,
        "templates": templates,
        "saved_reports": saved_reports,
        "total_dashboards": total_dashboards,
        "active_widgets": active_widgets,
        "system_templates": system_templates,
        "total_saved": total_saved,
    }
    return render(request, "business_intelligence/dashboard_list.html", context)
