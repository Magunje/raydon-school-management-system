from django.urls import path
from library import views

urlpatterns = [
    path('', views.library_dashboard, name='library'),
    path('books', views.book_list, name='library_books'),
    path('books/new', views.book_new, name='new_library_book'),
    path('books/<int:book_id>/edit', views.book_edit, name='edit_library_book'),
    path('books/<int:book_id>/delete', views.book_delete, name='delete_library_book'),
    path('books/<int:book_id>/qrcode', views.book_qrcode, name='book_qrcode'),
    
    path('issues', views.issue_list, name='library_issues'),
    path('issues/new', views.issue_new, name='new_library_issue'),
    path('issues/<int:issue_id>/return', views.return_library_book, name='return_library_book'),
    
    path('reservations', views.reservation_list, name='library_reservations'),
    path('reservations/<int:reservation_id>/<str:action>', views.reservation_action, name='library_reservation_action'),
    
    path('digital', views.digital_library, name='digital_library'),
    path('digital/<int:resource_id>/download', views.download_digital_resource, name='download_digital_resource'),
    
    path('fines', views.fine_management, name='library_fines'),
    path('reports', views.library_reports, name='library_reports'),
    
    # student portal routes
    path('student-portal/library', views.student_portal_library, name='student_portal_library'),
    path('student-portal/library/reserve/<int:book_id>', views.student_portal_reserve_book, name='student_portal_reserve_book'),
]
