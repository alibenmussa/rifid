"""
Management command to process recurring surveys
Run daily via cron to create new survey periods for recurring surveys

Usage:
    python manage.py process_recurring_surveys

Add to crontab:
    0 1 * * * cd /path/to/project && /path/to/venv/bin/python manage.py process_recurring_surveys
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from survey.models import Template, SurveyPeriod
from survey.services import create_survey_distribution, send_survey_notifications
from core.models import School


class Command(BaseCommand):
    help = 'Process recurring surveys and create new periods when needed'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually creating periods',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()

        self.stdout.write(self.style.SUCCESS(f'Processing recurring surveys for {today}'))

        # Get all active recurring surveys (not "once")
        recurring_surveys = Template.objects.exclude(
            send_frequency=Template.FREQ_ONCE
        ).filter(
            type=Template.FOOD
        )

        total_processed = 0
        total_created = 0
        total_distributions = 0

        for survey in recurring_surveys:
            total_processed += 1

            # Check if this survey needs a new period
            should_create, reason = self.should_create_new_period(survey, today)

            if should_create:
                self.stdout.write(
                    self.style.WARNING(f'  → {survey.name} needs new period: {reason}')
                )

                if not dry_run:
                    # Determine schools to send to
                    if survey.is_builtin:
                        # Send to all schools
                        schools = School.objects.filter(is_active=True)
                    else:
                        # Send to specific school
                        schools = [survey.school] if survey.school else []

                    for school in schools:
                        try:
                            period, distributions = create_survey_distribution(
                                survey=survey,
                                school=school,
                                sent_by=survey.created_by,  # System-generated
                                start_date=today
                            )

                            dist_count = len(distributions)
                            total_distributions += dist_count

                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'    ✓ Created period for {school.name if school else "Global"}: '
                                    f'{dist_count} distributions'
                                )
                            )

                            # Send notifications
                            send_survey_notifications(distributions)

                            total_created += 1

                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'    ✗ Error creating period for {school.name}: {e}')
                            )
                else:
                    self.stdout.write(
                        self.style.NOTICE(f'    (Dry run - skipping)')
                    )
            else:
                self.stdout.write(
                    f'  • {survey.name}: {reason}'
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(f'  Surveys processed: {total_processed}')
        self.stdout.write(f'  New periods created: {total_created}')
        self.stdout.write(f'  Total distributions: {total_distributions}')
        if dry_run:
            self.stdout.write(self.style.WARNING('  (DRY RUN - No changes made)'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

    def should_create_new_period(self, survey, today):
        """
        Determine if a new period should be created for this survey

        Returns:
            tuple: (bool, str) - (should_create, reason)
        """
        # Get latest period for this survey
        latest_period = survey.periods.order_by('-start_date').first()

        if not latest_period:
            return True, "No existing period found"

        # Check if current period is expired
        if not latest_period.is_expired:
            days_remaining = (latest_period.end_date - today).days
            return False, f"Current period still active ({days_remaining} days remaining)"

        # Period is expired, check if we should create new one based on frequency
        if survey.send_frequency == Template.FREQ_WEEKLY:
            # Create new period on Monday
            if today.weekday() == 0:  # Monday
                return True, "New week started (Monday)"
            return False, f"Waiting for Monday (today is {today.strftime('%A')})"

        elif survey.send_frequency == Template.FREQ_MONTHLY:
            # Create new period on 1st of month
            if today.day == 1:
                return True, "New month started"
            return False, f"Waiting for 1st of month (today is day {today.day})"

        elif survey.send_frequency == Template.FREQ_QUARTERLY:
            # Create new period on 1st of quarter (Jan, Apr, Jul, Oct)
            if today.day == 1 and today.month in [1, 4, 7, 10]:
                return True, f"New quarter started ({today.strftime('%B')})"
            return False, "Waiting for start of quarter"

        elif survey.send_frequency == Template.FREQ_YEARLY:
            # Create new period on academic year start
            # Assuming September 1st - can be configured per school
            if today.day == 1 and today.month == 9:
                return True, "New academic year started"
            return False, "Waiting for academic year start (Sep 1)"

        return False, "Unknown frequency"
