"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApplicationAnswersForm } from "@/components/ApplicationAnswersForm";
import { AutoApplyPanel } from "@/components/AutoApplyPanel";
import { JobMatches } from "@/components/JobMatches";
import { LogoutButton, Navbar } from "@/components/Navbar";
import {
  discoverJobs,
  getApplicationAnswers,
  getJobPreferences,
  getResumeProfile,
  getToken,
  JobPreferencesInput,
  MatchedJob,
  ParsedProfile,
  stopAutoApply,
  updateJobPreferences,
  updateResumeProfile,
  uploadResume,
} from "@/lib/api";

const emptyProfile = (): ParsedProfile => ({
  skills: [],
  education: [],
  experience: [],
  summary: "",
  years_experience: null,
  job_titles: [],
});

const emptyPreferences = (): JobPreferencesInput => ({
  job_titles: [""],
  locations: [""],
  work_types: [],
  seniority: null,
});

const WORK_TYPE_OPTIONS = [
  { id: "remote", label: "Remote" },
  { id: "hybrid", label: "Hybrid" },
  { id: "onsite", label: "On-site" },
] as const;

export default function ApplyPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [rawText, setRawText] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);
  const [profile, setProfile] = useState<ParsedProfile>(emptyProfile());
  const [saved, setSaved] = useState(false);
  const [prefs, setPrefs] = useState<JobPreferencesInput>(emptyPreferences());
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [prefsSaved, setPrefsSaved] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [matchedJobs, setMatchedJobs] = useState<MatchedJob[]>([]);
  const [totalFetched, setTotalFetched] = useState(0);
  const [jobsSearched, setJobsSearched] = useState(false);
  const [answersSaved, setAnswersSaved] = useState(false);

  const loadProfile = useCallback(async () => {
    try {
      const data = await getResumeProfile();
      setRawText(data.raw_text);
      setFilename(data.original_filename);
      if (data.parsed_json) {
        setProfile(data.parsed_json);
        setSaved(true);
      }
    } catch {
      // No resume yet — expected on first visit
    }
    try {
      const data = await getJobPreferences();
      setPrefs({
        job_titles: data.job_titles.length ? data.job_titles : [""],
        locations: data.locations.length ? data.locations : [""],
        work_types: data.work_types,
        seniority: data.seniority,
      });
      setPrefsSaved(true);
    } catch {
      // No preferences yet
    }
    try {
      const answers = await getApplicationAnswers();
      if (answers?.city?.trim() && answers?.phone?.trim()) {
        setAnswersSaved(true);
      }
    } catch {
      // No application answers yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    stopAutoApply().catch(() => {});
    loadProfile();
  }, [router, loadProfile]);

  async function handleFile(file: File) {
    const ext = file.name.toLowerCase();
    if (!ext.endsWith(".pdf") && !ext.endsWith(".docx")) {
      setError("Only PDF and DOCX files are supported.");
      return;
    }
    setUploading(true);
    setError("");
    setSuccess("");
    setSaved(false);
    try {
      const data = await uploadResume(file);
      setRawText(data.raw_text);
      setFilename(data.original_filename);
      if (data.parsed_json) {
        setProfile(data.parsed_json);
      } else {
        setProfile(emptyProfile());
      }
      if (data.parse_error) {
        setError(data.message || data.parse_error);
      } else {
        setSuccess(data.message || "Resume processed. Review and edit your profile below, then save.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await updateResumeProfile(profile);
      setSaved(true);
      setSuccess("Profile saved. Fill in your job preferences below (Step 2).");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function updateSkill(index: number, value: string) {
    const skills = [...profile.skills];
    skills[index] = value;
    setProfile({ ...profile, skills });
    setSaved(false);
  }

  function addSkill() {
    setProfile({ ...profile, skills: [...profile.skills, ""] });
    setSaved(false);
  }

  function removeSkill(index: number) {
    setProfile({ ...profile, skills: profile.skills.filter((_, i) => i !== index) });
    setSaved(false);
  }

  function updateEducation(index: number, field: keyof ParsedProfile["education"][0], value: string) {
    const education = [...profile.education];
    education[index] = { ...education[index], [field]: value };
    setProfile({ ...profile, education });
    setSaved(false);
  }

  function addEducation() {
    setProfile({
      ...profile,
      education: [...profile.education, { degree: "", school: "", year: "" }],
    });
    setSaved(false);
  }

  function updateExperience(
    index: number,
    field: keyof Omit<ParsedProfile["experience"][0], "bullets">,
    value: string,
  ) {
    const experience = [...profile.experience];
    experience[index] = { ...experience[index], [field]: value };
    setProfile({ ...profile, experience });
    setSaved(false);
  }

  function updateBullet(expIndex: number, bulletIndex: number, value: string) {
    const experience = [...profile.experience];
    const bullets = [...experience[expIndex].bullets];
    bullets[bulletIndex] = value;
    experience[expIndex] = { ...experience[expIndex], bullets };
    setProfile({ ...profile, experience });
    setSaved(false);
  }

  function addExperience() {
    setProfile({
      ...profile,
      experience: [
        ...profile.experience,
        { title: "", company: "", start: "", end: "", bullets: [""] },
      ],
    });
    setSaved(false);
  }

  async function handleDiscoverJobs() {
    setDiscovering(true);
    setError("");
    setSuccess("");
    setJobsSearched(false);
    try {
      const result = await discoverJobs();
      setMatchedJobs(result.jobs);
      setTotalFetched(result.total_fetched);
      setJobsSearched(true);
      if (result.jobs.length) {
        setSuccess(`Found ${result.jobs.length} jobs matching your preferences.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Job search failed");
    } finally {
      setDiscovering(false);
    }
  }

  async function handleSavePreferences() {
    setSavingPrefs(true);
    setError("");
    setSuccess("");
    try {
      await updateJobPreferences(prefs);
      setPrefsSaved(true);
      setSuccess("Preferences saved — ready for job matching (Step 3).");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingPrefs(false);
    }
  }

  function updatePrefList(
    field: "job_titles" | "locations",
    index: number,
    value: string,
  ) {
    const list = [...prefs[field]];
    list[index] = value;
    setPrefs({ ...prefs, [field]: list });
    setPrefsSaved(false);
  }

  function addPrefItem(field: "job_titles" | "locations") {
    setPrefs({ ...prefs, [field]: [...prefs[field], ""] });
    setPrefsSaved(false);
  }

  function removePrefItem(field: "job_titles" | "locations", index: number) {
    const list = prefs[field].filter((_, i) => i !== index);
    setPrefs({ ...prefs, [field]: list.length ? list : [""] });
    setPrefsSaved(false);
  }

  function toggleWorkType(id: string) {
    const has = prefs.work_types.includes(id);
    const work_types = has
      ? prefs.work_types.filter((w) => w !== id)
      : [...prefs.work_types, id];
    setPrefs({ ...prefs, work_types });
    setPrefsSaved(false);
  }

  const showProfileEditor = Boolean(rawText);

  return (
    <div className="hero-gradient min-h-screen">
      <Navbar showAuth={false} />
      <main className="mx-auto max-w-4xl px-6 py-12">
        <div className="flex items-center justify-between">
          <div>
            <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white">
              ← Dashboard
            </Link>
            <h1 className="mt-2 text-3xl font-bold text-white">Auto Apply Setup</h1>
            <p className="mt-2 text-slate-400">
              Steps 1–4: Resume → Preferences → Jobs → Auto-apply
            </p>
          </div>
          <LogoutButton />
        </div>

        <div
          className="card-glass mt-8 border-2 border-dashed border-white/10 p-10 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
        >
          <p className="text-slate-300">Drag and drop your resume here, or choose a file</p>
          <p className="mt-1 text-sm text-slate-500">PDF or DOCX only</p>
          <label className="mt-6 inline-block cursor-pointer rounded-full bg-emerald-500 px-6 py-3 font-semibold text-[#0b1020] hover:bg-emerald-400">
            {uploading ? "Processing…" : "Choose file"}
            <input
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              disabled={uploading}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />
          </label>
          {filename && (
            <p className="mt-4 text-sm text-emerald-400">Current file: {filename}</p>
          )}
        </div>

        {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
        {success && <p className="mt-4 text-sm text-emerald-400">{success}</p>}

        {loading && <p className="mt-8 text-slate-400">Loading profile…</p>}

        {!loading && rawText && (
          <div className="card-glass mt-8 p-6">
            <button
              type="button"
              onClick={() => setShowRawText(!showRawText)}
              className="text-sm font-medium text-violet-400 hover:text-violet-300"
            >
              {showRawText ? "Hide extracted text" : "View extracted text"}
            </button>
            {showRawText && (
              <pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-4 text-xs text-slate-300">
                {rawText}
              </pre>
            )}
          </div>
        )}

        {!loading && showProfileEditor && (
          <div className="card-glass mt-8 space-y-8 p-8">
            <section>
              <h2 className="text-lg font-semibold text-white">Summary</h2>
              <textarea
                value={profile.summary}
                onChange={(e) => {
                  setProfile({ ...profile, summary: e.target.value });
                  setSaved(false);
                }}
                rows={3}
                className="mt-3 w-full rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
              />
            </section>

            <section>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Skills</h2>
                <button
                  type="button"
                  onClick={addSkill}
                  className="text-sm text-emerald-400 hover:text-emerald-300"
                >
                  + Add skill
                </button>
              </div>
              <div className="mt-3 space-y-2">
                {profile.skills.map((skill, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      value={skill}
                      onChange={(e) => updateSkill(i, e.target.value)}
                      className="flex-1 rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                    />
                    <button
                      type="button"
                      onClick={() => removeSkill(i)}
                      className="text-sm text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Education</h2>
                <button
                  type="button"
                  onClick={addEducation}
                  className="text-sm text-emerald-400 hover:text-emerald-300"
                >
                  + Add education
                </button>
              </div>
              <div className="mt-3 space-y-4">
                {profile.education.map((edu, i) => (
                  <div key={i} className="grid gap-2 sm:grid-cols-3">
                    <input
                      placeholder="Degree"
                      value={edu.degree}
                      onChange={(e) => updateEducation(i, "degree", e.target.value)}
                      className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                    />
                    <input
                      placeholder="School"
                      value={edu.school}
                      onChange={(e) => updateEducation(i, "school", e.target.value)}
                      className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                    />
                    <input
                      placeholder="Year"
                      value={edu.year}
                      onChange={(e) => updateEducation(i, "year", e.target.value)}
                      className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                    />
                  </div>
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Experience</h2>
                <button
                  type="button"
                  onClick={addExperience}
                  className="text-sm text-emerald-400 hover:text-emerald-300"
                >
                  + Add experience
                </button>
              </div>
              <div className="mt-3 space-y-6">
                {profile.experience.map((exp, i) => (
                  <div key={i} className="rounded-lg border border-white/10 p-4">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <input
                        placeholder="Title"
                        value={exp.title}
                        onChange={(e) => updateExperience(i, "title", e.target.value)}
                        className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                      />
                      <input
                        placeholder="Company"
                        value={exp.company}
                        onChange={(e) => updateExperience(i, "company", e.target.value)}
                        className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                      />
                      <input
                        placeholder="Start"
                        value={exp.start}
                        onChange={(e) => updateExperience(i, "start", e.target.value)}
                        className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                      />
                      <input
                        placeholder="End"
                        value={exp.end}
                        onChange={(e) => updateExperience(i, "end", e.target.value)}
                        className="rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                      />
                    </div>
                    <div className="mt-3 space-y-2">
                      {exp.bullets.map((bullet, j) => (
                        <input
                          key={j}
                          placeholder="Achievement or responsibility"
                          value={bullet}
                          onChange={(e) => updateBullet(i, j, e.target.value)}
                          className="w-full rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-full bg-emerald-500 px-6 py-3 font-semibold text-[#0b1020] hover:bg-emerald-400 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save profile"}
            </button>

            {saved && (
              <p className="text-sm text-emerald-400">
                Profile saved. Scroll down to set job preferences (Step 2).
              </p>
            )}
          </div>
        )}

        {!loading && (
          <div className="card-glass mt-8 space-y-8 p-8">
            <div>
              <h2 className="text-xl font-semibold text-white">Job Preferences</h2>
              <p className="mt-2 text-sm text-slate-400">
                Step 2: Tell us what roles and locations you are looking for.
              </p>
            </div>

            <section>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">Target job titles</h3>
                <button
                  type="button"
                  onClick={() => addPrefItem("job_titles")}
                  className="text-sm text-emerald-400 hover:text-emerald-300"
                >
                  + Add title
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                e.g. Software Engineer, Data Analyst, Product Manager
              </p>
              <div className="mt-3 space-y-2">
                {prefs.job_titles.map((title, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      value={title}
                      onChange={(e) => updatePrefList("job_titles", i, e.target.value)}
                      placeholder="Job title"
                      className="flex-1 rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                    />
                    <button
                      type="button"
                      onClick={() => removePrefItem("job_titles", i)}
                      className="text-sm text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">Locations</h3>
                <button
                  type="button"
                  onClick={() => addPrefItem("locations")}
                  className="text-sm text-emerald-400 hover:text-emerald-300"
                >
                  + Add location
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Enter country only, e.g. USA, United States, Canada, UK
              </p>
              <div className="mt-3 space-y-2">
                {prefs.locations.map((loc, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      value={loc}
                      onChange={(e) => updatePrefList("locations", i, e.target.value)}
                      placeholder="Location"
                      className="flex-1 rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
                    />
                    <button
                      type="button"
                      onClick={() => removePrefItem("locations", i)}
                      className="text-sm text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white">Work type</h3>
              <div className="mt-3 flex flex-wrap gap-4">
                {WORK_TYPE_OPTIONS.map((opt) => (
                  <label
                    key={opt.id}
                    className="flex cursor-pointer items-center gap-2 text-sm text-slate-300"
                  >
                    <input
                      type="checkbox"
                      checked={prefs.work_types.includes(opt.id)}
                      onChange={() => toggleWorkType(opt.id)}
                      className="rounded border-white/20 bg-black/20"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </section>

            <section>
              <h3 className="text-lg font-semibold text-white">Seniority (optional)</h3>
              <select
                value={prefs.seniority ?? ""}
                onChange={(e) => {
                  setPrefs({
                    ...prefs,
                    seniority: e.target.value || null,
                  });
                  setPrefsSaved(false);
                }}
                className="mt-3 rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
              >
                <option value="">No preference</option>
                <option value="entry">Entry level</option>
                <option value="mid">Mid level</option>
                <option value="senior">Senior</option>
              </select>
            </section>

            <button
              type="button"
              onClick={handleSavePreferences}
              disabled={savingPrefs}
              className="rounded-full bg-violet-500 px-6 py-3 font-semibold text-white hover:bg-violet-400 disabled:opacity-50"
            >
              {savingPrefs ? "Saving…" : "Save preferences"}
            </button>

            {prefsSaved && (
              <p className="text-sm text-emerald-400">
                Preferences saved. Use Step 3 below to find matching jobs.
              </p>
            )}
          </div>
        )}

        {!loading && prefsSaved && (
          <div className="card-glass mt-8 p-8">
            <ApplicationAnswersForm onSaved={setAnswersSaved} />
          </div>
        )}

        {!loading && prefsSaved && answersSaved && (
          <div className="card-glass mt-8 space-y-6 p-8">
            <div>
              <h2 className="text-xl font-semibold text-white">Matching Jobs</h2>
              <p className="mt-2 text-sm text-slate-400">
                Step 4: Find up to 30 jobs matching your target titles, locations, and
                work type preferences.
              </p>
            </div>

            <button
              type="button"
              onClick={handleDiscoverJobs}
              disabled={discovering}
              className="rounded-full bg-emerald-500 px-6 py-3 font-semibold text-[#0b1020] hover:bg-emerald-400 disabled:opacity-50"
            >
              {discovering ? "Searching…" : "Find matching jobs"}
            </button>

            {(discovering || jobsSearched) && (
              <JobMatches
                jobs={matchedJobs}
                totalFetched={totalFetched}
                loading={discovering}
              />
            )}
          </div>
        )}

        {!loading && saved && prefsSaved && answersSaved && jobsSearched && matchedJobs.length > 0 && (
          <div className="card-glass mt-8 p-8">
            <AutoApplyPanel jobs={matchedJobs} />
          </div>
        )}
      </main>
    </div>
  );
}
