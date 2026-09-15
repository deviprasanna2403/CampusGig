from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.jobs.models import Job, JobCategory
from apps.matching.models import JobMatch, StudentJobEngagement, StudentPreference
from apps.matching.services import MatchingService, RecommendationService
from apps.profiles.models import Availability, BusinessProfile, Campus, Skill, StudentProfile, StudentSkill

User = get_user_model()


class MatchingPhase6Tests(APITestCase):
    def setUp(self):
        self.student_user = User.objects.create_user(
            email="student@example.com", password="C@mpusGig-Str0ng!", role=User.Role.STUDENT
        )
        self.business_user = User.objects.create_user(
            email="business@example.com", password="C@mpusGig-Str0ng!", role=User.Role.BUSINESS
        )
        self.campus = Campus.objects.create(
            name="Matching Campus", city="Bengaluru", location=Point(77.5946, 12.9716, srid=4326)
        )
        BusinessProfile.objects.create(user=self.business_user, business_name="Hiring Co", campus=self.campus)
        self.student = StudentProfile.objects.create(
            user=self.student_user, full_name="Student One", campus=self.campus
        )
        self.category = JobCategory.objects.get(name__iexact="events")
        self.skill = Skill.objects.create(name="Event Operations")
        StudentSkill.objects.create(
            student=self.student,
            skill=self.skill,
            proficiency=StudentSkill.Proficiency.EXPERT,
            years_of_experience=3,
        )
        Availability.objects.create(
            student=self.student,
            day_of_week=6,
            start_time=time(9),
            end_time=time(17),
        )

    def make_job(self, title="Event job", longitude=77.5946, category=None):
        job = Job.objects.create(
            business=self.business_user.business_profile,
            title=title,
            description="Help with event operations.",
            category=category or self.category,
            location=Point(longitude, 12.9716, srid=4326),
            start_date=date(2026, 9, 20),
            end_date=date(2026, 9, 20),
            start_time=time(9),
            end_time=time(17),
            payment_amount=Decimal("500"),
            payment_type=Job.PaymentType.HOURLY,
            workers_required=1,
            application_deadline=date(2026, 9, 18),
            eligibility_notes="Students welcome.",
            status=Job.Status.PUBLISHED,
        )
        job.required_skills.add(self.skill)
        return job

    def test_rule_based_score_uses_all_four_weighted_components(self):
        job = self.make_job()
        match = MatchingService().calculate(self.student, job)

        self.assertEqual(match.score, Decimal("100.00"))
        self.assertEqual(match.skill_score, Decimal("100.00"))
        self.assertEqual(match.location_score, Decimal("100.00"))
        self.assertEqual(match.availability_score, Decimal("100.00"))
        self.assertEqual(match.experience_score, Decimal("100.00"))
        self.assertEqual(match.strategy, "rule_based_v1")
        self.assertEqual(JobMatch.objects.filter(student=self.student, job=job).count(), 1)

    def test_unmatched_skill_reduces_score_and_is_explained(self):
        other_skill = Skill.objects.create(name="Photography")
        job = self.make_job()
        job.required_skills.clear()
        job.required_skills.add(other_skill)
        match = MatchingService().calculate(self.student, job)

        self.assertEqual(match.skill_score, Decimal("0.00"))
        self.assertIn("matched_skill_ids", match.explanation)
        self.assertLess(match.score, Decimal("100.00"))

    def test_recommendations_preserve_twenty_km_radius(self):
        nearby = self.make_job("Nearby")
        distant = self.make_job("Distant", longitude=78.5)
        recommendations = RecommendationService().recommend(self.student)
        ids = {item["job"].id for item in recommendations}

        self.assertIn(nearby.id, ids)
        self.assertNotIn(distant.id, ids)

    def test_preference_and_saved_signal_affect_recommendations(self):
        preferred = self.make_job("Preferred")
        other_category = JobCategory.objects.create(name="Retail")
        other = self.make_job("Other", category=other_category)
        StudentPreference.objects.create(student=self.student)
        preference = self.student.matching_preferences
        preference.preferred_categories.add(preferred.category)
        StudentJobEngagement.objects.create(
            student=self.student, job=other, kind=StudentJobEngagement.Kind.SAVED
        )

        ranked = RecommendationService().recommend(self.student)
        ranked_ids = [item["job"].id for item in ranked]
        self.assertEqual(ranked_ids[0], preferred.id)
        self.assertIn("preferred category", ranked[0]["recommendation_reasons"])

    def test_student_can_calculate_and_list_own_matches(self):
        job = self.make_job()
        self.client.force_authenticate(self.student_user)
        calculate = self.client.post(
            reverse("matching:match-calculate", kwargs={"job_id": job.id}), format="json"
        )
        self.assertEqual(calculate.status_code, status.HTTP_200_OK)
        listed = self.client.get(reverse("matching:match-list"))
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)

    def test_student_can_read_recommendations_api(self):
        job = self.make_job()
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse("matching:recommendations"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["job"]["id"], str(job.id))
        self.assertIn("match_components", response.data["results"][0])

    def test_business_cannot_use_student_matching_endpoints(self):
        self.client.force_authenticate(self.business_user)
        response = self.client.get(reverse("matching:recommendations"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_preferences_and_engagements_are_scoped(self):
        job = self.make_job()
        self.client.force_authenticate(self.student_user)
        preference = self.client.get(reverse("matching:preferences"))
        self.assertEqual(preference.status_code, status.HTTP_200_OK)
        engagement = self.client.post(
            reverse("matching:engagement-list"),
            {"job_id": str(job.id), "kind": "SAVED"},
            format="json",
        )
        self.assertEqual(engagement.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StudentJobEngagement.objects.count(), 1)

    def test_published_job_with_no_matching_availability_scores_zero_for_availability(self):
        self.student.availabilities.all().delete()
        match = MatchingService().calculate(self.student, self.make_job())
        self.assertEqual(match.availability_score, Decimal("0.00"))
