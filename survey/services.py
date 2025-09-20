from survey.models import Template


def convert_form_template_to_json(*, template: Template) -> list:
    form_list: list = []

    for field in template.fields.filter(is_public=True):
        field_dict = {
            "name": field.name,
            "kin": field.kind,
            "type": field.type,
            "value": field.value,
        }
        form_list.append(field_dict)

    return form_list

