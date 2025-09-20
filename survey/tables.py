import django_tables2 as tables
from django.utils.safestring import mark_safe
from django_tables2 import A

from survey.models import Template
from utilities import TABLE_STYLE, Button


class TemplateTable(tables.Table):
    detail = tables.TemplateColumn(
        Button(url="dashboard:template_detail", params="record.id", icon="bi bi-eye").render(),
        verbose_name="")
    actions = tables.TemplateColumn(
        Button(url="dashboard:template_edit", params="record.id", icon="bi bi-pencil-square").render(),
        verbose_name="")

    # category = tables.Column(verbose_name="التصنيف")

    class Meta:
        model = Template
        fields = ("name", "default_frequency", "created_at", "updated_at")

        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}
        empty_text = "لا توجد نماذج"
