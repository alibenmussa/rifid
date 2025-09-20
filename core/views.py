from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django_tables2 import RequestConfig

from core.tables import EmployeeTable, GuardianTable

User = get_user_model()

@login_required
def dashboard(request):
    context = {"bar":
        {
            "main": True,
            "title": "لوحة التحكم",
            "buttons": [
                {
                    "icon": "bi bi-box-arrow-right",
                    "url": reverse("accounts:logout"),
                    "color": "btn-outline-primary",
                }
            ]
        }}
    return render(request, "pages/dashboard.html", context=context)


@login_required
def employee_list(request):
    employees = User.objects.filter(is_staff=True)
    employee_table = EmployeeTable(employees)

    RequestConfig(request, paginate={"per_page": 10}).configure(employee_table)

    context = {
        "table": employee_table,
        "bar": {

            "main": True,
            "title": "الموظفين",
            "buttons": [
                {
                    "icon": "bi bi-plus",
                }
            ]
        }}
    return render(request, "components/list.html", context=context)


def employee_detail(request, pk):
    return render(request, "pages/dashboard.html")


# dashboard/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django_tables2 import RequestConfig

from core.models import Guardian
from core.forms import GuardianWithStudentForm
from core.tables import GuardianStudentTable


@login_required
def guardian_create_form(request):
    """
    Create Guardian + ONE Student (single crispy form)
    """
    if not request.user.has_perm("core.add_guardian") or not request.user.has_perm("core.add_student"):
        raise PermissionDenied()

    form = GuardianWithStudentForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        guardian, student = form.save(request_user=request.user)
        messages.success(request, "تم حفظ الولي والطالب بنجاح")
        return redirect("dashboard:guardian_students", guardian_id=guardian.id)

    context = {
        "form": form,
        "bar": {
            "title": "إضافة ولي أمر",
            "back": reverse("dashboard:guardian_list"),
        },
    }
    return render(request, "components/crispy.html", context)


