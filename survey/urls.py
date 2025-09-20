from django.urls import path
from survey import views


# app_name = 'survey'

urlpatterns = [
    path('', views.template_list, name='template_list'),
    path('add/', views.template_form, name='template_add'),
    path('<int:template_id>/', views.template_detail, name='template_detail'),
    path('<int:template_id>/html/', views.template_html, name='template_html'),
    path('edit/<int:template_id>/', views.template_form, name='template_edit'),
    path('<int:template_id>/swap/', views.template_field_swap, name='template_field_swap'),
    path('<int:template_id>/field/<str:field_key>/edit/', views.template_field_form, name='template_field_edit'),
    path('<int:template_id>/field/<str:field_key>/delete/', views.template_field_delete, name='template_field_delete'),
]

