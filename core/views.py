# core/views.py - Enhanced with school context and better UI
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django_tables2 import RequestConfig

from core.forms import (
    GuardianWithStudentForm, StudentForm, StudentTimelineForm,
    StudentSearchForm, GuardianStudentForm
)
from core.models import (
    School, Guardian, Student, GuardianStudent,
    StudentTimeline, StudentTimelineAttachment,
    Grade, SchoolClass
)
from core.tables import (
    EmployeeTable, GuardianTable, GuardianStudentTable, StudentTable
)

User = get_user_model()


# ==========================================
# DASHBOARD AND MAIN VIEWS
# ==========================================

@login_required
def dashboard(request):
    """Enhanced dashboard with school context and statistics"""
    school = getattr(request, 'school', None)
    user = request.user

    # Initialize stats
    stats = {
        'students': 0,
        'guardians': 0,
        'teachers': 0,
        'classes': 0,
        'timeline_posts': 0,
    }

    # Recent activities
    recent_activities = []

    if school:
        # School-wide statistics
        stats.update({
            'students': school.students.filter(is_active=True).count(),
            'guardians': school.guardians.count(),
            'teachers': school.teachers.filter(is_active=True).count(),
            'classes': school.classes.filter(is_active=True).count(),
            'timeline_posts': StudentTimeline.objects.filter(
                student__school=school
            ).count(),
        })

        # Recent timeline activities (last 7 days)
        week_ago = timezone.now() - timezone.timedelta(days=7)
        recent_activities = (
            StudentTimeline.objects
            .filter(student__school=school, created_at__gte=week_ago)
            .select_related('student', 'created_by')
            .order_by('-created_at')[:10]
        )

    # User-specific data
    user_data = {}
    if hasattr(user, 'guardian') and user.guardian:
        user_data = {
            'type': 'guardian',
            'children_count': user.guardian.students.filter(is_active=True).count(),
            'selected_student': user.guardian.selected_student,
            'recent_surveys': 0,  # Can be implemented later
        }
    elif hasattr(user, 'teacher_profile') and user.teacher_profile:
        user_data = {
            'type': 'teacher',
            'managed_classes': user.managed_classes.filter(is_active=True).count(),
            'subject': user.teacher_profile.subject,
            'students_count': Student.objects.filter(
                current_class__class_teacher=user,
                is_active=True
            ).count(),
        }
    elif hasattr(user, 'employee_profile') and user.employee_profile:
        user_data = {
            'type': 'employee',
            'position': user.employee_profile.get_position_display(),
            'department': user.employee_profile.department,
        }

    # Grade breakdown for charts
    grade_breakdown = []
    if school:
        grade_breakdown = list(
            school.grades.filter(is_active=True)
            .annotate(
                student_count=Count('classes__students', filter=Q(classes__students__is_active=True))
            )
            .values('name', 'grade_type', 'student_count')
            .order_by('grade_type', 'level')
        )

    context = {
        'stats': stats,
        'user_data': user_data,
        'recent_activities': recent_activities,
        'grade_breakdown': grade_breakdown,
        'bar': {
            'main': True,
            'title': 'لوحة التحكم',
            'subtitle': f'أهلاً بك في {school.name}' if school else 'أهلاً بك',
        }
    }

    return render(request, 'pages/dashboard.html', context)


# ==========================================
# GUARDIAN VIEWS
# ==========================================

