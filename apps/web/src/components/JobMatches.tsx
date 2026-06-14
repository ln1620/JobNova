"use client";

import { MatchedJob } from "@/lib/api";

function scoreColor(score: number): string {
  if (score >= 0.6) return "text-emerald-400";
  if (score >= 0.35) return "text-amber-400";
  return "text-slate-400";
}

export function JobMatches({
  jobs,
  totalFetched,
  loading,
}: {
  jobs: MatchedJob[];
  totalFetched: number;
  loading: boolean;
}) {
  if (loading) {
    return (
      <p className="text-sm text-slate-400">
        Searching Lever job boards for roles matching your preferences…
      </p>
    );
  }

  if (!jobs.length) {
    return (
      <p className="text-sm text-slate-400">
        No jobs matched your preferences. Try broader job titles or more locations.
        Scanned {totalFetched} open roles.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Showing top {jobs.length} jobs matching your preferences (from {totalFetched}{" "}
        open roles).
      </p>
      <div className="space-y-3">
        {jobs.map((job) => (
          <div
            key={job.external_id}
            className="rounded-lg border border-white/10 bg-black/20 p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-white">{job.title}</h3>
                <p className="mt-1 text-sm text-slate-400">
                  {job.company} · {job.location || "Location not listed"}
                </p>
              </div>
              <div className="text-right">
                <p className={`text-lg font-bold ${scoreColor(job.match_score)}`}>
                  {Math.round(job.match_score * 100)}%
                </p>
                <p className="text-xs text-slate-500">preference match</p>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500">
              <span>Title: {Math.round(job.title_score * 100)}%</span>
              <span>Location: {Math.round(job.location_score * 100)}%</span>
            </div>

            <a
              href={job.apply_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block text-sm font-medium text-violet-400 hover:text-violet-300"
            >
              View & apply →
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
