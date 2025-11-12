import datetime
import json
import re
import uuid

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class Template(models.Model):
    FOOD = 'food'

    TYPE_CHOICES = (
        (FOOD, 'طعام'),
    )

    # Target audience choices
    TARGET_GUARDIANS = 'guardians'
    TARGET_TEACHERS = 'teachers'
    TARGET_EMPLOYEES = 'employees'
    TARGET_ALL = 'all'

    TARGET_CHOICES = (
        (TARGET_GUARDIANS, 'أولياء الأمور'),
        (TARGET_TEACHERS, 'المعلمون'),
        (TARGET_EMPLOYEES, 'الموظفون'),
        (TARGET_ALL, 'الجميع'),
    )

    # Send frequency choices
    FREQ_ONCE = "once"
    FREQ_WEEKLY = "weekly"
    FREQ_MONTHLY = "monthly"
    FREQ_QUARTERLY = "quarterly"  # every 3 months
    FREQ_YEARLY = "yearly"

    FREQ_CHOICES = (
        (FREQ_ONCE, "مرة واحدة (يدوي)"),
        (FREQ_WEEKLY, "أسبوعي"),
        (FREQ_MONTHLY, "شهري"),
        (FREQ_QUARTERLY, "كل 3 أشهر"),
        (FREQ_YEARLY, "سنوي"),
    )

    name = models.CharField(max_length=255, verbose_name='الاسم', null=True, blank=True)
    type = models.CharField(choices=TYPE_CHOICES, default=FOOD, max_length=16, verbose_name='النوع')
    parent = models.OneToOneField('survey.TemplateField', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_form', verbose_name='حقل النموذج')
    school = models.ForeignKey('core.School', on_delete=models.CASCADE, null=True, blank=True, related_name='templates', verbose_name='المدرسة', help_text='إذا كان فارغاً، فهو متاح لجميع المدارس')

    # New fields for generic survey system
    target_audience = models.CharField(
        max_length=20,
        choices=TARGET_CHOICES,
        default=TARGET_GUARDIANS,
        verbose_name='المتلقي',
        help_text='لمن هذا الاستطلاع؟'
    )
    grades = models.ManyToManyField(
        'core.Grade',
        blank=True,
        related_name='templates',
        verbose_name='الصفوف',
        help_text='اختر الصفوف المستهدفة (فقط لاستطلاعات أولياء الأمور). اتركه فارغاً لجميع الصفوف.'
    )
    send_frequency = models.CharField(
        max_length=20,
        choices=FREQ_CHOICES,
        default=FREQ_MONTHLY,
        verbose_name="تكرار الإرسال",
        help_text='كم مرة سيتم إرسال هذا الاستطلاع؟'
    )
    is_builtin = models.BooleanField(
        default=False,
        verbose_name='نموذج مدمج',
        help_text='النماذج المدمجة من المسؤول متاحة لجميع المدارس. النماذج المخصصة خاصة بمدرسة واحدة فقط.'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التعديل')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_templates', verbose_name='منشئ النموذج')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='updated_templates', verbose_name='محدث النموذج')

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name_plural = 'نماذج التذاكر'
        verbose_name = 'نموذج التذكرة'
        ordering = [ 'name']

    def save(self, *args, **kwargs):
        # Auto-set is_builtin based on school field
        # If school is None, it's a built-in template available to all schools
        self.is_builtin = self.school is None
        super().save(*args, **kwargs)

    def as_json(self, is_public=None):
        query = self.fields.all() if is_public is None else self.fields.filter(is_public=is_public)
        return [x.as_json() for x in query]

    class CustomForm(forms.Form):
        def __init__(self, template, ticket, fields, *args, **kwargs):
            self.template = template
            self.ticket = ticket
            self.o_fields = fields
            self.user = kwargs.pop('user', None)
            super().__init__(*args, **kwargs)

        def save(self, commit=True, parent=None) -> list:
            rows = []
            sub_rows = []

            if self.ticket:
                if self.template.type == self.template.FOOD:
                        for f in self.o_fields:
                            value_data = self.cleaned_data.get(f.key)

                            additional_field = AdditionalField(response=self.ticket, field=f, type=f.type, name=f.name,  value=value_data if f.type != f.FORM else None, parent=parent)
                            additional_field.created_by = self.user
                            # if commit:
                            #     additional_field.save()

                            rows.append(additional_field)

                        if commit:
                            AdditionalField.objects.bulk_create(rows)
                            # AdditionalField.objects.bulk_create(sub_rows)

            return rows

        def clean(self):
            cleaned_data = super().clean()
            if not self.ticket:
                return cleaned_data

            # fields = self.ticket.category.template.fields.all()

            for f in self.o_fields:

                field_value = cleaned_data.get(f.key)

                if not field_value and f.is_required is False:
                    continue

                if f.type == f.DATE and isinstance(field_value, datetime.date):
                    cleaned_data[f.key] = field_value.strftime("%Y-%m-%d")

                # if f.type == f.MAP:
                #     try:
                #         lat, lng = field_value.split(",")
                #         lat = float(lat)
                #         lng = float(lng)
                #         if lat < -90 or lat > 90:
                #             self.add_error(f.key, "خطوط العرض يجب أن تكون بين -90 و90")
                #         if lng < -180 or lng > 180:
                #             self.add_error(f.key, "خطوط الطول يجب أن تكون بين -180 و180")
                #     except ValueError:
                #         self.add_error(f.key, "إحداثيات غير صحيحة")
                #         continue

                # print(type(cleaned_data.get(f.key)))
                # # field_value = json.dumps(cleaned_data.get(f.key), ensure_ascii=False)
                # print(field_value)
                # cleaned_data[f.key] = field_value

                if f.type == f.FORM:
                    # try:
                    #     field_value = re.sub(r"'", r'"', field_value)
                    #     print(type(field_value), field_value)
                    #     field_value = json.loads(field_value)
                    #     cleaned_data[f.key] = field_value
                    # except Exception as e:
                    #     print(e)
                    #     self.add_error(f.key, "القيمة غير صالحة")
                    #     continue

                    if not isinstance(field_value, list):
                        self.add_error(f.key, "القيمة يجب أن تكون قائمة")
                        continue

                    fields = f.sub_form.fields.all()
                    for item in field_value:
                        form = f.sub_form.build_django_form(ticket=self.ticket, data=item, user=self.user, is_public=True, fields=fields)
                        if not form.is_valid():
                            keys = form.errors.keys()

                            for key in keys:
                                if key not in self.fields.keys():
                                    self.fields[key] = form.fields[key]
                            #         raise ValidationError( "تم تحديث النموذج، يرجى تحديث الصفحة")
                            raise ValidationError(form.errors)

            return cleaned_data

    def build_django_form(self, ticket=None, data=None, user=None, is_public=False, fields=None):
        fields = fields or self.fields.all()

        form = self.CustomForm(data=data, template=self, ticket=ticket, fields=fields, user=user)

        for field in fields:
            form.fields[field.key] = field.get_corresponding_django_form_field()
            if field.is_required is True and field.is_public is False and is_public is True:
                form.fields[field.key].required = False

        return form

    def build_crispy_form(self, ticket=None, fields=None, form_tag=True, columns=1):
        from crispy_forms.helper import FormHelper
        from crispy_forms.layout import Layout, Div, Column, Row, Submit, HTML, Button, Field
        # from crispy_forms.bootstrap import FormActions

        form = self.build_django_form(ticket=ticket, fields=fields)
        form.helper = FormHelper(form)
        form.helper.form_tag = form_tag

        form.helper.layout = Layout()

        for field in self.fields.all():
            column = "col-md-12" if field.type == field.__class__.TEXTAREA else f"col-md-{12 // columns}"
            form.helper.layout.append(
                Column(
                    Field(field.key),
                    css_class=column
                )
            )

        return form


