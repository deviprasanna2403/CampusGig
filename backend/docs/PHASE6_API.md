# Phase 6 API - Matching and Recommendations

Phase 6 adds transparent, rule-based student/job matching. Communication,
notifications, payments, fraud, analytics, and other later-phase workflows
are documented separately; this file covers only the matching contract.
All endpoints require `Authorization: Bearer <access_token>` and are mounted
under `/api/v1/matching/`.

## Match scoring

`JobMatch` uses the replaceable `MatchingStrategy` contract. The default
`RuleBasedMatchingStrategy` is `rule_based_v1` and calculates:

- Skill match: **40%** — required skills held by the student divided by the
  job's required skills. Jobs with no required skills receive full credit.
- Location match: **25%** — campus-to-job haversine distance, linearly scored
  from 100 at the campus location to 0 at 20 km. A missing campus receives 0.
- Availability match: **20%** — full credit when an active weekly slot covers
  the job's day and time; otherwise 0.
- Experience match: **15%** — matched-skill experience, using the student's
  years of experience (three years is full credit) or proficiency as a
  transparent fallback.

The platform's campus-based discovery boundary remains 20 km. A student's
personal GPS position is never collected or used.

## Endpoints

### `GET /api/v1/matching/recommendations/`

Student-only, paginated. Calculates and persists matches for active `PUBLISHED`
or `OPEN` jobs within the student's configured recommendation distance, capped
at 20 km. It ranks by the base match score plus explainable preference signals:
preferred categories, preferred job types/payment types, and categories from
saved/application signals. Previously saved jobs receive a small ranking boost.

Each result includes the nested job, `match_score`, capped
`recommendation_score`, four `match_components`, and
`recommendation_reasons`.

### `GET /api/v1/matching/matches/`

Student-only, paginated list of the caller's persisted matches. Optional
filters: `job_id` and `minimum_score`.

### `POST /api/v1/matching/matches/calculate/{job_id}/`

Student-only. Calculates or refreshes one persisted match for an active,
published/open job and returns the component breakdown.

### `GET/PATCH /api/v1/matching/preferences/`

Student-only, lazily creates the caller's preferences. PATCH fields:
`preferred_category_ids`, `preferred_job_types`, `preferred_payment_types`,
`minimum_payment`, `maximum_payment`, and `maximum_distance_km`.
The maximum distance must be between 0 and 20 km.

### `GET/POST /api/v1/matching/engagements/`

Student-only, scoped to the caller. POST accepts `job_id` and `kind`, where
`kind` is `VIEWED`, `SAVED`, or `APPLIED`. These are recommendation signals,
not an application-processing workflow. Optional list filter: `?kind=SAVED`.

### `DELETE /api/v1/matching/engagements/{id}/`

Deletes the caller's own engagement signal, such as removing a saved job.

## Persistence and replacement strategy

`JobMatch` stores the total, all four component scores, the strategy key, and a
structured explanation. `apps.matching.strategies.MatchingStrategy` is the
replacement boundary for a future scoring implementation; the current strategy
is explicitly rule-based and is not described as AI.
