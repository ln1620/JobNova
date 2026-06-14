const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("jobnova_token");
}

export function setToken(token: string) {
  localStorage.setItem("jobnova_token", token);
}

export function clearToken() {
  localStorage.removeItem("jobnova_token");
  localStorage.removeItem("jobnova_user");
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join(", ")
          : res.statusText;
    throw new Error(message || "Request failed");
  }
  return res.json();
}

export type User = { id: number; email: string; display_name: string | null };

export async function login(email: string, display_name?: string) {
  return api<{ access_token: string; user: User }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, display_name }),
  });
}

export async function startInterview() {
  return api<{
    room_name: string;
    token: string;
    livekit_url: string;
    interview_id: number;
  }>("/interview/start", { method: "POST" });
}

export async function getInterview(id: number) {
  return api<{
    id: number;
    room_name: string;
    status: string;
    self_intro_summary: string | null;
    experience_summary: string | null;
    transcript: string | null;
  }>(`/interview/${id}`);
}

export type EducationEntry = {
  degree: string;
  school: string;
  year: string;
};

export type ExperienceEntry = {
  title: string;
  company: string;
  start: string;
  end: string;
  bullets: string[];
};

export type ParsedProfile = {
  skills: string[];
  education: EducationEntry[];
  experience: ExperienceEntry[];
  summary: string;
  years_experience: number | null;
  job_titles: string[];
};

export type ResumeProfile = {
  id: number;
  original_filename: string;
  file_type: string;
  raw_text: string | null;
  parsed_json: ParsedProfile | null;
  created_at: string;
  updated_at: string;
};

export async function uploadResume(
  file: File,
): Promise<ResumeProfile & { message?: string; parse_error?: string | null }> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/resume/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join(", ")
          : res.statusText;
    throw new Error(message || "Upload failed");
  }
  return res.json();
}

export async function getResumeProfile(): Promise<ResumeProfile> {
  return api<ResumeProfile>("/resume/profile");
}

export async function updateResumeProfile(parsed_json: ParsedProfile): Promise<ResumeProfile> {
  return api<ResumeProfile>("/resume/profile", {
    method: "PUT",
    body: JSON.stringify({ parsed_json }),
  });
}

export type JobPreferences = {
  id: number;
  job_titles: string[];
  locations: string[];
  work_types: string[];
  seniority: string | null;
  created_at: string;
  updated_at: string;
};

export type JobPreferencesInput = {
  job_titles: string[];
  locations: string[];
  work_types: string[];
  seniority: string | null;
};

export async function getJobPreferences(): Promise<JobPreferences> {
  return api<JobPreferences>("/preferences");
}

export async function updateJobPreferences(
  prefs: JobPreferencesInput,
): Promise<JobPreferences> {
  return api<JobPreferences>("/preferences", {
    method: "PUT",
    body: JSON.stringify(prefs),
  });
}

export type SkillMatchDetail = {
  jd_skill: string;
  resume_skill: string | null;
  match_score: number;
  match_type: string;
  importance: string;
  weight: number;
};

export type MatchedJob = {
  external_id: string;
  company: string;
  title: string;
  location: string;
  apply_url: string;
  board_token: string;
  match_score: number;
  title_score: number;
  skill_score: number;
  location_score: number;
  matched_skills: string[];
  skill_match_details: SkillMatchDetail[];
};

export type JobDiscoverResult = {
  total_fetched: number;
  total_analyzed: number;
  total_matched: number;
  min_skill_match: number;
  jobs: MatchedJob[];
};

export async function discoverJobs(): Promise<JobDiscoverResult> {
  return api<JobDiscoverResult>("/jobs/discover", { method: "POST" });
}

export type ApplicationRecord = {
  id: number;
  external_job_id: string;
  company: string;
  title: string;
  location: string;
  apply_url: string;
  status: string;
  message: string | null;
  created_at: string;
  updated_at: string;
};

export async function queueApplications(
  consent: boolean,
  jobs: {
    external_id: string;
    company: string;
    title: string;
    location: string;
    apply_url: string;
  }[],
): Promise<{ queued: number; resumed: boolean; applications: ApplicationRecord[] }> {
  return api("/applications/queue", {
    method: "POST",
    body: JSON.stringify({ consent, jobs }),
  });
}

export async function getApplications(): Promise<ApplicationRecord[]> {
  return api<ApplicationRecord[]>("/applications");
}

export async function resetStuckApplications(): Promise<{ reset: number }> {
  return api<{ reset: number }>("/applications/reset-stuck", { method: "POST" });
}

export async function clearQueuedApplications(): Promise<{ cleared: number }> {
  return api<{ cleared: number }>("/applications/clear-queued", { method: "POST" });
}

export async function stopAutoApply(): Promise<{ ok: boolean; stopped: number }> {
  return api<{ ok: boolean; stopped: number }>("/applications/stop-auto-apply", {
    method: "POST",
  });
}

export type ApplicationAnswersInput = {
  country: string;
  city: string;
  phone: string;
  linkedin_url: string | null;
  authorized_to_work: string;
  require_sponsorship: string;
  previously_employed: string;
  veteran_status: string;
  disability_status: string;
  race: string;
  ethnicity: string;
  gender: string;
};

export const DEFAULT_APPLICATION_ANSWERS: ApplicationAnswersInput = {
  country: "United States",
  city: "",
  phone: "",
  linkedin_url: null,
  authorized_to_work: "Yes",
  require_sponsorship: "No",
  previously_employed: "No",
  veteran_status: "I am not a protected veteran",
  disability_status: "No, I do not have a disability",
  race: "Decline to self-identify",
  ethnicity: "Decline to self-identify",
  gender: "Decline to self-identify",
};

export async function getApplicationAnswers(): Promise<ApplicationAnswersInput | null> {
  try {
    const data = await api<ApplicationAnswersInput & { id: number }>("/applications/answers");
    const { id: _id, ...rest } = data;
    return rest;
  } catch {
    return null;
  }
}

export async function saveApplicationAnswers(
  data: ApplicationAnswersInput,
): Promise<ApplicationAnswersInput> {
  const saved = await api<ApplicationAnswersInput & { id: number }>("/applications/answers", {
    method: "PUT",
    body: JSON.stringify(data),
  });
  const { id: _id, ...rest } = saved;
  return rest;
}

export type WorkerHealth = {
  at: string | null;
  status: string;
  message: string;
  apply_enabled?: boolean;
};

export async function getWorkerHealth(): Promise<WorkerHealth> {
  return api<WorkerHealth>("/applications/worker/health");
}

