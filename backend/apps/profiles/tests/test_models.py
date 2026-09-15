import datetime
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.profiles.models import Availability, BusinessProfile, Skill, StudentProfile, StudentSkill
from apps.profiles.tests.helpers import BENGALURU_CAMPUS_A, make_campus

User = get_user_model()


class CampusModelTests(TestCase):
    def test_campus_latitude_longitude_properties(self):
        campus = make_campus(**BENGALURU_CAMPUS_A)
        self.assertAlmostEqual(campus.latitude, BENGALURU_CAMPUS_A["latitude"], places=4)
        self.assertAlmostEqual(campus.longitude, BENGALURU_CAMPUS_A["longitude"], places=4)
        self.assertIsInstance(campus.id, uuid.UUID)

    def test_campus_name_must_be_unique(self):
        make_campus(**BENGALURU_CAMPUS_A)
        with self.assertRaises(IntegrityError):
            make_campus(**BENGALURU_CAMPUS_A)

    def test_campus_str(self):
        campus = make_campus(**BENGALURU_CAMPUS_A)
        self.assertEqual(str(campus), "Alpha Institute of Technology, Bengaluru")


class SkillModelTests(TestCase):
    def test_skill_name_must_be_unique(self):
        Skill.objects.create(name="Python")
        with self.assertRaises(IntegrityError):
            Skill.objects.create(name="Python")

    def test_skill_str(self):
        skill = Skill.objects.create(name="Graphic Design")
        self.assertEqual(str(skill), "Graphic Design")


class StudentProfileModelTests(TestCase):
    def setUp(self):
        self.student_user = User.objects.create_user(
            email="student@example.com", password="Str0ngPass!23", role=User.Role.STUDENT
        )
        self.business_user = User.objects.create_user(
            email="business@example.com", password="Str0ngPass!23", role=User.Role.BUSINESS
        )
        self.campus = make_campus(**BENGALURU_CAMPUS_A)

    def test_profile_created_with_defaults(self):
        profile = StudentProfile.objects.create(user=self.student_user)
        self.assertEqual(profile.completion_percentage, 0)
        self.assertFalse(profile.is_complete)

    def test_clean_rejects_non_student_user(self):
        profile = StudentProfile(user=self.business_user)
        with self.assertRaises(ValidationError):
            profile.clean()

    def test_completion_percentage_increases_with_each_field(self):
        profile = StudentProfile.objects.create(user=self.student_user)
        self.assertEqual(profile.completion_percentage, 0)

        profile.full_name = "Asha Rao"
        profile.save()
        self.assertEqual(profile.completion_percentage, 25)

        profile.campus = self.campus
        profile.save()
        self.assertEqual(profile.completion_percentage, 50)

        skill = Skill.objects.create(name="Data Entry")
        StudentSkill.objects.create(student=profile, skill=skill)
        self.assertEqual(profile.completion_percentage, 75)

        Availability.objects.create(
            student=profile,
            day_of_week=Availability.DayOfWeek.MONDAY,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(profile.completion_percentage, 100)
        self.assertTrue(profile.is_complete)

    def test_one_profile_per_user(self):
        StudentProfile.objects.create(user=self.student_user)
        with self.assertRaises(IntegrityError):
            StudentProfile.objects.create(user=self.student_user)


class BusinessProfileModelTests(TestCase):
    def setUp(self):
        self.business_user = User.objects.create_user(
            email="biz@example.com", password="Str0ngPass!23", role=User.Role.BUSINESS
        )
        self.student_user = User.objects.create_user(
            email="stud@example.com", password="Str0ngPass!23", role=User.Role.STUDENT
        )
        self.campus = make_campus(**BENGALURU_CAMPUS_A)

    def test_clean_rejects_non_business_user(self):
        profile = BusinessProfile(user=self.student_user)
        with self.assertRaises(ValidationError):
            profile.clean()

    def test_completion_percentage(self):
        profile = BusinessProfile.objects.create(user=self.business_user)
        self.assertEqual(profile.completion_percentage, 0)

        profile.business_name = "Acme Tutoring"
        profile.campus = self.campus
        profile.description = "We hire student tutors."
        profile.save()
        self.assertEqual(profile.completion_percentage, 100)
        self.assertTrue(profile.is_complete)


class StudentSkillModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="skilled@example.com", password="Str0ngPass!23", role=User.Role.STUDENT
        )
        self.profile = StudentProfile.objects.create(user=user)
        self.skill = Skill.objects.create(name="Python")

    def test_unique_student_skill_constraint(self):
        StudentSkill.objects.create(student=self.profile, skill=self.skill)
        with self.assertRaises(IntegrityError):
            StudentSkill.objects.create(student=self.profile, skill=self.skill)


class AvailabilityModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="avail@example.com", password="Str0ngPass!23", role=User.Role.STUDENT
        )
        self.profile = StudentProfile.objects.create(user=user)

    def test_clean_rejects_end_before_start(self):
        slot = Availability(
            student=self.profile,
            day_of_week=Availability.DayOfWeek.MONDAY,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(9, 0),
        )
        with self.assertRaises(ValidationError):
            slot.clean()

    def test_clean_rejects_overlapping_slot_same_day(self):
        Availability.objects.create(
            student=self.profile,
            day_of_week=Availability.DayOfWeek.TUESDAY,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
        )
        overlapping = Availability(
            student=self.profile,
            day_of_week=Availability.DayOfWeek.TUESDAY,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(13, 0),
        )
        with self.assertRaises(ValidationError):
            overlapping.clean()

    def test_clean_allows_back_to_back_slots(self):
        Availability.objects.create(
            student=self.profile,
            day_of_week=Availability.DayOfWeek.WEDNESDAY,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
        )
        back_to_back = Availability(
            student=self.profile,
            day_of_week=Availability.DayOfWeek.WEDNESDAY,
            start_time=datetime.time(12, 0),
            end_time=datetime.time(15, 0),
        )
        back_to_back.clean()  # should not raise

    def test_db_check_constraint_blocks_end_before_start_even_without_clean(self):
        # .clean() is not called automatically by .save(); the DB-level
        # CheckConstraint is the real backstop against bad data reaching
        # the database (e.g. via bulk_create or a future code path that
        # forgets to call full_clean()).
        slot = Availability(
            student=self.profile,
            day_of_week=Availability.DayOfWeek.THURSDAY,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(9, 0),
        )
        with self.assertRaises(IntegrityError):
            slot.save()
