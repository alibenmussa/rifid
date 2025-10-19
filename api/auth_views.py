# survey/api/auth_views.py
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from core.models import Guardian
from api.serializers import (
    AuthLoginInputSerializer,
    AuthLoginOutputSerializer,
    GuardianSerializer,
    StudentOptionSerializer,
    EmployeeProfileSerializer,
    TeacherProfileSerializer,
    # GuardianMiniSerializer,
)


def build_user_profile_data(user, include_token=False):
    """
    Build unified profile data for any user type (employee/teacher/guardian)

    Args:
        user: The authenticated user
        include_token: Whether to include authentication token in response

    Returns:
        dict: Profile data with consistent structure for all user types
    """
    response_data = {
        "user_type": None,
        "employee": None,
        "teacher": None,
        "guardian": None,
        "selected_student": None,
        "has_multiple_students": False,
        "students_count": 0,
    }

    # Add token if requested
    if include_token:
        token, _ = Token.objects.get_or_create(user=user)
        response_data["token"] = token.key

    # Check if user is an employee
    if hasattr(user, 'employee_profile') and user.employee_profile:
        response_data["user_type"] = "employee"
        response_data["employee"] = EmployeeProfileSerializer(user.employee_profile).data
        return response_data

    # Check if user is a teacher
    if hasattr(user, 'teacher_profile') and user.teacher_profile:
        response_data["user_type"] = "teacher"
        response_data["teacher"] = TeacherProfileSerializer(user.teacher_profile).data
        return response_data

    # Check if user is a guardian
    try:
        guardian = user.guardian
        students_qs = guardian.students.all().order_by("last_name", "first_name")
        students_count = students_qs.count()

        # Auto-select first student if none selected and has students
        if guardian.selected_student_id is None and students_count > 0:
            first_student = students_qs.first()
            guardian.selected_student = first_student
            guardian.save(update_fields=["selected_student", "updated_at"])

        response_data["user_type"] = "guardian"
        response_data["guardian"] = guardian
        response_data["selected_student"] = guardian.selected_student
        response_data["has_multiple_students"] = students_count > 1
        response_data["students_count"] = students_count
        return response_data

    except Guardian.DoesNotExist:
        return None

class AuthLoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Login (TokenAuth) for guardians",
        request_body=AuthLoginInputSerializer,
        responses={
            200: AuthLoginOutputSerializer,
            401: "Invalid credentials",
            403: "User missing guardian OR guardian has no students",
            400: "username and password are required",
        },
    )
    def post(self, request):
        in_ser = AuthLoginInputSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        username = in_ser.validated_data["username"]
        password = in_ser.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if not user or not user.is_active:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        guardian = getattr(user, "guardian", None)
        if not guardian:
            return Response({"detail": "This user is not linked to a guardian."}, status=status.HTTP_403_FORBIDDEN)

        # must have at least one student
        students_qs = guardian.students.all().order_by("last_name", "first_name")
        count = students_qs.count()
        if count == 0:
            return Response({"detail": "Guardian has no linked students."}, status=status.HTTP_403_FORBIDDEN)

        # auto-select first student if none selected
        if guardian.selected_student_id is None:
            first_student = students_qs.first()
            guardian.selected_student_id = first_student.id
            guardian.save(update_fields=["selected_student", "updated_at"])

        token, _ = Token.objects.get_or_create(user=user)

        out_payload = {
            "token": token.key,
            "guardian": GuardianSerializer(guardian).data,
            "selected_student": StudentOptionSerializer(
                guardian.selected_student, context={"selected_id": guardian.selected_student_id}
            ).data,
            "has_multiple_students": count > 1,
            "students_count": count,
        }
        out_ser = AuthLoginOutputSerializer(out_payload)
        return Response(out_ser.data, status=200)


class AuthLogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Logout (invalidate token)",
        responses={204: openapi.Response(description="No Content")},
    )
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# survey/api/auth_views.py - Add these to your existing auth_views.py

from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from core.models import Guardian
from .serializers import (
    RegistrationValidateCodeSerializer,
    RegistrationCompleteSerializer,
    RegistrationValidateCodeOutputSerializer,
    RegistrationCompleteOutputSerializer,
    StudentOptionSerializer,
    # GuardianMiniSerializer,
)

