from django.urls import path
from hostel import views

urlpatterns = [
    path('', views.hostel_dashboard, name='hostel_dashboard'),
    path('infrastructure', views.hostel_list, name='hostel_list'),
    path('infrastructure/new', views.hostel_new, name='hostel_new'),
    path('infrastructure/<int:hostel_id>/edit', views.hostel_edit, name='hostel_edit'),
    path('infrastructure/<int:hostel_id>/delete', views.hostel_delete, name='hostel_delete'),
    
    path('infrastructure/<int:hostel_id>/rooms', views.room_list, name='room_list'),
    path('infrastructure/<int:hostel_id>/rooms/new', views.room_new, name='room_new'),
    path('rooms/<int:room_id>/bedmap', views.bed_map_grid, name='bed_map_grid'),
    
    path('allocations', views.allocation_list, name='allocation_list'),
    path('allocations/new', views.allocation_new, name='allocation_new'),
    path('allocations/<int:allocation_id>/transfer', views.allocation_transfer, name='allocation_transfer'),
    path('allocations/<int:allocation_id>/vacate', views.allocation_vacate, name='allocation_vacate'),
    
    path('attendance', views.attendance_mark, name='hostel_attendance'),
    path('discipline', views.discipline_list, name='hostel_discipline'),
    path('discipline/new', views.discipline_new, name='hostel_discipline_new'),
    
    path('visitors', views.visitor_list, name='hostel_visitors'),
    path('visitors/new', views.visitor_new, name='hostel_visitor_new'),
    path('visitors/<int:visitor_id>/checkout', views.visitor_checkout, name='hostel_visitor_checkout'),
    path('visitors/<int:visitor_id>/pass', views.visitor_pass_detail, name='hostel_visitor_pass'),
    
    path('maintenance', views.maintenance_list, name='hostel_maintenance'),
    path('maintenance/<int:maintenance_id>/status/<str:status_val>', views.maintenance_status_update, name='hostel_maintenance_status'),
    
    # student portal
    path('student-portal/hostel', views.student_portal_hostel, name='student_portal_hostel'),
]
