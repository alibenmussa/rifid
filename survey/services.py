from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from survey.models import Template, SurveyPeriod, SurveyDistribution


def convert_form_template_to_json(*, template: Template) -> list:
    form_list: list = []

    for field in template.fields.filter(is_public=True):
        field_dict = {
            "name": field.name,
            "kin": field.kind,
            "type": field.type,
            "value": field.value,
        }
        form_list.append(field_dict)

    return form_list


def calculate_end_date(start_date, frequency):
    """
    Calculate end date based on survey frequency
    """
    if frequency == Template.FREQ_ONCE:
        # For manual surveys, default to 30 days
        return start_date + timedelta(days=30)
    elif frequency == Template.FREQ_WEEKLY:
        return start_date + timedelta(days=7)
    elif frequency == Template.FREQ_MONTHLY:
        return start_date + timedelta(days=30)
    elif frequency == Template.FREQ_QUARTERLY:
        return start_date + timedelta(days=90)
    elif frequency == Template.FREQ_YEARLY:
        return start_date + timedelta(days=365)
    else:
        return start_date + timedelta(days=30)  # Default


def get_survey_recipients(survey, school=None):
    """
    Get list of recipients for a survey based on target_audience and grades
    Returns list of tuples: (user, student) where student can be None
    """
    from accounts.models import User, TeacherProfile, EmployeeProfile
    from core.models import Guardian, Student

    recipients = []

    if survey.target_audience == Template.TARGET_GUARDIANS:
        # Get students based on grades
        if survey.grades.exists():
            # Specific grades selected
            students = Student.objects.filter(
                school_class__grade__in=survey.grades.all(),
                school_class__grade__school=school
            ).distinct()
        else:
            # All grades
            students = Student.objects.filter(
                school_class__grade__school=school
            ).distinct()

        # For each student, get all guardians and create (user, student) tuple
        for student in students:
            guardians = student.guardians.all()
            for guardian in guardians:
                if guardian.user:  # Ensure guardian has a user account
                    recipients.append((guardian.user, student))

    elif survey.target_audience == Template.TARGET_TEACHERS:
        # Get all teachers in the school
        if school:
            teacher_profiles = TeacherProfile.objects.filter(school=school)
            for profile in teacher_profiles:
                recipients.append((profile.user, None))

    elif survey.target_audience == Template.TARGET_EMPLOYEES:
        # Get all employees in the school
        if school:
            employee_profiles = EmployeeProfile.objects.filter(school=school)
            for profile in employee_profiles:
                recipients.append((profile.user, None))

    elif survey.target_audience == Template.TARGET_ALL:
        # Get all users in the school (guardians, teachers, employees)
        if school:
            # Teachers
            teacher_profiles = TeacherProfile.objects.filter(school=school)
            for profile in teacher_profiles:
                recipients.append((profile.user, None))

            # Employees
            employee_profiles = EmployeeProfile.objects.filter(school=school)
            for profile in employee_profiles:
                recipients.append((profile.user, None))

            # Guardians - get unique guardians
            students = Student.objects.filter(school_class__grade__school=school).distinct()
            seen_guardians = set()
            for student in students:
                guardians = student.guardians.all()
                for guardian in guardians:
                    if guardian.user and guardian.id not in seen_guardians:
                        recipients.append((guardian.user, None))
                        seen_guardians.add(guardian.id)

    return recipients


@transaction.atomic
def create_survey_distribution(survey, school, sent_by, start_date=None):
    """
    Create a new survey period and distributions for all eligible recipients

    Args:
        survey: Template instance
        school: School instance (None for built-in surveys sent globally)
        sent_by: User who is sending this survey
        start_date: Optional start date (defaults to today)

    Returns:
        tuple: (SurveyPeriod, list of created SurveyDistribution)
    """
    if start_date is None:
        start_date = timezone.now().date()

    # Calculate end date
    end_date = calculate_end_date(start_date, survey.send_frequency)

    # Create survey period
    period = SurveyPeriod.objects.create(
        survey=survey,
        start_date=start_date,
        end_date=end_date,
        is_active=True,
        school=school,
        sent_by=sent_by
    )

    # Get recipients
    recipients = get_survey_recipients(survey, school)

    # Create distributions
    distributions = []
    for user, student in recipients:
        dist = SurveyDistribution(
            period=period,
            survey=survey,
            user=user,
            student=student,
            school=school
        )
        distributions.append(dist)

    # Bulk create for performance
    SurveyDistribution.objects.bulk_create(distributions, ignore_conflicts=True)

    return period, distributions


def send_survey_notifications(distributions):
    """
    Send FCM notifications for survey distributions
    Uses Firebase Cloud Messaging to notify users about new surveys
    """
    import logging
    logger = logging.getLogger(__name__)

    # Try to import FCM library
    try:
        from firebase_admin import messaging
        import firebase_admin
    except ImportError:
        logger.warning("Firebase Admin SDK not installed. Skipping FCM notifications.")
        return

    # Check if Firebase is initialized
    try:
        firebase_admin.get_app()
    except ValueError:
        logger.warning("Firebase not initialized. Skipping FCM notifications.")
        return

    # Group distributions by user to batch notifications
    user_distributions = {}
    for dist in distributions:
        if dist.user.fcm_token:
            if dist.user.id not in user_distributions:
                user_distributions[dist.user.id] = []
            user_distributions[dist.user.id].append(dist)

    sent_count = 0
    failed_count = 0

    for user_id, user_dists in user_distributions.items():
        user = user_dists[0].user
        survey = user_dists[0].survey

        # Determine notification body based on count
        if len(user_dists) == 1:
            dist = user_dists[0]
            if dist.student:
                body = f"استطلاع جديد عن الطالب {dist.student.first_name}"
            else:
                body = f"استطلاع جديد: {survey.name}"
        else:
            body = f"لديك {len(user_dists)} استطلاع جديد"

        # Create notification
        message = messaging.Message(
            notification=messaging.Notification(
                title="استطلاع جديد",
                body=body,
            ),
            data={
                'type': 'survey',
                'survey_id': str(survey.id),
                'distribution_count': str(len(user_dists)),
                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
            },
            token=user.fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    icon='ic_notification',
                    color='#FF6B35',
                    sound='default',
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=len(user_dists),
                    )
                )
            )
        )

        try:
            response = messaging.send(message)
            sent_count += 1
            logger.info(f"FCM notification sent to user {user.id}: {response}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send FCM notification to user {user.id}: {e}")

    logger.info(f"FCM notifications sent: {sent_count} succeeded, {failed_count} failed")

