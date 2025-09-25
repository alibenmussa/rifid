# core/models.py - Enhanced with School Structure
import uuid
from django.core import validators
from django.db import models
from django.conf import settings
from django.utils import timezone


class School(models.Model):
    """
    Multi-tenant school model - each school is a separate tenant
    """
    name = models.CharField(max_length=100, verbose_name="اسم المدرسة")
    code = models.CharField(max_length=20, unique=True, verbose_name="رمز المدرسة")
    address = models.TextField(null=True, blank=True, verbose_name="العنوان")
    phone = models.CharField(max_length=15, null=True, blank=True, verbose_name="الهاتف")
    email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني")
    principal_name = models.CharField(max_length=100, null=True, blank=True, verbose_name="اسم المدير")

    # Settings for this school
    academic_year_start = models.DateField(null=True, blank=True, verbose_name="بداية السنة الدراسية")
    academic_year_end = models.DateField(null=True, blank=True, verbose_name="نهاية السنة الدراسية")

    is_active = models.BooleanField(default=True, verbose_name="مفعل؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "مدرسة"
        verbose_name_plural = "المدارس"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_unique_code()
        super().save(*args, **kwargs)

    def generate_unique_code(self):
        """Generate unique school code"""
        code = str(uuid.uuid4().hex[:8].upper())
        while School.objects.filter(code=code).exists():
            code = str(uuid.uuid4().hex[:8].upper())
        return code


class AcademicYear(models.Model):
    """Academic year for each school"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_years", verbose_name="المدرسة")
    name = models.CharField(max_length=50, verbose_name="السنة الدراسية")  # e.g., "2024-2025"
    start_date = models.DateField(verbose_name="تاريخ البداية")
    end_date = models.DateField(verbose_name="تاريخ النهاية")
    is_current = models.BooleanField(default=False, verbose_name="السنة الحالية؟")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "سنة دراسية"
        verbose_name_plural = "السنوات الدراسية"
        unique_together = [["school", "name"]]
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.school.name} - {self.name}"

    def save(self, *args, **kwargs):
        if self.is_current:
            # Ensure only one current academic year per school
            AcademicYear.objects.filter(school=self.school, is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Grade(models.Model):
    """School grades/levels"""
    GRADE_TYPES = [
        ('kindergarten', 'روضة'),
        ('primary', 'ابتدائي'),
        ('middle', 'إعدادي'),
        ('secondary', 'ثانوي'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="grades", verbose_name="المدرسة")
    name = models.CharField(max_length=50, verbose_name="اسم الصف")  # e.g., "الصف الأول"
    level = models.PositiveIntegerField(verbose_name="المستوى")  # 1, 2, 3, etc.
    grade_type = models.CharField(max_length=20, choices=GRADE_TYPES, verbose_name="نوع المرحلة")
    description = models.TextField(null=True, blank=True, verbose_name="الوصف")

    is_active = models.BooleanField(default=True, verbose_name="مفعل؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "صف دراسي"
        verbose_name_plural = "الصفوف الدراسية"
        unique_together = [["school", "level", "grade_type"]]
        ordering = ["grade_type", "level"]

    def __str__(self):
        return f"{self.school.name} - {self.name} ({self.get_grade_type_display()})"


class SchoolClass(models.Model):
    """School classes within grades"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="classes", verbose_name="المدرسة")
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="classes", verbose_name="الصف")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="classes",
                                      verbose_name="السنة الدراسية")

    name = models.CharField(max_length=50, verbose_name="اسم الفصل")  # e.g., "أ", "ب", "ج"
    section = models.CharField(max_length=10, null=True, blank=True, verbose_name="الشعبة")
    capacity = models.PositiveIntegerField(default=30, verbose_name="السعة القصوى")

    # Class teacher
    class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_classes",
        verbose_name="المعلم المسؤول"
    )

    is_active = models.BooleanField(default=True, verbose_name="مفعل؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "فصل دراسي"
        verbose_name_plural = "الفصول الدراسية"
        unique_together = [["school", "grade", "academic_year", "name"]]
        ordering = ["grade__level", "name"]

    def __str__(self):
        return f"{self.grade.name} - {self.name}"

    @property
    def full_name(self):
        """Full class name including grade"""
        return f"{self.grade.name} {self.name}"

    @property
    def student_count(self):
        """Current number of enrolled students"""
        return self.students.filter(is_active=True).count()

    @property
    def is_full(self):
        """Check if class is at capacity"""
        return self.student_count >= self.capacity


# Enhanced Guardian model with school relationship
class Guardian(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="guardians", verbose_name="المدرسة")

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
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
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
        if not self.code:
            self.code = str(uuid.uuid4().hex[:8].upper())
        super().save(*args, **kwargs)


# Enhanced Student model with school and class relationships
class Student(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="students", verbose_name="المدرسة")
    current_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
        verbose_name="الفصل الحالي"
    )

    # Student ID within school
    student_id = models.CharField(max_length=20, verbose_name="الرقم الجامعي")

    first_name = models.CharField(max_length=50, verbose_name="الاسم الأول")
    second_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="اسم الأب")
    third_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="اسم الجد")
    fourth_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="اسم جد الأب")
    last_name = models.CharField(max_length=50, verbose_name="اللقب")
    full_name = models.CharField(max_length=255, null=True, editable=False, verbose_name="الاسم الكامل")

    sex = models.CharField(max_length=10, choices=(("male", "ذكر"), ("female", "أنثى")), verbose_name="الجنس")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    place_of_birth = models.CharField(max_length=255, null=True, blank=True, verbose_name="مكان الميلاد")

    phone = models.CharField(max_length=15, null=True, blank=True, verbose_name="رقم الهاتف")
    alternative_phone = models.CharField(max_length=15, null=True, blank=True, verbose_name="رقم هاتف بديل")
    email = models.EmailField(null=True, blank=True, verbose_name="البريد الإلكتروني")
    nid = models.CharField(
        max_length=11, null=True, blank=True, verbose_name="الرقم الوطني",
        validators=[validators.MinLengthValidator(11), validators.MaxLengthValidator(11)]
    )
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name="عنوان السكن")

    # Academic info
    enrollment_date = models.DateField(null=True, blank=True, verbose_name="تاريخ التسجيل")
    graduation_date = models.DateField(null=True, blank=True, verbose_name="تاريخ التخرج")

    # Status
    is_active = models.BooleanField(default=True, verbose_name="مفعل؟")

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
        unique_together = [["school", "student_id"]]
        ordering = ["last_name", "first_name"]

    def save(self, *args, **kwargs):
        # Auto-generate full name
        parts = [self.first_name, self.second_name, self.third_name, self.fourth_name, self.last_name]
        self.full_name = " ".join([p for p in parts if p]) or None

        # Auto-generate student ID if not provided
        if not self.student_id and self.school_id:
            self.student_id = self.generate_student_id()

        super().save(*args, **kwargs)

    def generate_student_id(self):
        """Generate unique student ID within school"""
        year = str(timezone.now().year)[2:]  # Last 2 digits of year
        count = Student.objects.filter(school=self.school).count() + 1
        return f"{self.school.code}{year}{count:04d}"

    def __str__(self):
        return self.full_name or f"{self.first_name} {self.last_name}".strip()


