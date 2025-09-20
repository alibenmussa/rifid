# core/admin.py
from django.contrib import admin
from django.db.models import Count
from .models import Guardian, Student, GuardianStudent

# ── Inlines ────────────────────────────────────────────────────────────────
class GuardianStudentInline(admin.TabularInline):
    model = GuardianStudent
    fk_name = "guardian"
    extra = 1
    autocomplete_fields = ["student"]
    show_change_link = True

class StudentGuardianInline(admin.TabularInline):
    model = GuardianStudent
    fk_name = "student"
    extra = 1
    autocomplete_fields = ["guardian"]
    show_change_link = True

# ── Guardian ───────────────────────────────────────────────────────────────
@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    # list ALL concrete fields dynamically
    list_display = [f.name for f in Guardian._meta.fields]
    search_fields = (
        "first_name", "last_name", "phone", "email", "nid",
        "students__first_name", "students__last_name", "students__full_name",
    )
    inlines = [GuardianStudentInline]
    autocomplete_fields = ["selected_student"]
    readonly_fields = ("created_at", "updated_at")  # leave form fields default (no fieldsets)

    def get_form(self, request, obj=None, **kwargs):
        """
        Limit selected_student choices to this guardian's students when editing.
        On add, keep it empty until students are linked.
        """
        form = super().get_form(request, obj, **kwargs)
        if "selected_student" in form.base_fields:
            if obj:
                form.base_fields["selected_student"].queryset = obj.students.all()
                form.base_fields["selected_student"].help_text = "Choose from this guardian's linked students."
            else:
                from .models import Student
                form.base_fields["selected_student"].queryset = Student.objects.none()
                form.base_fields["selected_student"].help_text = "Save guardian, add students, then set selection."
        return form

    def save_related(self, request, form, formsets, change):
        """
        After saving inlines: if exactly one student is linked and no selection yet,
        auto-select that student.
        """
        super().save_related(request, form, formsets, change)
        guardian: Guardian = form.instance
        if guardian.selected_student_id is None:
            links = GuardianStudent.objects.filter(guardian=guardian).values_list("student_id", flat=True)
            if links.count() == 1:
                guardian.selected_student_id = links.first()
                guardian.save(update_fields=["selected_student"])

# ── Student ────────────────────────────────────────────────────────────────
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    # list ALL concrete fields dynamically
    list_display = [f.name for f in Student._meta.fields]
    search_fields = (
        "full_name", "first_name", "last_name", "phone", "alternative_phone",
        "email", "nid", "guardians__first_name", "guardians__last_name", "guardians__email",
    )
    list_filter = ("sex",)
    inlines = [StudentGuardianInline]
    # Make non-editable fields read-only so they can be displayed safely
    readonly_fields = ("full_name", "created_at", "updated_at")  # no fieldsets/fields specified

# ── GuardianStudent (through) ──────────────────────────────────────────────
@admin.register(GuardianStudent)
class GuardianStudentAdmin(admin.ModelAdmin):
    # list ALL concrete fields dynamically
    list_display = [f.name for f in GuardianStudent._meta.fields]
    list_select_related = ("guardian", "student")
    list_filter = ("relationship", "is_primary")
    search_fields = (
        "guardian__first_name", "guardian__last_name", "guardian__email", "guardian__phone",
        "student__first_name", "student__last_name", "student__full_name",
    )
    autocomplete_fields = ["guardian", "student"]
