from rest_framework.permissions import BasePermission

class IsGuardianUser(BasePermission):
    """
    Allows access only to authenticated users who have a related Guardian.
    """
    message = "User does not have a linked guardian profile."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user and user.is_authenticated and hasattr(user, "guardian") and user.guardian
        )


class HasSelectedStudent(BasePermission):
    message = "No student selected for guardian."
    def has_permission(self, request, view):
        g = getattr(getattr(request, "user", None), "guardian", None)
        return bool(g and g.selected_student_id)