# Enhanced GuardianStudent relationship
class GuardianStudent(models.Model):
    REL_CHOICES = (
        ("father", "الأب"),
        ("mother", "الأم"),
        ("brother", "الأخ"),
        ("sister", "الأخت"),
        ("grandparent", "الجد/الجدة"),
        ("uncle", "العم/الخال"),
        ("aunt", "العمة/الخالة"),
        ("other", "آخر"),
    )

    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, verbose_name="الولي")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="الطالب")
    relationship = models.CharField(max_length=20, choices=REL_CHOICES, default="father", verbose_name="العلاقة")
    is_primary = models.BooleanField(default=False, verbose_name="ولي أساسي؟")
    is_emergency_contact = models.BooleanField(default=False, verbose_name="جهة اتصال طارئة؟")

    # Permissions
    can_pickup = models.BooleanField(default=True, verbose_name="يمكنه استلام الطالب؟")
    can_receive_notifications = models.BooleanField(default=True, verbose_name="يستقبل الإشعارات؟")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

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


# Enhanced StudentTimeline with school context
def timeline_upload_path(instance, filename):
    return f"schools/{instance.timeline.student.school.code}/students/{instance.timeline.student_id}/timeline/{uuid.uuid4().hex}_{filename}"


class StudentTimeline(models.Model):
    """Timeline entry for students with school context"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="timeline", verbose_name="الطالب")
    title = models.CharField(max_length=255, verbose_name="العنوان", blank=True)
    note = models.TextField(verbose_name="المحتوى", blank=True)

    # Content type and visibility
    CONTENT_TYPES = [
        ('note', 'ملاحظة'),
        ('achievement', 'إنجاز'),
        ('behavior', 'سلوك'),
        ('health', 'صحة'),
        ('academic', 'أكاديمي'),
        ('attendance', 'حضور'),
        ('other', 'آخر'),
    ]
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES, default='note', verbose_name="نوع المحتوى")

    # Visibility settings
    is_visible_to_guardian = models.BooleanField(default=True, verbose_name="مرئي لولي الأمر؟")
    is_visible_to_student = models.BooleanField(default=False, verbose_name="مرئي للطالب؟")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="student_timeline_notes",
        verbose_name="أضيفت بواسطة"
    )
    is_pinned = models.BooleanField(default=False, verbose_name="مثبّت؟")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    class Meta:
        verbose_name = "ملاحظة الطالب"
        verbose_name_plural = "ملاحظات الطلبة"
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["student", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]

    def __str__(self):
        return self.title or (self.note[:40] if self.note else f"Timeline #{self.pk}")


class StudentTimelineAttachment(models.Model):
    """Attachments for timeline entries"""
    timeline = models.ForeignKey(StudentTimeline, on_delete=models.CASCADE, related_name="attachments",
                                 verbose_name="المحتوى")
    file = models.FileField(upload_to=timeline_upload_path, verbose_name="الملف")
    is_image = models.BooleanField(default=False, verbose_name="صورة؟")
    file_size = models.PositiveIntegerField(null=True, blank=True, verbose_name="حجم الملف")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "مرفق ملاحظة"
        verbose_name_plural = "مرفقات الملاحظات"

    def save(self, *args, **kwargs):
        # Auto-detect image files
        name = (self.file.name or "").lower()
        self.is_image = name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))

        # Store file size
        if self.file:
            self.file_size = self.file.size

        super().save(*args, **kwargs)