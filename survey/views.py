from crispy_forms.utils import render_crispy_form
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
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
from survey.models import Template, TemplateField
from survey.tables import TemplateTable


@login_required
# @permission_required('portal.sitecategory', raise_exception=True)
def template_list(request, view=Template.FOOD):
    template = Template.objects.filter(type=view)
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
                    "url": reverse('dashboard:template_add')
                }
            ]
        }
    }

    return render(request, 'components/list.html', context)


@login_required
# @permission_required('portal.sitecategory', raise_exception=True)
def template_form(request, template_id=None, view=Template.FOOD):
    if template_id and not request.user.has_perm('survey.change_template'):
        raise PermissionDenied()
    elif not template_id and not request.user.has_perm('survey.add_template'):
        raise PermissionDenied()

    template = get_object_or_404(Template, pk=template_id, type=view) if template_id else None

    form = TemplateForm(data=request.POST or None, instance=template, type=view)

    if request.method == "POST" and form.is_valid():
        x = form.save(commit=False)
        x.type = view

        if not template_id:
            x.created_by = request.user
        else:
            x.updated_by = request.user
        x.save()


        messages.success(request, "تم حفظ النموذج بنجاح")
        return redirect('dashboard:template_list')

    context = {
        "form": form,
        "bar": {
            "title": ("إضافة نموذج" if not template_id else "تعديل نموذج"),
            "back": reverse('dashboard:template_list'),
        }
    }

    return render(request, 'components/crispy.html', context)


@login_required
# @permission_required('portal.sitecategory', raise_exception=True)
def template_detail(request, template_id, view=Template.FOOD):
    template = get_object_or_404(Template.objects.prefetch_related("fields"), pk=template_id)

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