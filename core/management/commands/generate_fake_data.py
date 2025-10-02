# core/management/commands/generate_fake_data.py
import random
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from core.models import (
    School, AcademicYear, Grade, SchoolClass, Guardian, Student,
    GuardianStudent, StudentTimeline, StudentTimelineAttachment
)
from accounts.models import TeacherProfile, EmployeeProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate fake Arabic data for testing school management system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schools', type=int, default=3,
            help='Number of schools to create (default: 3)'
        )
        parser.add_argument(
            '--students', type=int, default=50,
            help='Number of students per school (default: 50)'
        )
        parser.add_argument(
            '--teachers', type=int, default=15,
            help='Number of teachers per school (default: 15)'
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Clear existing data before generating new data'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing data...'))
            with transaction.atomic():
                Student.objects.all().delete()
                Guardian.objects.all().delete()
                TeacherProfile.objects.all().delete()
                EmployeeProfile.objects.all().delete()
                SchoolClass.objects.all().delete()
                Grade.objects.all().delete()
                AcademicYear.objects.all().delete()
                School.objects.all().delete()
                User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.SUCCESS('Data cleared successfully'))

        self.stdout.write('Generating fake Arabic school data...')

        with transaction.atomic():
            # Create superuser
            self.create_super_user()

            # Generate data for each school
            for i in range(options['schools']):
                school = self.create_school(i + 1)
                self.stdout.write(f'Created school: {school.name}')

                # Create academic years
                academic_years = self.create_academic_years(school)
                current_year = academic_years[0]  # First one is current

                # Create grades and classes
                grades = self.create_grades(school)
                classes = self.create_classes(school, grades, current_year)

                # Create dashboard user for this school
                dashboard_user = self.create_dashboard_user(school)

                # Create teachers and employees
                teachers = self.create_teachers(school, options['teachers'])
                employees = self.create_employees(school)

                # Assign class teachers
                self.assign_class_teachers(classes, teachers)

                # Create students and guardians
                self.create_students_and_guardians(school, classes, options['students'])

                self.stdout.write(
                    self.style.SUCCESS(f'✓ School "{school.name}" setup complete')
                )
                self.stdout.write(f'  Dashboard: {dashboard_user.username} / Test@123')

        self.stdout.write(
            self.style.SUCCESS('🎉 Fake data generation completed successfully!')
        )
        self.stdout.write('Login credentials:')
        self.stdout.write('• Super Admin - Username: admin, Password: Test@123')

    def create_super_user(self):
        """Create super admin user"""
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@school.local',
                'first_name': 'مدير',
                'last_name': 'النظام',
                'is_staff': True,
                'is_superuser': True,
                'user_type': User.ADMIN,
                'is_active': True,
                'language': 'ar',
            }
        )
        if created:
            admin.set_password('Test@123')
            admin.save()
            self.stdout.write('✓ Super admin user created')

    def create_dashboard_user(self, school):
        """Create dashboard user as employee for specific school"""
        username = f'dashboard_{school.code.lower()}'

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'dashboard@{school.code.lower()}.edu.tn',
                'first_name': 'لوحة',
                'last_name': 'التحكم',
                'is_staff': True,
                'is_superuser': False,
                'user_type': User.EMPLOYEE,
                'phone': f'71{random.randint(100000, 999999)}',
                'is_active': True,
                'language': 'ar',
            }
        )
        if created:
            user.set_password('Test@123')
            user.save()

            # Create employee profile for dashboard user
            EmployeeProfile.objects.create(
                user=user,
                school=school,
                employee_id=f'E{school.code}000',
                position='admin',
                department='الإدارة',
                hire_date=date(2024, 9, 1),
                salary=Decimal('10000'),
                can_manage_students=True,
                can_manage_teachers=True,
                can_view_reports=True,
                is_active=True
            )
            self.stdout.write(f'✓ Dashboard user created for {school.name}')

        return user

    def create_school(self, index):
        """Create a school with Arabic name"""
        arabic_school_names = [
            'مدرسة النور الأساسية',
            'مدرسة الفجر الثانوية',
            'مدرسة الأمل الابتدائية',
            'مدرسة المستقبل المختلطة',
            'مدرسة التميز الأساسية',
            'مدرسة النجاح الثانوية',
            'مدرسة العلم والمعرفة',
            'مدرسة الرسالة التربوية',
        ]

        school = School.objects.create(
            name=arabic_school_names[(index - 1) % len(arabic_school_names)],
            address=f'حي السلام، شارع {random.randint(1, 50)}، تونس',
            phone=f'71{random.randint(100000, 999999)}',
            email=f'info@school{index}.edu.tn',
            principal_name=random.choice([
                'أحمد محمد بن علي', 'فاطمة الزهراء بن صالح', 'محمد الأمين بن يوسف',
                'نورا حسن بن عبدالله', 'سالم عبدالرحمن بن مبروك', 'مريم خالد بن حسين'
            ]),
            academic_year_start=date(2024, 9, 1),
            academic_year_end=date(2025, 6, 30),
            is_active=True
        )
        return school

    def create_academic_years(self, school):
        """Create academic years for school"""
        years = []
        current_year = AcademicYear.objects.create(
            school=school,
            name='2024-2025',
            start_date=date(2024, 9, 1),
            end_date=date(2025, 6, 30),
            is_current=True
        )
        years.append(current_year)

        # Previous year
        prev_year = AcademicYear.objects.create(
            school=school,
            name='2023-2024',
            start_date=date(2023, 9, 1),
            end_date=date(2024, 6, 30),
            is_current=False
        )
        years.append(prev_year)

        return years

    def create_grades(self, school):
        """Create grades for school - 6 primary + 3 middle + 3 secondary"""
        grades_data = [
            # Primary (6 grades)
            ('السنة الأولى ابتدائي', 1, 'primary'),
            ('السنة الثانية ابتدائي', 2, 'primary'),
            ('السنة الثالثة ابتدائي', 3, 'primary'),
            ('السنة الرابعة ابتدائي', 4, 'primary'),
            ('السنة الخامسة ابتدائي', 5, 'primary'),
            ('السنة السادسة ابتدائي', 6, 'primary'),
            # Middle (3 grades)
            ('السنة السابعة أساسي', 7, 'middle'),
            ('السنة الثامنة أساسي', 8, 'middle'),
            ('السنة التاسعة أساسي', 9, 'middle'),
            # Secondary (3 grades)
            ('السنة الأولى ثانوي', 10, 'secondary'),
            ('السنة الثانية ثانوي', 11, 'secondary'),
            ('السنة الثالثة ثانوي', 12, 'secondary'),
        ]

        grades = []
        for name, level, grade_type in grades_data:
            grade = Grade.objects.create(
                school=school,
                name=name,
                level=level,
                grade_type=grade_type,
                is_active=True
            )
            grades.append(grade)

        return grades

    def create_classes(self, school, grades, academic_year):
        """Create classes for each grade"""
        classes = []
        class_names = ['أ', 'ب', 'ج', 'د']

        for grade in grades:
            # Create 2-3 classes per grade randomly
            num_classes = random.randint(2, min(4, len(class_names)))
            for i in range(num_classes):
                school_class = SchoolClass.objects.create(
                    school=school,
                    grade=grade,
                    academic_year=academic_year,
                    name=class_names[i],
                    capacity=random.randint(25, 35),
                    is_active=True
                )
                classes.append(school_class)

        return classes

    def create_teachers(self, school, count):
        """Create teacher profiles"""
        arabic_first_names_male = [
            'محمد', 'أحمد', 'علي', 'حسن', 'عمر', 'يوسف', 'إبراهيم',
            'خالد', 'سعيد', 'كريم', 'رضا', 'منير', 'طارق', 'أمين', 'ياسين'
        ]
        arabic_first_names_female = [
            'فاطمة', 'عائشة', 'خديجة', 'مريم', 'نور', 'سارة', 'هند', 'أميرة',
            'رانيا', 'زينب', 'منى', 'سمية', 'ليلى', 'آمال', 'سلمى', 'نورا'
        ]
        arabic_last_names = [
            'بن علي', 'بن صالح', 'بن محمد', 'بن يوسف', 'بن حسن', 'بن عمر',
            'بن إبراهيم', 'بن عبدالله', 'بن مبروك', 'بن حسين', 'بن الطاهر', 'بن عيسى'
        ]
        subjects = [
            'اللغة العربية', 'الرياضيات', 'العلوم', 'التربية الإسلامية',
            'التاريخ', 'الجغرافيا', 'اللغة الإنجليزية', 'الفيزياء',
            'الكيمياء', 'الأحياء', 'التربية البدنية', 'الحاسوب'
        ]

        teachers = []
        for i in range(count):
            is_male = random.choice([True, False])
            first_names = arabic_first_names_male if is_male else arabic_first_names_female

            first_name = random.choice(first_names)
            last_name = random.choice(arabic_last_names)

            # Create user
            username = f'teacher_{school.code.lower()}_{i + 1}'
            user = User.objects.create(
                username=username,
                email=f'{username}@{school.code.lower()}.edu.sa',
                first_name=first_name,
                last_name=last_name,
                user_type=User.TEACHER,
                phone=f'05{random.randint(10000000, 99999999)}',
                is_active=True,
                language='ar'
            )
            user.set_password('Test@123')
            user.save()

            # Create teacher profile
            teacher = TeacherProfile.objects.create(
                user=user,
                school=school,
                employee_id=f'T{school.code}{str(i + 1).zfill(3)}',
                subject=random.choice(subjects),
                qualification=random.choice([
                    'بكالوريوس تربوي', 'ماجستير في التخصص', 'دبلوم عالي',
                    'بكالوريوس + دبلوم تربوي', 'ماجستير تربوي'
                ]),
                experience_years=random.randint(1, 20),
                hire_date=date(2020, 9, 1) + timedelta(days=random.randint(0, 1400)),
                salary=Decimal(str(random.randint(8000, 15000))),
                is_active=True,
                is_class_teacher=False  # Will be assigned later
            )
            teachers.append(teacher)

        return teachers

    def create_employees(self, school):
        """Create employee profiles"""
        arabic_names = [
            ('سليمان', 'بن رشيد'), ('منصف', 'بن عيسى'), ('بدر', 'بن مبروك'),
            ('هناء', 'بن صالح'), ('أمل', 'بن القاسم'), ('وفاء', 'بن زيد')
        ]

        employees = []
        positions = ['admin', 'accountant', 'librarian', 'nurse', 'security']

        for i, position in enumerate(positions):
            if i < len(arabic_names):
                first_name, last_name = arabic_names[i]
            else:
                first_name, last_name = random.choice(arabic_names)

            # Create user
            username = f'employee_{school.code.lower()}_{position}'
            user = User.objects.create(
                username=username,
                email=f'{username}@{school.code.lower()}.edu.sa',
                first_name=first_name,
                last_name=last_name,
                user_type=User.EMPLOYEE,
                phone=f'05{random.randint(10000000, 99999999)}',
                is_active=True,
                language='ar'
            )
            user.set_password('Test@123')
            user.save()

            # Create employee profile
            employee = EmployeeProfile.objects.create(
                user=user,
                school=school,
                employee_id=f'E{school.code}{str(i + 1).zfill(3)}',
                position=position,
                department=random.choice(['الإدارة', 'الشؤون المالية', 'الخدمات']),
                hire_date=date(2020, 9, 1) + timedelta(days=random.randint(0, 1400)),
                salary=Decimal(str(random.randint(6000, 12000))),
                can_manage_students=position in ['admin'],
                can_manage_teachers=position in ['admin'],
                can_view_reports=True,
                is_active=True
            )
            employees.append(employee)

        return employees

    def assign_class_teachers(self, classes, teachers):
        """Assign teachers to classes as class teachers"""
        available_teachers = list(teachers)
        random.shuffle(available_teachers)

        for i, school_class in enumerate(classes):
            if i < len(available_teachers):
                teacher = available_teachers[i]
                school_class.class_teacher = teacher.user
                school_class.save()

                teacher.is_class_teacher = True
                teacher.save()

    def create_students_and_guardians(self, school, classes, student_count):
        """Create students and their guardians"""
        arabic_first_names_male = [
            'محمد', 'أحمد', 'علي', 'حسن', 'يوسف', 'عمر', 'إبراهيم',
            'سعيد', 'كريم', 'خالد', 'أمين', 'ياسين', 'طارق', 'منير', 'رضا'
        ]
        arabic_first_names_female = [
            'فاطمة', 'سارة', 'مريم', 'نور', 'ليلى', 'هند', 'آمال', 'رانيا',
            'زينب', 'سلمى', 'أميرة', 'خديجة', 'منى', 'نادية', 'سمية'
        ]
        arabic_family_names = [
            'بن علي', 'بن صالح', 'بن محمد', 'بن يوسف', 'بن حسن', 'بن عمر',
            'بن إبراهيم', 'بن عبدالله', 'بن مبروك', 'بن حسين', 'بن الطاهر', 'بن عيسى',
            'بن سعيد', 'بن خليفة', 'بن رشيد', 'بن منصور', 'بن كريم', 'بن حمدي'
        ]

        for i in range(student_count):
            # Random student data
            is_male = random.choice([True, False])
            first_names = arabic_first_names_male if is_male else arabic_first_names_female

            first_name = random.choice(first_names)
            father_name = random.choice(arabic_first_names_male)
            grandfather_name = random.choice(arabic_first_names_male)
            family_name = random.choice(arabic_family_names)

            # Birth date (6-18 years old)
            birth_year = random.randint(2006, 2018)
            birth_date = date(birth_year, random.randint(1, 12), random.randint(1, 28))

            # Assign to random class
            current_class = random.choice(classes)

            # Create student
            student = Student.objects.create(
                school=school,
                current_class=current_class,
                first_name=first_name,
                second_name=father_name,
                third_name=grandfather_name,
                fourth_name=random.choice(arabic_first_names_male),
                last_name=family_name,
                sex='male' if is_male else 'female',
                date_of_birth=birth_date,
                place_of_birth=random.choice([
                    'تونس', 'صفاقس', 'سوسة', 'القيروان', 'بنزرت', 'قابس'
                ]),
                phone=f'2{random.randint(10000000, 99999999)}',
                address=f'حي {random.choice(["المنار", "الخضراء", "النصر", "السعادة"])}, تونس',
                enrollment_date=current_class.academic_year.start_date,
                is_active=True
            )

            # Create guardians (father and mother)
            self.create_guardians_for_student(student)

            # Create some timeline entries
            self.create_timeline_entries(student)

    def create_guardians_for_student(self, student):
        """Create father and optionally mother guardians for student"""
        arabic_father_names = [
            'محمد', 'أحمد', 'علي', 'حسن', 'عمر', 'يوسف', 'إبراهيم',
            'خالد', 'سعيد', 'كريم', 'رضا', 'منير', 'طارق', 'أمين'
        ]
        arabic_mother_names = [
            'فاطمة', 'عائشة', 'خديجة', 'مريم', 'نور', 'سارة', 'هند',
            'أميرة', 'رانيا', 'منى', 'سمية', 'ليلى', 'نادية', 'زينب'
        ]

        # Create father - always
        father_name = random.choice(arabic_father_names)
        father_phone = f'2{random.randint(10000000, 99999999)}'

        father = Guardian.objects.create(
            school=student.school,
            first_name=father_name,
            last_name=student.last_name,
            phone=father_phone,
            email=f'{father_name.lower()}.{student.student_id.lower()}@gmail.com',
            nid=f'0{random.randint(1000000, 9999999)}',
            address=student.address
        )

        # Create user for father - using phone as username
        user_father = User.objects.create(
            username=father_phone,
            email=father.email,
            first_name=father.first_name,
            last_name=father.last_name,
            user_type=User.GUARDIAN,
            phone=father.phone,
            is_active=True,
            language='ar'
        )
        user_father.set_password('Test@123')
        user_father.save()

        # Link father to user
        father.user = user_father
        father.selected_student = student
        father.save()

        # Create father-student relationship
        GuardianStudent.objects.create(
            guardian=father,
            student=student,
            relationship='father',
            is_primary=True,
            is_emergency_contact=True,
            can_pickup=True,
            can_receive_notifications=True,
        )

        # Create mother randomly (70% chance)
        if random.random() < 0.7:
            mother_name = random.choice(arabic_mother_names)
            mother_last_name = random.choice([
                'بن علي', 'بن صالح', 'بن محمد', 'بن يوسف', 'بن حسن', 'بن عمر'
            ])
            mother_phone = f'2{random.randint(10000000, 99999999)}'

            mother = Guardian.objects.create(
                school=student.school,
                first_name=mother_name,
                last_name=mother_last_name,
                phone=mother_phone,
                email=f'{mother_name.lower()}.{student.student_id.lower()}m@gmail.com',
                address=student.address
            )

            # Create user for mother - using phone as username
            user_mother = User.objects.create(
                username=mother_phone,
                email=mother.email,
                first_name=mother.first_name,
                last_name=mother.last_name,
                user_type=User.GUARDIAN,
                phone=mother.phone,
                is_active=True,
                language='ar'
            )
            user_mother.set_password('Test@123')
            user_mother.save()

            # Link mother to user
            mother.user = user_mother
            mother.selected_student = student
            mother.save()

            # Create mother-student relationship
            GuardianStudent.objects.create(
                guardian=mother,
                student=student,
                relationship='mother',
                is_primary=False,
                is_emergency_contact=True,
                can_pickup=True,
                can_receive_notifications=True
            )

    def create_timeline_entries(self, student):
        """Create timeline entries for student"""
        timeline_content = [
            ('تحسن في الدرجات', 'أظهر الطالب تحسناً ملحوظاً في مادة الرياضيات', 'academic'),
            ('سلوك إيجابي', 'تطوع الطالب لمساعدة زملائه في الفصل', 'behavior'),
            ('إنجاز رياضي', 'حصل على المركز الأول في مسابقة الجري', 'achievement'),
            ('ملاحظة صحية', 'يحتاج إلى متابعة طبية لضعف في النظر', 'health'),
            ('حضور ممتاز', 'حافظ على الحضور المنتظم طوال الشهر', 'attendance'),
        ]

        # Create 2-5 random timeline entries per student
        num_entries = random.randint(2, 5)
        selected_entries = random.sample(timeline_content, min(num_entries, len(timeline_content)))

        for title, note, content_type in selected_entries:
            StudentTimeline.objects.create(
                student=student,
                title=title,
                note=note,
                content_type=content_type,
                is_visible_to_guardian=random.choice([True, True, False]),  # 70% visible
                is_visible_to_student=random.choice([True, False]),
                created_by=student.current_class.class_teacher if student.current_class.class_teacher else None,
                is_pinned=random.choice([True, False, False, False]),  # 25% pinned
                created_at=timezone.now() - timedelta(days=random.randint(1, 90))
            )