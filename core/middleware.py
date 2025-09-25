# core/middleware.py - School context and activity middleware
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class SchoolContextMiddleware(MiddlewareMixin):
    """
    Middleware to add school context to all requests
    Sets request.school based on user's associated school
    """

    def process_request(self, request):
        """Add school context to request"""
        request.school = None

        if hasattr(request, 'user') and request.user.is_authenticated:
            # Get school from user's profile
            if hasattr(request.user, 'guardian') and request.user.guardian:
                request.school = request.user.guardian.school
            elif hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
                request.school = request.user.teacher_profile.school
            elif hasattr(request.user, 'employee_profile') and request.user.employee_profile:
                request.school = request.user.employee_profile.school

        return None


class UserActivityMiddleware(MiddlewareMixin):
    """
    Middleware to track user activity
    Updates last_activity field for authenticated users
    """

    def process_request(self, request):
        """Update user's last activity"""
        if (hasattr(request, 'user') and
                request.user.is_authenticated and
                not request.user.is_anonymous):

            # Update last activity every 5 minutes to avoid too many DB writes
            now = timezone.now()
            if (not request.user.last_activity or
                    (now - request.user.last_activity).seconds > 300):
                request.user.update_last_activity()

        return None


class SchoolPermissionMiddleware(MiddlewareMixin):
    """
    Middleware to enforce school-level permissions
    Ensures users can only access data from their school
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Check school permissions for views"""
        # Skip for public views and admin
        if (not hasattr(request, 'user') or
                not request.user.is_authenticated or
                request.user.is_superuser):
            return None

        # Skip for API views (handled by API permissions)
        if request.path.startswith('/api/'):
            return None

        # Skip for auth views
        if request.path.startswith('/accounts/'):
            return None

        # Add school filtering for guardian views
        if (hasattr(request.user, 'guardian') and
                request.user.guardian and
                not request.school):
            # Redirect to profile completion if no school
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.warning(request, 'يرجى إكمال ملف المدرسة أولاً.')
            return redirect('accounts:profile')

        return None


# Context processor to make school available in templates
def school_context(request):
    """Add school context to all templates"""
    context = {
        'request_school': getattr(request, 'school', None),
        'user_school': None,
        'school_stats': None,
    }

    # Add user's school information
    if hasattr(request, 'user') and request.user.is_authenticated:
        school = getattr(request, 'school', None)
        if school:
            context['user_school'] = {
                'id': school.id,
                'name': school.name,
                'code': school.code,
                'principal_name': school.principal_name,
                'phone': school.phone,
                'email': school.email,
            }

            # Add basic stats for dashboard
            if hasattr(school, 'students'):
                context['school_stats'] = {
                    'total_students': school.students.filter(is_active=True).count(),
                    'total_guardians': school.guardians.count(),
                    'total_classes': school.classes.filter(is_active=True).count(),
                    'total_grades': school.grades.filter(is_active=True).count(),
                }

    return context


def user_context(request):
    """Add user context to all templates"""
    context = {
        'user_role': None,
        'user_permissions': {},
        'user_school_role': None,
    }

    if hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user

        # User role information
        context['user_role'] = user.get_role_display()

        # School-specific role
        if hasattr(user, 'guardian') and user.guardian:
            context['user_school_role'] = 'ولي أمر'
            context['user_permissions'] = {
                'can_view_children': True,
                'can_post_timeline': True,
                'can_fill_surveys': True,
            }
        elif hasattr(user, 'teacher_profile') and user.teacher_profile:
            context['user_school_role'] = 'معلم'
            context['user_permissions'] = {
                'can_manage_students': True,
                'can_post_timeline': True,
                'can_view_reports': True,
                'is_class_teacher': user.teacher_profile.is_class_teacher,
            }
        elif hasattr(user, 'employee_profile') and user.employee_profile:
            emp = user.employee_profile
            context['user_school_role'] = emp.get_position_display()
            context['user_permissions'] = {
                'can_manage_students': emp.can_manage_students,
                'can_manage_teachers': emp.can_manage_teachers,
                'can_view_reports': emp.can_view_reports,
            }
        elif user.is_staff:
            context['user_school_role'] = 'مدير النظام'
            context['user_permissions'] = {
                'can_manage_all': True,
                'can_manage_schools': True,
                'can_view_all_reports': True,
            }

    return context