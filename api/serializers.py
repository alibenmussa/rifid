# api/serializers.py - Professional and Structured Serializers
from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.utils import timezone
from collections.abc import Mapping

from survey.models import Template, TemplateField, Response as SurveyResponse, AdditionalField
from core.models import (
    School, AcademicYear, Grade, SchoolClass,
    Student, Guardian, GuardianStudent,
    StudentTimeline, StudentTimelineAttachment
)
from .utils import is_available_now, next_available_at

User = get_user_model()


# ==========================================
# BASE AND UTILITY SERIALIZERS
# ==========================================

class TimestampMixin(serializers.Serializer):
    """Mixin for common timestamp fields"""
    created_at = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    updated_at = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')


class SchoolContextMixin:
    """Mixin to filter querysets by school context"""

    def get_school_from_context(self):
        """Get school from request context"""
        request = self.context.get('request')
        if request and hasattr(request.user, 'guardian'):
            return request.user.guardian.school
        elif request and hasattr(request.user, 'teacher_profile'):
            return request.user.teacher_profile.school
        return None


# ==========================================
# SCHOOL STRUCTURE SERIALIZERS
# ==========================================

class SchoolBasicSerializer(serializers.ModelSerializer):
    """Basic school information"""

    class Meta:
        model = School
        fields = [
            'id', 'name', 'code', 'address', 'phone',
            'email', 'principal_name', 'is_active'
        ]
        read_only_fields = ['id', 'code']


