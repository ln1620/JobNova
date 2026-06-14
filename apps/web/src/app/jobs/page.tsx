"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { getToken, searchJobs, type JobRow } from "@/lib/api";

function toCsv(rows: JobRow[]) {
  const header = "company_name,career_page_url,open_position_url";
  const lines = rows.map(
    (r) =>
      `"${r.company_name.replace(/"/g, '""')}","${(r.career_page_url || "").replace(/"/g, '""')}","${(r.open_position_url || "").replace(/"/g, '""')}"`,
  );
  return [header, ...lines].join("\n");
}

export default function JobsPage() {
  const router = useRouter();
  const [query, setQuery] = useState("AI engineer");
  const [location, setLocation] = useState("United States");
  const [rows, setRows] = useState<JobRow[]>([]);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!getToken()) {
      router.push("/login");
      return;
    }
    setLoading(true);
    setError("");
    setRows([]);
    try {
      const res = await searchJobs(query, location);
      setRows(res.rows);
      setSource(res.source);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function downloadCsv() {
    const blob = new Blob([toCsv(rows)], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "jobnova-jobs.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="hero-gradient min-h-screen">
      <Navbar />
      <main className="mx-auto max-w-5xl px-6 py-12">
        <h1 className="text-3xl font-bold text-white">AI Job Source Agent</h1>
        <p className="mt-2 text-slate-400">
          LinkedIn listings → company site → career page → one opening URL
        </p>

        <form onSubmit={handleSearch} className="card-glass mt-8 flex flex-wrap gap-4 p-6">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Job title or keywords"
            className="min-w-[200px] flex-1 rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-white"
          />
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location"
            className="min-w-[160px] rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-white"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-full bg-emerald-500 px-8 py-3 font-semibold text-[#0b1020] hover:bg-emerald-400 disabled:opacity-50"
          >
            {loading ? "Searching…" : "Search"}
          </button>
        </form>

        {loading && (
          <p className="mt-4 text-sm text-slate-400">
            Fetching jobs from RapidAPI, then resolving career pages (about 1–2 minutes
            for 2 companies)…
          </p>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-300">
            <p>{error}</p>
            {error.includes("429") || error.toLowerCase().includes("rate limit") ? (
              <p className="mt-2 text-sm text-red-200/80">
                RapidAPI free tiers allow very few searches per minute. Wait 1–2 minutes,
                then try again with a simpler query (e.g. &quot;software engineer&quot;).
              </p>
            ) : null}
          </div>
        )}
        {source && (
          <p className="mt-4 text-sm text-slate-500">Source: {source}</p>
        )}

        {rows.length > 0 && (
          <>
            <button
              type="button"
              onClick={downloadCsv}
              className="mt-6 rounded-full border border-white/20 px-4 py-2 text-sm text-white hover:bg-white/10"
            >
              Download CSV
            </button>
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="py-3 pr-4">Company name</th>
                    <th className="py-3 pr-4">Company website</th>
                    <th className="py-3 pr-4">Career page URL</th>
                    <th className="py-3 pr-4">Open position URL</th>
                    <th className="py-3">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className="border-b border-white/5">
                      <td className="py-3 pr-4 text-white">{r.company_name}</td>
                      <td className="py-3 pr-4">
                        {r.company_website ? (
                          <a
                            href={r.company_website}
                            target="_blank"
                            rel="noreferrer"
                            className="text-slate-300 hover:underline"
                          >
                            Website
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        {r.career_page_url ? (
                          <a
                            href={r.career_page_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-violet-400 hover:underline"
                          >
                            Link
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        {r.open_position_url ? (
                          <a
                            href={r.open_position_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-emerald-400 hover:underline"
                          >
                            Link
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-3 text-slate-500">{r.error || "OK"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!getToken() && (
          <p className="mt-6 text-slate-400">
            <Link href="/login" className="text-violet-400 hover:underline">
              Log in
            </Link>{" "}
            to search jobs.
          </p>
        )}
      </main>
    </div>
  );
}
