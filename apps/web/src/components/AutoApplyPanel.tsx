"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApplicationRecord,
  getApplications,
  getWorkerHealth,
  MatchedJob,
  clearQueuedApplications,
  queueApplications,
  resetStuckApplications,
} from "@/lib/api";

const CONSENT_TEXT =
  "I authorize JobNova to fill and submit job applications on my behalf using my resume and profile.";

type Toast = { id: number; type: "success" | "error" | "info"; text: string };

export function AutoApplyPanel({ jobs }: { jobs: MatchedJob[] }) {
  const [consent, setConsent] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [workerStatus, setWorkerStatus] = useState<string>("unknown");
  const [applyEnabled, setApplyEnabled] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seenStatus = useRef<Record<number, string>>({});
  const toastId = useRef(0);
  const initialLoad = useRef(true);

  const leverJobs = jobs.filter((j) => j.apply_url.includes("lever.co"));
  const queuedCount = applications.filter((a) => a.status === "queued").length;
  const inProgressCount = applications.filter((a) => a.status === "in_progress").length;

  const addToast = useCallback((type: Toast["type"], text: string) => {
    const id = ++toastId.current;
    setToasts((prev) => [...prev, { id, type, text }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 6000);
  }, []);

  const refreshApplications = useCallback(async () => {
    try {
      const apps = await getApplications();
      setApplications(apps);

      for (const app of apps) {
        const prev = seenStatus.current[app.id];
        if (prev === undefined && initialLoad.current) {
          seenStatus.current[app.id] = app.status;
          continue;
        }
        if (prev === app.status) continue;
        seenStatus.current[app.id] = app.status;

        if (app.status === "submitted") {
          addToast("success", `Successfully applied to ${app.title} at ${app.company}`);
        } else if (app.status === "failed") {
          const msg = app.message || "";
          if (msg.includes("Reset") || msg.includes("Skipped") || msg.includes("Stopped")) continue;
          addToast("error", `Failed to apply to ${app.title}: ${msg || "Unknown error"}`);
        } else if (app.status === "blocked") {
          addToast("info", `Paused on ${app.title} — manual review needed on server`);
        }
      }
      initialLoad.current = false;
    } catch {
      // ignore poll errors
    }
  }, [addToast]);

  useEffect(() => {
    refreshApplications();
    const interval = setInterval(refreshApplications, 3000);
    return () => clearInterval(interval);
  }, [refreshApplications]);

  useEffect(() => {
    async function pollWorker() {
      try {
        const health = await getWorkerHealth();
        setWorkerStatus(health.status || "unknown");
        setApplyEnabled(Boolean(health.apply_enabled));
      } catch {
        setWorkerStatus("offline");
      }
    }
    pollWorker();
    const interval = setInterval(pollWorker, 10000);
    return () => clearInterval(interval);
  }, []);

  async function handleStartApply() {
    if (!consent) {
      addToast("error", "Please check the consent box before starting auto-apply.");
      return;
    }
    if (!leverJobs.length) {
      addToast("error", "No Lever apply links found. Re-run job search.");
      return;
    }

    setApplying(true);
    try {
      const result = await queueApplications(
        true,
        leverJobs.map((j) => ({
          external_id: j.external_id,
          company: j.company,
          title: j.title,
          location: j.location,
          apply_url: j.apply_url,
        })),
      );
      addToast(
        "info",
        result.resumed
          ? `Worker resumed — ${result.applications.length} jobs in queue.`
          : `Queued ${result.queued} applications. EC2 worker will apply automatically.`,
      );
      await refreshApplications();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not start auto-apply";
      if (msg.includes("already queued") || msg.includes("No valid Lever")) {
        addToast(
          "info",
          queuedCount > 0 || inProgressCount > 0
            ? `${queuedCount + inProgressCount} jobs already in the queue. Worker is applying — no need to click again.`
            : "Jobs already queued. Check Application status below.",
        );
      } else {
        addToast("error", msg);
      }
    } finally {
      setApplying(false);
    }
  }

  const active = applications.filter((a) =>
    ["queued", "in_progress", "blocked"].includes(a.status),
  );
  const done = applications.filter((a) => ["submitted", "failed"].includes(a.status));

  const workerLabel =
    workerStatus === "running" && applyEnabled
      ? "EC2 apply worker: applying to your jobs"
      : workerStatus === "running"
        ? "EC2 apply worker: online (waiting for you to click Start)"
        : workerStatus === "offline"
          ? "EC2 apply worker: offline (start worker on server)"
          : `EC2 apply worker: ${workerStatus}`;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-white">Auto Apply</h2>
        <p className="mt-2 text-sm text-slate-400">
          Step 5: After login, resume, answers, and job search — click Start to apply.
        </p>
      </div>

      <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-1 rounded border-white/20 bg-black/20"
        />
        <span>{CONSENT_TEXT}</span>
      </label>

      <div
        className={`rounded-lg border p-4 text-sm ${
          workerStatus === "running"
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
            : "border-amber-500/30 bg-amber-500/10 text-amber-200"
        }`}
      >
        <p className="font-medium">{workerLabel}</p>
        <p className="mt-1 opacity-80">
          Applications run on EC2 with real Chrome + JobNova extension. No local extension needed.
        </p>
        {(queuedCount > 0 || inProgressCount > 0) && (
          <p className="mt-2 font-medium">
            {inProgressCount > 0 && `${inProgressCount} applying now`}
            {inProgressCount > 0 && queuedCount > 0 && " · "}
            {queuedCount > 0 && `${queuedCount} waiting in queue`}
            {" — "}
            do not click Start again.
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleStartApply}
          disabled={applying || !leverJobs.length}
          className="rounded-full bg-violet-500 px-6 py-3 font-semibold text-white hover:bg-violet-400 disabled:opacity-50"
        >
          {applying
            ? "Queueing…"
            : `Start auto-apply (${Math.min(leverJobs.length, 15)} Lever jobs)`}
        </button>
        <button
          type="button"
          onClick={async () => {
            const r = await clearQueuedApplications();
            addToast("info", `Cleared ${r.cleared} old queued jobs — re-run job search`);
            await refreshApplications();
          }}
          className="rounded-full border border-white/20 px-6 py-3 text-sm text-slate-300 hover:bg-white/10"
        >
          Clear old queue
        </button>
        <button
          type="button"
          onClick={async () => {
            const r = await resetStuckApplications();
            addToast("info", `Reset ${r.reset} stuck applications`);
            await refreshApplications();
          }}
          className="rounded-full border border-white/20 px-6 py-3 text-sm text-slate-300 hover:bg-white/10"
        >
          Reset stuck jobs
        </button>
      </div>

      {applications.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-white">Application status</h3>
          {active.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">In progress</p>
              {active.map((app) => (
                <div
                  key={app.id}
                  className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm"
                >
                  <span className="text-white">{app.title}</span>
                  <span className="text-slate-500"> · {app.company}</span>
                  <span className="ml-2 rounded bg-violet-500/20 px-2 py-0.5 text-xs text-violet-300">
                    {app.status}
                  </span>
                </div>
              ))}
            </div>
          )}
          {done.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">Completed</p>
              {done.slice(0, 15).map((app) => (
                <div
                  key={app.id}
                  className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm"
                >
                  <span className="text-white">{app.title}</span>
                  <span className="text-slate-500"> · {app.company}</span>
                  <span
                    className={`ml-2 rounded px-2 py-0.5 text-xs ${
                      app.status === "submitted"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-red-500/20 text-red-300"
                    }`}
                  >
                    {app.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`max-w-sm rounded-lg px-4 py-3 text-sm shadow-lg ${
              t.type === "success"
                ? "bg-emerald-600 text-white"
                : t.type === "error"
                  ? "bg-red-600 text-white"
                  : "bg-slate-700 text-white"
            }`}
          >
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
