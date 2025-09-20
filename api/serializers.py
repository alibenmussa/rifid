# survey/api/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from survey.models import Template, TemplateField, Response as SurveyResponse, AdditionalField
from .utils import is_available_now, next_available_at
from core.models import Student, GuardianStudent, Guardian

User = get_user_model()

class TemplateFieldOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateField
        fields = ("key", "name", "type", "is_required", "is_multiple", "value", "order")


class TemplateListItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    available_now = serializers.SerializerMethodField()
    next_available_at = serializers.SerializerMethodField()

    class Meta:
        model = Template
        fields = ("id", "name", "available_now", "next_available_at")

    def get_available_now(self, obj):
        last_map = (self.context or {}).get("last_map", {})
        return is_available_now(last_map.get(obj.id), obj.default_frequency)

    def get_next_available_at(self, obj):
        last_map = (self.context or {}).get("last_map", {})
        last_dt = last_map.get(obj.id)
        return next_available_at(last_dt, obj.default_frequency) if last_dt else None


class TemplateDetailSerializer(serializers.ModelSerializer):
    fields = serializers.SerializerMethodField(method_name="get_public_fields")
    class Meta:
        model = Template
        fields = ("id", "name", "default_frequency", "fields")
    def get_public_fields(self, obj):
        qs = obj.fields.filter(is_public=True).order_by("order", "id")
        return TemplateFieldOutputSerializer(qs, many=True).data


class ResponseListSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    student_id = serializers.IntegerField(source="student.id", read_only=True)
    student_name = serializers.SerializerMethodField()
    class Meta:
        model = SurveyResponse
        fields = ("id", "template_id", "template_name", "student_id", "student_name", "created_at")
    def get_student_name(self, obj):
        return getattr(obj.student, "full_name", None) or (str(obj.student) if obj.student else None)


class AdditionalFieldSerializer(serializers.ModelSerializer):
    key = serializers.SerializerMethodField()
    class Meta:
        model = AdditionalField
        fields = ("name", "type", "value", "key")
    def get_key(self, obj):
        return obj.field.key if obj.field else None


class ResponseDetailSerializer(serializers.ModelSerializer):
    fields = serializers.SerializerMethodField(method_name="get_answer_fields")
    template_name = serializers.CharField(source="template.name", read_only=True)
    guardian_id = serializers.IntegerField(source="guardian.id", read_only=True)
    student_id = serializers.IntegerField(source="student.id", read_only=True)
    student_name = serializers.SerializerMethodField()
    class Meta:
        model = SurveyResponse
        fields = ("id", "template_id", "template_name", "guardian_id", "student_id",
                  "student_name", "created_at", "fields")
    def get_answer_fields(self, obj):
        qs = obj.fields.select_related("field").order_by("row", "id")
        return AdditionalFieldSerializer(qs, many=True).data
    def get_student_name(self, obj):
        return getattr(obj.student, "full_name", None) or (str(obj.student) if obj.student else None)


class ResponseCreateSerializer(serializers.Serializer):
    template = serializers.PrimaryKeyRelatedField(queryset=Template.objects.all(), required=True)
    fields = serializers.JSONField(required=True)

    def validate(self, attrs):
        request = self.context["request"]
        guardian = request.user.guardian
        student = self.context.get("student")
        if not student:
            raise serializers.ValidationError({"detail": "No selected student for guardian."})

        last = (SurveyResponse.objects
                .filter(template=attrs["template"], guardian=guardian, student=student)
                .order_by("-created_at")
                .values_list("created_at", flat=True)
                .first())

        if not is_available_now(last, attrs["template"].default_frequency):
            raise serializers.ValidationError({"detail": "Survey not available yet for this student."})
        return attrs

    def create(self, validated_data):
        from django.db import transaction
        request = self.context["request"]
        guardian = request.user.guardian
        student = self.context["student"]
        template: Template = validated_data["template"]
        data = validated_data["fields"]
        public_fields = template.fields.filter(is_public=True).order_by("order", "id")

        with transaction.atomic():
            response = SurveyResponse.objects.create(template=template, guardian=guardian, student=student)
            form = template.build_django_form(ticket=response, data=data, user=None, is_public=True, fields=public_fields)
            if not form.is_valid():
                from rest_framework.exceptions import ValidationError
                raise ValidationError(form.errors)
            form.save(commit=True, parent=None)
        return response

from collections.abc import Mapping

# Student selection serializers
class StudentOptionSerializer(serializers.ModelSerializer):
    is_selected = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ("id", "full_name", "first_name", "last_name", "is_selected")

    def get_is_selected(self, obj):
        # Support both model instances and already-serialized dicts/ReturnDicts
        selected_id = (self.context or {}).get("selected_id")
        sid = getattr(obj, "id", None)
        if sid is None and isinstance(obj, Mapping):
            sid = obj.get("id")
        return sid == selected_id

class SelectedStudentOutputSerializer(serializers.Serializer):
    selected = StudentOptionSerializer(allow_null=True)
    options  = StudentOptionSerializer(many=True)
    requires_selection = serializers.BooleanField()
    auto_selected      = serializers.BooleanField()

class StudentSelectInputSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all(), required=True)
    def validate(self, attrs):
        request = self.context["request"]
        guardian = request.user.guardian
        student  = attrs["student"]
        linked = GuardianStudent.objects.filter(guardian=guardian, student=student).exists()
        if not linked:
            raise serializers.ValidationError({"student": "This student is not linked to the guardian."})
        return attrs


class GuardianMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = ("id", "first_name", "last_name", "phone", "email")



class AuthLoginInputSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True, trim_whitespace=False)

class AuthLoginOutputSerializer(serializers.Serializer):
    token = serializers.CharField()
    guardian = GuardianMiniSerializer()
    selected_student = StudentOptionSerializer()
    has_multiple_students = serializers.BooleanField()
    students_count = serializers.IntegerField()


# survey/api/serializers.py - Add these to your existing serializers

class RegistrationValidateCodeSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, max_length=50)

    def validate_code(self, value):
        code = value.strip().upper()
        try:
            guardian = Guardian.objects.get(code=code, user__isnull=True)
        except Guardian.DoesNotExist:
            raise serializers.ValidationError("كود التسجيل غير صحيح أو مستخدم بالفعل.")
        return code


class RegistrationCompleteSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, max_length=50)
    password = serializers.CharField(required=True, min_length=6, write_only=True)
    password_confirm = serializers.CharField(required=True, write_only=True)

    def validate_code(self, value):
        code = value.strip().upper()
        try:
            guardian = Guardian.objects.get(code=code, user__isnull=True)
            # Check if guardian has phone number
            if not guardian.phone:
                raise serializers.ValidationError("لا يوجد رقم هاتف مسجل لهذا الولي. يرجى التواصل مع الإدارة.")
        except Guardian.DoesNotExist:
            raise serializers.ValidationError("كود التسجيل غير صحيح أو مستخدم بالفعل.")
        return code

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "كلمات المرور غير متطابقة."})

        # Check if guardian's phone is already used by another user
        code = attrs['code']
        try:
            guardian = Guardian.objects.get(code=code, user__isnull=True)
            if guardian.phone and User.objects.filter(username=guardian.phone).exists():
                raise serializers.ValidationError({"code": "رقم الهاتف المرتبط بهذا الكود مستخدم بالفعل."})
        except Guardian.DoesNotExist:
            pass  # This will be caught by code validation

        return attrs

    def create(self, validated_data):
        from django.contrib.auth import get_user_model
        from django.db import transaction

        User = get_user_model()
        code = validated_data['code']
        password = validated_data['password']

        with transaction.atomic():
            # Get the guardian
            guardian = Guardian.objects.get(code=code, user__isnull=True)

            # Create user account using guardian's phone as username
            user = User.objects.create_user(
                username=guardian.phone,
                password=password
            )

            # Link guardian to user
            guardian.user = user
            guardian.save(update_fields=['user', 'updated_at'])

        return {'guardian': guardian, 'user': user}


class RegistrationValidateCodeOutputSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    guardian_name = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    students_count = serializers.IntegerField()


class RegistrationCompleteOutputSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    token = serializers.CharField()
    guardian = GuardianMiniSerializer()
    selected_student = StudentOptionSerializer(allow_null=True)
    has_multiple_students = serializers.BooleanField()
    students_count = serializers.IntegerField()


from rest_framework import serializers
from core.models import StudentTimeline, StudentTimelineAttachment

class StudentTimelineAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentTimelineAttachment
        fields = ["id", "file", "is_image"]

class StudentTimelineSerializer(serializers.ModelSerializer):
    # Read-only metadata
    student_id = serializers.IntegerField(read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)
    attachments = StudentTimelineAttachmentSerializer(many=True, read_only=True)

    # Single upload (write-only)
    file = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = StudentTimeline
        fields = [
            "id",
            "student_id",
            "title",
            "note",            # labeled "المحتوى" in the model
            "is_pinned",
            "created_by",
            "created_by_name",
            "created_at",
            "attachments",
            "file",
        ]
        read_only_fields = ["id", "student_id", "created_by", "created_at", "attachments", "created_by_name"]

    def get_created_by_name(self, obj):
        u = obj.created_by
        if not u:
            return None
        return (getattr(u, "get_full_name", lambda: None)() or str(u))

    def validate(self, attrs):
        note = (attrs.get("note") or "").strip()
        has_file = bool(self.initial_data.get("file"))
        if not note and not has_file:
            raise serializers.ValidationError("أدخل المحتوى أو ارفع ملف/صورة واحدة.")
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        guardian = getattr(request.user, "guardian", None)
        student = getattr(guardian, "selected_student", None)
        if not student:
            raise serializers.ValidationError("لا يوجد طالب محدّد. الرجاء اختيار الطالب أولاً.")
        file_obj = self.initial_data.get("file")
        validated_data["student"] = student
        validated_data["created_by"] = request.user
        timeline = super().create(validated_data)
        if file_obj:
            StudentTimelineAttachment.objects.create(timeline=timeline, file=file_obj)
        return timeline

    def update(self, instance, validated_data):
        # Replace the single file if a new one is provided (enforce “single” semantics)
        file_obj = self.initial_data.get("file")
        instance = super().update(instance, validated_data)
        if file_obj:
            instance.attachments.all().delete()
            StudentTimelineAttachment.objects.create(timeline=instance, file=file_obj)
        return instance

