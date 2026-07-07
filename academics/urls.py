from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("classes/", views.classes, name="classes"),
    path("classes/new/", views.class_new, name="class_new"),
    path("classes/<int:class_id>/", views.class_detail, name="class_detail"),
    path("classes/<int:class_id>/edit/", views.class_edit, name="class_edit"),
    path("classes/<int:class_id>/delete/", views.class_delete, name="class_delete"),
    path("subjects/", views.subjects, name="subjects"),
    path("subjects/new/", views.subject_new, name="subject_new"),
    path("subjects/<int:subject_id>/", views.subject_detail, name="subject_detail"),
    path("subjects/<int:subject_id>/edit/", views.subject_edit, name="subject_edit"),
    path("subjects/<int:subject_id>/delete/", views.subject_delete, name="subject_delete"),
    path("timetables/", views.timetables, name="timetables"),
    path("timetables/new/", views.timetable_new, name="timetable_new"),
    path("timetables/generate/", views.timetable_generate, name="timetable_generate"),
    path("timetables/<int:timetable_id>/edit/", views.timetable_edit, name="timetable_edit"),
    path("timetables/<int:timetable_id>/delete/", views.timetable_delete, name="timetable_delete"),
    path("e-learning/", views.e_learning, name="e_learning"),
    path("e-learning/new/", views.e_learning_new, name="e_learning_new"),
    path("e-learning/<int:assignment_id>/", views.e_learning_detail, name="e_learning_detail"),
    path("e-learning/<int:assignment_id>/edit/", views.e_learning_edit, name="e_learning_edit"),
    path("e-learning/<int:assignment_id>/delete/", views.e_learning_delete, name="e_learning_delete"),
    path("e-learning/notes/new/", views.e_learning_note_new, name="e_learning_note_new"),
    path("e-learning/notes/<int:note_id>/delete/", views.e_learning_note_delete, name="e_learning_note_delete"),
    path("e-learning/submissions/<int:submission_id>/mark/", views.mark_submission, name="mark_submission"),
    path("e-learning/download/<str:file_type>/<int:item_id>/", views.download, name="download"),
    path("library/", views.library, name="library"),
    path("library/new/", views.library_new, name="library_new"),
    path("library/<int:book_id>/edit/", views.library_edit, name="library_edit"),
    path("library/<int:book_id>/delete/", views.library_delete, name="library_delete"),
    path("library/issues/<int:issue_id>/return/", views.return_library_book, name="return_library_book"),
]
