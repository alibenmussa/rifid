import uuid

from django.core import validators
from django.db import models


class Guardian(models.Model):
    first_name = models.CharField(max_length=50, verbose_name="الاسم الأول")
    last_name = models.CharField(max_length=50, verbose_name="اللقب")
    phone = models.CharField(max_length=15, null=True, blank=True, verbose_name="الهاتف")
    email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني")
    nid = models.CharField(
        max_length=11, null=True, blank=True, verbose_name="الرقم الوطني",
        validators=[validators.MinLengthValidator(11), validators.MaxLengthValidator(11)]
    )
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="عنوان السكن")
    user = models.OneToOneField(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="guardian", verbose_name="المستخدم المرتبط"
    )

    selected_student = models.ForeignKey(
        "core.Student",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="selected_for_guardians",
        db_index=True,
        verbose_name="الطالب المختار"
    )

    code = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="كود التسجيل")


    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "ولي الأمر"
        verbose_name_plural = "أولياء الأمور"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        """Generate the unique registration code (UUID) if not already set."""
        if not self.code:
            self.code = str(uuid.uuid4().hex[:8].upper())  # Unique code (shortened UUID)
        super().save(*args, **kwargs)



class Student(models.Model):
    first_name = models.CharField(max_length=50, verbose_name="الاسم الأول")
    second_name = models.CharField(max_length=50, null=True, blank=False, verbose_name="اسم الأب")
    third_name = models.CharField(max_length=50, null=True, blank=False, verbose_name="اسم الجد")
    fourth_name = models.CharField(max_length=50, null=True, blank=False, verbose_name="اسم جد الأب")
    last_name = models.CharField(max_length=50, verbose_name="اللقب")
    full_name = models.CharField(max_length=255, null=True, editable=False, verbose_name="الاسم الكامل")
    sex = models.CharField(max_length=10, choices=(("male", "ذكر"), ("female", "أنثى")), verbose_name="الجنس")
    date_of_birth = models.DateField(null=True, verbose_name="تاريخ الميلاد")
    place_of_birth = models.CharField(max_length=255, null=True, verbose_name="مكان الميلاد")
    phone = models.CharField(max_length=10, null=True, blank=True, verbose_name="رقم الهاتف")
    alternative_phone = models.CharField(max_length=10, null=True, blank=True, verbose_name="رقم هاتف بديل")
    email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني")
    nid = models.CharField(max_length=11, null=True, blank=True, verbose_name="الرقم الوطني", validators=[validators.MinLengthValidator(11), validators.MaxLengthValidator(11)])
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="عنوان السكن")

    guardians = models.ManyToManyField(
        Guardian,
        through="GuardianStudent",
        related_name="students",
        verbose_name="الأولياء"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")



    class Meta:
        verbose_name = "طالب"
        verbose_name_plural = "الطلبة"
        ordering = ["last_name", "first_name"]

    def save(self, *args, **kwargs):
        parts = [self.first_name, self.second_name, self.third_name, self.fourth_name, self.last_name]
        self.full_name = " ".join([p for p in parts if p]) or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or f"{self.first_name} {self.last_name}".strip()



class GuardianStudent(models.Model):
    REL_CHOICES = (
        ("father", "الأب"),
        ("mother", "الأم"),
        ("brother", "الأخ"),
        ("sister", "الأخت"),
        ("grandparent", "الجد/الجدة"),
        ("other", "آخر"),
    )
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, verbose_name="الولي")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="الطالب")
    relationship = models.CharField(max_length=20, choices=REL_CHOICES, default="father", verbose_name="العلاقة")
    is_primary = models.BooleanField(default=False, verbose_name="ولي أساسي؟")

    class Meta:
        verbose_name = "صلة ولي الأمر بالطالب"
        verbose_name_plural = "صلات الأولياء بالطلبة"
        unique_together = [("guardian", "student")]
        indexes = [
            models.Index(fields=["guardian", "student"]),
            models.Index(fields=["student", "is_primary"]),
        ]

    def __str__(self):
        return f"{self.guardian} ↔ {self.student} ({self.get_relationship_display()})"




# core/models.py (add below your existing models)
from django.conf import settings

def timeline_upload_path(instance, filename):
    # media/students/<student_id>/timeline/<uuid>_<filename>
    return f"students/{instance.timeline.student_id}/timeline/{uuid.uuid4().hex}_{filename}"

class StudentTimeline(models.Model):
    """
    A timeline entry (note) added by a teacher/staff about a student.
    """
    student = models.ForeignKey("core.Student", on_delete=models.CASCADE, related_name="timeline", verbose_name="الطالب")
    title = models.CharField(max_length=255, verbose_name="العنوان", blank=True)
    note = models.TextField(verbose_name="المحتوى", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="student_timeline_notes", verbose_name="أضيفت بواسطة")
    is_pinned = models.BooleanField(default=False, verbose_name="مثبّت؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "ملاحظة الطالب"
        verbose_name_plural = "ملاحظات الطلبة"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title or (self.note[:40] if self.note else f"Timeline #{self.pk}")


class StudentTimelineAttachment(models.Model):
    """
    Attachments for a timeline entry (image or any file).
    """
    timeline = models.ForeignKey(StudentTimeline, on_delete=models.CASCADE, related_name="attachments", verbose_name="المحتوى")
    file = models.FileField(upload_to=timeline_upload_path, verbose_name="الملف")
    is_image = models.BooleanField(default=False, verbose_name="صورة؟")

    class Meta:
        verbose_name = "مرفق ملاحظة"
        verbose_name_plural = "مرفقات الملاحظات"

    def save(self, *args, **kwargs):
        # naive image detection by extension (fast + framework-free)
        name = (self.file.name or "").lower()
        self.is_image = name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
        return super().save(*args, **kwargs)

