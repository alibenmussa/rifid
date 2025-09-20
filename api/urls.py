from django.conf import settings
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .auth_views import AuthLoginView, AuthLogoutView, RegistrationValidateCodeView, RegistrationCompleteView
from .views import TemplateViewSet, ResponseViewSet, StudentsListView, StudentSetView, MyTimelineViewSet

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
router.register(r"timeline", MyTimelineViewSet, basename="my-timeline"),

urlpatterns = [
    path("", include(router.urls)),
    path("students/", StudentsListView.as_view(), name="students-list"),
    path("students/set/", StudentSetView.as_view(), name="students-set"),  # ← your preferred path



    path("auth/login/", AuthLoginView.as_view(), name="auth-login"),
    path("auth/logout/", AuthLogoutView.as_view(), name="auth-logout"),

    path('auth/register/validate-code/', RegistrationValidateCodeView.as_view(), name='register_validate_code'),
    path('auth/register/complete/', RegistrationCompleteView.as_view(), name='register_complete'),

]

if settings.DEBUG:
    urlpatterns += [
        path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
        path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    ]