class TemplateField(models.Model):
    TEXT = 'text'
    TEXTAREA = 'textarea'
    NUMBER = 'number'
    SELECT = 'select'
    CHECKBOX = 'checkbox'
    RADIO = 'radio'
    DATE = 'date'
    MAP = 'map'
    FORM = 'form'

    TYPE_CHOICES = (
        (TEXT, 'نص'),
        (TEXTAREA, 'نص طويل'),
        (NUMBER, 'رقم'),
        (SELECT, 'قائمة منسدلة'),
        (CHECKBOX, 'متعدد الخيارات'),
        (RADIO, 'خيار واحد'),
        (DATE, 'تاريخ'),
        # (MAP, 'خريطة'),
        # (FORM, 'نموذج')
    )

    key = models.CharField(max_length=16, verbose_name='المفتاح', unique=True)
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='fields', verbose_name='النموذج')
    name = models.CharField(max_length=255, verbose_name='عنوان الحقل')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TEXT, verbose_name='النوع')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    is_public = models.BooleanField(default=True, verbose_name='مرئي للمواطن؟')
    is_required = models.BooleanField(default=False, verbose_name='حقل إجباري؟')
    is_multiple = models.BooleanField(default=False, verbose_name='متعدد الإدخالات؟')
    value = models.JSONField(verbose_name='القيم', null=True, blank=True, default=None) # todo: to rename to choices

    # sub_form = models.OneToOneField(Template, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_template_fields', verbose_name='منشئ الحقل')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التعديل')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='updated_template_fields', verbose_name='محدث الحقل')

    def generate_key(self):
        key = "f" + str(uuid.uuid4().hex).lower()[:11]
        if self.__class__.objects.filter(key=key).exists():
            return self.generate_key()
        return key

    @transaction.atomic
    def save(self, *args, **kwargs):
        created = not self.pk
        if not self.key:
            self.key = self.generate_key()

        if not self.order and self.template:
            self.order = self.template.fields.count() + 1

        if self.type in (self.FORM, ):
            self.is_multiple = True

        super().save(*args, **kwargs)

        if created and self.type == self.FORM:
            # if not hasattr(self, 'sub_form'):
            Template.objects.create(name=f"{self.name} - {self.template.name}", type=Template.FOOD, parent=self, created_by=self.created_by, updated_by=self.updated_by)

    class Meta:
        verbose_name_plural = 'حقول نماذج البلاغات'
        verbose_name = 'حقل نموذج البلاغ'
        ordering = ['template', 'order']

    def __str__(self):
        return self.name

    @property
    def kind(self):
        return type(self.value).__name__

    def as_json(self):
        return {
            "order": self.order,
            "key": self.key,
            "value": self.value,
            "name": self.name,
            "type": self.type,
            "is_public": self.is_public,
            "is_required": self.is_required,
        }

    def get_corresponding_django_form_field(self):
        if self.type == self.TEXT:
            return forms.CharField(label=self.name, required=self.is_required, widget=forms.TextInput(
                attrs={"data-order": self.order, "data-is-public": self.is_public}))
        elif self.type == self.TEXTAREA:
            return forms.CharField(label=self.name, required=self.is_required, widget=forms.Textarea(
                attrs={"rows": 2, "data-order": self.order, "data-is-public": self.is_public}))
        elif self.type == self.NUMBER:
            return forms.FloatField(label=self.name, required=self.is_required, widget=forms.NumberInput(
                attrs={"data-order": self.order, "data-is-public": self.is_public}))
        elif self.type == self.SELECT:
            choices = [(x, x) for x in list(self.value)]
            choices.insert(0, ("", "---------"))
            return forms.ChoiceField(label=self.name, required=self.is_required, choices=choices, widget=forms.Select(
                attrs={"data-order": self.order, "data-is-public": self.is_public, "class": "form-select"}))
        elif self.type == self.CHECKBOX:
            choices = [(x, x) for x in list(self.value)]
            return forms.MultipleChoiceField(label=self.name, required=self.is_required, choices=choices,
                                             widget=forms.CheckboxSelectMultiple(
                                                 attrs={"data-order": self.order, "data-is-public": self.is_public}))
        elif self.type == self.RADIO:
            choices = [(x, x) for x in list(self.value)]
            return forms.ChoiceField(label=self.name, required=self.is_required, choices=choices,
                                     widget=forms.RadioSelect(
                                         attrs={"data-order": self.order, "data-is-public": self.is_public}))
        elif self.type == self.DATE:
            return forms.DateField(label=self.name, required=self.is_required, widget=forms.DateInput(
                attrs={"type": "date", "data-order": self.order, "data-is-public": self.is_public}))
        elif self.type == self.MAP:
            attrs = {"data-order": self.order, "data-is-public": self.is_public, "data-map": True}
            return forms.CharField(label=self.name, required=self.is_required, widget=forms.HiddenInput(
                attrs=attrs))

        elif self.type == self.FORM:
            return forms.JSONField(label=self.name, required=self.is_required, widget=forms.HiddenInput(
                attrs={"data-order": self.order, "data-is-public": self.is_public}))



        return forms.CharField(label=self.name, required=self.is_required, widget=forms.TextInput(
            attrs={"data-order": self.order, "data-is-public": self.is_public}))


