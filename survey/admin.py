from django.contrib import admin

from survey.models import Template, TemplateField, AdditionalField


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ['name',
                    # 'category'
                    ]
    search_fields = ['name',
                     # 'category'
                     ]


@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    list_display = [x.name for x in TemplateField._meta.fields]


@admin.register(AdditionalField)
class AdditionalFieldAdmin(admin.ModelAdmin):
    list_display = [x.name for x in AdditionalField._meta.fields]
