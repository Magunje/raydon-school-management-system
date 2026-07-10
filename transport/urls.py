from django.urls import path
from transport import views

urlpatterns = [
    path('', views.transport_dashboard, name='transport_dashboard_root'),
    path('dashboard', views.transport_dashboard, name='transport_dashboard'),
    path('vehicles', views.vehicle_list, name='vehicle_list'),
    path('vehicles/new', views.vehicle_new, name='vehicle_new'),
    path('vehicles/<int:vehicle_id>/edit', views.vehicle_edit, name='vehicle_edit'),
    
    path('drivers', views.driver_list, name='driver_list'),
    path('drivers/new', views.driver_new, name='driver_new'),
    
    path('routes', views.route_list, name='route_list'),
    path('routes/new', views.route_new, name='route_new'),
    path('routes/<int:route_id>/edit', views.route_edit, name='route_edit'),
    path('routes/<int:route_id>/stops', views.pickup_point_list, name='pickup_point_list'),
    path('routes/<int:route_id>/stops/new', views.pickup_point_new, name='pickup_point_new'),
    
    path('allocations', views.registration_list, name='registration_list'),
    path('allocations/new', views.student_registration_new, name='registration_new'),
    path('allocations/<int:registration_id>/cancel', views.registration_cancel, name='registration_cancel'),
    
    path('attendance', views.transport_attendance, name='transport_attendance'),
    path('maintenance', views.maintenance_list, name='transport_maintenance'),
    path('fuel', views.fuel_list, name='transport_fuel'),
    path('incidents', views.incident_list, name='transport_incidents'),
    path('reports', views.transport_reports, name='transport_reports'),
    
    # student portal route
    path('student-portal/transport', views.student_portal_transport, name='student_portal_transport'),
]
