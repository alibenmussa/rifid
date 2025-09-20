from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.models import GuardianStudent, Guardian


@receiver(post_delete, sender=GuardianStudent)
def clear_selection_if_link_removed(sender, instance, **kwargs):
    g = instance.guardian
    if g.selected_student_id == instance.student_id:
        Guardian.objects.filter(pk=g.pk).update(selected_student=None)
