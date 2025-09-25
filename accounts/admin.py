from django.contrib import admin
from django.contrib.auth import get_user_model

from accounts.models import TeacherProfile, EmployeeProfile

User = get_user_model()

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'email', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username', 'email')
    filter_horizontal = ('groups', 'user_permissions')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name','email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        # user_type
        # avatar
        # phone
        # date_of_birth
        # is_verified
        # last_activity
        # language
        # theme
        ('other info', {'fields': ('user_type', 'avatar', 'phone', 'date_of_birth', 'is_verified', 'last_activity', 'language', 'theme')}),
    )

admin.site.register(TeacherProfile)
admin.site.register(EmployeeProfile)

