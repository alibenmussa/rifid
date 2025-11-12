from django.conf import settings
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .auth_views import (
    AuthLoginView, AuthLogoutView, RegistrationValidateCodeView, 
    RegistrationCompleteView, UpdateFCMTokenView
)
from .views import (
    TemplateViewSet, ResponseViewSet, SurveyDistributionViewSet,
    StudentsListView, StudentSetView, MyTimelineViewSet,
    ProfileView, EmployeeStudentsViewSet, EmployeeTimelineViewSet
)

schema_view = get_schema_view(
    openapi.Info(
        title="Rifid APIs",
        default_version='v1',
        description="A collection of APIs for Rifid",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@snippets.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    # permission_classes=(permissions.AllowAny,),
)


router = DefaultRouter()
router.register(r"surveys", TemplateViewSet, basename="surveys")
router.register(r"responses", ResponseViewSet, basename="responses")
router.register(r"distributions", SurveyDistributionViewSet, basename="distributions")

# Guardian endpoints
router.register(r"timeline", MyTimelineViewSet, basename="my-timeline")

# Employee endpoints
router.register(r"employee/students", EmployeeStudentsViewSet, basename="api_employee_students")
# Note: employee timeline is registered with nested URL pattern below (not here)

urlpatterns = [
    path("", include(router.urls)),

    # Employee timeline endpoints - nested under students
    path(
        "employee/students/<int:student_id>/timeline/",
        EmployeeTimelineViewSet.as_view({'get': 'list', 'post': 'create'}),
        name="api_employee_timeline-list"
    ),
    path(
        "employee/students/<int:student_id>/timeline/<int:pk>/",
        EmployeeTimelineViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }),
        name="api_employee_timeline-detail"
    ),
    path(
        "employee/students/<int:student_id>/timeline/<int:pk>/add_attachment/",
        EmployeeTimelineViewSet.as_view({'post': 'add_attachment'}),
        name="api_employee_timeline_add_attachment"
    ),
    path(
        "employee/students/<int:student_id>/timeline/<int:pk>/attachments/",
        EmployeeTimelineViewSet.as_view({'get': 'attachments'}),
        name="api_employee_timeline_attachments"
    ),
    path(
        "employee/students/<int:student_id>/timeline/<int:pk>/attachments/<int:attachment_id>/",
        EmployeeTimelineViewSet.as_view({'delete': 'delete_attachment'}),
        name="api_employee_timeline_delete_attachment"
    ),

    # Profile endpoint (for both Guardian and Employee)
    path("profile/", ProfileView.as_view(), name="profile"),

    # Guardian student management
    path("students/", StudentsListView.as_view(), name="students-list"),
    path("students/set/", StudentSetView.as_view(), name="students-set"),

    # Authentication
    path("auth/login/", AuthLoginView.as_view(), name="auth-login"),
    path("auth/logout/", AuthLogoutView.as_view(), name="auth-logout"),
    path('auth/register/validate-code/', RegistrationValidateCodeView.as_view(), name='register_validate_code'),
    path('auth/register/complete/', RegistrationCompleteView.as_view(), name='register_complete'),
    path('auth/update-fcm-token/', UpdateFCMTokenView.as_view(), name='update-fcm-token'),
]

if settings.DEBUG:
    urlpatterns += [
        path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
        path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    ]
