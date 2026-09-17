/**
 * TypeScript mirrors of the CampusGig API resources.
 *
 * Shapes are taken from the backend serializers (Phase 1–9B), not invented:
 * - User: apps/accounts/serializers.py::UserSerializer
 * - Error envelope: apps/core/exceptions.py (errors only — successes are raw)
 * - Pagination: DRF PageNumberPagination, PAGE_SIZE=20
 */

export type Role = "student" | "business" | "admin";

export interface User {
  id: string; // UUID
  email: string;
  phone: string | null;
  role: Role;
  is_verified: boolean;
  date_joined: string;
}

/** POST /auth/login/ and /auth/register/ responses. */
export interface TokenPairResponse {
  access: string;
  refresh: string;
  user: User;
}

/** POST /auth/token/refresh/ response (ROTATE_REFRESH_TOKENS=True). */
export interface RefreshResponse {
  access: string;
  refresh: string;
}

/** Field-level validation details from the error envelope. */
export type ApiErrorDetails = Record<string, string[] | string | undefined>;

/** The standard error envelope for every non-2xx response. */
export interface ErrorEnvelope {
  success: false;
  data: null;
  error: {
    code: number;
    message: string;
    details: ApiErrorDetails | null;
  };
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/* --- profiles (Phase 4) ------------------------------------------------- */

export interface Campus {
  id: string;
  name: string;
  city: string;
  state: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  is_active: boolean;
}

export interface Skill {
  id: string;
  name: string;
  category: string;
  is_active: boolean;
}

/* --- jobs (Phase 5) ------------------------------------------------------ */

export type JobStatus =
  | "DRAFT"
  | "PUBLISHED"
  | "OPEN"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CLOSED"
  | "EXPIRED"
  | "CANCELLED";

export interface JobCategory {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
}

export interface Job {
  id: string;
  title: string;
  description: string;
  category: JobCategory | null;
  job_type: string;
  required_skills: { id: string; name: string }[];
  location_latitude: number | null;
  location_longitude: number | null;
  start_date: string;
  end_date: string;
  start_time: string;
  end_time: string;
  payment_amount: string;
  payment_type: string;
  workers_required: number;
  application_deadline: string;
  eligibility_notes: string;
  status: JobStatus;
  /** Business owner's account email (serializer method field). */
  business: string;
  /** Phase F6: business owner's user id — links to their reviews page. */
  business_user_id?: string;
  /** F6: requesting student has an application/engagement on this job —
   *  drives the taken-down/unavailable banner on non-open jobs. */
  viewer_has_history?: boolean;
  created_at: string;
  updated_at: string;
}

/* --- applications (Phase 6) ---------------------------------------------- */

export type ApplicationStatus =
  | "SUBMITTED"
  | "SHORTLISTED"
  | "INTERVIEW"
  | "SELECTED"
  | "REJECTED"
  | "WITHDRAWN";

export interface Application {
  id: string;
  job: string;
  job_id: string;
  student: string;
  cover_note: string;
  status: ApplicationStatus;
  /** Phase F6: job status echo — reviews require a completed job. */
  job_status?: JobStatus;
  /** Phase F6: the other party's user id (business for students, student for businesses). */
  counterparty_id?: string;
  /** Phase F6: rating the current user already gave on this application (null if none). */
  my_review_rating?: number | null;
  submitted_at: string;
  created_at: string;
  updated_at: string;
}

/* --- reviews (Phase 8 API, F6 UI) ----------------------------------------- */

export type ReviewStatus = "PUBLISHED" | "HIDDEN" | "UNDER_REVIEW";

export interface ReviewRow {
  id: string;
  application: string;
  /** Reviewer/reviewee user ids (UUIDs). */
  reviewer: string;
  reviewee: string;
  /** Display emails (F6). */
  reviewer_email: string;
  reviewee_email: string;
  rating: number; // 1..5
  comment: string;
  status: ReviewStatus;
  created_at: string;
  updated_at: string;
}

/* --- student profile (Phase 4) ------------------------------------------- */

export interface StudentProfileFull {
  id: string;
  email: string;
  full_name: string;
  campus: Campus | null;
  campus_id?: string | null; // write-only on the API; echoed in campus
  year_of_study: number | null;
  bio: string;
  resume_headline: string;
  skills: StudentSkillRow[];
  availability: AvailabilityRow[];
  completion_percentage: number;
  is_complete: boolean;
  created_at: string;
  updated_at: string;
}

export interface StudentSkillRow {
  id: string;
  skill: Skill;
  proficiency: string;
  years_of_experience: number | null;
  created_at: string;
}

export interface AvailabilityRow {
  id: string;
  day_of_week: number; // 0=Monday .. 6=Sunday (backend IntegerChoices)
  start_time: string;
  end_time: string;
  is_active: boolean;
  created_at: string;
}

/* --- business profile (Phase 4) ------------------------------------------- */

export interface BusinessProfileFull {
  id: string;
  email: string;
  business_name: string;
  description: string;
  website: string;
  industry: string;
  campus: Campus | null;
  campus_id?: string | null; // write-only on the API; echoed in campus
  completion_percentage: number;
  is_complete: boolean;
  created_at: string;
  updated_at: string;
}

/* --- business verification (Phase 8/9A) ----------------------------------- */

export type VerificationStatus =
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "VERIFIED"
  | "REJECTED"
  | "REVOKED";

export interface BusinessVerification {
  id: string;
  business: string;
  status: VerificationStatus;
  legal_name: string;
  registration_reference: string;
  evidence: Record<string, string>;
  review_notes: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

/* --- analytics (Phase 9B) ------------------------------------------------ */

export interface TimeseriesPoint {
  date: string;
  count: number;
}

export interface AdminAnalytics {
  window: { from: string; to: string };
  interval: "day" | "week" | "month";
  users: { total: number; by_role: Record<string, number>; verified: number; new_in_window: number };
  jobs: { total: number; by_status: Record<string, number>; new_in_window: number };
  applications: {
    total: number;
    by_status: Record<string, number>;
    new_in_window: number;
    selection_rate: number | null;
  };
  verifications: { by_status: Record<string, number> };
  reports: { by_status: Record<string, number> };
  timeseries: {
    new_users: TimeseriesPoint[];
    new_jobs: TimeseriesPoint[];
    new_applications: TimeseriesPoint[];
  };
}

export interface BusinessAnalytics {
  window: { from: string; to: string };
  interval: "day" | "week" | "month";
  jobs: { total: number; by_status: Record<string, number>; cancelled: number };
  applications: { received: number; by_status: Record<string, number>; selection_rate: number | null };
  rating_average: number | null;
  timeseries: { applications_received: TimeseriesPoint[] };
}

export interface StudentAnalytics {
  window: { from: string; to: string };
  interval: "day" | "week" | "month";
  profile_completion_percentage: number;
  applications: {
    total: number;
    by_status: Record<string, number>;
    success_rate: number | null;
    withdrawn: number;
  };
  completed_gigs: number;
  rating_average: number | null;
  open_jobs_near_campus: number;
  timeseries: { applications_submitted: TimeseriesPoint[] };
}

/* --- matching (Phase 7) --------------------------------------------------- */

export interface MatchComponents {
  skill: string;
  location: string;
  availability: string;
  experience: string;
}

export interface Recommendation {
  job: Job;
  match_score: string;
  recommendation_score: number;
  match_components: MatchComponents;
  recommendation_reasons: string[];
}

export interface JobMatch {
  id: string;
  job: Job;
  score: string;
  components: MatchComponents;
  explanation: string;
  strategy: string;
  calculated_at: string;
}

export interface StudentPreference {
  id: string;
  preferred_category_ids: string[];
  preferred_job_types: string[];
  preferred_payment_types: string[];
  minimum_payment: string | null;
  maximum_payment: string | null;
  maximum_distance_km: number | null;
}

/* --- communication (Phase 7) ---------------------------------------------- */

export interface Conversation {
  id: string;
  other_party: string;
  is_active: boolean;
  unread_count: number;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation: string;
  sender: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

/* --- interviews (Phase 7) -------------------------------------------------- */

export type InterviewStatus = "SCHEDULED" | "CONFIRMED" | "DECLINED" | "COMPLETED" | "CANCELLED";

export interface Interview {
  id: string;
  proposed_by: string;
  starts_at: string;
  ends_at: string;
  timezone_name: string | null;
  meeting_url: string;
  notes: string;
  status: InterviewStatus;
  created_at: string;
  updated_at: string;
}

/* --- notifications (Phase 7) ------------------------------------------------ */

export interface NotificationRow {
  id: string;
  event: string;
  title: string;
  body: string;
  payload: Record<string, string>;
  read_at: string | null;
  email_sent_at: string | null;
  created_at: string;
}

/* --- audit logs (Phase 9B, admin-only, GET-only) -------------------------- */

export interface AuditLog {
  id: string;
  actor: string | null;
  actor_email: string | null;
  actor_role: string;
  action: string;
  target_type: string;
  target_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

/* --- admin console (Phase F5) --------------------------------------------- */

export type ReportStatus =
  | "OPEN"
  | "UNDER_REVIEW"
  | "VALID"
  | "DISMISSED"
  | "ACTIONED";

export type ReportTargetType = "JOB" | "BUSINESS" | "USER" | "APPLICATION" | "MESSAGE";

export interface Report {
  id: string;
  reporter: string | null;
  target_type: ReportTargetType;
  target_id: string;
  category: string;
  description: string;
  status: ReportStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  resolution_notes: string;
  created_at: string;
  updated_at: string;
}
