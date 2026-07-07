from django.urls import path
from timetable import views

app_name = 'timetable'

urlpatterns = [
    # Dashboard and Master grid
    path('', views.timetable_dashboard, name='dashboard'),
    path('grid', views.timetable_grid, name='grid'),
    path('generate', views.timetable_generate, name='generate'),
    
    # API endpoints for interactive actions
    path('api/check-conflict', views.api_check_conflict, name='api_check_conflict'),
    path('api/save-slot', views.api_save_slot, name='api_save_slot'),
    path('api/toggle-lock', views.api_toggle_lock, name='api_toggle_lock'),
    
    # Exports
    path('export/pdf', views.export_pdf, name='export_pdf'),
    path('export/excel', views.export_excel, name='export_excel'),
    
    # Room CRUD
    path('rooms', views.room_list, name='room_list'),
    path('rooms/new', views.room_new, name='room_new'),
    path('rooms/<int:room_id>/edit', views.room_edit, name='room_edit'),
    path('rooms/<int:room_id>/delete', views.room_delete, name='room_delete'),
    
    # SubjectAllocation CRUD
    path('allocations', views.allocation_list, name='allocation_list'),
    path('allocations/new', views.allocation_new, name='allocation_new'),
    path('allocations/<int:allocation_id>/edit', views.allocation_edit, name='allocation_edit'),
    path('allocations/<int:allocation_id>/delete', views.allocation_delete, name='allocation_delete'),
    
    # TeacherAvailability CRUD
    path('availabilities', views.availability_list, name='availability_list'),
    path('availabilities/new', views.availability_new, name='availability_new'),
    path('availabilities/<int:availability_id>/edit', views.availability_edit, name='availability_edit'),
    path('availabilities/<int:availability_id>/delete', views.availability_delete, name='availability_delete'),
    
    # TimetablePeriodConfig CRUD
    path('period-configs', views.period_config_list, name='period_config_list'),
    path('period-configs/new', views.period_config_new, name='period_config_new'),
    path('period-configs/<int:config_id>/edit', views.period_config_edit, name='period_config_edit'),
    path('period-configs/<int:config_id>/delete', views.period_config_delete, name='period_config_delete'),
]