class SurveyPeriod(models.Model):
    """
    Represents a time period when a survey is active
    For recurring surveys, a new period is created each cycle (weekly, monthly, etc.)
    For manual surveys, one period is created when sent
    """
    survey = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='periods', verbose_name='الاستطلاع')
    start_date = models.DateField(verbose_name='تاريخ البداية')
    end_date = models.DateField(verbose_name='تاريخ الانتهاء (الموعد النهائي)')
    is_active = models.BooleanField(default=True, verbose_name='نشط؟', help_text='فترة واحدة فقط يمكن أن تكون نشطة لكل استطلاع')
    school = models.ForeignKey('core.School', on_delete=models.CASCADE, null=True, blank=True, related_name='survey_periods', verbose_name='المدرسة')
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_survey_periods', verbose_name='أرسل بواسطة')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التعديل')

    class Meta:
        verbose_name = 'فترة استطلاع'
        verbose_name_plural = 'فترات الاستطلاعات'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['survey', 'is_active']),
            models.Index(fields=['school', 'is_active']),
            models.Index(fields=['-start_date']),
        ]

    def __str__(self):
        return f"{self.survey.name} - {self.start_date} إلى {self.end_date}"

    def save(self, *args, **kwargs):
        # Ensure only one active period per survey
        if self.is_active:
            SurveyPeriod.objects.filter(survey=self.survey, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if this period has expired"""
        from django.utils import timezone
        return timezone.now().date() > self.end_date

    @property
    def completion_rate(self):
        """Calculate completion rate for this period"""
        total = self.distributions.count()
        if total == 0:
            return 0
        completed = self.distributions.filter(is_completed=True).count()
        return round((completed / total) * 100, 2)


class SurveyDistribution(models.Model):
    """
    Individual survey assignment to a specific user (and student for guardian surveys)
    Tracks whether the survey was sent, completed, and links to the response
    """
    period = models.ForeignKey(SurveyPeriod, on_delete=models.CASCADE, related_name='distributions', verbose_name='الفترة')
    survey = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='distributions', verbose_name='الاستطلاع')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='survey_distributions', verbose_name='المستخدم')
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, null=True, blank=True, related_name='survey_distributions', verbose_name='الطالب', help_text='الطالب المعني (فقط لاستطلاعات أولياء الأمور)')
    response = models.OneToOneField('Response', on_delete=models.SET_NULL, null=True, blank=True, related_name='distribution', verbose_name='الرد')

    is_completed = models.BooleanField(default=False, verbose_name='تم الإكمال؟')
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإكمال')

    school = models.ForeignKey('core.School', on_delete=models.CASCADE, related_name='survey_distributions', verbose_name='المدرسة')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التعديل')

    class Meta:
        verbose_name = 'توزيع استطلاع'
        verbose_name_plural = 'توزيعات الاستطلاعات'
        ordering = ['-sent_at']
        unique_together = [['period', 'user', 'student']]  # Prevent duplicate distributions
        indexes = [
            models.Index(fields=['user', 'is_completed']),
            models.Index(fields=['period', 'user']),
            models.Index(fields=['school', 'user']),
            models.Index(fields=['school', 'is_completed']),
        ]

    def __str__(self):
        if self.student:
            return f"{self.survey.name} - {self.user.get_full_name()} (الطالب: {self.student.first_name})"
        return f"{self.survey.name} - {self.user.get_full_name()}"

    @property
    def is_expired(self):
        """Check if the distribution period has expired"""
        return self.period.is_expired

    @property
    def can_respond(self):
        """Check if user can still respond to this survey"""
        return not self.is_completed and not self.is_expired


class Response(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='responses', verbose_name='النموذج')
    # Temporarily nullable to allow migration from guardian to user
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='survey_responses', verbose_name='المستخدم', null=True, blank=True)
    # Keep guardian temporarily for migration
    guardian = models.ForeignKey('core.Guardian', on_delete=models.CASCADE, related_name='old_responses', verbose_name='الولي (قديم)', null=True, blank=True)
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='responses', verbose_name='الطالب', null=True, blank=True, help_text='الطالب المعني (فقط لاستطلاعات أولياء الأمور)')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التعديل')

    class Meta:
        verbose_name_plural = 'ردود نماذج البلاغات'
        verbose_name = 'رد نموذج البلاغ'
        ordering = ['-created_at']

        indexes = [
            models.Index(fields=["template", "user", "-created_at"]),
            models.Index(fields=["template", "student", "-created_at"]),
        ]


class AdditionalField(models.Model):
    response = models.ForeignKey("survey.Response", on_delete=models.CASCADE, related_name='fields', verbose_name='الرد')
    field = models.ForeignKey(TemplateField, on_delete=models.SET_NULL, null=True, blank=True, related_name='responses', verbose_name='الحقل')
    type = models.CharField(max_length=10, choices=TemplateField.TYPE_CHOICES, default=TemplateField.TEXT, verbose_name='النوع')
    name = models.CharField(max_length=255, verbose_name='الاسم')
    value = models.JSONField(verbose_name='القيمة', null=True, blank=True, default=None)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_fields', verbose_name='حقل النموذج')
    row = models.IntegerField(default=0, verbose_name='الترتيب')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التعديل')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_additional_fields', verbose_name='منشئ الحقل')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_additional_fields', verbose_name='محدث الحقل')

    objects = models.Manager()


    def save(self, *args, **kwargs):
        if self.parent:
            self.row = self.parent.sub_fields.filter(field=self.field).count()

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['row']


    def sub_fields_table(self):
        values = self.sub_fields.all()

        rows = {}

        for x in values:
            if x.row not in rows:
                rows[x.row] = []

            rows[x.row].append(x)

        table = list(rows.values())

        return table

