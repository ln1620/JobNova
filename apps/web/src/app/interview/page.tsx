"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { InterviewRoom } from "@/components/InterviewRoom";
import { getToken } from "@/lib/api";

export default function InterviewPage() {
  const router = useRouter();
  const [session, setSession] = useState<{
    token: string;
    livekit_url: string;
    interview_id: number;
  } | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    const raw = sessionStorage.getItem("jobnova_interview");
    if (!raw) {
      router.replace("/dashboard");
      return;
    }
    setSession(JSON.parse(raw));
  }, [router]);

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        Loading interview…
      </div>
    );
  }

  return (
    <div className="hero-gradient min-h-screen">
      <div className="mx-auto max-w-3xl px-6 py-8">
        <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white">
          ← Back
        </Link>
        <h1 className="mt-4 text-2xl font-bold text-white">Mock Interview</h1>
        <p className="mt-2 text-sm text-slate-400">
          Listen to each question, then press Record, speak, and press Done.
        </p>
        <InterviewRoom
          token={session.token}
          serverUrl={session.livekit_url}
          interviewId={session.interview_id}
        />
      </div>
    </div>
  );
}
