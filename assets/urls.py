from django.urls import path
from assets import views

urlpatterns = [
    path('', views.asset_dashboard, name='asset_dashboard_root'),
    path('dashboard', views.asset_dashboard, name='asset_dashboard'),
    path('register', views.asset_list, name='asset_list'),
    path('register/new', views.asset_new, name='asset_new'),
    path('register/<int:asset_id>/edit', views.asset_edit, name='asset_edit'),
    
    path('assignments/new', views.asset_assignment_new, name='asset_assignment_new'),
    path('transfers/<int:asset_id>/new', views.asset_transfer_new, name='asset_transfer_new'),
    path('maintenance', views.asset_maintenance_list, name='asset_maintenance'),
    path('depreciation', views.calculate_depreciation_trigger, name='asset_depreciation'),
    path('disposal/<int:asset_id>/new', views.asset_disposal_new, name='asset_disposal_new'),
    path('verification', views.asset_verification_list, name='asset_verification'),
    path('reports', views.asset_reports, name='asset_reports'),
    
    # student portal route
    path('student-portal/assets', views.student_portal_assets, name='student_portal_assets'),
]