@login_required
def guardian_students(request, guardian_id: int):
    """
    List a guardian's students (django-tables2)
    """
    if not request.user.has_perm("core.view_guardian"):
        raise PermissionDenied()

    guardian = get_object_or_404(Guardian, pk=guardian_id)
    qs = guardian.guardianstudent_set.select_related("student").all()
    table = GuardianStudentTable(qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    context = {
        "table": table,
        "bar": {
            "main": True,
            "title": f"أبناء {guardian}",
            "back": reverse("dashboard:guardian_list"),
        },
    }
    return render(request, "components/list.html", context)


@login_required
def guardian_list(request):
    if not request.user.has_perm("core.view_guardian"):
        raise PermissionDenied()

    qs = Guardian.objects.select_related("selected_student").order_by("-created_at")
    table = GuardianTable(qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    context = {
        "table": table,
        "bar": {
            "main": True,
            "title": "أولياء الأمور",
            "buttons": [
                {
                    "icon": "bi bi-plus",
                    "label": "إضافة ولي أمر",
                    "url": reverse("dashboard:guardian_create"),  # your create form
                }
            ],
        },
    }
    return render(request, "components/list.html", context)


@login_required
def guardian_detail(request, guardian_id):
    guardian = get_object_or_404(Guardian, id=guardian_id)
    students_table = GuardianStudentTable(guardian.guardianstudent_set.all())

    context = {
        'guardian': guardian,
        'students_table': students_table,  # Pass the table to the template

        'bar': {
            "title": "بيانات ولي الأمر",
            "back": reverse("dashboard:guardian_list"),  # Change the URL here as per your setup
        }
    }
    return render(request, 'pages/guardian_detail.html', context)


# dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from core.models import Guardian, Student
from core.forms import StudentForm

@login_required
def student_form(request, guardian_id, student_id=None):
    guardian = get_object_or_404(Guardian, id=guardian_id)

    if student_id:
        student = get_object_or_404(Student, id=student_id)
        if student not in guardian.students.all():
            messages.error(request, "هذا الطالب غير مرتبط بالولي المحدد.")
            return redirect('dashboard:guardian_detail', guardian_id=guardian.id)
    else:
        student = None

    if request.method == "POST":
        form = StudentForm(data=request.POST, instance=student, guardian=guardian)
        if form.is_valid():
            form.save()
            if student:
                messages.success(request, "تم تعديل بيانات الطالب بنجاح")
            else:
                messages.success(request, "تم إضافة الطالب بنجاح")
            return redirect('dashboard:guardian_detail', guardian_id=guardian.id)
    else:
        form = StudentForm(instance=student, guardian=guardian)

    context = {
        'form': form,
        'guardian': guardian,
        'bar': {
            'title': "إضافة/تعديل طالب",
            'back': reverse('dashboard:guardian_detail', args=[guardian.id]),
        }
    }
    return render(request, 'components/crispy.html', context)



# dashboard/views.py (append / or new block)
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django_tables2 import RequestConfig

from core.models import Guardian, Student, StudentTimeline, StudentTimelineAttachment, GuardianStudent
from core.forms import StudentTimelineForm
from core.tables import StudentTable

# ---- helpers ----
def _can_view_student(user, student: Student) -> bool:
    """
    Staff with 'core.view_student' can view all; guardians can view only their linked students.
    """
    if user.is_staff and user.has_perm("core.view_student"):
        return True
    if hasattr(user, "guardian"):
        return GuardianStudent.objects.filter(guardian=user.guardian, student=student).exists()
    return False

def _can_post_timeline(user) -> bool:
    # teachers/staff who can add timeline
    return user.is_staff and user.has_perm("core.add_studenttimeline")


@login_required
def students_list(request):
    """
    - Staff (with permission) see all students.
    - Guardians see only their own children.
    """
    if request.user.is_staff:
        if not request.user.has_perm("core.view_student"):
            raise PermissionDenied()
        qs = Student.objects.select_related().all().order_by("last_name", "first_name")
        title = "الطلاب"
    else:
        # guardian view (only their students)
        if not hasattr(request.user, "guardian"):
            raise PermissionDenied()
        qs = request.user.guardian.students.all().order_by("last_name", "first_name")
        title = "أبنائي"

    table = StudentTable(qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    context = {
        "table": table,
        "bar": {
            "main": True,
            "title": title,
            "back": reverse("dashboard:dashboard"),
        },
    }
    return render(request, "components/list.html", context)


# dashboard/views.py (student_detail)

@login_required
def student_detail(request, student_id: int):
    student = get_object_or_404(Student, pk=student_id)
    if not _can_view_student(request.user, student):
        raise PermissionDenied()

    timeline_qs = (
        StudentTimeline.objects
        .filter(student=student)
        .select_related("created_by", "student")
        .prefetch_related("attachments")
        .order_by("-is_pinned", "-created_at")
    )

    form = None
    if request.method == "POST":
        if not _can_post_timeline(request.user):
            raise PermissionDenied()
        form = StudentTimelineForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                entry = form.save(commit=False)
                entry.student = student
                entry.created_by = request.user
                entry.save()
                f = request.FILES.get("file")
                if f:
                    StudentTimelineAttachment.objects.create(timeline=entry, file=f)
            messages.success(request, "تم نشر المحتوى بنجاح.")
            return redirect("dashboard:student_detail", student_id=student.id)
    else:
        if _can_post_timeline(request.user):
            form = StudentTimelineForm()

    context = {
        "student": student,
        "timeline": timeline_qs,
        "form": form,
        "bar": {
            "main": True,
            "title": f"الطالب: {student.full_name or student}",
            "back": reverse("dashboard:students_list"),
        },
    }
    return render(request, "pages/student_detail.html", context)




@login_required
def guardian_select_student(request, guardian_id: int, student_id: int):
    """
    Set a guardian's selected student (used by web/mobile to 'switch child').
    """
    guardian = get_object_or_404(Guardian, pk=guardian_id)
    student = get_object_or_404(Student, pk=student_id)

    # only staff or the guardian himself can switch
    if not (request.user.is_staff or (hasattr(request.user, "guardian") and request.user.guardian_id == guardian.id)):
        raise PermissionDenied()

    # ensure relation exists
    if not GuardianStudent.objects.filter(guardian=guardian, student=student).exists():
        messages.error(request, "هذا الطالب غير مرتبط بهذا الولي.")
        return redirect("dashboard:guardian_detail", guardian_id=guardian.id)

    guardian.selected_student = student
    guardian.save(update_fields=["selected_student"])
    messages.success(request, f"تم اختيار {student.full_name} كطالب نشط.")
    return redirect("dashboard:student_detail", student_id=student.id)
