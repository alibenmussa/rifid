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

    target_audience = tables.Column(verbose_name="الجمهور المتلقي")
    send_frequency = tables.Column(verbose_name="تكرار الإرسال")

    # Custom column to display grade count for guardian surveys
    grades_info = tables.Column(verbose_name="الصفوف", empty_values=(), orderable=False)

    # Custom column for send action
    # send_action = tables.Column(verbose_name="إرسال", empty_values=(), orderable=False)

    def render_grades_info(self, record):
        if record.target_audience == Template.TARGET_GUARDIANS:
            grade_count = record.grades.count()
            if grade_count == 0:
                return mark_safe('<span class="badge bg-secondary">جميع الصفوف</span>')
            else:
                return mark_safe(f'<span class="badge bg-primary">{grade_count} صف</span>')
        return mark_safe('<span class="text-muted">—</span>')

    def render_send_action(self, record):
        if record.send_frequency == Template.FREQ_ONCE:
            # Manual survey - show send button
            from django.urls import reverse
            url = reverse('dashboard:template_send', kwargs={'template_id': record.id})
            return mark_safe(
                f'<a href="{url}" class="btn btn-sm btn-primary">'
                f'<i class="bi bi-send"></i> إرسال</a>'
            )
        else:
            # Recurring survey - show periods link
            from django.urls import reverse
            url = reverse('dashboard:template_periods', kwargs={'template_id': record.id})
            return mark_safe(
                f'<a href="{url}" class="btn btn-sm btn-info">'
                f'<i class="bi bi-clock-history"></i> الفترات</a>'
            )

    class Meta:
        model = Template
        fields = ("name", "target_audience", "send_frequency", "grades_info",
                  # "send_action",
                  "created_at")

        template_name = TABLE_STYLE.get("template")
        attrs = {"class": TABLE_STYLE.get("class")}
        empty_text = "لا توجد نماذج"
