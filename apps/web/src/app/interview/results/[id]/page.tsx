"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getInterview, getToken } from "@/lib/api";

export default function InterviewResultsPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [data, setData] = useState<Awaited<ReturnType<typeof getInterview>> | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getInterview(id)
      .then(setData)
      .catch(() => setData(null));
  }, [id, router]);

  return (
    <div className="hero-gradient min-h-screen px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white">
          ← Dashboard
        </Link>
        <h1 className="mt-4 text-3xl font-bold text-white">Interview Summary</h1>
        {!data ? (
          <p className="mt-8 text-slate-400">
            Waiting for agent to save results… Refresh in a few seconds after finishing.
          </p>
        ) : (
          <div className="card-glass mt-8 space-y-6 p-8">
            <div>
              <h2 className="text-sm font-medium text-violet-300">Self introduction</h2>
              <p className="mt-2 text-slate-300">
                {data.self_intro_summary || "—"}
              </p>
            </div>
            <div>
              <h2 className="text-sm font-medium text-violet-300">Past experience</h2>
              <p className="mt-2 text-slate-300">
                {data.experience_summary || "—"}
              </p>
            </div>
            {data.transcript && (
              <div>
                <h2 className="text-sm font-medium text-violet-300">Transcript</h2>
                <pre className="mt-2 whitespace-pre-wrap text-sm text-slate-500">
                  {data.transcript}
                </pre>
              </div>
            )}
            <p className="text-xs text-slate-500">Status: {data.status}</p>
          </div>
        )}
      </div>
    </div>
  );
}
