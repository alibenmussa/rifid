


# core/forms.py
from django import forms
from django.db import transaction
from core.models import Guardian, Student, GuardianStudent


class GuardianWithStudentForm(forms.Form):
    g_first_name = forms.CharField(label="الاسم الأول (الولي)")
    g_last_name  = forms.CharField(label="اللقب (الولي)")
    g_phone      = forms.CharField(label="الهاتف", required=False)
    g_email      = forms.EmailField(label="البريد الإلكتروني", required=False)
    g_nid        = forms.CharField(label="الرقم الوطني", required=False, min_length=11, max_length=11)
    g_address    = forms.CharField(label="عنوان السكن", required=False)

    s_first_name     = forms.CharField(label="الاسم الأول (الطالب)")
    s_last_name      = forms.CharField(label="اللقب (الطالب)")
    s_sex            = forms.ChoiceField(label="الجنس", choices=Student._meta.get_field("sex").choices)
    s_date_of_birth  = forms.DateField(label="تاريخ الميلاد", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    s_place_of_birth = forms.CharField(label="مكان الميلاد", required=False)
    s_phone          = forms.CharField(label="رقم الهاتف", required=False)
    s_email          = forms.EmailField(label="البريد الإلكتروني", required=False)
    s_nid            = forms.CharField(label="الرقم الوطني", required=False, min_length=11, max_length=11)
    s_address        = forms.CharField(label="عنوان السكن", required=False)

    # ---- Relationship ----
    relationship = forms.ChoiceField(label="العلاقة", choices=GuardianStudent.REL_CHOICES, initial="father")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Crispy layout (keeps your components/crispy.html happy)
        from crispy_forms.helper import FormHelper
        from crispy_forms.layout import Layout, Row, Column, HTML, Field

        self.helper = FormHelper(self)
        self.helper.form_tag = False

        self.helper.layout = Layout(
            HTML("<h5 class='mb-3'>بيانات الولي</h5>"),
            Row(
                Column("g_first_name", css_class="col-md-6"),
                Column("g_last_name", css_class="col-md-6"),
            ),
            Row(
                Column("g_phone", css_class="col-md-6"),
                Column("g_email", css_class="col-md-6"),
            ),
            Row(
                Column("g_nid", css_class="col-md-6"),
                Column("g_address", css_class="col-md-6"),
            ),
            HTML("<hr/><h5 class='mb-3'>بيانات الطالب</h5>"),
            Row(
                Column("s_first_name", css_class="col-md-6"),
                Column("s_last_name", css_class="col-md-6"),
            ),
            Row(
                Column("s_sex", css_class="col-md-6"),
                Column("s_date_of_birth", css_class="col-md-6"),
            ),
            Row(
                Column("s_place_of_birth", css_class="col-md-6"),
                Column("s_phone", css_class="col-md-6"),
            ),
            Row(
                Column("s_email", css_class="col-md-6"),
                Column("s_nid", css_class="col-md-6"),
            ),
            Row(
                Column("s_address", css_class="col-md-12"),
            ),
            HTML("<hr/>"),
            Row(
                Column("relationship", css_class="col-md-6"),
            ),
        )

    @transaction.atomic
    def save(self, *, request_user=None):
        """Create Guardian + Student + link, and set selected_student to the created student."""
        g = Guardian.objects.create(
            first_name=self.cleaned_data["g_first_name"],
            last_name=self.cleaned_data["g_last_name"],
            phone=self.cleaned_data.get("g_phone") or None,
            email=self.cleaned_data.get("g_email") or None,
            nid=self.cleaned_data.get("g_nid") or None,
            address=self.cleaned_data.get("g_address") or None,
        )

        s = Student.objects.create(
            first_name=self.cleaned_data["s_first_name"],
            last_name=self.cleaned_data["s_last_name"],
            sex=self.cleaned_data["s_sex"],
            date_of_birth=self.cleaned_data.get("s_date_of_birth"),
            place_of_birth=self.cleaned_data.get("s_place_of_birth") or None,
            phone=self.cleaned_data.get("s_phone") or None,
            email=self.cleaned_data.get("s_email") or None,
            nid=self.cleaned_data.get("s_nid") or None,
            address=self.cleaned_data.get("s_address") or None,
        )

        GuardianStudent.objects.create(
            guardian=g,
            student=s,
            relationship=self.cleaned_data["relationship"],
            is_primary=True,
        )

        # Make this student selected by default (matches your API behavior)
        g.selected_student_id = s.id
        g.save(update_fields=["selected_student"])

        return g, s


# core/forms.py
from django import forms
from core.models import Student, GuardianStudent


class StudentForm(forms.ModelForm):
    guardian = forms.ModelChoiceField(queryset=Guardian.objects.all(), required=False, widget=forms.HiddenInput())

    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'second_name', 'third_name', 'fourth_name',
            'sex', 'date_of_birth', 'place_of_birth', 'phone', 'alternative_phone',
            'email', 'nid', 'address'
        ]

    def __init__(self, *args, **kwargs):
        guardian = kwargs.get('guardian', None)
        super().__init__(*args, **kwargs)
        if guardian:
            self.fields['guardian'].initial = guardian
            self.fields['guardian'].queryset = Guardian.objects.filter(id=guardian.id)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data['guardian']:
            guardian = self.cleaned_data['guardian']
            GuardianStudent.objects.get_or_create(guardian=guardian, student=instance)
        if commit:
            instance.save()
        return instance


# core/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.forms.widgets import ClearableFileInput
from core.models import StudentTimeline

class StudentTimelineForm(forms.ModelForm):
    file = forms.FileField(            # ← single file
        label="الملف / الصورة",
        required=False,
        widget=ClearableFileInput
    )

    class Meta:
        model = StudentTimeline
        fields = ["title", "note", "is_pinned", "file"]
        labels = {
            "title": "العنوان",
            "note": "المحتوى",         # ← renamed
            "is_pinned": "تثبيت المنشور",
        }
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "اكتب المحتوى هنا…"}),
        }

    def clean(self):
        data = super().clean()
        note = (data.get("note") or "").strip()
        the_file = self.files.get("file")
        if not note and not the_file:
            raise ValidationError("أضف محتوى أو قم برفع ملف/صورة واحدة.")
        return data
