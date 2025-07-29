import uuid

from django.conf import settings
from django.http import Http404
from django.views.static import serve


def protected_media(request, path: str, document_root=settings.MEDIA_ROOT, show_indexes=False):
    if not request.user.is_authenticated:
        raise Http404("File not found")
    return serve(request, path, document_root, show_indexes)


def upload_to_directory(route, filename):
    return '{0}/{1}.{2}'.format(route, uuid.uuid4().hex[:24], filename.split('.')[-1])


def get_badge(value, color="primary", size=""):
    return f'<span class="badge {size} p-1 px-2 bg-{color}">{value}</span>'


class Button:
    def __init__(self, url=None, params=None, label=None, icon=None, style="", attrs=""):
        self.url = url
        self.params = params or "record.id"
        self.label = label or ""
        self.icon = icon or "bi-pencil"
        self.style = style
        self.attrs = attrs

    def render(self):
        html = ""
        icon = f'<i class="bi align-middle {self.icon}"></i>'
        if self.url:
            url = '{% url "' + self.url + '" ' + self.params + ' %}'
            html += f'<a href="{url}" class="btn btn-sm btn-primary {self.style}" {self.attrs}>'
            html += icon
            html += f'{self.label}</a>' if self.label else '</a>'
        else:
            html += f'<button class="btn btn-sm btn-primary {self.style}" {self.attrs}>'
            html += icon
            html += f'{self.label}</button>' if self.label else '</button>'
        return html


TABLE_STYLE = {
    "template": "django_tables2/bootstrap4.html",
    "class": "table text-md-nowrap w-100 table-hover mb-0 rounded-3 text-center",
}

