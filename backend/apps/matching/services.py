from django.conf import settings
from django.db import transaction

from apps.jobs.models import Job
from apps.matching.models import JobMatch, StudentJobEngagement, StudentPreference
from apps.matching.strategies import MatchResult, get_matching_strategy
from apps.profiles.models import StudentProfile


class MatchingService:
    """Coordinates strategy scoring and persistence without owning HTTP concerns."""

    def __init__(self, strategy=None):
        self.strategy = strategy or get_matching_strategy()

    @transaction.atomic
    def calculate(self, student: StudentProfile, job: Job) -> JobMatch:
        result = self.strategy.score(student, job)
        match, _created = JobMatch.objects.update_or_create(
            student=student,
            job=job,
            defaults={
                "score": result.score,
                "skill_score": result.skill_score,
                "location_score": result.location_score,
                "availability_score": result.availability_score,
                "experience_score": result.experience_score,
                "explanation": result.explanation,
                "strategy": result.strategy,
            },
        )
        return match


class RecommendationService:
    """Ranks active jobs using persisted match scores plus student-owned signals."""

    def __init__(self, matching_service=None):
        self.matching_service = matching_service or MatchingService()

    def recommend(self, student: StudentProfile):
        preferences = getattr(student, "matching_preferences", None)
        maximum_distance = min(
            float(getattr(preferences, "maximum_distance_km", settings.DEFAULT_DISCOVERY_RADIUS_KM)),
            float(settings.DEFAULT_DISCOVERY_RADIUS_KM),
        )
        jobs = Job.objects.filter(
            status__in=[Job.Status.PUBLISHED, Job.Status.OPEN], is_active=True
        ).select_related("category", "business__user").prefetch_related("required_skills")
        engagements = StudentJobEngagement.objects.filter(student=student)
        engaged = {(item.job_id, item.kind) for item in engagements}
        saved_categories = {
            item.job.category_id
            for item in engagements
            if item.kind in {StudentJobEngagement.Kind.SAVED, StudentJobEngagement.Kind.APPLIED}
        }
        preferred_categories = set(preferences.preferred_categories.values_list("id", flat=True)) if preferences else set()
        preferred_job_types = set(preferences.preferred_job_types or []) if preferences else set()
        preferred_payment_types = set(preferences.preferred_payment_types or []) if preferences else set()

        ranked = []
        for job in jobs:
            match = self.matching_service.calculate(student, job)
            distance = match.explanation.get("distance_km")
            if distance is None or distance > maximum_distance:
                continue
            if preferences and preferences.minimum_payment is not None and job.payment_amount < preferences.minimum_payment:
                continue
            if preferences and preferences.maximum_payment is not None and job.payment_amount > preferences.maximum_payment:
                continue
            boost = 0.0
            reasons = []
            if job.category_id in preferred_categories:
                boost += 12
                reasons.append("preferred category")
            if job.category_id in saved_categories:
                boost += 5
                reasons.append("category from saved or applied jobs")
            if job.job_type in preferred_job_types:
                boost += 4
                reasons.append("preferred job type")
            if job.payment_type in preferred_payment_types:
                boost += 3
                reasons.append("preferred payment type")
            if (job.id, StudentJobEngagement.Kind.SAVED) in engaged:
                boost += 2
                reasons.append("saved job")
            ranked.append(
                {
                    "job": job,
                    "match": match,
                    "recommendation_boost": boost,
                    "recommendation_score": round(min(100.0, float(match.score) + boost), 2),
                    "recommendation_reasons": reasons,
                }
            )
        ranked.sort(
            key=lambda item: (
                -item["recommendation_score"],
                -item["recommendation_boost"],
                -float(item["match"].score),
                str(item["job"].id),
            )
        )
        return ranked
