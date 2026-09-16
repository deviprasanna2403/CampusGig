import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listCategories } from "../../api/jobs";
import type { JobQuery } from "../../api/jobs";

const JOB_TYPES = [
  ["ONE_DAY_GIG", "One-day gig"],
  ["WEEKEND", "Weekend"],
  ["PART_TIME", "Part-time"],
  ["TEMPORARY", "Temporary"],
  ["SEASONAL", "Seasonal"],
  ["EVENT_BASED", "Event-based"],
  ["INTERNSHIP", "Internship"],
] as const;

const PAYMENT_TYPES = [
  ["HOURLY", "Hourly"],
  ["DAILY", "Daily"],
  ["WEEKLY", "Weekly"],
  ["MONTHLY", "Monthly"],
  ["FIXED_PROJECT", "Fixed project"],
] as const;

const SORTS = [
  ["newest", "Newest first"],
  ["payment", "Highest payment"],
  ["deadline", "Apply-by deadline"],
  ["distance", "Nearest campus first"],
] as const;

export default function JobFilters({
  value,
  onChange,
}: {
  value: JobQuery;
  onChange: (next: JobQuery) => void;
}) {
  const [searchDraft, setSearchDraft] = useState(value.search ?? "");
  const categoriesQ = useQuery({ queryKey: ["job-categories"], queryFn: listCategories, staleTime: 300_000 });

  // Debounce free-text search so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      if ((value.search ?? "") !== searchDraft) onChange({ ...value, search: searchDraft || undefined, page: 1 });
    }, 400);
    return () => clearTimeout(t);
  }, [searchDraft]); // eslint-disable-line react-hooks/exhaustive-deps

  function set<K extends keyof JobQuery>(key: K, v: JobQuery[K]) {
    onChange({ ...value, [key]: v || undefined, page: 1 });
  }

  return (
    <aside className="filters card">
      <label>
        Search
        <input
          type="search"
          placeholder="Title or description…"
          value={searchDraft}
          onChange={(e) => setSearchDraft(e.target.value)}
        />
      </label>

      <label>
        Category
        <select value={value.category ?? ""} onChange={(e) => set("category", e.target.value)}>
          <option value="">All categories</option>
          {(categoriesQ.data ?? []).map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Job type
        <select value={value.job_type ?? ""} onChange={(e) => set("job_type", e.target.value)}>
          <option value="">Any type</option>
          {JOB_TYPES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>

      <label>
        Payment type
        <select value={value.payment_type ?? ""} onChange={(e) => set("payment_type", e.target.value)}>
          <option value="">Any payment</option>
          {PAYMENT_TYPES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>

      <div className="range-row">
        <label>
          Min ₹
          <input
            type="number"
            min="0"
            value={value.min_payment ?? ""}
            onChange={(e) => set("min_payment", e.target.value)}
          />
        </label>
        <label>
          Max ₹
          <input
            type="number"
            min="0"
            value={value.max_payment ?? ""}
            onChange={(e) => set("max_payment", e.target.value)}
          />
        </label>
      </div>

      <label>
        Sort by
        <select
          value={value.sort ?? "newest"}
          onChange={(e) => set("sort", e.target.value as JobQuery["sort"])}
        >
          {SORTS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        className="btn ghost"
        onClick={() => {
          setSearchDraft("");
          onChange({ sort: "newest", page: 1 });
        }}
      >
        Clear filters
      </button>
    </aside>
  );
}
