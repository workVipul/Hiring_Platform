"use client";

import { useState } from "react";

import { jdApi } from "@/services/jdApi";
import type { GeneratedJD } from "@/types/jd";
import SkillGraph from "./SkillGraph";

export default function ReviewTab({
  jd,
  onChange,
  onNext,
}: {
  jd: GeneratedJD | null;
  onChange: (jd: GeneratedJD) => void;
  onNext: () => void;
}) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!jd) return <div className="empty-state">Generate a JD first.</div>;

  const currentJD = jd;
  const improvementSuggestions = getQualitySuggestions(currentJD);

  function updateField(key: "title" | "summary" | "compensation" | "about_company", value: string) {
    onChange({ ...currentJD, [key]: value });
  }

  function updateList(key: "responsibilities" | "requirements" | "nice_to_have" | "soft_skills", value: string) {
    onChange({ ...currentJD, [key]: value.split("\n").map((item) => stripExperienceLead(item.trim())).filter(Boolean) });
  }

  function updateExperience(value: string) {
    onChange({
      ...currentJD,
      metadata: { ...(currentJD.metadata ?? {}), experience_years: value },
    });
  }

  async function handleRefine() {
    setLoading(true);
    setError(null);
    try {
      const refined = await jdApi.refine(0, instruction, JSON.stringify(currentJD));
      onChange(refined);
      setInstruction("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refinement failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="review-grid">
      <div className="panel stack">
        <label>Title<input value={currentJD.title} onChange={(e) => updateField("title", e.target.value)} /></label>
        <label>Summary<textarea value={currentJD.summary ?? ""} onChange={(e) => updateField("summary", e.target.value)} rows={6} /></label>
        <label>Experience<input value={getExperience(currentJD)} onChange={(e) => updateExperience(e.target.value)} placeholder="Example: 8-12 years" /></label>
        <label>Responsibilities<textarea value={(currentJD.responsibilities ?? []).join("\n")} onChange={(e) => updateList("responsibilities", e.target.value)} rows={6} /></label>
        <label>Requirements<textarea value={(currentJD.requirements ?? []).join("\n")} onChange={(e) => updateList("requirements", e.target.value)} rows={6} /></label>
        <label>Nice to have<textarea value={(currentJD.nice_to_have ?? []).join("\n")} onChange={(e) => updateList("nice_to_have", e.target.value)} rows={4} /></label>
        <label>Soft skills<textarea value={(currentJD.soft_skills ?? []).join("\n")} onChange={(e) => updateList("soft_skills", e.target.value)} rows={4} /></label>
        <button className="primary-button" onClick={onNext}>Continue to Publish</button>
      </div>

      <aside className="panel stack">
        <h2>Refine</h2>
        <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Example: make this Senior Engineer focused" rows={5} />
        {error && <p className="error">{error}</p>}
        <button className="secondary-button" disabled={loading || instruction.trim().length < 5} onClick={handleRefine}>
          {loading ? "Refining..." : "Apply refinement"}
        </button>
        <div className="metric">
          <span>Quality score</span>
          <strong>{currentJD.jd_score ?? "-"}</strong>
        </div>
        <div className="quality-suggestions">
          <strong>Improve this JD</strong>
          {improvementSuggestions.length > 0 ? (
            <ul>
              {improvementSuggestions.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : (
            <p className="muted small">This draft has the core details recruiters need.</p>
          )}
        </div>
        <SkillGraph jd={currentJD} />
      </aside>
    </div>
  );
}

function getExperience(jd: GeneratedJD): string {
  const metadata = jd.metadata ?? {};
  const value = metadata.experience_years ?? metadata.experience ?? jd["experience"];
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function stripExperienceLead(value: string): string {
  return value.replace(/^experience\s*:?\s*/i, "").trim();
}

function getQualitySuggestions(jd: GeneratedJD): string[] {
  const suggestions: string[] = [];
  const metadata = jd.metadata ?? {};
  if (!jd.summary || jd.summary.length < 120) suggestions.push("Add a sharper job summary with project/domain context.");
  if ((jd.responsibilities ?? []).length < 5) suggestions.push("Add at least 5 key responsibilities.");
  if ((jd.requirements ?? []).length < 5) suggestions.push("Add more qualifications and required skills.");
  if ((jd.skills ?? []).length < 5) suggestions.push("List the must-have technical skills separately.");
  if (!getExperience(jd)) suggestions.push("Add a clear experience range, for example 8-12 years.");
  if (!metadata.location) suggestions.push("Add location.");
  if (!metadata.work_mode) suggestions.push("Add mode of work such as Hybrid, Remote, or Onsite.");
  if ((jd.nice_to_have ?? []).length < 2) suggestions.push("Add good-to-have skills or domain preferences.");
  return suggestions.slice(0, 5);
}
