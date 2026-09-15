from dataclasses import dataclass
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Protocol

from apps.jobs.models import Job
from apps.profiles.models import StudentProfile


@dataclass(frozen=True)
class MatchResult:
    score: float
    skill_score: float
    location_score: float
    availability_score: float
    experience_score: float
    explanation: dict
    strategy: str = "rule_based_v1"


class MatchingStrategy(Protocol):
    key: str

    def score(self, student: StudentProfile, job: Job) -> MatchResult:
        ...


class RuleBasedMatchingStrategy:
    """Transparent weighted scorer; replaceable through the strategy protocol."""

    key = "rule_based_v1"
    weights = {
        "skill_score": 0.40,
        "location_score": 0.25,
        "availability_score": 0.20,
        "experience_score": 0.15,
    }
    max_distance_km = 20.0
    proficiency_scores = {
        "beginner": 0.25,
        "intermediate": 0.50,
        "advanced": 0.75,
        "expert": 1.00,
    }

    def score(self, student: StudentProfile, job: Job) -> MatchResult:
        skills = list(student.student_skills.select_related("skill").all())
        required_skills = list(job.required_skills.all())
        skills_by_id = {item.skill_id: item for item in skills}
        required_ids = {skill.id for skill in required_skills}
        matched_ids = required_ids.intersection(skills_by_id)

        if not required_ids:
            skill_score = 1.0
            experience_score = 1.0
        else:
            skill_score = len(matched_ids) / len(required_ids)
            experience_values = []
            for skill_id in matched_ids:
                student_skill = skills_by_id[skill_id]
                years_score = min((student_skill.years_of_experience or 0) / 3, 1)
                proficiency_score = self.proficiency_scores.get(student_skill.proficiency, 0)
                experience_values.append(max(years_score, proficiency_score))
            experience_score = sum(experience_values) / len(required_ids)

        distance_km = self._distance_km(student, job)
        location_score = max(0.0, 1.0 - (distance_km / self.max_distance_km)) if distance_km is not None else 0.0
        availability_score = 1.0 if self._has_matching_availability(student, job) else 0.0

        components = {
            "skill_score": round(skill_score * 100, 2),
            "location_score": round(location_score * 100, 2),
            "availability_score": round(availability_score * 100, 2),
            "experience_score": round(experience_score * 100, 2),
        }
        total = sum(components[name] * weight for name, weight in self.weights.items())
        return MatchResult(
            score=round(total, 2),
            skill_score=components["skill_score"],
            location_score=components["location_score"],
            availability_score=components["availability_score"],
            experience_score=components["experience_score"],
            explanation={
                "weights": {name: int(weight * 100) for name, weight in self.weights.items()},
                "matched_skill_ids": [str(skill_id) for skill_id in matched_ids],
                "required_skill_count": len(required_ids),
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "within_discovery_radius": distance_km is not None and distance_km <= self.max_distance_km,
                "availability_matched": bool(availability_score),
            },
            strategy=self.key,
        )

    def _distance_km(self, student: StudentProfile, job: Job):
        if not student.campus_id or not student.campus.location or not job.location:
            return None
        first = student.campus.location
        second = job.location
        lat1, lon1, lat2, lon2 = map(radians, [first.y, first.x, second.y, second.x])
        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1
        value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        return 6371.0088 * 2 * asin(sqrt(value))

    def _has_matching_availability(self, student: StudentProfile, job: Job):
        if not job.start_date or not job.end_date or not job.start_time or not job.end_time:
            return False
        slots = list(student.availabilities.filter(is_active=True))
        current = job.start_date
        while current <= job.end_date:
            for slot in slots:
                if slot.day_of_week == current.weekday() and slot.start_time <= job.start_time and slot.end_time >= job.end_time:
                    return True
            current += timedelta(days=1)
        return False


def get_matching_strategy() -> MatchingStrategy:
    return RuleBasedMatchingStrategy()
