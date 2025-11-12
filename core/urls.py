from django.urls import path, include

from core import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path('surveys/', include('survey.urls',)),

    path("schools/", include([
        path("", views.school_list, name="school_list"),
        path("my-school/", views.my_school, name="my_school"),
        path("create/", views.school_create, name="school_create"),
        path("<int:school_id>/", views.school_detail, name="school_detail"),
        path("<int:school_id>/edit/", views.school_edit, name="school_edit"),
        path("<int:school_id>/delete/", views.school_delete, name="school_delete"),
    ])),

    path("guardians/", include(
        [
            path("", views.guardian_list, name="guardian_list"),
            path("create/", views.guardian_create_form, name="guardian_create"),
            # path("<int:guardian_id>/students/", views.guardian_students, name="guardian_students"),
            path("guardians/<int:guardian_id>/", views.guardian_detail, name="guardian_detail"),
            path("guardians/<int:guardian_id>/add/", views.student_form, name="student_add")

        ]
    )),

    path("students/", include([
        path("", views.students_list, name="students_list"),
        path("<int:student_id>/", views.student_detail, name="student_detail"),
        path("<int:student_id>/edit/", views.student_form, name="student_form"),
        path("<int:student_id>/add-guardian/", views.guardian_student_form, name="guardian_student_form"),
    ])),

    path("grades/", include([
        # path("", views.grade_list, name="grade_list"),  # Removed: grades accessed via school detail
        path("create/", views.grade_create, name="grade_create"),
        path("<int:grade_id>/", views.grade_detail, name="grade_detail"),
        path("<int:grade_id>/edit/", views.grade_edit, name="grade_edit"),
        path("<int:grade_id>/delete/", views.grade_delete, name="grade_delete"),
    ])),

    path("classes/", include([
        # path("", views.class_list, name="class_list"),  # Removed: classes accessed via grade detail
        path("create/", views.class_create, name="class_create"),
        path("<int:class_id>/", views.class_detail, name="class_detail"),
        path("<int:class_id>/edit/", views.class_edit, name="class_edit"),
        path("<int:class_id>/delete/", views.class_delete, name="class_delete"),
    ])),

    path("teachers/", include([
        path("", views.teacher_list, name="teacher_list"),
        path("create/", views.teacher_create, name="teacher_create"),
        path("<int:pk>/", views.teacher_detail, name="teacher_detail"),
        path("<int:pk>/edit/", views.teacher_edit, name="teacher_edit"),
        path("<int:pk>/delete/", views.teacher_delete, name="teacher_delete"),
    ])),

    path("employees/", include(
        [
            path("", views.employee_list, name="employee_list"),
            path("create/", views.employee_create, name="employee_create"),
            path("<int:pk>/", views.employee_detail, name="employee_detail"),
            path("<int:pk>/edit/", views.employee_edit, name="employee_edit"),
            path("<int:pk>/delete/", views.employee_delete, name="employee_delete"),
        ]
    )),

    # AJAX endpoints
    path("ajax/", include([
        path("classes-by-grade/", views.get_classes_by_grade, name="ajax_classes_by_grade"),
        path("students-by-class/", views.get_students_by_class, name="ajax_students_by_class"),
        path("guardians/<int:guardian_id>/select-student/<int:student_id>/",
             views.guardian_select_student, name="guardian_select_student"),
    ])),
]
