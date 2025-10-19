# api/views.py - Enhanced API views with school structure
from django.db.models import Max, Q, Count, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import mixins, viewsets, status, filters
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from survey.models import Template, Response as SurveyResponse
from core.models import (
    School, AcademicYear, Grade, SchoolClass,
    Guardian, Student, GuardianStudent,
    StudentTimeline
)
from .filters import StudentTimelineFilter, StudentFilter
from .permissions import IsGuardianUser, HasSelectedStudent, IsSchoolMember, IsEmployeeUser
from .serializers import (
    # School structure serializers
    SchoolBasicSerializer, AcademicYearSerializer, GradeSerializer, SchoolClassSerializer,

    # User serializers
    GuardianSerializer, StudentSerializer, StudentBasicSerializer,

    # Student selection serializers
    StudentOptionSerializer, StudentSelectInputSerializer, SelectedStudentOutputSerializer,

    # Timeline serializers
    StudentTimelineAttachmentSerializer, StudentTimelineListSerializer, StudentTimelineDetailSerializer,
    StudentTimelineCreateSerializer, StudentTimelineUpdateSerializer,

    # Survey serializers
    TemplateListItemSerializer, TemplateDetailSerializer,
    ResponseListSerializer, ResponseDetailSerializer, ResponseCreateSerializer,

    # Auth serializers
    AuthLoginInputSerializer, AuthLoginOutputSerializer,
    RegistrationValidateCodeSerializer, RegistrationValidateCodeOutputSerializer,
    RegistrationCompleteSerializer, RegistrationCompleteOutputSerializer,
    ProfileOutputSerializer,

    # Employee and Profile serializers
    ProfileSerializer, EmployeeProfileSerializer, StudentListSerializerForEmployee,
)
from .utils import is_available_now, get_or_select_student_fast


# ==========================================
# SCHOOL STRUCTURE VIEWSETS
# ==========================================

class SchoolInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """School information for authenticated users"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsSchoolMember]
    serializer_class = SchoolBasicSerializer

    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return School.objects.none()

        if not self.request.user.is_authenticated:
            return School.objects.none()

        user = self.request.user
        if hasattr(user, 'guardian'):
            return School.objects.filter(id=user.guardian.school_id)
        elif hasattr(user, 'teacher_profile'):
            return School.objects.filter(id=user.teacher_profile.school_id)
        return School.objects.none()


class GradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Grades within user's school"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsSchoolMember]
    serializer_class = GradeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grade_type', 'is_active']
    ordering_fields = ['level', 'name']
    ordering = ['grade_type', 'level']

    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Grade.objects.none()

        if not self.request.user.is_authenticated:
            return Grade.objects.none()

        user = self.request.user
        school = None

        if hasattr(user, 'guardian'):
            school = user.guardian.school
        elif hasattr(user, 'teacher_profile'):
            school = user.teacher_profile.school

        if school:
            return Grade.objects.filter(school=school).prefetch_related('classes')
        return Grade.objects.none()


class SchoolClassViewSet(viewsets.ReadOnlyModelViewSet):
    """School classes within user's school"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsSchoolMember]
    serializer_class = SchoolClassSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['grade', 'academic_year', 'is_active']
    ordering_fields = ['grade__level', 'name']
    ordering = ['grade__level', 'name']

    def get_queryset(self):
        user = self.request.user
        school = None

        if hasattr(user, 'guardian'):
            school = user.guardian.school
        elif hasattr(user, 'teacher_profile'):
            school = user.teacher_profile.school

        if school:
            return SchoolClass.objects.filter(school=school).select_related(
                'grade', 'academic_year', 'class_teacher'
            ).annotate(
                student_count=Count('students', filter=Q(students__is_active=True))
            )
        return SchoolClass.objects.none()


# ==========================================
# ENHANCED SURVEY VIEWSETS
# ==========================================

class TemplateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Survey templates available to guardians"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser, HasSelectedStudent]

    def get_queryset(self):
        # Check if this is being called during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Template.objects.none()

        # Check if user is authenticated
        if not self.request.user.is_authenticated:
            return Template.objects.none()

        guardian = getattr(self.request.user, 'guardian', None)
        if not guardian:
            return Template.objects.none()

        school = guardian.school

        # Filter templates: either specific to this school or global (school=None)
        return Template.objects.filter(
            Q(school=school) | Q(school__isnull=True)
        ).order_by("name", "id")

    @swagger_auto_schema(
        operation_summary="قائمة الاستبيانات المتاحة",
        responses={200: TemplateListItemSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        guardian = request.user.guardian
        student = guardian.selected_student
        school = guardian.school

        # Get templates with last response dates (filtered by school)
        qs = (Template.objects
        .filter(Q(school=school) | Q(school__isnull=True))
        .annotate(
            last_response_at=Max(
                "responses__created_at",
                filter=Q(
                    responses__guardian=guardian,
                    responses__student=student
                )
            )
        ))

        # Create last response map
        last_map = {t.id: t.last_response_at for t in qs}

        # Filter available templates
        available = [
            t for t in qs
            if is_available_now(last_map.get(t.id), t.default_frequency)
        ]

        page = self.paginate_queryset(available)
        serializer = TemplateListItemSerializer(
            page or available,
            many=True,
            context={"last_map": last_map}
        )

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="تفاصيل الاستبيان",
        responses={200: TemplateDetailSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        template = self.get_object()
        serializer = TemplateDetailSerializer(template)
        return Response(serializer.data)


class ResponseViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                      mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Survey responses for guardians"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser, HasSelectedStudent]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['template', 'created_at']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        # Check if this is being called during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return SurveyResponse.objects.none()

        # Check if user is authenticated
        if not self.request.user.is_authenticated:
            return SurveyResponse.objects.none()

        # Check if user has guardian profile
        if not hasattr(self.request.user, 'guardian'):
            return SurveyResponse.objects.none()

        guardian = self.request.user.guardian
        student = guardian.selected_student

        if not student:
            return SurveyResponse.objects.none()

        return (SurveyResponse.objects
                .filter(guardian=guardian, student=student)
                .select_related("template", "guardian", "student")
                .prefetch_related("fields__field")
                .order_by("-created_at", "-id"))

    def get_serializer_class(self):
        if self.action == "create":
            return ResponseCreateSerializer
        elif self.action == "list":
            return ResponseListSerializer
        return ResponseDetailSerializer

    @swagger_auto_schema(
        operation_summary="قائمة إجابات الاستبيانات",
        responses={200: ResponseListSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = ResponseListSerializer(page or queryset, many=True)

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="إنشاء إجابة استبيان جديدة",
        request_body=ResponseCreateSerializer,
        responses={
            201: ResponseDetailSerializer,
            400: "خطأ في البيانات",
            403: "الاستبيان غير متاح حالياً"
        }
    )
    def create(self, request, *args, **kwargs):
        guardian = request.user.guardian
        student = guardian.selected_student

        serializer = ResponseCreateSerializer(
            data=request.data,
            context={"request": request, "student": student}
        )
        serializer.is_valid(raise_exception=True)

        response = serializer.save()
        output_data = ResponseDetailSerializer(response).data

        return Response(output_data, status=status.HTTP_201_CREATED)


# ==========================================
# ENHANCED STUDENT MANAGEMENT
# ==========================================

class StudentsListView(APIView):
    """List guardian's children with selection status"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser]

    @swagger_auto_schema(
        operation_summary="قائمة أطفال ولي الأمر",
        responses={200: StudentOptionSerializer(many=True)}
    )
    def get(self, request):
        guardian = request.user.guardian
        students = guardian.students.filter(is_active=True).select_related(
            'current_class', 'current_class__grade'
        ).order_by("last_name", "first_name")

        serializer = StudentOptionSerializer(
            students,
            many=True,
            context={"selected_id": guardian.selected_student_id}
        )
        return Response(serializer.data, status=200)


class StudentSetView(APIView):
    """Set guardian's selected student"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser]

    @swagger_auto_schema(
        operation_summary="اختيار الطالب النشط",
        request_body=StudentSelectInputSerializer,
        responses={
            200: StudentOptionSerializer(many=True),
            400: "خطأ في البيانات"
        }
    )
    def post(self, request):
        guardian = request.user.guardian
        serializer = StudentSelectInputSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        student = serializer.validated_data["student"]

        # Update selected student
        guardian.selected_student = student
        guardian.save(update_fields=["selected_student", "updated_at"])

        # Return updated list
        students = guardian.students.filter(is_active=True).select_related(
            'current_class'
        ).order_by("last_name", "first_name")

        output_serializer = StudentOptionSerializer(
            students,
            many=True,
            context={"selected_id": guardian.selected_student_id}
        )

        return Response(output_serializer.data, status=status.HTTP_200_OK)


class StudentDetailView(APIView):
    """Get detailed information about selected student"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser, HasSelectedStudent]

    @swagger_auto_schema(
        operation_summary="تفاصيل الطالب المختار",
        responses={200: StudentSerializer}
    )
    def get(self, request):
        guardian = request.user.guardian
        student = guardian.selected_student

        serializer = StudentSerializer(student, context={'request': request})
        return Response(serializer.data)


# ==========================================
# ENHANCED TIMELINE VIEWSET
# ==========================================

class MyTimelineViewSet(viewsets.ReadOnlyModelViewSet):
    """Student timeline view for guardians (read-only)"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = StudentTimelineFilter
    ordering_fields = ["created_at", "is_pinned", "id"]
    ordering = ["-is_pinned", "-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer for each action"""
        if self.action == 'list':
            return StudentTimelineListSerializer
        return StudentTimelineDetailSerializer

    def _current_student(self):
        """Get current selected student"""
        # Check if this is being called during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return None

        # Check if user is authenticated
        if not self.request.user.is_authenticated:
            raise ValidationError("المستخدم غير مسجل دخول.")

        guardian = getattr(self.request.user, "guardian", None)
        student = getattr(guardian, "selected_student", None)

        if not guardian or not student:
            raise ValidationError("لا يوجد طالب محدّد لهذا المستخدم.")
        return student

    def get_queryset(self):
        # Check if this is being called during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return StudentTimeline.objects.none()

        # Check if user is authenticated
        if not self.request.user.is_authenticated:
            return StudentTimeline.objects.none()

        # Check if user has guardian profile
        if not hasattr(self.request.user, 'guardian'):
            return StudentTimeline.objects.none()

        try:
            student = self._current_student()
        except ValidationError:
            return StudentTimeline.objects.none()

        if not student:
            return StudentTimeline.objects.none()

        return (
            StudentTimeline.objects
            .filter(student=student, is_visible_to_guardian=True)
            .select_related("student", "created_by")
            .prefetch_related("attachments")
            .order_by("-is_pinned", "-created_at")
        )

    @swagger_auto_schema(
        operation_summary="قائمة منشورات الطالب (ولي الأمر - قراءة فقط)",
        responses={200: StudentTimelineListSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        """Get timeline entries with content_type choices"""
        response = super().list(request, *args, **kwargs)

        # Add content_type choices to response
        response.data = {
            'results': response.data if not isinstance(response.data, dict) else response.data.get('results', []),
            'content_type_choices': [
                {'value': choice[0], 'label': choice[1]}
                for choice in StudentTimeline.CONTENT_TYPES
            ]
        }

        # Add pagination info if paginated
        if isinstance(self.paginator, type(None)) is False:
            paginated = self.paginate_queryset(self.get_queryset())
            if paginated is not None:
                response.data['count'] = self.paginator.page.paginator.count
                response.data['next'] = self.paginator.get_next_link()
                response.data['previous'] = self.paginator.get_previous_link()

        return response

    @swagger_auto_schema(
        operation_summary="تفاصيل منشور",
        responses={200: StudentTimelineDetailSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get timeline statistics for current student"""
        student = self._current_student()

        queryset = self.get_queryset()
        total_count = queryset.count()
        pinned_count = queryset.filter(is_pinned=True).count()

        # Count by content type
        content_types = queryset.values('content_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Recent activity (last 7 days)
        week_ago = timezone.now() - timezone.timedelta(days=7)
        recent_count = queryset.filter(created_at__gte=week_ago).count()

        return Response({
            'total_posts': total_count,
            'pinned_posts': pinned_count,
            'recent_posts': recent_count,
            'content_types': list(content_types),
            'student_name': student.full_name
        })


# ==========================================
# AUTHENTICATION VIEWS
# ==========================================

class AuthLoginView(APIView):
    """Enhanced login with school context"""
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="تسجيل دخول أولياء الأمور",
        operation_description="تسجيل دخول باستخدام رقم الهاتف وكلمة المرور",
        request_body=AuthLoginInputSerializer,
        responses={
            200: AuthLoginOutputSerializer,
            401: "بيانات دخول غير صحيحة",
            403: "حساب غير مرتبط بولي أمر أو لا يوجد أطفال",
        }
    )
    def post(self, request):
        from django.contrib.auth import authenticate
        from rest_framework.authtoken.models import Token

        serializer = AuthLoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]

        # Authenticate user
        user = authenticate(request, username=username, password=password)
        if not user or not user.is_active:
            return Response(
                {"detail": "رقم الهاتف أو كلمة المرور غير صحيحة"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check guardian profile
        try:
            guardian = user.guardian
        except Guardian.DoesNotExist:
            return Response(
                {"detail": "هذا المستخدم غير مرتبط بحساب ولي أمر"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check students
        students_qs = guardian.students.filter(is_active=True).select_related(
            'current_class'
        ).order_by("last_name", "first_name")
        students_count = students_qs.count()

        if students_count == 0:
            return Response(
                {"detail": "لا يوجد أطفال نشطون مرتبطين بهذا الحساب"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Auto-select first student if none selected
        if guardian.selected_student_id is None:
            first_student = students_qs.first()
            guardian.selected_student = first_student
            guardian.save(update_fields=["selected_student", "updated_at"])

        # Create/get token
        token, _ = Token.objects.get_or_create(user=user)

        # Prepare response
        response_data = {
            "token": token.key,
            "guardian": GuardianSerializer(guardian, context={'request': request}).data,
            "selected_student": StudentOptionSerializer(
                guardian.selected_student,
                context={"selected_id": guardian.selected_student_id}
            ).data if guardian.selected_student else None,
            "has_multiple_students": students_count > 1,
            "students_count": students_count,
            "school_info": SchoolBasicSerializer(guardian.school).data
        }

        output_serializer = AuthLoginOutputSerializer(response_data)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class AuthLogoutView(APIView):
    """Logout and invalidate token"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="تسجيل الخروج",
        responses={204: "تم تسجيل الخروج بنجاح"}
    )
    def post(self, request):
        from rest_framework.authtoken.models import Token

        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegistrationValidateCodeView(APIView):
    """Validate registration code - Step 1"""
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="التحقق من كود التسجيل",
        operation_description="التحقق من صحة كود التسجيل وإرجاع معلومات ولي الأمر",
        request_body=RegistrationValidateCodeSerializer,
        responses={
            200: RegistrationValidateCodeOutputSerializer,
            400: "كود غير صحيح أو مفقود رقم الهاتف",
            404: "كود غير موجود أو مستخدم بالفعل",
        }
    )
    def post(self, request):
        serializer = RegistrationValidateCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['code']

        try:
            guardian = Guardian.objects.select_related('school').get(
                code=code, user__isnull=True
            )

            if not guardian.phone:
                return Response(
                    {'detail': 'لا يوجد رقم هاتف مسجل لهذا الولي. يرجى التواصل مع الإدارة'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            students_count = guardian.students.filter(is_active=True).count()

            response_data = {
                'valid': True,
                'guardian_name': str(guardian),
                'phone': guardian.phone,
                'students_count': students_count,
                'school_name': guardian.school.name
            }

            output_serializer = RegistrationValidateCodeOutputSerializer(response_data)
            return Response(output_serializer.data, status=status.HTTP_200_OK)

        except Guardian.DoesNotExist:
            return Response(
                {'detail': 'كود التسجيل غير صحيح أو مستخدم بالفعل'},
                status=status.HTTP_404_NOT_FOUND
            )


class RegistrationCompleteView(APIView):
    """Complete registration with password - Step 2"""
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="إكمال التسجيل",
        operation_description="إكمال عملية التسجيل بإدخال كلمة المرور",
        request_body=RegistrationCompleteSerializer,
        responses={
            201: RegistrationCompleteOutputSerializer,
            400: "خطأ في التحقق أو رقم الهاتف مستخدم",
        }
    )
    def post(self, request):
        from rest_framework.authtoken.models import Token

        serializer = RegistrationCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = serializer.save()
            guardian = result['guardian']
            user = result['user']

            # Get guardian's students
            students_qs = guardian.students.filter(is_active=True).select_related(
                'current_class'
            ).order_by("last_name", "first_name")
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
                'guardian': GuardianSerializer(guardian, context={'request': request}).data,
                'selected_student': StudentOptionSerializer(
                    selected_student,
                    context={'selected_id': selected_student.id if selected_student else None}
                ).data if selected_student else None,
                'has_multiple_students': students_count > 1,
                'students_count': students_count,
                'school_info': SchoolBasicSerializer(guardian.school).data
            }

            output_serializer = RegistrationCompleteOutputSerializer(response_data)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'detail': 'حدث خطأ أثناء التسجيل'},
                status=status.HTTP_400_BAD_REQUEST
            )


# ==========================================
# UTILITY VIEWS
# ==========================================

class SelectStudentView(APIView):
    """Helper endpoint to switch selected student"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser]
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_summary="تغيير الطالب المختار",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['student_id'],
            properties={
                'student_id': openapi.Schema(type=openapi.TYPE_INTEGER)
            }
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'selected_student': openapi.Schema(type=openapi.TYPE_INTEGER)
                }
            )
        }
    )
    def post(self, request):
        guardian = getattr(request.user, "guardian", None)
        if not guardian:
            raise ValidationError("لا يوجد ولي أمر مرتبط بهذا المستخدم.")

        student_id = request.data.get("student_id")
        if not student_id:
            raise ValidationError("student_id مطلوب.")

        try:
            student = Student.objects.get(pk=student_id, is_active=True)
        except Student.DoesNotExist:
            raise ValidationError("الطالب غير موجود أو غير نشط.")

        # Ensure student belongs to same school
        if student.school_id != guardian.school_id:
            raise ValidationError("الطالب لا ينتمي لنفس المدرسة.")

        # Ensure guardian-student relationship exists
        if not GuardianStudent.objects.filter(guardian=guardian, student=student).exists():
            raise ValidationError("الطالب غير مرتبط بولي الأمر الحالي.")

        guardian.selected_student = student
        guardian.save(update_fields=["selected_student", "updated_at"])

        return Response({"selected_student": student.id})


class SchoolStatsView(APIView):
    """School statistics for dashboards"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsSchoolMember]

    @swagger_auto_schema(
        operation_summary="إحصائيات المدرسة",
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'total_students': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'total_guardians': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'total_classes': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'total_grades': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'school_info': SchoolBasicSerializer()
                }
            )
        }
    )
    def get(self, request):
        user = request.user
        school = None

        if hasattr(user, 'guardian'):
            school = user.guardian.school
        elif hasattr(user, 'teacher_profile'):
            school = user.teacher_profile.school

        if not school:
            return Response(
                {'detail': 'لا يمكن تحديد المدرسة للمستخدم'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get statistics
        stats = {
            'total_students': school.students.filter(is_active=True).count(),
            'total_guardians': school.guardians.count(),
            'total_classes': school.classes.filter(is_active=True).count(),
            'total_grades': school.grades.filter(is_active=True).count(),
            'school_info': SchoolBasicSerializer(school).data
        }

        # Add grade breakdown
        grade_stats = (
            school.grades.filter(is_active=True)
            .annotate(student_count=Count('classes__students', filter=Q(classes__students__is_active=True)))
            .values('name', 'grade_type', 'student_count')
            .order_by('grade_type', 'level')
        )
        stats['grade_breakdown'] = list(grade_stats)

        return Response(stats)


# ==========================================
# PROFILE AND EMPLOYEE VIEWS
# ==========================================

class ProfileView(APIView):
    """Get user profile (Employee/Teacher/Guardian)"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="الملف الشخصي للمستخدم",
        operation_description="الحصول على معلومات الملف الشخصي لجميع أنواع المستخدمين (موظف/معلم/ولي أمر)",
        responses={
            200: ProfileOutputSerializer,
            403: "User has no profile"
        }
    )
    def get(self, request):
        from api.auth_views import build_user_profile_data

        user = request.user

        # Build profile data using reusable function (without token)
        response_data = build_user_profile_data(user, include_token=False)

        # Check if user has valid profile
        if response_data is None or response_data["user_type"] is None:
            return Response(
                {"detail": "هذا المستخدم غير مرتبط بأي حساب"},
                status=status.HTTP_403_FORBIDDEN
            )

        output_serializer = ProfileOutputSerializer(response_data)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class EmployeeStudentsViewSet(viewsets.ReadOnlyModelViewSet):
    """Students list for Employee users"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsEmployeeUser]
    serializer_class = StudentListSerializerForEmployee
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = StudentFilter
    ordering_fields = ['student_id', 'full_name', 'date_of_birth', 'created_at']
    ordering = ['full_name']
    search_fields = ['student_id', 'full_name', 'first_name', 'last_name', 'phone']

    def get_queryset(self):
        """Return students from employee's school"""
        if getattr(self, 'swagger_fake_view', False):
            return Student.objects.none()

        if not self.request.user.is_authenticated:
            return Student.objects.none()

        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            return Student.objects.none()

        school = employee.school

        return (
            Student.objects
            .filter(school=school, is_active=True)
            .select_related('current_class', 'current_class__grade', 'school')
            .prefetch_related('guardians')
            .order_by('full_name')
        )

    @swagger_auto_schema(
        operation_summary="قائمة الطلاب للموظف",
        responses={200: StudentListSerializerForEmployee(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="تفاصيل طالب",
        responses={200: StudentSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        """Get full student details"""
        instance = self.get_object()
        serializer = StudentSerializer(instance, context={'request': request})
        return Response(serializer.data)


class EmployeeTimelineViewSet(viewsets.ModelViewSet):
    """Timeline management for Employee users"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsEmployeeUser]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = StudentTimelineFilter
    ordering_fields = ["created_at", "is_pinned", "id"]
    ordering = ["-is_pinned", "-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer for each action"""
        if self.action == 'list':
            return StudentTimelineListSerializer
        elif self.action == 'retrieve':
            return StudentTimelineDetailSerializer
        elif self.action == 'create':
            return StudentTimelineCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return StudentTimelineUpdateSerializer
        return StudentTimelineDetailSerializer

    def get_queryset(self):
        """Return timeline entries from employee's school"""
        if getattr(self, 'swagger_fake_view', False):
            return StudentTimeline.objects.none()

        if not self.request.user.is_authenticated:
            return StudentTimeline.objects.none()

        employee = getattr(self.request.user, 'employee_profile', None)
        if not employee:
            return StudentTimeline.objects.none()

        school = employee.school

        # Get student_id from query params for filtering
        student_id = self.request.query_params.get('student_id')

        queryset = StudentTimeline.objects.filter(student__school=school)

        if student_id:
            queryset = queryset.filter(student_id=student_id)

        return (
            queryset
            .select_related("student", "created_by")
            .prefetch_related("attachments")
            .order_by("-is_pinned", "-created_at")
        )

    def create(self, request, *args, **kwargs):
        """Override create to set student from request data"""
        # Get student_id from request data
        student_id = request.data.get('student_id')
        if not student_id:
            return Response(
                {'detail': 'يجب تحديد student_id للطالب.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify student belongs to employee's school
        employee = request.user.employee_profile
        try:
            student = Student.objects.get(id=student_id, school=employee.school)
        except Student.DoesNotExist:
            return Response(
                {'detail': 'الطالب غير موجود أو لا ينتمي لمدرستك.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Create serializer with modified context
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Override context to use specific student instead of selected_student
        serializer.context['student'] = student

        # Save the timeline entry
        timeline = serializer.save()

        # Return detailed serializer
        output_serializer = StudentTimelineDetailSerializer(timeline, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="قائمة المنشورات (موظف)",
        responses={200: StudentTimelineListSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="تفاصيل منشور",
        responses={200: StudentTimelineDetailSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="تعديل منشور (موظف)",
        request_body=StudentTimelineUpdateSerializer,
        responses={
            200: StudentTimelineDetailSerializer,
            400: "خطأ في البيانات"
        }
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="تعديل جزئي لمنشور (موظف)",
        request_body=StudentTimelineUpdateSerializer,
        responses={
            200: StudentTimelineDetailSerializer,
            400: "خطأ في البيانات"
        }
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="حذف منشور (موظف)",
        responses={204: "تم الحذف بنجاح"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="إضافة مرفق لمنشور",
        manual_parameters=[
            openapi.Parameter('file', openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description='الملف المراد رفعه')
        ],
        responses={
            201: StudentTimelineAttachmentSerializer,
            400: "خطأ في البيانات"
        }
    )
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def add_attachment(self, request, pk=None):
        """Add attachment to timeline entry"""
        timeline = self.get_object()
        file_obj = request.FILES.get('file')

        if not file_obj:
            return Response(
                {'detail': 'يجب رفع ملف.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create attachment
        attachment = StudentTimelineAttachment.objects.create(
            timeline=timeline,
            file=file_obj
        )

        serializer = StudentTimelineAttachmentSerializer(attachment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="قائمة مرفقات منشور",
        responses={200: StudentTimelineAttachmentSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def attachments(self, request, pk=None):
        """List all attachments for a timeline entry"""
        timeline = self.get_object()
        attachments = timeline.attachments.all()
        serializer = StudentTimelineAttachmentSerializer(attachments, many=True, context={'request': request})
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="حذف مرفق من منشور",
        responses={204: "تم الحذف بنجاح"}
    )
    @action(detail=True, methods=['delete'], url_path='attachments/(?P<attachment_id>[^/.]+)')
    def delete_attachment(self, request, pk=None, attachment_id=None):
        """Delete specific attachment"""
        timeline = self.get_object()

        try:
            attachment = timeline.attachments.get(id=attachment_id)
            attachment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except StudentTimelineAttachment.DoesNotExist:
            return Response(
                {'detail': 'المرفق غير موجود.'},
                status=status.HTTP_404_NOT_FOUND
            )


# ==========================================
# ERROR HANDLERS
# ==========================================

class APIErrorView(APIView):
    """Custom error handler for API endpoints"""

    def handle_exception(self, exc):
        """Custom exception handling"""
        if isinstance(exc, ValidationError):
            return Response(
                {'detail': str(exc), 'code': 'validation_error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif isinstance(exc, PermissionDenied):
            return Response(
                {'detail': str(exc), 'code': 'permission_denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().handle_exception(exc)