class AcademicYearSerializer(serializers.ModelSerializer, TimestampMixin):
    """Academic year serializer"""

    is_active = serializers.SerializerMethodField()
    duration_days = serializers.SerializerMethodField()

    class Meta:
        model = AcademicYear
        fields = [
            'id', 'name', 'start_date', 'end_date', 'is_current',
            'is_active', 'duration_days', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id']

    def get_is_active(self, obj):
        """Check if academic year is currently active"""
        now = timezone.now().date()
        return obj.start_date <= now <= obj.end_date

    def get_duration_days(self, obj):
        """Calculate academic year duration in days"""
        return (obj.end_date - obj.start_date).days


class GradeSerializer(serializers.ModelSerializer, TimestampMixin):
    """Grade/level serializer"""

    grade_type_display = serializers.CharField(source='get_grade_type_display', read_only=True)
    classes_count = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Grade
        fields = [
            'id', 'name', 'level', 'grade_type', 'grade_type_display',
            'description', 'is_active', 'classes_count', 'students_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'grade_type_display', 'classes_count', 'students_count']

    def get_classes_count(self, obj):
        """Count active classes in this grade"""
        return obj.classes.filter(is_active=True).count()

    def get_students_count(self, obj):
        """Count active students in this grade"""
        return Student.objects.filter(
            current_class__grade=obj,
            is_active=True
        ).count()


class SchoolClassSerializer(serializers.ModelSerializer, TimestampMixin):
    """School class serializer"""

    grade_name = serializers.CharField(source='grade.name', read_only=True)
    grade_level = serializers.IntegerField(source='grade.level', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    class_teacher_name = serializers.SerializerMethodField()
    student_count = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()

    class Meta:
        model = SchoolClass
        fields = [
            'id', 'name', 'section', 'full_name', 'capacity',
            'grade', 'grade_name', 'grade_level',
            'academic_year', 'academic_year_name',
            'class_teacher', 'class_teacher_name',
            'student_count', 'is_full', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'full_name', 'grade_name', 'grade_level',
            'academic_year_name', 'student_count', 'is_full'
        ]

    def get_class_teacher_name(self, obj):
        """Get class teacher's full name"""
        if obj.class_teacher:
            return obj.class_teacher.get_full_name() or obj.class_teacher.username
        return None


# ==========================================
# USER AND AUTHENTICATION SERIALIZERS
# ==========================================

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user information"""

    full_name = serializers.SerializerMethodField()
    user_type_display = serializers.CharField(source='get_user_type_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'full_name', 'user_type', 'user_type_display', 'phone', 'avatar'
        ]
        read_only_fields = ['id', 'full_name', 'user_type_display']

    def get_full_name(self, obj):
        """Get user's full name"""
        return obj.get_display_name()


class GuardianSerializer(serializers.ModelSerializer, TimestampMixin):
    """Complete guardian information"""

    full_name = serializers.SerializerMethodField()
    school_name = serializers.CharField(source='school.name', read_only=True)
    user_info = UserBasicSerializer(source='user', read_only=True)
    children_count = serializers.SerializerMethodField()
    school = SchoolBasicSerializer(read_only=True)

    class Meta:
        model = Guardian
        fields = [
            'id', 'first_name', 'last_name', 'full_name',
            'phone', 'email', 'nid', 'address',
            'school', 'school_name', 'code',
            'user_info', 'children_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'code', 'full_name', 'school_name',
            'user_info', 'children_count'
        ]

    def get_full_name(self, obj):
        """Get guardian's full name"""
        return str(obj)

    def get_children_count(self, obj):
        """Count guardian's children"""
        return obj.guardianstudent_set.filter(student__is_active=True).count()


class StudentSerializer(serializers.ModelSerializer, TimestampMixin):
    """Complete student information"""

    school_name = serializers.CharField(source='school.name', read_only=True)
    current_class_info = SchoolClassSerializer(source='current_class', read_only=True)
    current_grade = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    guardians_info = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'full_name',
            'first_name', 'second_name', 'third_name', 'fourth_name', 'last_name',
            'sex', 'date_of_birth', 'place_of_birth', 'age',
            'phone', 'alternative_phone', 'email', 'nid', 'address',
            'school', 'school_name',
            'current_class', 'current_class_info', 'current_grade',
            'enrollment_date', 'graduation_date', 'is_active',
            'guardians_info', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'student_id', 'full_name', 'school_name',
            'current_class_info', 'current_grade', 'age', 'guardians_info'
        ]

    def get_current_grade(self, obj):
        """Get current grade information"""
        if obj.current_class and obj.current_class.grade:
            grade = obj.current_class.grade
            return {
                'id': grade.id,
                'name': grade.name,
                'level': grade.level,
                'grade_type': grade.grade_type,
                'grade_type_display': grade.get_grade_type_display()
            }
        return None

    def get_age(self, obj):
        """Calculate student's age"""
        if obj.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.date_of_birth.year - (
                    (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
            )
        return None

    def get_guardians_info(self, obj):
        """Get student's guardians information"""
        relations = GuardianStudent.objects.filter(student=obj).select_related('guardian')
        return [
            {
                'id': rel.guardian.id,
                'name': str(rel.guardian),
                'relationship': rel.get_relationship_display(),
                'phone': rel.guardian.phone,
                'is_primary': rel.is_primary,
                'is_emergency_contact': rel.is_emergency_contact
            }
            for rel in relations
        ]


class StudentBasicSerializer(serializers.ModelSerializer):
    """Basic student information for lists"""

    current_class_name = serializers.CharField(source='current_class.full_name', read_only=True)
    age = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'full_name', 'first_name', 'last_name',
            'sex', 'date_of_birth', 'age', 'phone',
            'current_class', 'current_class_name', 'is_active'
        ]
        read_only_fields = ['id', 'student_id', 'full_name', 'current_class_name', 'age']

    def get_age(self, obj):
        """Calculate student's age"""
        if obj.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.date_of_birth.year - (
                    (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
            )
        return None


# ==========================================
# STUDENT SELECTION SERIALIZERS
# ==========================================

class StudentOptionSerializer(serializers.ModelSerializer):
    """Student option for guardian selection"""

    is_selected = serializers.SerializerMethodField()
    current_class_name = serializers.CharField(source='current_class.full_name', read_only=True)
    school = SchoolBasicSerializer(read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'full_name', 'first_name', 'last_name',
            'current_class_name', 'school', 'is_selected'
        ]
        read_only_fields = ['id', 'full_name', 'current_class_name', 'school', 'is_selected']

    def get_is_selected(self, obj):
        """Check if student is currently selected"""
        selected_id = (self.context or {}).get("selected_id")
        sid = getattr(obj, "id", None)
        if sid is None and isinstance(obj, Mapping):
            sid = obj.get("id")
        return sid == selected_id


class StudentSelectInputSerializer(serializers.Serializer):
    """Input serializer for student selection"""

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all(), required=True)

    def validate(self, attrs):
        request = self.context["request"]
        guardian = request.user.guardian
        student = attrs["student"]

        # Ensure student belongs to guardian's school
        if student.school_id != guardian.school_id:
            raise serializers.ValidationError({
                "student": "هذا الطالب لا ينتمي لنفس المدرسة."
            })

        # Ensure guardian-student relationship exists
        if not GuardianStudent.objects.filter(guardian=guardian, student=student).exists():
            raise serializers.ValidationError({
                "student": "هذا الطالب غير مرتبط بولي الأمر."
            })

        return attrs


class SelectedStudentOutputSerializer(serializers.Serializer):
    """Output for student selection operations"""

    selected = StudentOptionSerializer(allow_null=True)
    options = StudentOptionSerializer(many=True)
    requires_selection = serializers.BooleanField()
    auto_selected = serializers.BooleanField()


# ==========================================
# GUARDIAN-STUDENT RELATIONSHIP SERIALIZERS
# ==========================================

class GuardianStudentSerializer(serializers.ModelSerializer, TimestampMixin):
    """Guardian-Student relationship serializer"""

    guardian_name = serializers.CharField(source='guardian.full_name', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    relationship_display = serializers.CharField(source='get_relationship_display', read_only=True)

    class Meta:
        model = GuardianStudent
        fields = [
            'id', 'guardian', 'guardian_name', 'student', 'student_name',
            'relationship', 'relationship_display', 'is_primary',
            'is_emergency_contact', 'can_pickup', 'can_receive_notifications',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'guardian_name', 'student_name', 'relationship_display'
        ]


# ==========================================
# EMPLOYEE AND PROFILE SERIALIZERS
# ==========================================

class EmployeeProfileSerializer(serializers.ModelSerializer, TimestampMixin):
    """Employee profile information"""

    user_info = UserBasicSerializer(source='user', read_only=True)
    school = SchoolBasicSerializer(read_only=True)
    position_display = serializers.CharField(source='get_position_display', read_only=True)

    class Meta:
        from accounts.models import EmployeeProfile
        model = EmployeeProfile
        fields = [
            'id', 'user_info', 'school', 'employee_id',
            'position', 'position_display', 'department',
            'hire_date', 'is_active',
            'can_manage_students', 'can_manage_teachers', 'can_view_reports',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user_info', 'school', 'position_display'
        ]


class ProfileSerializer(serializers.Serializer):
    """Unified profile serializer for Guardian and Employee"""

    user = UserBasicSerializer(read_only=True)
    school = SchoolBasicSerializer(read_only=True)
    user_type = serializers.CharField(read_only=True)
    profile_data = serializers.SerializerMethodField()

    def get_profile_data(self, obj):
        """Get profile-specific data based on user type"""
        user = obj.get('user')
        user_type = obj.get('user_type')

        if user_type == 'guardian' and hasattr(user, 'guardian'):
            return GuardianSerializer(user.guardian, context=self.context).data
        elif user_type == 'employee' and hasattr(user, 'employee_profile'):
            return EmployeeProfileSerializer(user.employee_profile, context=self.context).data
        elif user_type == 'teacher' and hasattr(user, 'teacher_profile'):
            from accounts.models import TeacherProfile
            teacher = user.teacher_profile
            return {
                'id': teacher.id,
                'school': SchoolBasicSerializer(teacher.school).data,
                'employee_id': teacher.employee_id,
                'subject': teacher.subject,
                'qualification': teacher.qualification,
                'experience_years': teacher.experience_years,
                'is_class_teacher': teacher.is_class_teacher,
                'is_active': teacher.is_active
            }
        return None


class StudentListSerializerForEmployee(serializers.ModelSerializer):
    """Student list serializer for employee endpoint"""

    current_class_name = serializers.CharField(source='current_class.full_name', read_only=True)
    current_grade = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    guardians_count = serializers.SerializerMethodField()
    timeline_count = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'full_name',
            'sex', 'date_of_birth', 'age',
            'current_class', 'current_class_name', 'current_grade',
            'guardians_count', 'timeline_count',
            'is_active'
        ]
        read_only_fields = fields

    def get_current_grade(self, obj):
        """Get current grade info"""
        if obj.current_class and obj.current_class.grade:
            grade = obj.current_class.grade
            return {
                'id': grade.id,
                'name': grade.name,
                'level': grade.level,
                'grade_type': grade.grade_type
            }
        return None

    def get_age(self, obj):
        """Calculate age"""
        if obj.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.date_of_birth.year - (
                (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
            )
        return None

    def get_guardians_count(self, obj):
        """Count guardians"""
        return obj.guardians.count()

    def get_timeline_count(self, obj):
        """Count timeline entries"""
        return obj.timeline.count()


# ==========================================
# TIMELINE SERIALIZERS
# ==========================================

class StudentTimelineAttachmentSerializer(serializers.ModelSerializer):
    """Timeline attachment serializer for read operations"""

    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = StudentTimelineAttachment
        fields = [
            'id', 'file_url', 'file_name', 'file_size',
            'file_size_display', 'is_image', 'created_at'
        ]
        read_only_fields = ['id', 'file_url', 'file_name', 'file_size_display', 'is_image', 'created_at']

    def get_file_url(self, obj):
        """Get full file URL"""
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_name(self, obj):
        """Get file name without path"""
        if obj.file:
            return obj.file.name.split('/')[-1]
        return None

    def get_file_size_display(self, obj):
        """Human readable file size"""
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return None


class StudentTimelineListSerializer(serializers.ModelSerializer):
    """Simplified timeline serializer for list view"""

    created_by_info = UserBasicSerializer(source='created_by', read_only=True)
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    has_attachments = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = StudentTimeline
        fields = [
            'id', 'title', 'excerpt', 'content_type', 'content_type_display',
            'is_pinned', 'has_attachments', 'attachment_count',
            'created_by_info', 'created_at'
        ]
        read_only_fields = fields

    def get_has_attachments(self, obj):
        """Check if timeline has attachments"""
        return obj.attachments.exists()

    def get_attachment_count(self, obj):
        """Count attachments"""
        return obj.attachments.count()

    def get_excerpt(self, obj):
        """Get note excerpt (first 100 chars)"""
        if obj.note:
            return obj.note[:100] + "..." if len(obj.note) > 100 else obj.note
        return ""


class StudentTimelineDetailSerializer(serializers.ModelSerializer, TimestampMixin):
    """Detailed timeline serializer for retrieve view"""

    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id = serializers.IntegerField(source='student.id', read_only=True)
    created_by_info = UserBasicSerializer(source='created_by', read_only=True)
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    attachments = StudentTimelineAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = StudentTimeline
        fields = [
            'id', 'student_id', 'student_name',
            'title', 'note',
            'content_type', 'content_type_display',
            'is_visible_to_guardian', 'is_visible_to_student',
            'is_pinned',
            'created_by_info',
            'attachments',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class StudentTimelineCreateSerializer(serializers.ModelSerializer):
    """Timeline serializer for create operations"""

    # Write-only file upload (accepts single or multiple files)
    file = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = StudentTimeline
        fields = [
            'title', 'note', 'content_type',
            'is_visible_to_guardian', 'is_visible_to_student',
            'is_pinned', 'file'
        ]

    def validate(self, attrs):
        """Validate timeline entry - must have note or file"""
        note = (attrs.get("note") or "").strip()
        has_file = bool(self.initial_data.get("file"))

        if not note and not has_file:
            raise serializers.ValidationError({
                "detail": "يجب إدخال المحتوى أو رفع ملف/صورة."
            })

        return attrs

    def create(self, validated_data):
        """Create timeline entry with file attachment"""
        from django.db import transaction

        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context required.")

        # Check if student is provided in context (for Employee)
        student = self.context.get("student")

        # If not, try to get from guardian's selected_student
        if not student:
            guardian = getattr(request.user, "guardian", None)
            student = getattr(guardian, "selected_student", None) if guardian else None

        if not student:
            raise serializers.ValidationError({
                "detail": "لا يوجد طالب محدّد. الرجاء اختيار الطالب أولاً."
            })

        # Get file from initial data
        file_obj = self.initial_data.get("file")

        # Remove file from validated_data (not a model field)
        validated_data.pop('file', None)

        with transaction.atomic():
            # Set student and creator
            validated_data["student"] = student
            validated_data["created_by"] = request.user

            # Create timeline entry
            timeline = StudentTimeline.objects.create(**validated_data)

            # Create attachment if file provided
            if file_obj:
                StudentTimelineAttachment.objects.create(
                    timeline=timeline,
                    file=file_obj
                )

        return timeline


class StudentTimelineUpdateSerializer(serializers.ModelSerializer):
    """Timeline serializer for update operations"""

    # Write-only file upload
    file = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = StudentTimeline
        fields = [
            'title', 'note', 'content_type',
            'is_visible_to_guardian', 'is_visible_to_student',
            'is_pinned', 'file'
        ]

    def validate(self, attrs):
        """Validate timeline update"""
        # Check if we're updating note
        note = attrs.get("note")
        if note is not None:
            note = note.strip()
            if not note and not self.instance.attachments.exists():
                has_file = bool(self.initial_data.get("file"))
                if not has_file:
                    raise serializers.ValidationError({
                        "note": "لا يمكن حذف المحتوى إذا لم يكن هناك مرفقات."
                    })

        return attrs

    def update(self, instance, validated_data):
        """Update timeline entry and optionally replace file"""
        from django.db import transaction

        file_obj = self.initial_data.get("file")

        # Remove file from validated_data (not a model field)
        validated_data.pop('file', None)

        with transaction.atomic():
            # Update timeline fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Replace file if new one provided
            if file_obj:
                # Delete existing attachments
                instance.attachments.all().delete()
                # Create new attachment
                StudentTimelineAttachment.objects.create(
                    timeline=instance,
                    file=file_obj
                )

        return instance


# ==========================================
# SURVEY SERIALIZERS
# ==========================================

class TemplateFieldOutputSerializer(serializers.ModelSerializer):
    """Template field for survey display"""

    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = TemplateField
        fields = [
            'key', 'name', 'type', 'type_display', 'is_required',
            'is_multiple', 'value', 'order'
        ]
        read_only_fields = ['key', 'type_display']


class TemplateListItemSerializer(serializers.ModelSerializer):
    """Template item for survey lists"""

    available_now = serializers.SerializerMethodField()
    next_available_at = serializers.SerializerMethodField()
    frequency_display = serializers.CharField(source='get_default_frequency_display', read_only=True)

    class Meta:
        model = Template
        fields = [
            'id', 'name', 'default_frequency', 'frequency_display',
            'available_now', 'next_available_at'
        ]
        read_only_fields = ['id', 'frequency_display']

    def get_available_now(self, obj):
        """Check if survey is available now"""
        last_map = (self.context or {}).get("last_map", {})
        return is_available_now(last_map.get(obj.id), obj.default_frequency)

    def get_next_available_at(self, obj):
        """Get next available date"""
        last_map = (self.context or {}).get("last_map", {})
        last_dt = last_map.get(obj.id)
        return next_available_at(last_dt, obj.default_frequency) if last_dt else None


class TemplateDetailSerializer(serializers.ModelSerializer):
    """Detailed template information"""

    # Renamed 'fields' to 'template_fields' to avoid conflict
    template_fields = serializers.SerializerMethodField()
    frequency_display = serializers.CharField(source='get_default_frequency_display', read_only=True)

    class Meta:
        model = Template
        fields = [
            'id', 'name', 'default_frequency', 'frequency_display', 'template_fields'
            # Changed 'fields' to 'template_fields'
        ]
        read_only_fields = ['id', 'frequency_display']

    def get_template_fields(self, obj):  # Renamed from get_fields to get_template_fields
        """Get public template fields"""
        qs = obj.fields.filter(is_public=True).order_by("order", "id")
        return TemplateFieldOutputSerializer(qs, many=True).data


class AdditionalFieldSerializer(serializers.ModelSerializer):
    """Survey response field serializer"""

    key = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = AdditionalField
        fields = ['name', 'type', 'type_display', 'value', 'key']
        read_only_fields = ['type_display', 'key']

    def get_key(self, obj):
        """Get field key"""
        return obj.field.key if obj.field else None


class ResponseListSerializer(serializers.ModelSerializer, TimestampMixin):
    """Survey response list serializer"""

    template_name = serializers.CharField(source="template.name", read_only=True)
    student_name = serializers.SerializerMethodField()
    guardian_name = serializers.CharField(source="guardian.full_name", read_only=True)

    class Meta:
        model = SurveyResponse
        fields = [
            'id', 'template', 'template_name',
            'student', 'student_name', 'guardian_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'template_name', 'student_name', 'guardian_name']

    def get_student_name(self, obj):
        """Get student's full name"""
        return getattr(obj.student, "full_name", None) or str(obj.student) if obj.student else None


class ResponseDetailSerializer(serializers.ModelSerializer, TimestampMixin):
    """Detailed survey response serializer"""

    # Renamed 'fields' to 'response_fields' to avoid conflict with DRF's internal get_fields()
    response_fields = serializers.SerializerMethodField()
    template_name = serializers.CharField(source="template.name", read_only=True)
    student_info = StudentBasicSerializer(source="student", read_only=True)
    guardian_info = serializers.SerializerMethodField()

    class Meta:
        model = SurveyResponse
        fields = [
            'id', 'template', 'template_name',
            'student_info', 'guardian_info',
            'response_fields', 'created_at', 'updated_at'  # Changed 'fields' to 'response_fields'
        ]
        read_only_fields = [
            'id', 'template_name', 'student_info', 'guardian_info', 'response_fields'
        ]

    def get_response_fields(self, obj):  # Renamed from get_fields to get_response_fields
        """Get response fields"""
        qs = obj.fields.select_related("field").order_by("row", "id")
        return AdditionalFieldSerializer(qs, many=True).data

    def get_guardian_info(self, obj):
        """Get guardian basic info"""
        if obj.guardian:
            return {
                'id': obj.guardian.id,
                'name': str(obj.guardian),
                'phone': obj.guardian.phone
            }
        return None


class ResponseCreateSerializer(serializers.Serializer):
    """Survey response creation serializer"""

    template = serializers.PrimaryKeyRelatedField(queryset=Template.objects.all(), required=True)
    fields = serializers.JSONField(required=True)

    def validate_fields(self, value):
        """Validate fields data"""
        print(f"DEBUG validate_fields: {value} (type: {type(value)})")
        return value

    def validate_template(self, value):
        """Validate that the template is accessible to the guardian's school"""
        request = self.context.get("request")
        if not request or not hasattr(request.user, 'guardian'):
            raise serializers.ValidationError("المستخدم غير مصرح له.")

        guardian = request.user.guardian
        school = guardian.school

        # Check if template is either for this school or global
        if value.school and value.school != school:
            raise serializers.ValidationError("هذا الاستبيان غير متاح لمدرستك.")

        return value

    def validate(self, attrs):
        """Validate survey response creation"""
        request = self.context["request"]
        guardian = request.user.guardian
        student = self.context.get("student")

        if not student:
            raise serializers.ValidationError({
                "detail": "لا يوجد طالب محدد لولي الأمر."
            })

        # Check survey availability
        last_response = (
            SurveyResponse.objects
            .filter(template=attrs["template"], guardian=guardian, student=student)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )

        if not is_available_now(last_response, attrs["template"].default_frequency):
            raise serializers.ValidationError({
                "detail": "الاستبيان غير متاح حالياً لهذا الطالب."
            })

        return attrs

    def create(self, validated_data):
        """Create survey response"""
        from django.db import transaction

        request = self.context["request"]
        guardian = request.user.guardian
        student = self.context["student"]
        template = validated_data["template"]
        data = validated_data["fields"]

        print(f"DEBUG: RECEIVED DATA TYPE: {type(data)}")
        print(f"DEBUG: RECEIVED DATA: {data}")
        for key, value in data.items():
            print(f"DEBUG: Field {key} = {value} (type: {type(value)})")

        # Get public fields
        public_fields = template.fields.filter(is_public=True).order_by("order", "id")

        with transaction.atomic():
            # Create response
            response = SurveyResponse.objects.create(
                template=template,
                guardian=guardian,
                student=student
            )

            # Build and validate form
            form = template.build_django_form(
                ticket=response,
                data=data,
                user=request.user,
                is_public=True,
                fields=public_fields
            )

            print(f"DEBUG: FORM ERRORS: {form.errors}")
            print(f"DEBUG: FORM IS VALID: {form.is_valid()}")

            if not form.is_valid():
                raise serializers.ValidationError(form.errors)

            # Save form data
            form.save(commit=True, parent=None)

        return response


# ==========================================
# AUTHENTICATION SERIALIZERS
# ==========================================

class AuthLoginInputSerializer(serializers.Serializer):
    """Login input serializer"""

    username = serializers.CharField(
        required=True,
        help_text="رقم الهاتف أو اسم المستخدم"
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        trim_whitespace=False,
        help_text="كلمة المرور"
    )


class AuthLoginOutputSerializer(serializers.Serializer):
    """Login output serializer"""

    token = serializers.CharField(help_text="رمز المصادقة")
    guardian = GuardianSerializer(help_text="معلومات ولي الأمر")
    selected_student = serializers.SerializerMethodField(help_text="الطالب المختار حالياً")
    has_multiple_students = serializers.BooleanField(help_text="يملك أكثر من طالب؟")
    students_count = serializers.IntegerField(help_text="عدد الأطفال")

    def get_selected_student(self, obj):
        """Serialize selected student with context"""
        student = obj.get('selected_student')
        if student:
            return StudentOptionSerializer(
                student,
                context={'selected_id': student.id}
            ).data
        return None


class RegistrationValidateCodeSerializer(serializers.Serializer):
    """Registration code validation serializer"""

    code = serializers.CharField(
        required=True,
        max_length=50,
        help_text="كود التسجيل المستلم من المدرسة"
    )

    def validate_code(self, value):
        """Validate registration code"""
        code = value.strip().upper()
        try:
            guardian = Guardian.objects.get(code=code, user__isnull=True)
            if not guardian.phone:
                raise serializers.ValidationError(
                    "لا يوجد رقم هاتف مسجل لهذا الولي. يرجى التواصل مع الإدارة"
                )
        except Guardian.DoesNotExist:
            raise serializers.ValidationError(
                "كود التسجيل غير صحيح أو مستخدم بالفعل."
            )
        return code


class RegistrationValidateCodeOutputSerializer(serializers.Serializer):
    """Registration code validation output"""

    valid = serializers.BooleanField(help_text="هل الكود صالح؟")
    guardian_name = serializers.CharField(
        allow_null=True,
        help_text="اسم ولي الأمر"
    )
    phone = serializers.CharField(
        allow_null=True,
        help_text="رقم الهاتف المسجل"
    )
    students_count = serializers.IntegerField(help_text="عدد الأطفال")
    school_name = serializers.CharField(
        allow_null=True,
        help_text="اسم المدرسة"
    )


class RegistrationCompleteSerializer(serializers.Serializer):
    """Complete registration serializer"""

    code = serializers.CharField(
        required=True,
        max_length=50,
        help_text="كود التسجيل"
    )
    password = serializers.CharField(
        required=True,
        min_length=6,
        write_only=True,
        help_text="كلمة المرور الجديدة"
    )
    password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        help_text="تأكيد كلمة المرور"
    )

    def validate_code(self, value):
        """Validate registration code"""
        code = value.strip().upper()
        try:
            guardian = Guardian.objects.get(code=code, user__isnull=True)
            if not guardian.phone:
                raise serializers.ValidationError(
                    "لا يوجد رقم هاتف مسجل لهذا الولي. يرجى التواصل مع الإدارة."
                )
        except Guardian.DoesNotExist:
            raise serializers.ValidationError(
                "كود التسجيل غير صحيح أو مستخدم بالفعل."
            )
        return code

    def validate(self, attrs):
        """Cross-field validation"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "كلمات المرور غير متطابقة."
            })

        # Check if phone is already used
        code = attrs['code']
        try:
            guardian = Guardian.objects.get(code=code, user__isnull=True)
            if guardian.phone and User.objects.filter(username=guardian.phone).exists():
                raise serializers.ValidationError({
                    "code": "رقم الهاتف المرتبط بهذا الكود مستخدم بالفعل."
                })
        except Guardian.DoesNotExist:
            pass

        return attrs

    def create(self, validated_data):
        """Complete user registration"""
        from django.db import transaction

        code = validated_data['code']
        password = validated_data['password']

        with transaction.atomic():
            # Get guardian
            guardian = Guardian.objects.get(code=code, user__isnull=True)

            # Create user account
            user = User.objects.create_user(
                username=guardian.phone,
                password=password
            )

            # Link guardian to user
            guardian.user = user
            guardian.save(update_fields=['user', 'updated_at'])

        return {'guardian': guardian, 'user': user}


class RegistrationCompleteOutputSerializer(serializers.Serializer):
    """Registration completion output"""

    success = serializers.BooleanField(help_text="نجح التسجيل؟")
    message = serializers.CharField(help_text="رسالة النتيجة")
    token = serializers.CharField(help_text="رمز المصادقة")
    guardian = GuardianSerializer(help_text="معلومات ولي الأمر")
    selected_student = serializers.SerializerMethodField(help_text="الطالب المختار")
    has_multiple_students = serializers.BooleanField(help_text="يملك أكثر من طالب؟")
    students_count = serializers.IntegerField(help_text="عدد الأطفال")

    def get_selected_student(self, obj):
        """Serialize selected student with context"""
        student = obj.get('selected_student')
        if student:
            return StudentOptionSerializer(
                student,
                context={'selected_id': student.id}
            ).data
        return None
