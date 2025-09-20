from django.urls import path, include

from core import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path('surveys/', include('survey.urls',)),

    path("guardians/", include(
        [
            path("", views.guardian_list, name="guardian_list"),
            path("create/", views.guardian_create_form, name="guardian_create"),
            path("<int:guardian_id>/students/", views.guardian_students, name="guardian_students"),
            path("guardians/<int:guardian_id>/", views.guardian_detail, name="guardian_detail"),
            path("guardians/<int:guardian_id>/add/", views.student_form, name="student_add")

        ]
    )),

    path("students/", include([
        path("", views.students_list, name="students_list"),
        path("<int:student_id>/", views.student_detail, name="student_detail"),
    ])),

    path("employees/", include(
        [
            path("", views.employee_list, name="employee_list"),
            path("<int:pk>/", views.employee_detail, name="employee_detail"),
            # path("add/", views.employee_add, name="employee_add"),
            # path("edit/<int:pk>/", views.employee_edit, name="employee_edit"),
            # path("delete/<int:pk>/", views.employee_delete, name="employee_delete"),
        ]
    )),
]
