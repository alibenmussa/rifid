# core/forms.py - Enhanced forms with school context
from crispy_forms.layout import Div
from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError
from django.forms.widgets import ClearableFileInput

from core.models import (
    School, AcademicYear, Grade, SchoolClass,
    Guardian, Student, GuardianStudent,
    StudentTimeline
)


class SchoolContextMixin:
    """Mixin to add school context to forms"""

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        if self.school:
            self.filter_by_school()

    def filter_by_school(self):
        """Filter form fields by school context"""
        # Override in subclasses
        pass


class SchoolForm(forms.ModelForm):
    """Form for creating/editing schools"""

    class Meta:
        model = School
        fields = [
            'name', 'address', 'phone', 'email', 'principal_name',
            'academic_year_start', 'academic_year_end', 'is_active'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'academic_year_start': forms.DateInput(attrs={'type': 'date'}),
            'academic_year_end': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make fields required
        self.fields['name'].required = True
        self.fields['principal_name'].required = True

        # Add CSS classes
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('academic_year_start')
        end_date = cleaned_data.get('academic_year_end')

        if start_date and end_date and start_date >= end_date:
            raise ValidationError(
                'تاريخ بداية السنة الدراسية يجب أن يكون قبل تاريخ النهاية.'
            )

        return cleaned_data


class GradeForm(forms.ModelForm, SchoolContextMixin):
    """Form for creating/editing grades"""

    class Meta:
        model = Grade
        fields = ['name', 'level', 'grade_type', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.TextInput):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})


