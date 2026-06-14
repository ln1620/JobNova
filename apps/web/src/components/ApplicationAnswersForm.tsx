"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApplicationAnswersInput,
  DEFAULT_APPLICATION_ANSWERS,
  getApplicationAnswers,
  saveApplicationAnswers,
} from "@/lib/api";

const YES_NO = ["Yes", "No"];

const VETERAN_OPTIONS = [
  "I am not a protected veteran",
  "I identify as one or more of the classifications of a protected veteran",
  "Decline to self-identify",
];

const DISABILITY_OPTIONS = [
  "Yes, I have a disability",
  "No, I do not have a disability",
  "Decline to self-identify",
];

const RACE_OPTIONS = [
  "American Indian or Alaska Native",
  "Asian",
  "Black or African American",
  "Native Hawaiian or Other Pacific Islander",
  "White",
  "Two or More Races",
  "Decline to self-identify",
];

const ETHNICITY_OPTIONS = [
  "Hispanic or Latino",
  "Not Hispanic or Latino",
  "Decline to self-identify",
];

const GENDER_OPTIONS = [
  "Male",
  "Female",
  "Non-binary",
  "Decline to self-identify",
];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-white">{label}</label>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
    >
      {options.map((opt) => (
        <option key={opt} value={opt} className="bg-slate-900">
          {opt}
        </option>
      ))}
    </select>
  );
}

export function ApplicationAnswersForm({ onSaved }: { onSaved?: (saved: boolean) => void }) {
  const [answers, setAnswers] = useState<ApplicationAnswersInput>(DEFAULT_APPLICATION_ANSWERS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getApplicationAnswers();
      if (data) {
        setAnswers(data);
        setSaved(Boolean(data.city.trim() && data.phone.trim()));
        onSaved?.(Boolean(data.city.trim() && data.phone.trim()));
      }
    } finally {
      setLoading(false);
    }
  }, [onSaved]);

  useEffect(() => {
    load();
  }, [load]);

  function update<K extends keyof ApplicationAnswersInput>(key: K, value: ApplicationAnswersInput[K]) {
    setAnswers((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
    onSaved?.(false);
  }

  async function handleSave() {
    setError("");
    if (!answers.city.trim()) {
      setError("City is required.");
      return;
    }
    if (!answers.phone.trim()) {
      setError("Phone is required.");
      return;
    }
    setSaving(true);
    try {
      await saveApplicationAnswers(answers);
      setSaved(true);
      onSaved?.(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save answers");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-400">Loading application answers…</p>;
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-white">Application Answers</h2>
        <p className="mt-2 text-sm text-slate-400">
          Step 3: Answer common job application questions once. JobNova uses these to auto-fill
          forms, and AI writes answers for company-specific questions (e.g. &quot;Why do you want
          to join us?&quot;).
        </p>
      </div>

      <section className="grid gap-6 md:grid-cols-2">
        <Field label="Country *" hint="Used for country dropdowns on application forms">
          <input
            value={answers.country}
            onChange={(e) => update("country", e.target.value)}
            placeholder="United States"
            className="w-full rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
          />
        </Field>
        <Field label="City *" hint="Your current city for location fields">
          <input
            value={answers.city}
            onChange={(e) => update("city", e.target.value)}
            placeholder="San Francisco"
            className="w-full rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
          />
        </Field>
        <Field label="Phone *">
          <input
            value={answers.phone}
            onChange={(e) => update("phone", e.target.value)}
            placeholder="5551234567"
            className="w-full rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
          />
        </Field>
        <Field label="LinkedIn URL">
          <input
            value={answers.linkedin_url || ""}
            onChange={(e) => update("linkedin_url", e.target.value || null)}
            placeholder="https://linkedin.com/in/yourprofile"
            className="w-full rounded-lg border border-white/10 bg-black/20 px-4 py-2 text-sm text-white"
          />
        </Field>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <Field label="Authorized to work in the country you applied for?">
          <Select
            value={answers.authorized_to_work}
            onChange={(v) => update("authorized_to_work", v)}
            options={YES_NO}
          />
        </Field>
        <Field label="Do you require visa sponsorship?">
          <Select
            value={answers.require_sponsorship}
            onChange={(v) => update("require_sponsorship", v)}
            options={YES_NO}
          />
        </Field>
        <Field label="Previously employed at this company?">
          <Select
            value={answers.previously_employed}
            onChange={(v) => update("previously_employed", v)}
            options={YES_NO}
          />
        </Field>
      </section>

      <section>
        <h3 className="text-lg font-semibold text-white">Voluntary self-identification (EEO)</h3>
        <p className="mt-1 text-xs text-slate-500">
          Most employers ask these. Your choices are saved and used to fill matching dropdowns.
        </p>
        <div className="mt-4 grid gap-6 md:grid-cols-2">
          <Field label="Veteran status">
            <Select
              value={answers.veteran_status}
              onChange={(v) => update("veteran_status", v)}
              options={VETERAN_OPTIONS}
            />
          </Field>
          <Field label="Disability status">
            <Select
              value={answers.disability_status}
              onChange={(v) => update("disability_status", v)}
              options={DISABILITY_OPTIONS}
            />
          </Field>
          <Field label="Race">
            <Select value={answers.race} onChange={(v) => update("race", v)} options={RACE_OPTIONS} />
          </Field>
          <Field label="Ethnicity">
            <Select
              value={answers.ethnicity}
              onChange={(v) => update("ethnicity", v)}
              options={ETHNICITY_OPTIONS}
            />
          </Field>
          <Field label="Gender">
            <Select
              value={answers.gender}
              onChange={(v) => update("gender", v)}
              options={GENDER_OPTIONS}
            />
          </Field>
        </div>
      </section>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <button
        type="button"
        onClick={handleSave}
        disabled={saving}
        className="rounded-full bg-violet-500 px-6 py-3 font-semibold text-white hover:bg-violet-400 disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save application answers"}
      </button>

      {saved && (
        <p className="text-sm text-emerald-400">
          Answers saved. Continue to find matching jobs below.
        </p>
      )}
    </div>
  );
}
