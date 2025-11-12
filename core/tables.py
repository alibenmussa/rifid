import django_tables2 as tables
from django.contrib.auth import get_user_model

from core.models import GuardianStudent, Guardian, Grade, SchoolClass, School
from accounts.models import TeacherProfile
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


class GradeTable(tables.Table):
    """Table for displaying grades"""
    name = tables.Column(verbose_name="اسم الصف")
    grade_type = tables.Column(verbose_name="نوع المرحلة", accessor="get_grade_type_display")
    level = tables.Column(verbose_name="المستوى")
    classes_count = tables.Column(verbose_name="عدد الفصول", orderable=False)
    students_count = tables.Column(verbose_name="عدد الطلاب", orderable=False)
    is_active = tables.TemplateColumn(
        '<span class="badge bg-success">نشط</span>'
        '{% if not value %}<span class="badge bg-secondary">غير نشط</span>{% endif %}',
        verbose_name="الحالة"
    )
    actions = tables.TemplateColumn(
        Button(url="dashboard:grade_detail", params="record.id", icon="bi bi-eye", style="mx-2").render() +
        Button(url="dashboard:grade_edit", params="record.id", icon="bi bi-pencil", style="mx-2").render(),
        verbose_name="الإجراءات"
    )

    class Meta:
        model = Grade
        fields = ("name", "grade_type", "level", "classes_count", "students_count", "is_active")
        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}


class SchoolClassTable(tables.Table):
    """Table for displaying school classes"""
    full_name = tables.Column(verbose_name="اسم الفصل", accessor="full_name")
    grade = tables.Column(verbose_name="الصف", accessor="grade.name")
    academic_year = tables.Column(verbose_name="السنة الدراسية", accessor="academic_year.name")
    class_teacher = tables.Column(
        verbose_name="المعلم المسؤول",
        accessor="class_teacher.get_display_name",
        default="—"
    )
    capacity = tables.Column(verbose_name="السعة")
    students_count = tables.Column(verbose_name="عدد الطلاب", orderable=False)
    occupancy_rate = tables.TemplateColumn(
        '{{ record.students_count|floatformat:0 }}/{{ record.capacity }} '
        '({% widthratio record.students_count record.capacity 100 %}%)',
        verbose_name="امتلاء الفصل",
        orderable=False
    )
    is_active = tables.TemplateColumn(
        '{% if value %}<span class="badge bg-success">نشط</span>'
        '{% else %}<span class="badge bg-secondary">غير نشط</span>{% endif %}',
        verbose_name="الحالة"
    )
    actions = tables.TemplateColumn(
        Button(url="dashboard:class_detail", params="record.id", icon="bi bi-eye", style="mx-2").render() +
        Button(url="dashboard:class_edit", params="record.id", icon="bi bi-pencil", style="mx-2").render(),
        verbose_name="الإجراءات"
    )

    class Meta:
        model = SchoolClass
        fields = ("full_name", "grade", "academic_year", "class_teacher", "capacity", "students_count", "is_active")
        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}


class TeacherTable(tables.Table):
    """Table for displaying teachers"""
    name = tables.Column(verbose_name="الاسم", accessor="user.get_display_name", orderable=False)
    employee_id = tables.Column(verbose_name="الرقم الوظيفي")
    subject = tables.Column(verbose_name="المادة")
    experience_years = tables.Column(verbose_name="سنوات الخبرة")
    is_class_teacher = tables.TemplateColumn(
        '{% if value %}<span class="badge bg-primary">نعم</span>'
        '{% else %}<span class="badge bg-secondary">لا</span>{% endif %}',
        verbose_name="معلم فصل"
    )
    is_active = tables.TemplateColumn(
        '{% if value %}<span class="badge bg-success">نشط</span>'
        '{% else %}<span class="badge bg-secondary">غير نشط</span>{% endif %}',
        verbose_name="الحالة"
    )
    actions = tables.TemplateColumn(
        Button(url="dashboard:teacher_detail", params="record.id", icon="bi bi-eye", style="mx-2").render() +
        Button(url="dashboard:teacher_edit", params="record.id", icon="bi bi-pencil", style="mx-2").render(),
        verbose_name="الإجراءات"
    )

    class Meta:
        model = TeacherProfile
        fields = ("name", "employee_id", "subject", "experience_years", "is_class_teacher", "is_active")
        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}


class SchoolTable(tables.Table):
    """Table for displaying schools"""
    name = tables.Column(verbose_name="اسم المدرسة")
    code = tables.Column(verbose_name="رمز المدرسة")
    principal_name = tables.Column(verbose_name="اسم المدير", default="—")
    phone = tables.Column(verbose_name="الهاتف", default="—")
    email = tables.Column(verbose_name="البريد الإلكتروني", default="—")
    students_count = tables.Column(verbose_name="عدد الطلاب", orderable=False)
    teachers_count = tables.Column(verbose_name="عدد المعلمين", orderable=False)
    is_active = tables.TemplateColumn(
        '{% if value %}<span class="badge bg-success">نشط</span>'
        '{% else %}<span class="badge bg-secondary">غير نشط</span>{% endif %}',
        verbose_name="الحالة"
    )
    actions = tables.TemplateColumn(
        Button(url="dashboard:school_detail", params="record.id", icon="bi bi-eye", style="mx-2").render() +
        Button(url="dashboard:school_edit", params="record.id", icon="bi bi-pencil", style="mx-2").render(),
        verbose_name="الإجراءات"
    )

    class Meta:
        model = School
        fields = ("name", "code", "principal_name", "phone", "students_count", "teachers_count", "is_active")
        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}