@login_required
@permission_required('core.view_guardian', raise_exception=True)
def guardian_list(request):
    """Enhanced guardian list with school context and search"""
    school = getattr(request, 'school', None)

    if not school and not request.user.is_superuser:
        messages.error(request, 'لا يمكن الوصول إلى هذه الصفحة بدون تحديد المدرسة.')
        return redirect('dashboard:dashboard')

    # Build queryset
    if request.user.is_superuser:
        queryset = Guardian.objects.all()
    else:
        queryset = Guardian.objects.filter(school=school)

    # Add related data
    queryset = queryset.select_related('school', 'selected_student', 'user').annotate(
        children_count=Count('students', filter=Q(students__is_active=True))
    ).order_by('-created_at')

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        queryset = queryset.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(students__full_name__icontains=search_query)
        ).distinct()

    # Pagination
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    guardians = paginator.get_page(page_number)

    # Table
    table = GuardianTable(guardians)
    RequestConfig(request, paginate={"per_page": 20}).configure(table)

    context = {
        'table': table,
        'guardians': guardians,
        'search_query': search_query,
        'total_count': queryset.count(),
        'bar': {
            'main': True,
            'title': 'أولياء الأمور',
            'subtitle': f'إدارة أولياء أمور {school.name}' if school else 'إدارة أولياء الأمور',
            'count': {
                'total': queryset.count(),
                'label': 'ولي أمر'
            },
            'buttons': [
                {
                    'icon': 'bi bi-plus',
                    'label': 'إضافة ولي أمر',
                    'url': reverse('dashboard:guardian_create'),
                    'color': 'btn-primary'
                },
                {
                    'icon': 'bi bi-download',
                    'label': 'تصدير',
                    'color': 'btn-outline-secondary'
                }
            ],
        },
    }

    return render(request, 'components/list.html', context)


@login_required
@permission_required('core.add_guardian', raise_exception=True)
def guardian_create_form(request):
    """Enhanced guardian creation with school context"""
    school = getattr(request, 'school', None)

    if not school and not request.user.is_superuser:
        messages.error(request, 'لا يمكن إنشاء ولي أمر بدون تحديد المدرسة.')
        return redirect('dashboard:guardian_list')

    form = GuardianWithStudentForm(request.POST or None, school=school)

    if request.method == "POST" and form.is_valid():
        try:
            guardian, student = form.save(request_user=request.user)
            messages.success(
                request,
                f'تم إنشاء ولي الأمر {guardian} والطالب {student} بنجاح.'
            )
            return redirect("dashboard:guardian_detail", guardian_id=guardian.id)
        except Exception as e:
            messages.error(request, f'حدث خطأ أثناء الحفظ: {str(e)}')

    context = {
        'form': form,
        'school': school,
        'bar': {
            'title': 'إضافة ولي أمر وطالب',
            'subtitle': f'إضافة ولي أمر جديد في {school.name}' if school else 'إضافة ولي أمر جديد',
            'back': reverse("dashboard:guardian_list"),
        },
    }
    return render(request, "components/crispy.html", context)


@login_required
@permission_required('core.view_guardian', raise_exception=True)
def guardian_detail(request, guardian_id: int):
    """Enhanced guardian detail view with comprehensive information"""
    guardian = get_object_or_404(
        Guardian.objects.select_related('school', 'user', 'selected_student')
        .prefetch_related(
            Prefetch(
                'guardianstudent_set',
                queryset=GuardianStudent.objects.select_related('student')
                .order_by('-is_primary', 'student__last_name')
            )
        ),
        pk=guardian_id
    )

    # Check school permission
    school = getattr(request, 'school', None)
    if (school and guardian.school != school and
            not request.user.is_superuser):
        raise PermissionDenied('ليس لديك صلاحية لعرض هذا الولي.')

    # Guardian-Student relationships
    relationships = guardian.guardianstudent_set.all()
    students_table = GuardianStudentTable(relationships)

    # Recent timeline activities for guardian's children
    recent_timeline = (
        StudentTimeline.objects
        .filter(
            student__guardians=guardian,
            is_visible_to_guardian=True
        )
        .select_related('student', 'created_by')
        .prefetch_related('attachments')
        .order_by('-is_pinned', '-created_at')[:10]
    )

    # Statistics
    stats = {
        'total_children': guardian.students.filter(is_active=True).count(),
        'timeline_posts': StudentTimeline.objects.filter(
            student__guardians=guardian,
            is_visible_to_guardian=True
        ).count(),
        'recent_posts': 0,
    }

    context = {
        'guardian': guardian,
        'students_table': students_table,
        'relationships': relationships,
        'recent_timeline': recent_timeline,
        'stats': stats,
        'bar': {
            'title': f'ولي الأمر: {guardian}',
            'subtitle': f'معلومات تفصيلية - {guardian.school.name}',
            'back': reverse("dashboard:guardian_list"),
            'buttons': [
                {
                    'icon': 'bi bi-pencil',
                    'label': 'تعديل',
                    'url': f'#',  # Add edit URL when needed
                    'color': 'btn-primary'
                },
                {
                    'icon': 'bi bi-person-plus',
                    'label': 'إضافة طالب',
                    'url': reverse('dashboard:student_add', args=[guardian.id]),
                    'color': 'btn-success'
                }
            ]
        }
    }

    return render(request, 'pages/guardian_detail.html', context)


