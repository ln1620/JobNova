"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LogoutButton, Navbar } from "@/components/Navbar";
import { getToken, startInterview } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ email: string; display_name: string | null } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    const raw = localStorage.getItem("jobnova_user");
    if (raw) setUser(JSON.parse(raw));
  }, [router]);

  async function handleInterview() {
    setLoading(true);
    setError("");
    try {
      const res = await startInterview();
      sessionStorage.setItem(
        "jobnova_interview",
        JSON.stringify({
          token: res.token,
          livekit_url: res.livekit_url,
          interview_id: res.interview_id,
        }),
      );
      router.push("/interview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start interview");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="hero-gradient min-h-screen">
      <Navbar showAuth={false} />
      <main className="mx-auto max-w-4xl px-6 py-12">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">
              Hi{user?.display_name ? `, ${user.display_name}` : ""}
            </h1>
            <p className="mt-2 text-slate-400">{user?.email}</p>
          </div>
          <LogoutButton />
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-2">
        <div className="card-glass p-8">
          <h2 className="text-xl font-semibold text-white">Auto Apply</h2>
          <p className="mt-2 text-sm text-slate-400">
            Upload resume, set preferences, and find matching jobs from Greenhouse boards.
          </p>
          <Link
            href="/apply"
            className="mt-6 inline-block rounded-full bg-violet-500 px-6 py-3 font-semibold text-white hover:bg-violet-400"
          >
            Upload Resume
          </Link>
        </div>

        <div className="card-glass p-8">
          <h2 className="text-xl font-semibold text-white">Mock Interview</h2>
          <p className="mt-2 text-sm text-slate-400">
            Two voice questions: introduce yourself, then past experience. Use Record
            and Done for each answer.
          </p>
          {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
          <button
            type="button"
            onClick={handleInterview}
            disabled={loading}
            className="mt-6 rounded-full bg-emerald-500 px-6 py-3 font-semibold text-[#0b1020] hover:bg-emerald-400 disabled:opacity-50"
          >
            {loading ? "Starting…" : "Take Interview"}
          </button>
        </div>
        </div>
      </main>
    </div>
  );
}
