from crispy_forms.utils import render_crispy_form
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction, models
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes, \
    parser_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from survey.forms import TemplateForm, TemplateFieldForm
from survey.models import Template, TemplateField, SurveyPeriod, SurveyDistribution
from survey.tables import TemplateTable
from survey.services import create_survey_distribution, get_survey_recipients, send_survey_notifications


@login_required
def template_target_selection(request, view=Template.FOOD):
    """
    View to select target audience for new survey template
    Shows 4 cards: Guardians, Teachers, Employees, All
    """
    if not request.user.has_perm('survey.add_template'):
        raise PermissionDenied()

    context = {
        "bar": {
            "main": False,
            "title": "إنشاء استطلاع جديد - اختر المتلقي",
            "back": reverse('dashboard:template_list'),
        },
        "targets": [
            {
                "key": Template.TARGET_GUARDIANS,
                "name": "أولياء الأمور",
                "icon": "bi bi-people-fill",
                "description": "استطلاع لأولياء أمور الطلاب",
                "color": "primary",
                "url": reverse('dashboard:template_add_with_target', kwargs={'target_audience': Template.TARGET_GUARDIANS})
            },
            {
                "key": Template.TARGET_TEACHERS,
                "name": "المعلمون",
                "icon": "bi bi-person-workspace",
                "description": "استطلاع للمعلمين في المدرسة",
                "color": "success",
                "url": reverse('dashboard:template_add_with_target', kwargs={'target_audience': Template.TARGET_TEACHERS})
            },
            {
                "key": Template.TARGET_EMPLOYEES,
                "name": "الموظفون",
                "icon": "bi bi-person-badge-fill",
                "description": "استطلاع للموظفين في المدرسة",
                "color": "info",
                "url": reverse('dashboard:template_add_with_target', kwargs={'target_audience': Template.TARGET_EMPLOYEES})
            },
            {
                "key": Template.TARGET_ALL,
                "name": "الجميع",
                "icon": "bi bi-globe",
                "description": "استطلاع لجميع المستخدمين",
                "color": "warning",
                "url": reverse('dashboard:template_add_with_target', kwargs={'target_audience': Template.TARGET_ALL})
            },
        ]
    }

    return render(request, 'survey/target_selection.html', context)


@login_required
# @permission_required('portal.sitecategory', raise_exception=True)
def template_list(request, view=Template.FOOD):
    school = getattr(request, 'school', None)

    # Filter templates based on user's school context
    if request.user.is_superuser:
        # Superuser sees all templates
        template = Template.objects.filter(type=view)
    elif school:
        # School users see templates for their school or global templates (school=None)
        template = Template.objects.filter(type=view).filter(
            models.Q(school=school) | models.Q(school__isnull=True)
        )
    else:
        # No school context - only show global templates
        template = Template.objects.filter(type=view, school__isnull=True)

    exclude = []
    if not request.user.has_perm("survey.change_template"):
        exclude.append("actions")

    # if view == Template.SURVEY:
    #     exclude.append("category")

    template_table = TemplateTable(template, exclude=exclude)

    context = {
        "table": template_table,
        "bar": {
            "main": True,
            "title": "نماذج استطلاعات الرأي",
            "count": {
                "label": "نموذج",
                "total": len(template_table.data)
            },
            "buttons": [
                {
                    "label": "إضافة استطلاع رأي",
                    "url": reverse('dashboard:template_target_selection')
                }
            ]
        }
    }

    return render(request, 'components/list.html', context)


@login_required
# @permission_required('portal.sitecategory', raise_exception=True)
def template_form(request, template_id=None, target_audience=None, view=Template.FOOD):
    if template_id and not request.user.has_perm('survey.change_template'):
        raise PermissionDenied()
    elif not template_id and not request.user.has_perm('survey.add_template'):
        raise PermissionDenied()

    school = getattr(request, 'school', None)
    template = get_object_or_404(Template, pk=template_id, type=view) if template_id else None

    # Check permission for editing templates from other schools
    if template and template.school and template.school != school and not request.user.is_superuser:
        raise PermissionDenied('ليس لديك صلاحية لتعديل هذا النموذج.')

    # Pass target_audience and school to the form
    form = TemplateForm(
        data=request.POST or None,
        instance=template,
        type=view,
        target_audience=target_audience,
        school=school
    )

    if request.method == "POST" and form.is_valid():
        x = form.save(commit=False)
        x.type = view

        if not template_id:
            x.created_by = request.user
            # If user has school context and is not superuser, assign school
            if school and not request.user.is_superuser:
                x.school = school
        else:
            x.updated_by = request.user

        x.save()

        # Save M2M relationships (grades)
        form.save_m2m()

        messages.success(request, "تم حفظ النموذج بنجاح")
        return redirect('dashboard:template_list')

    # Build title based on context
    if template_id:
        title = "تعديل نموذج"
    elif target_audience:
        target_name = dict(Template.TARGET_CHOICES).get(target_audience, "")
        title = f"إضافة استطلاع لـ {target_name}"
    else:
        title = "إضافة نموذج"

    context = {
        "form": form,
        "bar": {
            "title": title,
            "back": reverse('dashboard:template_target_selection') if not template_id else reverse('dashboard:template_list'),
        }
    }

    return render(request, 'components/crispy.html', context)


