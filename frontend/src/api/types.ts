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
  created_at: string;
  updated_at: string;
}

/* --- applications (Phase 6) ---------------------------------------------- */

export type ApplicationStatus =
  | "SUBMITTED"
  | "SELECTED"
  | "REJECTED"
  | "WITHDRAWN"
  | "COMPLETED";

export interface Application {
  id: string;
  job: string;
  job_id: string;
  student: string;
  cover_note: string;
  status: ApplicationStatus;
  submitted_at: string;
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
