from datetime import timedelta
from django.utils import timezone
from core.models import Guardian, GuardianStudent

FREQ_TO_DELTA = {
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "quarterly": timedelta(days=90),
    "yearly": timedelta(days=365),
}

def next_available_at(last_dt, freq: str):
    if not last_dt:
        return timezone.now()
    return last_dt + FREQ_TO_DELTA.get(freq or "monthly", timedelta(days=30))

def is_available_now(last_dt, freq: str) -> bool:
    return not last_dt or timezone.now() >= next_available_at(last_dt, freq)

def get_or_select_student_fast(guardian: Guardian):
    """
    Fast path:
      - If guardian.selected_student_id present -> return it (no extra query).
      - Else, if exactly one GuardianStudent exists -> persist-select it and return.
      - Else return None (client must pick).
    """
    # O(1) check
    if guardian.selected_student_id:
        return guardian.selected_student  # accessing .id only uses selected_student_id

    # No selection yet — see how many
    links = GuardianStudent.objects.select_related("student").filter(guardian=guardian)
    count = links.count()
    if count == 0:
        return None
    if count == 1:
        only = links.first()
        guardian.selected_student_id = only.student_id
        guardian.save(update_fields=["selected_student", "updated_at"])
        return only.student

    # Multiple and none selected
    return None
