from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    STUDENT = 'student'
    GUARDIAN = 'guardian'
    TEACHER = 'teacher'
    EMPLOYEE = 'employee'

    USER_TYPE_CHOICES = [
        (STUDENT, 'Student'),
        (GUARDIAN, 'Guardian'),
    ]
    type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default=EMPLOYEE, verbose_name="نوع المستخدم")

    def __str__(self):
        return self.username
