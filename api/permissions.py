from rest_framework.permissions import BasePermission
from core.models import GuardianStudent


class IsGuardianUser(BasePermission):
    """
    Allows access only to authenticated users who have a related Guardian.
    """
    message = "المستخدم لا يملك ملف ولي أمر مرتبط."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user and user.is_authenticated and
            hasattr(user, "guardian") and user.guardian
        )


class HasSelectedStudent(BasePermission):
    """
    Ensures guardian has a selected student.
    """
    message = "لا يوجد طالب محدد لولي الأمر."

    def has_permission(self, request, view):
        guardian = getattr(getattr(request, "user", None), "guardian", None)
        return bool(guardian and guardian.selected_student_id)


class IsSchoolMember(BasePermission):
    """
    Ensures user belongs to a school (guardian or teacher).
    """
    message = "المستخدم غير مرتبط بمدرسة."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        # Check if user has guardian with school
        if hasattr(user, "guardian") and user.guardian:
            return bool(user.guardian.school_id)

        # Check if user has teacher profile with school
        if hasattr(user, "teacher_profile") and user.teacher_profile:
            return bool(user.teacher_profile.school_id)

        # Check if user is staff (can access all schools)
        return user.is_staff


class CanAccessStudent(BasePermission):
    """
    Check if user can access specific student data.
    """
    message = "ليس لديك صلاحية للوصول إلى بيانات هذا الطالب."

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Staff can access all students
        if user.is_staff:
            return True

        # Guardian can access their own students
        if hasattr(user, "guardian") and user.guardian:
            return GuardianStudent.objects.filter(
                guardian=user.guardian,
                student=obj
            ).exists()

        # Teacher can access students in their school
        if hasattr(user, "teacher_profile") and user.teacher_profile:
            return obj.school_id == user.teacher_profile.school_id

        return False


class CanModifyTimeline(BasePermission):
    """
    Check if user can create/modify timeline entries.
    """
    message = "ليس لديك صلاحية لتعديل السجل الزمني."

    def has_permission(self, request, view):
        user = request.user

        # Staff/teachers can create timeline entries
        if user.is_staff:
            return True

        # Guardians can create timeline entries for their children
        if hasattr(user, "guardian") and user.guardian:
            return True

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Staff can modify all entries
        if user.is_staff:
            return True

        # Users can modify their own entries
        if obj.created_by == user:
            return True

        # Guardians can modify entries for their students
        if hasattr(user, "guardian") and user.guardian:
            return GuardianStudent.objects.filter(
                guardian=user.guardian,
                student=obj.student
            ).exists()

        return False


class IsInSameSchool(BasePermission):
    """
    Ensure objects belong to the same school as the user.
    """
    message = "هذا العنصر لا ينتمي لنفس المدرسة."

    def has_object_permission(self, request, view, obj):
        user = request.user
        user_school = None

        # Get user's school
        if hasattr(user, "guardian") and user.guardian:
            user_school = user.guardian.school
        elif hasattr(user, "teacher_profile") and user.teacher_profile:
            user_school = user.teacher_profile.school
        elif user.is_staff:
            return True  # Staff can access all schools

        if not user_school:
            return False

        # Check object's school
        if hasattr(obj, 'school'):
            return obj.school == user_school
        elif hasattr(obj, 'student') and hasattr(obj.student, 'school'):
            return obj.student.school == user_school
        elif hasattr(obj, 'guardian') and hasattr(obj.guardian, 'school'):
            return obj.guardian.school == user_school

        return False


class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level permission to only allow owners to edit objects.
    """
    message = "يمكنك فقط تعديل البيانات التي تملكها."

    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True

        # Write permissions only to the owner
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        elif hasattr(obj, 'guardian'):
            return hasattr(request.user, 'guardian') and obj.guardian == request.user.guardian
        elif hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class GuardianCanAccessOwnData(BasePermission):
    """
    Guardian can only access their own data and their students' data.
    """
    message = "يمكنك فقط الوصول إلى بياناتك وبيانات أطفالك."

    def has_permission(self, request, view):
        return hasattr(request.user, 'guardian') and request.user.guardian

    def has_object_permission(self, request, view, obj):
        user = request.user
        guardian = getattr(user, 'guardian', None)

        if not guardian:
            return False

        # Guardian accessing their own data
        if hasattr(obj, 'guardian') and obj.guardian == guardian:
            return True

        # Guardian accessing their student's data
        if hasattr(obj, 'student'):
            return GuardianStudent.objects.filter(
                guardian=guardian,
                student=obj.student
            ).exists()

        # Guardian accessing survey responses
        if hasattr(obj, 'guardian') and obj.guardian == guardian:
            return True

        return False


class IsEmployeeUser(BasePermission):
    """
    Allows access only to authenticated users who have a related Employee profile.
    """
    message = "المستخدم لا يملك ملف موظف مرتبط."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user and user.is_authenticated and
            hasattr(user, "employee_profile") and user.employee_profile
        )