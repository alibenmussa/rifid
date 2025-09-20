import django_filters
from core.models import StudentTimeline

class StudentTimelineFilter(django_filters.FilterSet):
    is_pinned = django_filters.BooleanFilter()
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = StudentTimeline
        fields = ["is_pinned", "created_after", "created_before"]