User = get_user_model()


class RegistrationValidateCodeView(APIView):
    """
    Validate registration code - Step 1 of registration
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="التحقق من كود التسجيل",
        operation_description="التحقق من صحة كود التسجيل وإرجاع معلومات الولي ورقم الهاتف",
        request_body=RegistrationValidateCodeSerializer,
        responses={
            200: RegistrationValidateCodeOutputSerializer,
            400: "Invalid code format or missing phone number",
            404: "Code not found or already used",
        },
    )
    def post(self, request):
        serializer = RegistrationValidateCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['code']

        try:
            guardian = Guardian.objects.get(code=code, user__isnull=True)

            # Check if guardian has phone number
            if not guardian.phone:
                return Response(
                    {'detail': 'لا يوجد رقم هاتف مسجل لهذا الولي. يرجى التواصل مع الإدارة'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            students_count = guardian.students.count()

            response_data = {
                'valid': True,
                'guardian_name': str(guardian),
                'phone': guardian.phone,  # Show the phone number to user
                'students_count': students_count
            }

            output_serializer = RegistrationValidateCodeOutputSerializer(response_data)
            return Response(output_serializer.data, status=status.HTTP_200_OK)

        except Guardian.DoesNotExist:
            return Response(
                {'detail': 'كود التسجيل غير صحيح أو مستخدم بالفعل'},
                status=status.HTTP_404_NOT_FOUND
            )


class RegistrationCompleteView(APIView):
    """
    Complete registration with phone and password - Step 2 of registration
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="إكمال التسجيل",
        operation_description="إكمال عملية التسجيل بإدخال كلمة المرور فقط (رقم الهاتف محفوظ مسبقاً)",
        request_body=RegistrationCompleteSerializer,
        responses={
            201: RegistrationCompleteOutputSerializer,
            400: "Validation errors or phone number already used",
            404: "Code not found or already used",
        },
    )
    def post(self, request):
        serializer = RegistrationCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()
        guardian = result['guardian']
        user = result['user']

        # Get guardian's students
        students_qs = guardian.students.all().order_by("last_name", "first_name")
        students_count = students_qs.count()

        # Auto-select first student if available
        selected_student = None
        if students_count > 0:
            first_student = students_qs.first()
            guardian.selected_student = first_student
            guardian.save(update_fields=['selected_student', 'updated_at'])
            selected_student = first_student

        # Create authentication token
        token, _ = Token.objects.get_or_create(user=user)

        response_data = {
            'success': True,
            'message': 'تم التسجيل بنجاح',
            'token': token.key,
            'guardian': guardian,
            'selected_student': selected_student,
            'has_multiple_students': students_count > 1,
            'students_count': students_count,
        }

        output_serializer = RegistrationCompleteOutputSerializer(response_data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


# Updated AuthLoginView with better phone number handling
class AuthLoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="تسجيل الدخول",
        operation_description="تسجيل دخول أولياء الأمور والموظفين باستخدام اسم المستخدم/رقم الهاتف وكلمة المرور",
        request_body=AuthLoginInputSerializer,
        responses={
            200: AuthLoginOutputSerializer,
            401: "Invalid credentials",
            403: "User missing guardian profile OR guardian has no students",
            400: "username and password are required",
        },
    )
    def post(self, request):
        serializer = AuthLoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]

        # Try authentication with the provided username (phone number or username)
        user = authenticate(request, username=username, password=password)

        if not user or not user.is_active:
            return Response(
                {"detail": "اسم المستخدم أو كلمة المرور غير صحيحة"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Build profile data using reusable function
        response_data = build_user_profile_data(user, include_token=True)

        # Check if user has valid profile
        if response_data is None or response_data["user_type"] is None:
            return Response(
                {"detail": "هذا المستخدم غير مرتبط بحساب ولي أمر أو موظف"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Additional check for guardians with no students
        if response_data["user_type"] == "guardian" and response_data["students_count"] == 0:
            return Response(
                {"detail": "لا يوجد طلاب مرتبطين بهذا الحساب"},
                status=status.HTTP_403_FORBIDDEN
            )

        output_serializer = AuthLoginOutputSerializer(response_data)
        return Response(output_serializer.data, status=status.HTTP_200_OK)