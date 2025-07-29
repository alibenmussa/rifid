from django.core import validators
from django.db import models


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



