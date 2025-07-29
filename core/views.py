from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django_tables2 import RequestConfig

from core.tables import EmployeeTable

User = get_user_model()

@login_required
def dashboard(request):
    context = {"bar":
        {
            "main": True,
            "title": "لوحة التحكم",
            "buttons": [
                {
                    "icon": "bi bi-box-arrow-right",
                    "url": reverse("accounts:logout"),
                    "color": "btn-outline-primary",
                }
            ]
        }}
    return render(request, "pages/dashboard.html", context=context)


@login_required
def employee_list(request):
    employees = User.objects.filter(is_staff=True)
    employee_table = EmployeeTable(employees)

    RequestConfig(request, paginate={"per_page": 10}).configure(employee_table)

    context = {
        "table": employee_table,
        "bar": {

            "main": True,
            "title": "الموظفين",
            "buttons": [
                {
                    "icon": "bi bi-plus",
                }
            ]
        }}
    return render(request, "components/list.html", context=context)


def employee_detail(request, pk):
    return render(request, "pages/dashboard.html")