# ==========================================
# STUDENT VIEWS
# ==========================================

@login_required
def students_list(request):
    """Enhanced students list with advanced filtering and school context"""
    school = getattr(request, 'school', None)
    user = request.user

    print(school)

    # Determine queryset based on user role
    if user.has_perm("core.view_student"):
        if school:
            queryset = Student.objects.filter(school=school)
            title = f"طلاب {school.name}"
        else:
            queryset = Student.objects.all()
            title = "جميع الطلاب"
    elif hasattr(user, 'guardian') and user.guardian:
        queryset = user.guardian.students.all()
        title = "أطفالي"
    elif hasattr(user, 'teacher_profile') and user.teacher_profile:
        if school:
            queryset = Student.objects.filter(school=school)
            title = f"طلاب {school.name}"
        else:
            queryset = Student.objects.none()
            title = "الطلاب"
    else:
        raise PermissionDenied('ليس لديك صلاحية لعرض الطلاب.')

    # Add related data
    queryset = queryset.select_related(
        'school', 'current_class__grade'
    ).prefetch_related(
        'guardians'
    ).filter(is_active=True).order_by('last_name', 'first_name')

    # Search and filtering
    search_form = StudentSearchForm(request.GET, school=school)

    if search_form.is_valid():
        search_query = search_form.cleaned_data.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(student_id__icontains=search_query) |
                Q(full_name__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(phone__icontains=search_query) |
                Q(email__icontains=search_query)
            )

        grade = search_form.cleaned_data.get('grade')
        if grade:
            queryset = queryset.filter(current_class__grade=grade)

        school_class = search_form.cleaned_data.get('school_class')
        if school_class:
            queryset = queryset.filter(current_class=school_class)

        sex = search_form.cleaned_data.get('sex')
        if sex:
            queryset = queryset.filter(sex=sex)

    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    students = paginator.get_page(page_number)

    # Table
    table = StudentTable(students)
    RequestConfig(request, paginate={"per_page": 25}).configure(table)

    context = {
        'table': table,
        'students': students,
        'search_form': search_form,
        'total_count': queryset.count(),
        'bar': {
            'main': True,
            'title': title,
            'subtitle': f'إدارة الطلاب - {queryset.count()} طالب',
            'count': {
                'total': queryset.count(),
                'label': 'طالب'
            },
            'buttons': [
                {
                    'icon': 'bi bi-plus',
                    'label': 'إضافة طالب',
                    'url': '#',
                    'color': 'btn-primary'
                } if user.is_staff else None,
                {
                    'icon': 'bi bi-upload',
                    'label': 'رفع ملف',
                    'color': 'btn-outline-primary'
                } if user.is_staff else None,
                {
                    'icon': 'bi bi-download',
                    'label': 'تصدير',
                    'color': 'btn-outline-secondary'
                }
            ] if user.is_staff else [],
        },
    }

    return render(request, 'components/list.html', context)


