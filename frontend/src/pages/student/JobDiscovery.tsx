import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { listJobs, nearbyJobs } from "../../api/jobs";
import type { JobQuery } from "../../api/jobs";
import { getMyStudentProfile } from "../../api/profiles";
import JobCard from "../../components/jobs/JobCard";
import JobFilters from "../../components/jobs/JobFilters";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";

/**
 * Discovery = two tabs over the verified endpoints:
 * - "All jobs" hits /jobs/jobs/ with the filter set (server-filtered and
 *   server-sorted; students only ever see PUBLISHED/OPEN).
 * - "Nearby campus" hits /jobs/jobs/nearby/ with the student's campus (or an
 *   explicit campus_id) and a radius in km.
 */
export default function JobDiscovery() {
  const [tab, setTab] = useState<"all" | "nearby">("all");
  const [query, setQuery] = useState<JobQuery>({ sort: "newest", page: 1 });
  const [radius, setRadius] = useState("10");
  const [nearbyPage, setNearbyPage] = useState(1);

  const profileQ = useQuery({ queryKey: ["student-profile"], queryFn: getMyStudentProfile, staleTime: 60_000 });
  const campusId = query.campus_id ?? (tab === "nearby" ? (profileQ.data?.campus?.id ?? undefined) : undefined);

  const jobsQ = useQuery({
    queryKey: ["jobs", query],
    queryFn: () => listJobs(query),
    enabled: tab === "all",
    placeholderData: keepPreviousData,
  });

  const nearbyQ = useQuery({
    queryKey: ["jobs-nearby", campusId, radius, nearbyPage],
    queryFn: () => nearbyJobs({ campus_id: campusId, radius_km: radius, page: nearbyPage }),
    enabled: tab === "nearby" && !!campusId,
    retry: false,
    placeholderData: keepPreviousData,
  });

  const active = tab === "all" ? jobsQ : nearbyQ;
  const data = active.data;

  return (
    <section className="discovery-layout">
      <JobFilters value={query} onChange={setQuery} />

      <div className="discovery-main">
        <div className="tab-row">
          <button className={`btn ${tab === "all" ? "primary" : "ghost"}`} onClick={() => setTab("all")}>
            All jobs
          </button>
          <button className={`btn ${tab === "nearby" ? "primary" : "ghost"}`} onClick={() => setTab("nearby")}>
            Nearby campus
          </button>
          {tab === "nearby" && (
            <label className="radius-control">
              Within
              <select value={radius} onChange={(e) => { setRadius(e.target.value); setNearbyPage(1); }}>
                <option value="5">5 km</option>
                <option value="10">10 km</option>
                <option value="20">20 km</option>
                <option value="50">50 km</option>
              </select>
              <span className="muted small">
                {profileQ.data?.campus ? `of ${profileQ.data.campus.name}` : "— set a campus on your profile"}
              </span>
            </label>
          )}
        </div>

        {active.isLoading && <div className="page-loading">Loading jobs…</div>}
        {active.isError && <ErrorState error={active.error} retry={() => active.refetch()} />}

        {data && (
          <>
            <p className="muted small result-count">{data.count} job{data.count === 1 ? "" : "s"} found</p>
            <div className="job-grid">
              {data.results.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
            {data.count === 0 && (
              <div className="card center">
                <p className="muted">No jobs match these filters yet.</p>
              </div>
            )}
            <Pagination
              count={data.count}
              page={tab === "all" ? (query.page ?? 1) : nearbyPage}
              onPage={(p) => (tab === "all" ? setQuery({ ...query, page: p }) : setNearbyPage(p))}
            />
          </>
        )}
      </div>
    </section>
  );
}