class SchoolClassForm(forms.ModelForm, SchoolContextMixin):
    """Form for creating/editing school classes"""

    class Meta:
        model = SchoolClass
        fields = [
            'grade', 'academic_year', 'name', 'section',
            'capacity', 'class_teacher', 'is_active'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def filter_by_school(self):
        """Filter choices by school"""
        if self.school:
            self.fields['grade'].queryset = Grade.objects.filter(
                school=self.school, is_active=True
            )
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(
                school=self.school
            )
            # Filter teachers by school (if you have a teacher model)
            # self.fields['class_teacher'].queryset = Teacher.objects.filter(
            #     school=self.school, is_active=True
            # )


class GuardianWithStudentForm(forms.Form, SchoolContextMixin):
    """Enhanced form for creating guardian with student"""

    # Guardian fields
    g_first_name = forms.CharField(label="الاسم الأول (الولي)", max_length=50)
    g_last_name = forms.CharField(label="اللقب (الولي)", max_length=50)
    g_phone = forms.CharField(label="الهاتف", required=False, max_length=15)
    g_email = forms.EmailField(label="البريد الإلكتروني", required=False)
    g_nid = forms.CharField(
        label="الرقم الوطني",
        required=False,
        min_length=12,
        max_length=12
    )
    g_address = forms.CharField(
        label="عنوان السكن",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2})
    )

    # Student fields
    s_student_id = forms.CharField(
        label="الرقم الجامعي",
        required=False,
        help_text="سيتم إنشاؤه تلقائياً إذا ترك فارغاً"
    )
    s_first_name = forms.CharField(label="الاسم الأول (الطالب)", max_length=50)
    s_second_name = forms.CharField(label="اسم الأب", required=False, max_length=50)
    s_third_name = forms.CharField(label="اسم الجد", required=False, max_length=50)
    s_fourth_name = forms.CharField(label="اسم جد الأب", required=False, max_length=50)
    s_last_name = forms.CharField(label="اللقب (الطالب)", max_length=50)
    s_sex = forms.ChoiceField(
        label="الجنس",
        choices=Student._meta.get_field("sex").choices
    )
    s_date_of_birth = forms.DateField(
        label="تاريخ الميلاد",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"})
    )
    s_place_of_birth = forms.CharField(label="مكان الميلاد", required=False, max_length=255)
    s_phone = forms.CharField(label="رقم الهاتف", required=False, max_length=15)
    s_email = forms.EmailField(label="البريد الإلكتروني", required=False)
    s_nid = forms.CharField(
        label="الرقم الوطني",
        required=False,
        min_length=12,
        max_length=12
    )
    s_address = forms.CharField(
        label="عنوان السكن",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2})
    )

    # Class assignment
    s_current_class = forms.ModelChoiceField(
        label="الفصل الحالي",
        queryset=SchoolClass.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Relationship
    relationship = forms.ChoiceField(
        label="العلاقة",
        choices=GuardianStudent.REL_CHOICES,
        initial="father"
    )

    def __init__(self, *args, **kwargs):
        self.school = school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        if not school:
            self.fields['school'] = forms.ModelChoiceField(
                label="المدرسة",
                queryset=School.objects.filter(is_active=True),
                required=True,
                widget=forms.Select(attrs={'class': 'form-select'})
            )

        # Setup crispy forms layout
        from crispy_forms.helper import FormHelper
        from crispy_forms.layout import Layout, Row, Column, HTML, Fieldset

        self.helper = FormHelper(self)
        self.helper.form_tag = False

        self.helper.layout = Layout(
            Div(
                'school',
                css_class='mb-4'
            )  if not school else '',
            Fieldset(
                'بيانات ولي الأمر',
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
            ),
            HTML("<hr/>"),
            Fieldset(
                'بيانات الطالب',
                Row(
                    Column("s_student_id", css_class="col-md-6"),
                    Column("s_sex", css_class="col-md-6"),
                ),
                Row(
                    Column("s_first_name", css_class="col-md-6"),
                    Column("s_second_name", css_class="col-md-6"),
                ),
                Row(
                    Column("s_third_name", css_class="col-md-6"),
                    Column("s_fourth_name", css_class="col-md-6"),
                ),
                Row(
                    Column("s_last_name", css_class="col-md-6"),
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
                    Column("s_address", css_class="col-md-6"),
                    Column("s_current_class", css_class="col-md-6"),
                ),
            ),
            HTML("<hr/>"),
            Fieldset(
                'العلاقة',
                Row(
                    Column("relationship", css_class="col-md-6"),
                ),
            ),
        )

    def filter_by_school(self):
        """Filter class choices by school"""
        if self.school:
            self.fields['s_current_class'].queryset = SchoolClass.objects.filter(
                school=self.school, is_active=True
            ).select_related('grade', 'academic_year')

    def clean_s_student_id(self):
        """Validate student ID uniqueness within school"""
        student_id = self.cleaned_data.get('s_student_id')
        if student_id and self.school:
            if Student.objects.filter(school=self.school, student_id=student_id).exists():
                raise ValidationError('الرقم الجامعي موجود بالفعل في هذه المدرسة.')
        return student_id

    @transaction.atomic
    def save(self, *, request_user=None):
        """Create Guardian + Student + link within school context"""
        if not self.school:
            raise ValueError("School context is required")

        # Create Guardian
        guardian = Guardian.objects.create(
            school=self.school,
            first_name=self.cleaned_data["g_first_name"],
            last_name=self.cleaned_data["g_last_name"],
            phone=self.cleaned_data.get("g_phone") or None,
            email=self.cleaned_data.get("g_email") or None,
            nid=self.cleaned_data.get("g_nid") or None,
            address=self.cleaned_data.get("g_address") or None,
        )

        # Create Student
        student = Student.objects.create(
            school=self.school,
            student_id=self.cleaned_data.get("s_student_id") or None,
            first_name=self.cleaned_data["s_first_name"],
            second_name=self.cleaned_data.get("s_second_name") or None,
            third_name=self.cleaned_data.get("s_third_name") or None,
            fourth_name=self.cleaned_data.get("s_fourth_name") or None,
            last_name=self.cleaned_data["s_last_name"],
            sex=self.cleaned_data["s_sex"],
            date_of_birth=self.cleaned_data.get("s_date_of_birth"),
            place_of_birth=self.cleaned_data.get("s_place_of_birth") or None,
            phone=self.cleaned_data.get("s_phone") or None,
            email=self.cleaned_data.get("s_email") or None,
            nid=self.cleaned_data.get("s_nid") or None,
            address=self.cleaned_data.get("s_address") or None,
            current_class=self.cleaned_data.get("s_current_class"),
        )

        # Create Guardian-Student relationship
        GuardianStudent.objects.create(
            guardian=guardian,
            student=student,
            relationship=self.cleaned_data["relationship"],
            is_primary=True,
        )

        # Set selected student
        guardian.selected_student = student
        guardian.save(update_fields=["selected_student"])

        return guardian, student


class StudentForm(forms.ModelForm, SchoolContextMixin):
    """Enhanced student form with school context"""

    class Meta:
        model = Student
        fields = [
            'student_id', 'first_name', 'second_name', 'third_name',
            'fourth_name', 'last_name', 'sex', 'date_of_birth',
            'place_of_birth', 'phone', 'alternative_phone', 'email',
            'nid', 'address', 'current_class', 'enrollment_date',
            'is_active'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.guardian = kwargs.pop('guardian', None)
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

        # Make student_id readonly if editing
        if self.instance and self.instance.pk:
            self.fields['student_id'].widget.attrs['readonly'] = True

    def filter_by_school(self):
        """Filter class choices by school"""
        if self.school:
            self.fields['current_class'].queryset = SchoolClass.objects.filter(
                school=self.school, is_active=True
            ).select_related('grade', 'academic_year')

    def clean_student_id(self):
        """Validate student ID uniqueness within school"""
        student_id = self.cleaned_data.get('student_id')
        if student_id and self.school:
            qs = Student.objects.filter(school=self.school, student_id=student_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('الرقم الجامعي موجود بالفعل في هذه المدرسة.')
        return student_id

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set school if provided
        if self.school:
            instance.school = self.school

        if commit:
            instance.save()

            # Create guardian relationship if guardian provided
            if self.guardian:
                GuardianStudent.objects.get_or_create(
                    guardian=self.guardian,
                    student=instance,
                    defaults={
                        'relationship': 'father',
                        'is_primary': True
                    }
                )

        return instance


class StudentTimelineForm(forms.ModelForm):
    """Enhanced student timeline form"""

    file = forms.FileField(
        label="الملف / الصورة",
        required=False,
        widget=ClearableFileInput,
        help_text="حد أقصى 10 ميجابايت. أنواع مدعومة: صور، PDF، مستندات"
    )

    class Meta:
        model = StudentTimeline
        fields = [
            'title', 'note', 'content_type',
            'is_pinned', 'is_visible_to_guardian', 'is_visible_to_student'
        ]
        labels = {
            'title': 'العنوان',
            'note': 'المحتوى',
            'content_type': 'نوع المحتوى',
            'is_pinned': 'تثبيت المنشور',
            'is_visible_to_guardian': 'مرئي لولي الأمر',
            'is_visible_to_student': 'مرئي للطالب',
        }
        widgets = {
            'note': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'اكتب المحتوى هنا…'
            }),
            'content_type': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

        # Set default visibility
        self.fields['is_visible_to_guardian'].initial = True

    def clean_file(self):
        """Validate uploaded file"""
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (10MB limit)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('حجم الملف يجب أن يكون أقل من 10 ميجابايت.')

            # Check file type
            allowed_types = [
                'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ]

            if file.content_type not in allowed_types:
                raise ValidationError(
                    'نوع الملف غير مدعوم. الأنواع المدعومة: صور، PDF، مستندات Word/Excel.'
                )

        return file

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        note = (cleaned_data.get("note") or "").strip()
        file = self.files.get("file") or cleaned_data.get("file")

        if not note and not file:
            raise ValidationError("يجب إضافة محتوى نصي أو رفع ملف.")

        return cleaned_data


class GuardianStudentForm(forms.ModelForm):
    """Form for managing guardian-student relationships"""

    class Meta:
        model = GuardianStudent
        fields = [
            'relationship', 'is_primary', 'is_emergency_contact',
            'can_pickup', 'can_receive_notifications'
        ]
        labels = {
            'relationship': 'العلاقة',
            'is_primary': 'ولي أمر أساسي',
            'is_emergency_contact': 'جهة اتصال طارئة',
            'can_pickup': 'يمكنه استلام الطالب',
            'can_receive_notifications': 'يستقبل الإشعارات',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})


class StudentSearchForm(forms.Form):
    """Form for searching students"""

    search = forms.CharField(
        label="البحث",
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'ابحث بالاسم، الرقم الجامعي، أو الهاتف...',
            'class': 'form-control'
        })
    )
    grade = forms.ModelChoiceField(
        label="الصف",
        queryset=Grade.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    school_class = forms.ModelChoiceField(
        label="الفصل",
        queryset=SchoolClass.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sex = forms.ChoiceField(
        label="الجنس",
        choices=[('', 'الكل')] + list(Student._meta.get_field("sex").choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_active = forms.ChoiceField(
        label="الحالة",
        choices=[('', 'الكل'), (True, 'نشط'), (False, 'غير نشط')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        if school:
            self.fields['grade'].queryset = Grade.objects.filter(
                school=school, is_active=True
            ).order_by('grade_type', 'level')

            self.fields['school_class'].queryset = SchoolClass.objects.filter(
                school=school, is_active=True
            ).select_related('grade').order_by('grade__level', 'name')


class BulkStudentUploadForm(forms.Form):
    """Form for bulk student upload via CSV/Excel"""

    file = forms.FileField(
        label="ملف البيانات",
        help_text="ارفع ملف CSV أو Excel يحتوي على بيانات الطلاب",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        })
    )
    grade = forms.ModelChoiceField(
        label="الصف الافتراضي",
        queryset=Grade.objects.none(),
        required=False,
        help_text="الصف الذي سيتم تعيينه للطلاب (اختياري)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    school_class = forms.ModelChoiceField(
        label="الفصل الافتراضي",
        queryset=SchoolClass.objects.none(),
        required=False,
        help_text="الفصل الذي سيتم تعيينه للطلاب (اختياري)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        if school:
            self.fields['grade'].queryset = Grade.objects.filter(
                school=school, is_active=True
            )
            self.fields['school_class'].queryset = SchoolClass.objects.filter(
                school=school, is_active=True
            ).select_related('grade')

    def clean_file(self):
        """Validate uploaded file"""
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (5MB limit)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError('حجم الملف يجب أن يكون أقل من 5 ميجابايت.')

            # Check file extension
            allowed_extensions = ['.csv', '.xlsx', '.xls']
            file_extension = file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(
                    f'نوع الملف غير مدعوم. الأنواع المدعومة: {", ".join(allowed_extensions)}'
                )

        return file


class AcademicYearForm(forms.ModelForm, SchoolContextMixin):
    """Form for managing academic years"""

    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_current']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        """Validate academic year dates"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date >= end_date:
            raise ValidationError(
                'تاريخ بداية السنة الدراسية يجب أن يكون قبل تاريخ النهاية.'
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set school if provided
        if self.school:
            instance.school = self.school

        if commit:
            instance.save()

        return instance


# Enhanced crispy forms helpers
def get_guardian_student_form_helper():
    """Get crispy form helper for guardian-student forms"""
    from crispy_forms.helper import FormHelper
    from crispy_forms.layout import Layout, Row, Column, HTML, Submit

    helper = FormHelper()
    helper.form_tag = False
    helper.layout = Layout(
        Row(
            Column('relationship', css_class='col-md-6'),
        ),
        HTML('<hr>'),
        Row(
            Column('is_primary', css_class='col-md-3'),
            Column('is_emergency_contact', css_class='col-md-3'),
            Column('can_pickup', css_class='col-md-3'),
            Column('can_receive_notifications', css_class='col-md-3'),
        ),
    )

    return helper


def get_student_search_form_helper():
    """Get crispy form helper for student search"""
    from crispy_forms.helper import FormHelper
    from crispy_forms.layout import Layout, Row, Column, HTML, Submit

    helper = FormHelper()
    helper.form_method = 'GET'
    helper.form_class = 'form-inline'
    helper.layout = Layout(
        Row(
            Column('search', css_class='col-md-4'),
            Column('grade', css_class='col-md-2'),
            Column('school_class', css_class='col-md-2'),
            Column('sex', css_class='col-md-2'),
            Column('is_active', css_class='col-md-2'),
        ),
        HTML('<div class="mt-2">'),
        Submit('submit', 'بحث', css_class='btn btn-primary me-2'),
        HTML('<a href="?" class="btn btn-secondary">إلغاء</a>'),
        HTML('</div>'),
    )

    return helper