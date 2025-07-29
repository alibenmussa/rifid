import django_tables2 as tables
from django.contrib.auth import get_user_model

from rifid.utilities import TABLE_STYLE, Button


class EmployeeTable(tables.Table):
    actions = tables.TemplateColumn(
        Button(url="dashboard:employee_detail", params="record.id", icon="bi bi-eye", style="mx-3").render()
        # + "" +
        # Button(url="deposit_edit", params="record.id").render()
        , verbose_name="")

    name = tables.Column(verbose_name="الاسم", accessor="get_full_name")
    is_active = tables.TemplateColumn('<input type="checkbox" id="checkbox1" class="form-check-input" {% if value %}checked{% endif %} disabled>', verbose_name="مفعل؟")


    class Meta:
        model = get_user_model()
        fields = ("username", "name", "email", "is_active", "last_login", "date_joined")

        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}