@login_required
# @permission_required('portal.sitecategory', raise_exception=True)
def template_detail(request, template_id, view=Template.FOOD):
    school = getattr(request, 'school', None)
    template = get_object_or_404(Template.objects.prefetch_related("fields"), pk=template_id)

    # Check permission for viewing templates from other schools
    if template.school and template.school != school and not request.user.is_superuser:
        raise PermissionDenied('ليس لديك صلاحية لعرض هذا النموذج.')

    form = TemplateFieldForm(data=request.POST or None, template=template)

    if request.method == "POST" and form.is_valid():

        x = form.save(commit=False)

        template.updated_by = request.user
        template.save()

        x.template = template
        x.created_by = request.user
        x.save()

        messages.success(request, "تم إضافة الحقل بنجاح")
        return redirect('dashboard:template_detail', template_id=template.id)

    map_obj = None

    context = {
        "map": map_obj,
        "form": form,
        "template": template,
        "fields": [(x, y) for x, y in zip(template.fields.all(), template.build_crispy_form(ticket=None))],
        "bar": {
            "title": f"نموذج {template.name}",
            "main": False,
            "back": reverse('dashboard:template_list'),
            # "buttons": [
            #     {
            #         "icon": "bi bi-pencil-square",
            #         "label": "تعديل النموذج",
            #         "url": reverse('dashboard:templates:template_edit', kwargs={"template_id": template_id})
            #     }
            # ]
        }
    }

    return render(request, 'template.html', context)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@throttle_classes([UserRateThrottle])
@parser_classes([JSONParser])
@transaction.atomic
# @permission_required(['survey.view_template', 'survey.change_template'], raise_exception=True)
def template_field_swap(request, template_id, view=Template.FOOD):
    template = get_object_or_404(Template, pk=template_id, type=view)
    field_1 = request.data.get("field1")
    field_2 = request.data.get("field2")

    if not field_1 or not field_2 or field_1 == field_2 or template.fields.filter(key__in=[field_1, field_2]).count() != 2:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    field_1 = template.fields.get(key=field_1)
    field_2 = template.fields.get(key=field_2)

    field_1.order, field_2.order = field_2.order, field_1.order
    field_1.updated_by = request.user
    field_2.updated_by = request.user
    template.updated_by = request.user
    field_1.save()
    field_2.save()
    template.save()

    return Response(status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication])
@throttle_classes([UserRateThrottle])
def template_html(request, template_id, view=Template.FOOD):
    template = get_object_or_404(Template, pk=template_id, type=view)
    csrf_token = get_token(request)
    form = template.build_crispy_form(columns=2)
    form = render_crispy_form(form, context={"form": form, "csrf_token": csrf_token})
    form = form.strip().replace("\n", "").replace("\r", "").replace("\t", "")

    return HttpResponse(form)

    # return Response(template.build_django_form())


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication])
@throttle_classes([UserRateThrottle])
@parser_classes([JSONParser])
@transaction.atomic
# @permission_required(['survey.view_template', 'survey.change_template'], raise_exception=True)
def template_field_delete(request, template_id, field_key, view=Template.FOOD):
    field = get_object_or_404(TemplateField.objects.select_related("template"), template_id=template_id, key=field_key, template__type=view)

    for f in field.template.fields.filter(order__gt=field.order):
        f.order -= 1
        f.save(update_fields=["order"])

    field.delete()
    field.template.updated_by = request.user
    field.template.save()

    return Response(status=status.HTTP_200_OK)


