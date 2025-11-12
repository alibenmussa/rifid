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
    class Meta:
        model = Template
        fields = [
            'name',
            'target_audience',
            'send_frequency',
            'grades',
        ]
        widgets = {
            'grades': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, type, target_audience=None, school=None, *args, **kwargs):
        self.type = type
        self.target_audience = target_audience
        self.school = school
        super().__init__(*args, **kwargs)

        # If target_audience is provided (from URL), set it and disable the field
        if target_audience:
            self.fields['target_audience'].initial = target_audience
            self.fields['target_audience'].widget = forms.HiddenInput()

        # Filter grades to only show grades from the current school
        if school:
            self.fields['grades'].queryset = school.grades.filter(is_active=True)
        else:
            # If no school context, show all grades (for superuser)
            from core.models import Grade
            self.fields['grades'].queryset = Grade.objects.filter(is_active=True)

        self.helper = FormHelper()
        self.helper.form_tag = False

        # Build layout based on whether we're showing target_audience or not
        if target_audience:
            # Target is already selected, show appropriate fields
            if target_audience == Template.TARGET_GUARDIANS:
                # Show grades field for guardian surveys
                self.helper.layout = layout.Layout(
                    layout.Field('target_audience'),  # Hidden field
                    layout.Div(
                        layout.Column('name', css_class='col-md-6'),
                        layout.Column('send_frequency', css_class='col-md-6'),
                        css_class='row'
                    ),
                    layout.Div(
                        layout.Column('grades', css_class='col-md-12'),
                        css_class='row'
                    ),
                )
            else:
                # No grades field for other target types
                self.helper.layout = layout.Layout(
                    layout.Field('target_audience'),  # Hidden field
                    layout.Div(
                        layout.Column('name', css_class='col-md-6'),
                        layout.Column('send_frequency', css_class='col-md-6'),
                        css_class='row'
                    ),
                )
        else:
            # Editing existing template, show all fields
            self.helper.layout = layout.Layout(
                layout.Div(
                    layout.Column('name', css_class='col-md-6'),
                    layout.Column('target_audience', css_class='col-md-6'),
                    css_class='row'
                ),
                layout.Div(
                    layout.Column('send_frequency', css_class='col-md-6'),
                    css_class='row'
                ),
                layout.Div(
                    layout.Column('grades', css_class='col-md-12'),
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
