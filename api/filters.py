# api/filters.py - Enhanced filters for the API
import django_filters
from django.db.models import Q
from core.models import Student, StudentTimeline, School, Grade, SchoolClass


class StudentFilter(django_filters.FilterSet):
    """Filter for student searches"""

    search = django_filters.CharFilter(method='filter_search', label="البحث")
    grade = django_filters.ModelChoiceFilter(
        field_name='current_class__grade',
        queryset=Grade.objects.none(),
        label="الصف"
    )
    school_class = django_filters.ModelChoiceFilter(
        field_name='current_class',
        queryset=SchoolClass.objects.none(),
        label="الفصل"
    )
    sex = django_filters.ChoiceFilter(
        choices=Student._meta.get_field('sex').choices,
        label="الجنس"
    )
    is_active = django_filters.BooleanFilter(label="نشط")
    enrollment_year = django_filters.NumberFilter(
        field_name='enrollment_date__year',
        label="سنة التسجيل"
    )
    age_min = django_filters.NumberFilter(method='filter_age_min', label="العمر الأدنى")
    age_max = django_filters.NumberFilter(method='filter_age_max', label="العمر الأقصى")
    has_phone = django_filters.BooleanFilter(method='filter_has_phone', label="له هاتف")

    class Meta:
        model = Student
        fields = [
            'search', 'grade', 'school_class', 'sex', 'is_active',
            'enrollment_year', 'age_min', 'age_max', 'has_phone'
        ]

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        if school:
            self.filters['grade'].queryset = Grade.objects.filter(
                school=school, is_active=True
            )
            self.filters['school_class'].queryset = SchoolClass.objects.filter(
                school=school, is_active=True
            ).select_related('grade')

    def filter_search(self, queryset, name, value):
        """Search across multiple fields"""
        if value:
            return queryset.filter(
                Q(student_id__icontains=value) |
                Q(first_name__icontains=value) |
                Q(last_name__icontains=value) |
                Q(full_name__icontains=value) |
                Q(phone__icontains=value) |
                Q(alternative_phone__icontains=value) |
                Q(email__icontains=value)
            )
        return queryset

    def filter_age_min(self, queryset, name, value):
        """Filter by minimum age"""
        if value:
            from django.utils import timezone
            from datetime import date
            today = timezone.now().date()
            max_birth_date = date(today.year - value, today.month, today.day)
            return queryset.filter(date_of_birth__lte=max_birth_date)
        return queryset

    def filter_age_max(self, queryset, name, value):
        """Filter by maximum age"""
        if value:
            from django.utils import timezone
            from datetime import date
            today = timezone.now().date()
            min_birth_date = date(today.year - value - 1, today.month, today.day)
            return queryset.filter(date_of_birth__gte=min_birth_date)
        return queryset

    def filter_has_phone(self, queryset, name, value):
        """Filter students with/without phone numbers"""
        if value is True:
            return queryset.filter(
                Q(phone__isnull=False) & ~Q(phone='') |
                Q(alternative_phone__isnull=False) & ~Q(alternative_phone='')
            )
        elif value is False:
            return queryset.filter(
                Q(phone__isnull=True) | Q(phone=''),
                Q(alternative_phone__isnull=True) | Q(alternative_phone='')
            )
        return queryset


class StudentTimelineFilter(django_filters.FilterSet):
    """Enhanced filter for student timeline"""

    content_type = django_filters.ChoiceFilter(
        choices=StudentTimeline.CONTENT_TYPES,
        label="نوع المحتوى"
    )
    is_pinned = django_filters.BooleanFilter(label="مثبت")
    has_attachments = django_filters.BooleanFilter(
        method='filter_has_attachments',
        label="يحتوي على مرفقات"
    )
    created_after = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
        label="تم إنشاؤه بعد"
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
        label="تم إنشاؤه قبل"
    )
    created_by = django_filters.ModelChoiceFilter(
        field_name="created_by",
        queryset=None,  # Will be set in __init__
        label="أنشأ بواسطة"
    )
    search = django_filters.CharFilter(
        method='filter_search',
        label="البحث في العنوان والمحتوى"
    )

    class Meta:
        model = StudentTimeline
        fields = [
            'content_type', 'is_pinned', 'has_attachments',
            'created_after', 'created_before', 'created_by', 'search'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set created_by queryset to users who have created timeline entries
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.filters['created_by'].queryset = User.objects.filter(
            student_timeline_notes__isnull=False
        ).distinct()

    def filter_has_attachments(self, queryset, name, value):
        """Filter by attachment presence"""
        if value is True:
            return queryset.filter(attachments__isnull=False).distinct()
        elif value is False:
            return queryset.filter(attachments__isnull=True)
        return queryset

    def filter_search(self, queryset, name, value):
        """Search in title and note content"""
        if value:
            return queryset.filter(
                Q(title__icontains=value) |
                Q(note__icontains=value)
            )
        return queryset


class SchoolFilter(django_filters.FilterSet):
    """Filter for schools (admin use)"""

    search = django_filters.CharFilter(method='filter_search', label="البحث")
    is_active = django_filters.BooleanFilter(label="مفعل")
    has_students = django_filters.BooleanFilter(
        method='filter_has_students',
        label="يحتوي على طلاب"
    )
    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="gte",
        label="تم إنشاؤها بعد"
    )

    class Meta:
        model = School
        fields = ['search', 'is_active', 'has_students', 'created_after']

    def filter_search(self, queryset, name, value):
        """Search across school fields"""
        if value:
            return queryset.filter(
                Q(name__icontains=value) |
                Q(code__icontains=value) |
                Q(principal_name__icontains=value) |
                Q(phone__icontains=value) |
                Q(email__icontains=value)
            )
        return queryset

    def filter_has_students(self, queryset, name, value):
        """Filter schools with/without students"""
        if value is True:
            return queryset.filter(students__isnull=False).distinct()
        elif value is False:
            return queryset.filter(students__isnull=True)
        return queryset