@login_required
@transaction.atomic
# @permission_required(['portal.sitecategory'], raise_exception=True)
def template_field_form(request, template_id, field_key, view=Template.FOOD):
    field = get_object_or_404(TemplateField.objects.select_related("template"), template_id=template_id, key=field_key, template__type=view)

    form = TemplateFieldForm(data=request.POST or None, template=field.template, instance=field)

    if request.method == "POST" and form.is_valid():
        x = form.save(commit=False)
        x.is_public = True
        x.updated_by = request.user
        field.template.updated_by = request.user
        x.save()
        field.template.save(update_fields=["updated_by", "updated_at"])


        messages.success(request, "تم تعديل الحقل بنجاح")

        return redirect('dashboard:template_detail', template_id=field.template.id)


    context = {
        "form": form,
        "template": field.template,
        "field": field,
        "includes": [
            {
                "template": 'widgets/choices.html',
            }
        ],
        "bar": {
            "title": f"تعديل حقل '{field.name}'"
        }
    }

    return render(request, 'components/crispy.html', context)


@login_required
def template_send(request, template_id, view=Template.FOOD):
    """
    Send a manual (once) survey to recipients
    """
    if not request.user.has_perm('survey.add_surveyperiod'):
        raise PermissionDenied()

    school = getattr(request, 'school', None)
    template = get_object_or_404(Template, pk=template_id, type=view)

    # Check permissions
    if template.school and template.school != school and not request.user.is_superuser:
        raise PermissionDenied('ليس لديك صلاحية لإرسال هذا الاستطلاع.')

    # Only allow sending for "once" frequency surveys
    if template.send_frequency != Template.FREQ_ONCE:
        messages.error(request, 'هذا الاستطلاع متكرر ويتم إرساله تلقائياً.')
        return redirect('dashboard:template_list')

    # Calculate recipient count for preview
    recipients = get_survey_recipients(template, school)
    recipient_count = len(recipients)

    if request.method == "POST":
        try:
            # Create period and distributions
            period, distributions = create_survey_distribution(
                survey=template,
                school=school,
                sent_by=request.user
            )

            # Send notifications
            send_survey_notifications(distributions)

            messages.success(
                request,
                f'تم إرسال الاستطلاع بنجاح إلى {len(distributions)} مستخدم'
            )
            return redirect('dashboard:template_periods', template_id=template.id)

        except Exception as e:
            messages.error(request, f'حدث خطأ أثناء إرسال الاستطلاع: {str(e)}')

    context = {
        "template": template,
        "recipient_count": recipient_count,
        "school": school,
        "bar": {
            "title": f"إرسال استطلاع: {template.name}",
            "back": reverse('dashboard:template_list'),
        }
    }

    return render(request, 'survey/template_send.html', context)


@login_required
def template_periods(request, template_id, view=Template.FOOD):
    """
    View all periods for a survey with statistics
    """
    school = getattr(request, 'school', None)
    template = get_object_or_404(Template, pk=template_id, type=view)

    # Check permissions
    if template.school and template.school != school and not request.user.is_superuser:
        raise PermissionDenied('ليس لديك صلاحية لعرض هذا الاستطلاع.')

    # Get all periods for this survey
    if request.user.is_superuser:
        periods = template.periods.all()
    elif school:
        periods = template.periods.filter(school=school)
    else:
        periods = template.periods.none()

    # Add statistics to each period
    period_stats = []
    for period in periods:
        stats = {
            'period': period,
            'total': period.distributions.count(),
            'completed': period.distributions.filter(is_completed=True).count(),
            'pending': period.distributions.filter(is_completed=False).count(),
            'completion_rate': period.completion_rate,
        }
        period_stats.append(stats)

    context = {
        "template": template,
        "period_stats": period_stats,
        "bar": {
            "title": f"فترات استطلاع: {template.name}",
            "back": reverse('dashboard:template_list'),
        }
    }

    return render(request, 'survey/template_periods.html', context)


@login_required
def period_detail(request, period_id):
    """
    View detailed distributions for a specific period
    """
    school = getattr(request, 'school', None)
    period = get_object_or_404(SurveyPeriod, pk=period_id)

    # Check permissions
    if period.school and period.school != school and not request.user.is_superuser:
        raise PermissionDenied('ليس لديك صلاحية لعرض هذه الفترة.')

    # Get all distributions for this period
    distributions = period.distributions.select_related('user', 'student', 'response').all()

    # Filter completed and pending
    completed_distributions = distributions.filter(is_completed=True)
    pending_distributions = distributions.filter(is_completed=False)

    context = {
        "period": period,
        "distributions": distributions,
        "completed_distributions": completed_distributions,
        "pending_distributions": pending_distributions,
        "stats": {
            'total': distributions.count(),
            'completed': completed_distributions.count(),
            'pending': pending_distributions.count(),
            'completion_rate': period.completion_rate,
        },
        "bar": {
            "title": f"تفاصيل فترة: {period.survey.name}",
            "back": reverse('dashboard:template_periods', kwargs={'template_id': period.survey.id}),
        }
    }

    return render(request, 'survey/period_detail.html', context)