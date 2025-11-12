# accounts/models.py - Enhanced with school structure
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Enhanced user model with school context"""

    STUDENT = 'student'
    GUARDIAN = 'guardian'
    TEACHER = 'teacher'
    EMPLOYEE = 'employee'
    ADMIN = 'admin'
    SUPERVISOR = 'supervisor'

    USER_TYPE_CHOICES = [
        (STUDENT, 'طالب'),
        (GUARDIAN, 'ولي أمر'),
        (TEACHER, 'معلم'),
        (EMPLOYEE, 'موظف'),
        (ADMIN, 'مدير'),
        (SUPERVISOR, 'مشرف'),
    ]

    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default=EMPLOYEE,
        verbose_name="نوع المستخدم"
    )

    # Additional profile fields
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        null=True, blank=True,
        verbose_name="الصورة الشخصية"
    )
    phone = models.CharField(
        max_length=15,
        null=True, blank=True,
        verbose_name="رقم الهاتف"
    )
    date_of_birth = models.DateField(
        null=True, blank=True,
        verbose_name="تاريخ الميلاد"
    )

    # Status fields
    is_verified = models.BooleanField(
        default=False,
        verbose_name="تم التحقق منه"
    )
    last_activity = models.DateTimeField(
        null=True, blank=True,
        verbose_name="آخر نشاط"
    )

    # Preferences
    language = models.CharField(
        max_length=10,
        choices=[('ar', 'العربية'), ('en', 'English')],
        default='ar',
        verbose_name="اللغة"
    )
    theme = models.CharField(
        max_length=10,
        choices=[('light', 'فاتح'), ('dark', 'داكن')],
        default='light',
        verbose_name="المظهر"
    )

    # Firebase Cloud Messaging token for push notifications
    fcm_token = models.CharField(
        max_length=255,
        null=True, blank=True,
        verbose_name="رمز FCM"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")

    class Meta:
        verbose_name = "مستخدم"
        verbose_name_plural = "المستخدمون"

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        """Get user's display name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.username

    def get_school(self):
        """Get user's associated school"""
        if hasattr(self, 'guardian') and self.guardian:
            return self.guardian.school
        elif hasattr(self, 'teacher_profile') and self.teacher_profile:
            return self.teacher_profile.school
        elif hasattr(self, 'employee_profile') and self.employee_profile:
            return self.employee_profile.school
        return None

    def get_role_display(self):
        """Get user's role in Arabic"""
        return self.get_user_type_display()

    def update_last_activity(self):
        """Update user's last activity timestamp"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])

    def get_age(self):
        """Calculate user's age"""
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                    (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None


class TeacherProfile(models.Model):
    QUALIFICATION_CHOICES = [
        ("bachelors", "بكالوريوس"),
        ("diploma", "دبلوم"),
        ("masters", "ماجستير"),
        ("phd", "دكتوراة"),

    ]
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        verbose_name="المستخدم"
    )
    school = models.ForeignKey(
        'core.School',
        on_delete=models.CASCADE,
        related_name="teachers",
        verbose_name="المدرسة"
    )

    # Teacher specific fields
    employee_id = models.CharField(
        max_length=20,
        verbose_name="الرقم الوظيفي"
    )
    subject = models.CharField(
        max_length=100,
        null=True, blank=True,
        verbose_name="المادة المتخصصة"
    )
    qualification = models.CharField(
        max_length=200,
        null=True, blank=True,
        choices=QUALIFICATION_CHOICES,
        verbose_name="المؤهل العلمي"
    )
    experience_years = models.PositiveIntegerField(
        default=0,
        verbose_name="سنوات الخبرة"
    )

    # Employment details
    hire_date = models.DateField(
        null=True, blank=True,
        verbose_name="تاريخ التوظيف"
    )
    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        verbose_name="الراتب"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط"
    )
    is_class_teacher = models.BooleanField(
        default=False,
        verbose_name="معلم فصل"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")

    class Meta:
        verbose_name = "ملف معلم"
        verbose_name_plural = "ملفات المعلمين"
        unique_together = [['school', 'employee_id']]

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.school.name}"


class EmployeeProfile(models.Model):
    """Employee profile for school staff"""

    POSITION_CHOICES = [
        ('principal', 'مدير المدرسة'),
        ('vice_principal', 'نائب المدير'),
        ('admin', 'إداري'),
        ('accountant', 'محاسب'),
        ('librarian', 'أمين مكتبة'),
        ('nurse', 'ممرض'),
        ('security', 'أمن'),
        ('cleaner', 'نظافة'),
        ('other', 'أخرى'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        verbose_name="المستخدم"
    )
    school = models.ForeignKey(
        'core.School',
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name="المدرسة"
    )

    # Employee details
    employee_id = models.CharField(
        max_length=20,
        verbose_name="الرقم الوظيفي"
    )
    position = models.CharField(
        max_length=50,
        choices=POSITION_CHOICES,
        verbose_name="المنصب"
    )
    department = models.CharField(
        max_length=100,
        null=True, blank=True,
        verbose_name="القسم"
    )

    # Employment details
    hire_date = models.DateField(
        null=True, blank=True,
        verbose_name="تاريخ التوظيف"
    )
    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        verbose_name="الراتب"
    )

    # Permissions
    can_manage_students = models.BooleanField(
        default=False,
        verbose_name="يمكنه إدارة الطلاب"
    )
    can_manage_teachers = models.BooleanField(
        default=False,
        verbose_name="يمكنه إدارة المعلمين"
    )
    can_view_reports = models.BooleanField(
        default=True,
        verbose_name="يمكنه عرض التقارير"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")

    class Meta:
        verbose_name = "ملف موظف"
        verbose_name_plural = "ملفات الموظفين"
        unique_together = [['school', 'employee_id']]

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.get_position_display()}"