import django_tables2 as tables
from django.contrib.auth import get_user_model

from core.models import GuardianStudent, Guardian
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



class GuardianStudentTable(tables.Table):
    student = tables.Column(accessor="student.full_name", verbose_name="الطالب")
    relationship = tables.Column(verbose_name="العلاقة")
    # is_primary = tables.BooleanColumn(verbose_name="أساسي؟")

    class Meta:
        model = GuardianStudent
        fields = ("student", "relationship")

        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}



class GuardianTable(tables.Table):
    # id = tables.Column(verbose_name="المعرف")
    first_name = tables.Column(verbose_name="الاسم")
    last_name = tables.Column(verbose_name="اللقب")
    phone = tables.Column(verbose_name="الهاتف")
    email = tables.Column(verbose_name="البريد الإلكتروني")
    selected_student = tables.Column(
        accessor="selected_student.full_name",
        verbose_name="الطالب المختار",
        default="—",
    )
    actions = tables.TemplateColumn(
        Button(url="dashboard:guardian_detail", params="record.id", icon="bi bi-eye", style="mx-3").render()
        # + "" +
        # Button(url="deposit_edit", params="record.id").render()
        , verbose_name="")



    class Meta:
        model = Guardian
        fields = (
            # "id",
            "first_name", "last_name", "phone", "email",)

        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}


# core/tables.py (append)
import django_tables2 as tables
from core.models import Student
from rifid.utilities import TABLE_STYLE, Button

class StudentTable(tables.Table):
    full_name = tables.Column(verbose_name="الاسم الكامل")
    actions = tables.TemplateColumn(
        Button(url="dashboard:student_detail", params="record.id", icon="bi bi-eye", style="mx-3").render(),
        verbose_name=""
    )

    class Meta:
        model = Student
        fields = ("full_name", "sex", "date_of_birth", "phone", "email")
        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}
