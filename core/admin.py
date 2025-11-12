# core/admin.py - Enhanced Admin with School Structure
from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    School, AcademicYear, Grade, SchoolClass,
    Guardian, Student, GuardianStudent,
    StudentTimeline, StudentTimelineAttachment
)


# ==========================================
# SCHOOL STRUCTURE ADMIN
# ==========================================

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'principal_name', 'phone', 'logo',
        'students_count', 'guardians_count', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'principal_name', 'phone', 'email']
    readonly_fields = ['code', 'created_at', 'updated_at']

    fieldsets = (
        ('معلومات أساسية', {
            'fields': ('name', 'code', 'principal_name', 'logo')
        }),
        ('معلومات الاتصال', {
            'fields': ('address', 'phone', 'email')
        }),
        ('السنة الدراسية', {
            'fields': ('academic_year_start', 'academic_year_end')
        }),
        ('الحالة', {
            'fields': ('is_active',)
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def students_count(self, obj):
        return obj.students.filter(is_active=True).count()

    students_count.short_description = 'عدد الطلاب'

    def guardians_count(self, obj):
        return obj.guardians.count()

    guardians_count.short_description = 'عدد الأولياء'


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'school', 'start_date']
    search_fields = ['name', 'school__name']

    fieldsets = (
        ('معلومات السنة الدراسية', {
            'fields': ('school', 'name', 'start_date', 'end_date', 'is_current')
        }),
    )


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'grade_type', 'level', 'classes_count', 'students_count', 'is_active']
    list_filter = ['grade_type', 'is_active', 'school']
    search_fields = ['name', 'school__name']

    def classes_count(self, obj):
        return obj.classes.filter(is_active=True).count()

    classes_count.short_description = 'عدد الفصول'

    def students_count(self, obj):
        return Student.objects.filter(
            current_class__grade=obj,
            is_active=True
        ).count()

    students_count.short_description = 'عدد الطلاب'


class StudentInline(admin.TabularInline):
    model = Student
    fk_name = "current_class"
    extra = 0
    fields = ['student_id', 'full_name', 'sex', 'phone', 'is_active']
    readonly_fields = ['student_id', 'full_name']
    can_delete = False


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'grade', 'academic_year', 'class_teacher',
        'student_count', 'capacity', 'is_full_display', 'is_active'
    ]
    list_filter = ['grade__grade_type', 'academic_year', 'is_active', 'grade__school']
    search_fields = ['name', 'grade__name', 'class_teacher__username']
    inlines = [StudentInline]

    fieldsets = (
        ('معلومات الفصل', {
            'fields': ('school', 'grade', 'academic_year', 'name', 'section')
        }),
        ('السعة والمعلم', {
            'fields': ('capacity', 'class_teacher')
        }),
        ('الحالة', {
            'fields': ('is_active',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'grade', 'academic_year', 'class_teacher'
        ).annotate(
            students_count=Count('students', filter=Q(students__is_active=True))
        )

    def is_full_display(self, obj):
        if obj.is_full:
            return format_html(
                '<span style="color: red; font-weight: bold;">ممتلئ</span>'
            )
        return format_html(
            '<span style="color: green;">متاح</span>'
        )

    is_full_display.short_description = 'حالة السعة'


# ==========================================
# ENHANCED USER ADMIN
# ==========================================

class GuardianStudentInline(admin.TabularInline):
    model = GuardianStudent
    fk_name = "guardian"
    extra = 1
    autocomplete_fields = ["student"]
    show_change_link = True
    fields = ['student', 'relationship', 'is_primary', 'is_emergency_contact', 'can_pickup']


class StudentGuardianInline(admin.TabularInline):
    model = GuardianStudent
    fk_name = "student"
    extra = 1
    autocomplete_fields = ["guardian"]
    show_change_link = True
    fields = ['guardian', 'relationship', 'is_primary', 'is_emergency_contact', 'can_pickup']


class StudentTimelineInline(admin.TabularInline):
    model = StudentTimeline
    extra = 0
    fields = ['title', 'content_type', 'is_pinned', 'is_visible_to_guardian', 'created_by', 'created_at']
    readonly_fields = ['created_by', 'created_at']
    ordering = ['-is_pinned', '-created_at']


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'school', 'phone', 'email',
        'children_count', 'selected_student', 'has_user_account', 'created_at'
    ]
    list_filter = ['school', 'created_at']
    search_fields = [
        'first_name', 'last_name', 'phone', 'email', 'nid', 'code',
        'students__first_name', 'students__last_name', 'students__full_name',
        'school__name'
    ]
    inlines = [GuardianStudentInline]
    autocomplete_fields = ["selected_student", "school"]
    readonly_fields = ["code", "created_at", "updated_at"]

    fieldsets = (
        ('معلومات المدرسة', {
            'fields': ('school',)
        }),
        ('المعلومات الشخصية', {
            'fields': ('first_name', 'last_name', 'phone', 'email', 'nid', 'address')
        }),
        ('الحساب والتسجيل', {
            'fields': ('user', 'code', 'selected_student')
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Limit selected_student choices to this guardian's students"""
        form = super().get_form(request, obj, **kwargs)
        if "selected_student" in form.base_fields:
            if obj:
                form.base_fields["selected_student"].queryset = obj.students.filter(is_active=True)
                form.base_fields["selected_student"].help_text = "اختر من أطفال هذا الولي."
            else:
                form.base_fields["selected_student"].queryset = Student.objects.none()
                form.base_fields["selected_student"].help_text = "احفظ الولي أولاً، ثم أضف الأطفال."
        return form

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'school', 'selected_student', 'user'
        ).annotate(
            children_count=Count('students', filter=Q(students__is_active=True))
        )

    def full_name(self, obj):
        return str(obj)

    full_name.short_description = 'الاسم الكامل'

    def children_count(self, obj):
        return obj.children_count

    children_count.short_description = 'عدد الأطفال'

    def has_user_account(self, obj):
        if obj.user:
            return format_html(
                '<span style="color: green;">✓</span>'
            )
        return format_html(
            '<span style="color: red;">✗</span>'
        )

    has_user_account.short_description = 'له حساب؟'

    def save_related(self, request, form, formsets, change):
        """Auto-select student if only one child"""
        super().save_related(request, form, formsets, change)
        guardian = form.instance
        if guardian.selected_student_id is None:
            children = guardian.students.filter(is_active=True)
            if children.count() == 1:
                guardian.selected_student = children.first()
                guardian.save(update_fields=["selected_student"])


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'student_id', 'full_name', 'school', 'current_class',
        'sex', 'age_display', 'guardians_count', 'is_active'
    ]
    list_filter = [
        'sex', 'is_active', 'school', 'current_class__grade__grade_type',
        'current_class__grade', 'enrollment_date'
    ]
    search_fields = [
        'student_id', 'full_name', 'first_name', 'last_name',
        'phone', 'alternative_phone', 'email', 'nid',
        'guardians__first_name', 'guardians__last_name', 'guardians__email',
        'school__name'
    ]
    inlines = [StudentGuardianInline, StudentTimelineInline]
    readonly_fields = ["student_id", "full_name", "created_at", "updated_at"]
    autocomplete_fields = ["school", "current_class"]

    fieldsets = (
        ('معلومات المدرسة', {
            'fields': ('school', 'student_id', 'current_class')
        }),
        ('المعلومات الشخصية', {
            'fields': (
                'first_name', 'second_name', 'third_name', 'fourth_name', 'last_name',
                'full_name', 'sex', 'date_of_birth', 'place_of_birth'
            )
        }),
        ('معلومات الاتصال', {
            'fields': ('phone', 'alternative_phone', 'email', 'nid', 'address')
        }),
        ('المعلومات الأكاديمية', {
            'fields': ('enrollment_date', 'graduation_date', 'is_active')
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'school', 'current_class__grade'
        ).annotate(
            guardians_count=Count('guardians')
        )

    def guardians_count(self, obj):
        return obj.guardians_count

    guardians_count.short_description = 'عدد الأولياء'

    def age_display(self, obj):
        if obj.date_of_birth:
            from django.utils import timezone
            today = timezone.now().date()
            age = today.year - obj.date_of_birth.year - (
                    (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
            )
            return f"{age} سنة"
        return "-"

    age_display.short_description = 'العمر'


@admin.register(GuardianStudent)
class GuardianStudentAdmin(admin.ModelAdmin):
    list_display = [
        'guardian_name', 'student_name', 'school', 'relationship_display',
        'is_primary', 'is_emergency_contact', 'can_pickup', 'can_receive_notifications'
    ]
    list_filter = [
        'relationship', 'is_primary', 'is_emergency_contact',
        'can_pickup', 'can_receive_notifications',
        'guardian__school'
    ]
    search_fields = [
        'guardian__first_name', 'guardian__last_name', 'guardian__phone',
        'student__first_name', 'student__last_name', 'student__full_name'
    ]
    autocomplete_fields = ["guardian", "student"]

    fieldsets = (
        ('العلاقة', {
            'fields': ('guardian', 'student', 'relationship')
        }),
        ('الحالة والأذونات', {
            'fields': (
                'is_primary', 'is_emergency_contact',
                'can_pickup', 'can_receive_notifications'
            )
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'guardian', 'student', 'guardian__school'
        )

    def guardian_name(self, obj):
        return str(obj.guardian)

    guardian_name.short_description = 'ولي الأمر'

    def student_name(self, obj):
        return str(obj.student)

    student_name.short_description = 'الطالب'

    def school(self, obj):
        return obj.guardian.school.name

    school.short_description = 'المدرسة'

    def relationship_display(self, obj):
        return obj.get_relationship_display()

    relationship_display.short_description = 'العلاقة'


# ==========================================
# TIMELINE ADMIN
# ==========================================

class StudentTimelineAttachmentInline(admin.TabularInline):
    model = StudentTimelineAttachment
    extra = 0
    fields = ['file', 'is_image', 'file_size', 'created_at']
    readonly_fields = ['is_image', 'file_size', 'created_at']


@admin.register(StudentTimeline)
class StudentTimelineAdmin(admin.ModelAdmin):
    list_display = [
        'title_display', 'student', 'school', 'content_type_display',
        'created_by', 'is_pinned', 'is_visible_to_guardian', 'created_at'
    ]
    list_filter = [
        'content_type', 'is_pinned', 'is_visible_to_guardian',
        'is_visible_to_student', 'student__school', 'created_at'
    ]
    search_fields = [
        'title', 'note', 'student__full_name', 'student__student_id',
        'created_by__username', 'created_by__first_name', 'created_by__last_name'
    ]
    inlines = [StudentTimelineAttachmentInline]
    autocomplete_fields = ['student']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('المحتوى', {
            'fields': ('student', 'title', 'note', 'content_type')
        }),
        ('الرؤية والتثبيت', {
            'fields': ('is_visible_to_guardian', 'is_visible_to_student', 'is_pinned')
        }),
        ('معلومات الإنشاء', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'student', 'student__school', 'created_by'
        )

    def title_display(self, obj):
        title = obj.title or 'بدون عنوان'
        if len(title) > 50:
            title = title[:47] + '...'
        if obj.is_pinned:
            return format_html(
                '<span style="font-weight: bold;">📌 {}</span>', title
            )
        return title

    title_display.short_description = 'العنوان'

    def school(self, obj):
        return obj.student.school.name

    school.short_description = 'المدرسة'

    def content_type_display(self, obj):
        return obj.get_content_type_display()

    content_type_display.short_description = 'النوع'

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(StudentTimelineAttachment)
class StudentTimelineAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        'timeline_title', 'student_name', 'file_name',
        'file_size_display', 'is_image', 'created_at'
    ]
    list_filter = ['is_image', 'created_at']
    search_fields = ['timeline__title', 'timeline__student__full_name']
    readonly_fields = ['is_image', 'file_size', 'created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'timeline', 'timeline__student'
        )

    def timeline_title(self, obj):
        return obj.timeline.title or 'بدون عنوان'

    timeline_title.short_description = 'عنوان المنشور'

    def student_name(self, obj):
        return obj.timeline.student.full_name

    student_name.short_description = 'الطالب'

    def file_name(self, obj):
        if obj.file:
            return obj.file.name.split('/')[-1]
        return '-'

    file_name.short_description = 'اسم الملف'

    def file_size_display(self, obj):
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return '-'

    file_size_display.short_description = 'حجم الملف'


# ==========================================
# ADMIN SITE CUSTOMIZATION
# ==========================================

# Customize admin site headers
admin.site.site_header = 'نظام إدارة المدارس - رفد'
admin.site.site_title = 'رفد - الإدارة'
admin.site.index_title = 'لوحة التحكم الرئيسية'

# Group models in admin index
# admin.site.register(School, SchoolAdmin)
# admin.site.register(AcademicYear, AcademicYearAdmin)
# admin.site.register(Grade, GradeAdmin)
# admin.site.register(SchoolClass, SchoolClassAdmin)