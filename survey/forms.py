import json

from crispy_forms.layout import HTML
from django.utils.safestring import mark_safe
from mptt.forms import TreeNodeChoiceField
from crispy_forms.helper import FormHelper
from crispy_forms import layout
from django import forms

from survey.models import Template, TemplateField
# from survey.models import SiteCategory




class TemplateForm(forms.ModelForm):
    # category = TreeNodeChoiceField(
    #     queryset=Template.objects.none(),
    #     # level_indicator=mark_safe("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"),
    #     level_indicator=mark_safe("&nbsp;&nbsp;&nbsp;&nbsp;"),
    #     # level_indicator=mark_safe("&nbsp;&nbsp;┤──"),
    #     # empty_label=None,
    #     required=True,
    #     label="التصنيف",
    #     widget=forms.Select(attrs={"class": "form-control form-select2"}),
    # )

    class Meta:
        model = Template
        fields = [
            'name',
            'default_frequency',
        ]

    def __init__(self, type, *args, **kwargs):
        self.type = type
        super().__init__(*args, **kwargs)
        # self.fields['category'].queryset = self.fields['category'].queryset.exclude(template__isnull=False)

        # if self.type == Template.SURVEY:
        #     self.fields["name"].required = True
        #     self.fields.pop("category")

        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.layout = layout.Layout(
            layout.Div(
                layout.Column('name', css_class='col-md-6'),
                layout.Column('default_frequency', css_class='col-md-6'),
                css_class='row'
            ),
        )


class TemplateFieldForm(forms.ModelForm):
    class Meta:
        model = TemplateField
        fields = ["name", "type", "is_required", "value"]

    def clean(self):
        cleaned_data = super().clean()
        value = cleaned_data.get("value")
        field_type = cleaned_data.get("type")

        if field_type in (TemplateField.SELECT, TemplateField.CHECKBOX, TemplateField.RADIO):
            if not value:
                self.add_error("value", "هذا الحقل مطلوب")
                return cleaned_data
            try:
                value = json.loads(json.dumps(value))
                print(value, type(value))
            except Exception as e:
                self.add_error("value", "القيمة غير صالحة")
                return cleaned_data

            if type(value) not in [list, tuple]:
                self.add_error("value", "القيمة يجب أن تكون قائمة")
                return cleaned_data

        else:
            cleaned_data["value"] = None

            # print(cleaned_data["value"], value)
            # cleaned_data["value"] = [(x, x) for x in value if x]
            # print(cleaned_data["value"], value)

        return cleaned_data

    # def clean_is_public(self):
    #     if self.template.type == Template.FOOD:
    #         return True
    #
    #     return self.cleaned_data.get("is_public")

    def __init__(self, template: Template, *args, **kwargs):
        self.template = template

        super().__init__(*args, **kwargs)
        self.fields["value"].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False

        self.fields['value'].widget.attrs['rows'] = 2

        if self.template.parent:
            self.fields["type"].choices = [x for x in self.fields["type"].choices if x[0] != TemplateField.FORM]
            self.fields["type"].widget.attrs.update({"class": "form-select"})
        # if self.template.type == Template.FOOD:
        #     self.fields["is_public"].initial = True
            # self.fields["is_public"].widget = forms.HiddenInput()

        self.helper.layout = layout.Layout(
            layout.Div(
                layout.Column('name', css_class='col-md-6'),
                layout.Column('type', css_class='col-md-3'),
                layout.Column(
                    # layout.Div('is_public'),
                    layout.Div('is_required'),
                    css_class='col-md-3 d-flex flex-column justify-content-end'
                ),
                css_class='row'
            ),
            layout.Div(
                layout.Column(
                    layout.Field('value', rows=2)
                , css_class='col col-md-6'),
                layout.Column(css_class='col col-md-6'),
                css_class='row'
            ),

        )
