# core/filters.py (add this to your existing filters)

import django_filters
from django import forms
from django.db.models import Q
from core.models import GuardianStudent, Student


class GuardianStudentFilter(django_filters.FilterSet):
    """Enhanced filter for Guardian Students with search and relationship filtering"""

    search = django_filters.CharFilter(
        method='filter_search',
        label="البحث في الطلاب",
        widget=forms.TextInput(attrs={
            'placeholder': 'ابحث بالاسم، الهاتف، أو البريد الإلكتروني...',
            'class': 'form-control'
        })
    )

    relationship = django_filters.ChoiceFilter(
        choices=GuardianStudent.REL_CHOICES,
        label="نوع العلاقة",
        empty_label="جميع العلاقات",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    student_sex = django_filters.ChoiceFilter(
        field_name="student__sex",
        choices=Student._meta.get_field("sex").choices,
        label="الجنس",
        empty_label="الجميع",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    has_phone = django_filters.BooleanFilter(
        method='filter_has_phone',
        label="لديه هاتف",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    has_email = django_filters.BooleanFilter(
        method='filter_has_email',
        label="لديه بريد إلكتروني",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    is_active = django_filters.BooleanFilter(
        field_name="student__is_active",
        label="نشط",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = GuardianStudent
        fields = ['search', 'relationship', 'student_sex', 'has_phone', 'has_email', 'is_active']

    def filter_search(self, queryset, name, value):
        """Search across student and guardian fields"""
        if value:
            return queryset.filter(
                Q(student__first_name__icontains=value) |
                Q(student__last_name__icontains=value) |
                Q(student__second_name__icontains=value) |
                Q(student__third_name__icontains=value) |
                Q(student__fourth_name__icontains=value) |
                Q(student__phone__icontains=value) |
                Q(student__alternative_phone__icontains=value) |
                Q(student__email__icontains=value)
            )
        return queryset

    def filter_has_phone(self, queryset, name, value):
        """Filter students with/without phone"""
        if value is True:
            return queryset.filter(
                Q(student__phone__isnull=False, student__phone__gt='') |
                Q(student__alternative_phone__isnull=False, student__alternative_phone__gt='')
            )
        elif value is False:
            return queryset.filter(
                Q(student__phone__isnull=True) | Q(student__phone=''),
                Q(student__alternative_phone__isnull=True) | Q(student__alternative_phone='')
            )
        return queryset

    def filter_has_email(self, queryset, name, value):
        """Filter students with/without email"""
        if value is True:
            return queryset.filter(
                student__email__isnull=False,
                student__email__gt=''
            )
        elif value is False:
            return queryset.filter(
                Q(student__email__isnull=True) | Q(student__email='')
            )
        return queryset
