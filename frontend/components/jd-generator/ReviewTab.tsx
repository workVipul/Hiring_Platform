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

  function updateField(key: "title" | "summary" | "compensation" | "about_company", value: string) {
    onChange({ ...currentJD, [key]: value });
  }

  function updateList(key: "responsibilities" | "requirements" | "nice_to_have", value: string) {
    onChange({ ...currentJD, [key]: value.split("\n").map((item) => item.trim()).filter(Boolean) });
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
        <label>Summary<textarea value={currentJD.summary ?? ""} onChange={(e) => updateField("summary", e.target.value)} rows={4} /></label>
        <label>Responsibilities<textarea value={(currentJD.responsibilities ?? []).join("\n")} onChange={(e) => updateList("responsibilities", e.target.value)} rows={6} /></label>
        <label>Requirements<textarea value={(currentJD.requirements ?? []).join("\n")} onChange={(e) => updateList("requirements", e.target.value)} rows={6} /></label>
        <label>Nice to have<textarea value={(currentJD.nice_to_have ?? []).join("\n")} onChange={(e) => updateList("nice_to_have", e.target.value)} rows={4} /></label>
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
        <SkillGraph jd={currentJD} />
      </aside>
    </div>
  );
}