@login_required
def student_detail(request, student_id: int):
    """Enhanced student detail view with comprehensive information and timeline"""
    student = get_object_or_404(
        Student.objects.select_related(
            'school', 'current_class__grade', 'current_class__academic_year'
        ).prefetch_related(
            # 'guardians__guardian',
            'timeline__created_by',
            'timeline__attachments'
        ),
        pk=student_id
    )

    # Permission check
    user = request.user
    school = getattr(request, 'school', None)

    if not _can_view_student(user, student, school):
        raise PermissionDenied('ليس لديك صلاحية لعرض هذا الطالب.')

    # Timeline with filtering
    timeline_qs = student.timeline.select_related(
        'created_by'
    ).prefetch_related('attachments').order_by('-is_pinned', '-created_at')

    # Filter timeline based on user role
    if hasattr(user, 'guardian') and user.guardian:
        timeline_qs = timeline_qs.filter(is_visible_to_guardian=True)

    # Timeline form for authorized users
    form = None
    if _can_post_timeline(user):
        if request.method == "POST":
            form = StudentTimelineForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        timeline_entry = form.save(commit=False)
                        timeline_entry.student = student
                        timeline_entry.created_by = user
                        timeline_entry.save()

                        # Handle file attachment
                        uploaded_file = request.FILES.get("file")
                        if uploaded_file:
                            StudentTimelineAttachment.objects.create(
                                timeline=timeline_entry,
                                file=uploaded_file
                            )

                        messages.success(request, 'تم إضافة المنشور بنجاح.')
                        return redirect("dashboard:student_detail", student_id=student.id)
                except Exception as e:
                    messages.error(request, f'حدث خطأ: {str(e)}')
        else:
            form = StudentTimelineForm()

    # Student statistics
    stats = {
        'timeline_posts': timeline_qs.count(),
        'pinned_posts': timeline_qs.filter(is_pinned=True).count(),
        'guardians_count': student.guardians.count(),
        'age': student.date_of_birth and _calculate_age(student.date_of_birth) or None,
    }

    # Guardian relationships
    guardian_relationships = GuardianStudent.objects.filter(
        student=student
    ).select_related('guardian').order_by('-is_primary')

    # Academic information
    academic_info = {
        'current_class': student.current_class,
        'enrollment_date': student.enrollment_date,
        'student_id': student.student_id,
        'school': student.school,
    }

    context = {
        'student': student,
        'timeline': timeline_qs[:20],  # Show latest 20 posts
        'form': form,
        'stats': stats,
        'guardian_relationships': guardian_relationships,
        'academic_info': academic_info,
        'can_post_timeline': _can_post_timeline(user),
        'bar': {
            'main': True,
            'title': f'الطالب: {student.full_name}',
            'subtitle': f'{student.student_id} - {student.school.name}',
            'back': reverse("dashboard:students_list"),
            'buttons': [
                {
                    'icon': 'bi bi-pencil',
                    'label': 'تعديل البيانات',
                    'color': 'btn-primary'
                } if user.is_staff else None,
                {
                    'icon': 'bi bi-person-lines-fill',
                    'label': 'إضافة ولي أمر',
                    'color': 'btn-success'
                } if user.is_staff else None,
                {
                    'icon': 'bi bi-printer',
                    'label': 'طباعة',
                    'color': 'btn-outline-secondary'
                }
            ]
        },
    }

    return render(request, 'pages/student_detail.html', context)


@login_required
def student_form(request, guardian_id=None, student_id=None):
    """Enhanced student form with school context"""
    guardian = None
    student = None
    school = getattr(request, 'school', None)

    if guardian_id:
        guardian = get_object_or_404(Guardian, id=guardian_id)
        if school and guardian.school != school and not request.user.is_superuser:
            raise PermissionDenied()

    if student_id:
        student = get_object_or_404(Student, id=student_id)
        if guardian and student not in guardian.students.all():
            messages.error(request, "هذا الطالب غير مرتبط بالولي المحدد.")
            return redirect('dashboard:guardian_detail', guardian_id=guardian.id)

    if request.method == "POST":
        form = StudentForm(
            data=request.POST,
            instance=student,
            guardian=guardian,
            school=school
        )
        if form.is_valid():
            try:
                student_obj = form.save()
                action = "تعديل" if student else "إضافة"
                messages.success(request, f"تم {action} بيانات الطالب بنجاح")

                if guardian:
                    return redirect('dashboard:guardian_detail', guardian_id=guardian.id)
                else:
                    return redirect('dashboard:student_detail', student_id=student_obj.id)
            except Exception as e:
                messages.error(request, f'حدث خطأ: {str(e)}')
    else:
        form = StudentForm(instance=student, guardian=guardian, school=school)

    context = {
        'form': form,
        'guardian': guardian,
        'student': student,
        'school': school,
        'bar': {
            'title': "تعديل طالب" if student else "إضافة طالب",
            'subtitle': f'في {school.name}' if school else '',
            'back': reverse('dashboard:guardian_detail', args=[guardian.id]) if guardian else reverse(
                'dashboard:students_list'),
        }
    }
    return render(request, 'components/crispy.html', context)


# ==========================================
# EMPLOYEE VIEWS
# ==========================================

