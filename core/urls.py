from django.urls import path, include

from core import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
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
