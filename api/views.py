# survey/api/views.py
from django.db.models import Max, Q
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, viewsets, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from survey.models import Template, Response as SurveyResponse
from core.models import GuardianStudent
from .permissions import IsGuardianUser, HasSelectedStudent
from .serializers import (
    TemplateListItemSerializer, TemplateDetailSerializer,
    ResponseListSerializer, ResponseDetailSerializer, ResponseCreateSerializer,
    SelectedStudentOutputSerializer, StudentOptionSerializer, StudentSelectInputSerializer
)
from .utils import is_available_now, get_or_select_student_fast


class TemplateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser, HasSelectedStudent]
    queryset = Template.objects.all().order_by("name", "id")

    def list(self, request, *args, **kwargs):
        guardian = request.user.guardian
        student  = guardian.selected_student   # guaranteed by permission
        qs = (Template.objects
              .all()
              .annotate(
                  last_response_at=Max(
                      "responses__created_at",
                      filter=Q(responses__guardian=guardian, responses__student=student)
                  )
              ))
        last_map = {t.id: t.last_response_at for t in qs}
        available = [t for t in qs if is_available_now(last_map.get(t.id), t.default_frequency)]
        page = self.paginate_queryset(available)
        ser = TemplateListItemSerializer(page or available, many=True, context={"last_map": last_map})
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)


    def retrieve(self, request, *args, **kwargs):
        template = self.get_object()
        ser = TemplateDetailSerializer(template)
        return Response(ser.data)


class ResponseViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser, HasSelectedStudent]
    queryset = (SurveyResponse.objects
                .all()
                .select_related("template", "guardian", "student")
                .order_by("-created_at", "-id"))


    def get_serializer_class(self):
        if self.action == "create":
            return ResponseCreateSerializer
        if self.action == "list":
            return ResponseListSerializer
        return ResponseDetailSerializer

    def list(self, request, *args, **kwargs):
        g = request.user.guardian
        s = g.selected_student
        qs = self.get_queryset().filter(guardian=g, student=s)
        page = self.paginate_queryset(qs)
        ser = ResponseListSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(ser.data)
        return Response(ser.data)

    def create(self, request, *args, **kwargs):
        g = request.user.guardian
        s = g.selected_student
        serializer = ResponseCreateSerializer(data=request.data, context={"request": request, "student": s})
        serializer.is_valid(raise_exception=True)
        resp = serializer.save()
        out = ResponseDetailSerializer(resp).data
        return Response(out, status=status.HTTP_201_CREATED)


class StudentsListView(APIView):
    """
    GET /api/students/ -> list my children with is_selected
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser]

    def get(self, request):
        g = request.user.guardian
        students = g.students.all().order_by("last_name", "first_name")
        ser = StudentOptionSerializer(students, many=True, context={"selected_id": g.selected_student_id})
        return Response(ser.data, status=200)


class StudentSetView(APIView):
    """
    POST /api/students/set/ { "student": <id> } -> set selected student
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser]

    @swagger_auto_schema(
        operation_summary="نحديد الطالب الحالي",
        request_body=StudentSelectInputSerializer,
        responses={
            200: StudentOptionSerializer(many=True),
        },
    )
    def post(self, request):
        g = request.user.guardian
        ser = StudentSelectInputSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        student = ser.validated_data["student"]

        g.selected_student_id = student.id
        g.save(update_fields=["selected_student", "updated_at"])

        # return the updated list (useful for UI)
        students = g.students.all().order_by("last_name", "first_name")
        out = StudentOptionSerializer(students, many=True, context={"selected_id": g.selected_student_id}).data
        return Response(out, status=status.HTTP_200_OK)


from rest_framework import viewsets
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from core.models import StudentTimeline, Student, GuardianStudent
from .serializers import StudentTimelineSerializer
from .filters import StudentTimelineFilter

class MyTimelineViewSet(viewsets.ModelViewSet):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGuardianUser]

    serializer_class = StudentTimelineSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = StudentTimelineFilter
    ordering_fields = ["created_at", "is_pinned", "id"]
    ordering = ["-is_pinned", "-created_at"]

    def _current_student(self):
        guardian = getattr(self.request.user, "guardian", None)
        student = getattr(guardian, "selected_student", None)
        if not guardian or not student:
            raise ValidationError("لا يوجد طالب محدّد لهذا المستخدم.")
        return student

    def get_queryset(self):
        student = self._current_student()
        return (
            StudentTimeline.objects
            .filter(student=student)
            .select_related("student", "created_by")
            .prefetch_related("attachments")
            .order_by("-is_pinned", "-created_at")
        )

    # create/update logic handled in serializer (uses current selected_student)


class SelectStudentView(APIView):
    """
    Helper endpoint to switch selected_student for the logged-in guardian.

      POST /api/me/selected-student/
      body: { "student_id": 123 }

    Returns: { "selected_student": 123 }
    """
    parser_classes = [JSONParser]

    def post(self, request):
        guardian = getattr(request.user, "guardian", None)
        if not guardian:
            raise ValidationError("لا يوجد ولي أمر مرتبط بهذا المستخدم.")
        student_id = request.data.get("student_id")
        if not student_id:
            raise ValidationError("student_id مطلوب.")
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            raise ValidationError("الطالب غير موجود.")

        # Ensure relation exists (light safety even though we're “forgetting permissions”)
        if not GuardianStudent.objects.filter(guardian=guardian, student=student).exists():
            raise ValidationError("الطالب غير مرتبط بولي الأمر الحالي.")

        guardian.selected_student = student
        guardian.save(update_fields=["selected_student"])
        return Response({"selected_student": student.id})