@login_required
@permission_required('accounts.view_user', raise_exception=True)
def employee_list(request):
    """Enhanced employee list with school context"""
    school = getattr(request, 'school', None)

    if school:
        # Filter by school employees
        employees = User.objects.filter(
            Q(teacher_profile__school=school) |
            Q(employee_profile__school=school)
        ).select_related(
            'teacher_profile', 'employee_profile'
        ).filter(is_staff=True)
        title = f"موظفو {school.name}"
    else:
        employees = User.objects.filter(is_staff=True)
        title = "الموظفين"

    employee_table = EmployeeTable(employees)
    RequestConfig(request, paginate={"per_page": 15}).configure(employee_table)

    context = {
        "table": employee_table,
        "bar": {
            "main": True,
            "title": title,
            "subtitle": f"إدارة الموظفين - {employees.count()} موظف",
            "buttons": [
                {
                    "icon": "bi bi-plus",
                    "label": "إضافة موظف",
                    "color": "btn-primary"
                }
            ]
        }
    }
    return render(request, "pages/employee_list.html", context)


@login_required
def employee_detail(request, pk):
    """Employee detail view"""
    employee = get_object_or_404(User, pk=pk, is_staff=True)

    context = {
        'employee': employee,
        'bar': {
            'title': f'الموظف: {employee.get_display_name()}',
            'back': reverse('dashboard:employee_list'),
        }
    }
    return render(request, "pages/employee_detail.html", context)


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def _can_view_student(user, student, school=None):
    """Check if user can view specific student"""
    if user.has_perm("core.view_student"):
        return True

    if hasattr(user, "guardian") and user.guardian:
        return GuardianStudent.objects.filter(
            guardian=user.guardian, student=student
        ).exists()

    if hasattr(user, "teacher_profile") and user.teacher_profile:
        return student.school == user.teacher_profile.school

    return False


def _can_post_timeline(user):
    """Check if user can post to timeline"""
    if user.is_staff:
        return True

    if hasattr(user, "teacher_profile") and user.teacher_profile:
        return True

    # Guardians can post to their children's timeline
    if hasattr(user, "guardian") and user.guardian:
        return True

    return False


def _calculate_age(birth_date):
    """Calculate age from birth date"""
    today = timezone.now().date()
    return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
    )


@login_required
def guardian_select_student(request, guardian_id: int, student_id: int):
    """Set guardian's selected student with enhanced feedback"""
    guardian = get_object_or_404(Guardian, pk=guardian_id)
    student = get_object_or_404(Student, pk=student_id)

    # Permission check
    if not (request.user.is_staff or
            (hasattr(request.user, "guardian") and
             request.user.guardian_id == guardian.id)):
        raise PermissionDenied()

    # Ensure relationship exists
    if not GuardianStudent.objects.filter(guardian=guardian, student=student).exists():
        messages.error(request, "هذا الطالب غير مرتبط بهذا الولي.")
        return redirect("dashboard:guardian_detail", guardian_id=guardian.id)

    guardian.selected_student = student
    guardian.save(update_fields=["selected_student", "updated_at"])

    messages.success(
        request,
        f"تم اختيار {student.full_name} كطالب نشط لولي الأمر {guardian}."
    )
    return redirect("dashboard:student_detail", student_id=student.id)


# ==========================================
# AJAX AND API-LIKE VIEWS
# ==========================================

@login_required
def get_classes_by_grade(request):
    """AJAX endpoint to get classes by grade"""
    from django.http import JsonResponse

    grade_id = request.GET.get('grade_id')
    school = getattr(request, 'school', None)

    if not grade_id or not school:
        return JsonResponse({'classes': []})

    classes = SchoolClass.objects.filter(
        grade_id=grade_id,
        school=school,
        is_active=True
    ).values('id', 'name', 'full_name').order_by('name')

    return JsonResponse({'classes': list(classes)})


@login_required
def get_students_by_class(request):
    """AJAX endpoint to get students by class"""
    from django.http import JsonResponse

    class_id = request.GET.get('class_id')
    if not class_id:
        return JsonResponse({'students': []})

    students = Student.objects.filter(
        current_class_id=class_id,
        is_active=True
    ).values('id', 'full_name', 'student_id').order_by('full_name')

    return JsonResponse({'students': list(students)})