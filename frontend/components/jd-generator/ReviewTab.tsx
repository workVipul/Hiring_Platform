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
  const canPublish = improvementSuggestions.length === 0;

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

        {false && (
        <>
        {/* Canva-Style Template Chooser Section */}
        <div style={{ marginTop: "24px", borderTop: "1px solid var(--border)", paddingTop: "20px", marginBottom: "20px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: "700", color: "var(--text)", marginBottom: "4px" }}>Select PDF Template</h3>
          <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "14px" }}>
            Choose a professional layout style for the generated Job Description PDF.
          </p>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
            gap: "14px",
            marginBottom: "10px"
          }}>
            {[
              {
                id: "corporate",
                name: "Corporate Classic",
                desc: "Standard Wissen presentation",
                preview: (
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", padding: "8px", background: "#ffffff", height: "90px", width: "100%" }}>
                    {/* Header */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #1A2D58", paddingBottom: "2px" }}>
                      <span style={{ fontSize: "6px", fontWeight: "800", color: "#1A2D58" }}>WISSEN</span>
                      <span style={{ fontSize: "5px", color: "#ccc" }}>•••</span>
                    </div>
                    {/* Content */}
                    <div style={{ height: "4px", background: "#1A2D58", width: "60%", borderRadius: "1px" }} />
                    <div style={{ height: "3px", background: "#f0f0f0", width: "100%", borderRadius: "1px" }} />
                    <div style={{ height: "3px", background: "#f0f0f0", width: "90%", borderRadius: "1px" }} />
                    <div style={{ height: "3px", background: "#f0f0f0", width: "40%", borderRadius: "1px", marginTop: "2px" }} />
                    <div style={{ height: "3px", background: "#f0f0f0", width: "80%", borderRadius: "1px" }} />
                  </div>
                )
              },
              {
                id: "modern",
                name: "Modern Minimalist",
                desc: "Clean & compact text layout",
                preview: (
                  <div style={{ display: "flex", flexDirection: "column", gap: "3px", padding: "8px", background: "#ffffff", height: "90px", width: "100%" }}>
                    {/* Header with logo on the right side */}
                    <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", borderBottom: "1px solid #1A2D58", paddingBottom: "2px" }}>
                      <span style={{ fontSize: "5px", fontWeight: "800", color: "#1A2D58" }}>WISSEN</span>
                    </div>
                    {/* Content */}
                    <div style={{ height: "4px", background: "#1A2D58", width: "45%", borderRadius: "1px", marginTop: "2px" }} />
                    <div style={{ height: "3px", background: "#f5f5f5", width: "100%", borderRadius: "1px" }} />
                    <div style={{ height: "3px", background: "#f5f5f5", width: "100%", borderRadius: "1px" }} />
                    <div style={{ height: "3px", background: "#f5f5f5", width: "95%", borderRadius: "1px" }} />
                    <div style={{ height: "3px", background: "#f5f5f5", width: "60%", borderRadius: "1px" }} />
                  </div>
                )
              },
              {
                id: "executive",
                name: "Executive Serif",
                desc: "Centered editorial design",
                preview: (
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", padding: "8px", background: "#ffffff", height: "90px", width: "100%" }}>
                    {/* Header with centered logo */}
                    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", borderBottom: "2.5px double #1A2D58", paddingBottom: "2px", width: "100%" }}>
                      <span style={{ fontSize: "5.5px", fontWeight: "800", color: "#1A2D58" }}>WISSEN</span>
                    </div>
                    {/* Content */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px", width: "100%", marginTop: "2px" }}>
                      <div style={{ height: "4px", background: "#1A2D58", width: "50%", borderRadius: "1px" }} />
                      <div style={{ height: "3px", background: "#f3f3f3", width: "90%", borderRadius: "1px" }} />
                      <div style={{ height: "3px", background: "#f3f3f3", width: "85%", borderRadius: "1px" }} />
                      <div style={{ height: "3px", background: "#f3f3f3", width: "95%", borderRadius: "1px" }} />
                    </div>
                  </div>
                )
              },
              {
                id: "tech",
                name: "Clean Tech",
                desc: "Tech-focused code layout",
                preview: (
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", padding: "8px", background: "#ffffff", height: "90px", width: "100%" }}>
                    {/* Header */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "2px solid #1A2D58", paddingBottom: "2px", width: "100%" }}>
                      <span style={{ fontSize: "5.5px", fontWeight: "800", color: "#1A2D58" }}>WISSEN</span>
                      <span style={{ fontSize: "5px", fontFamily: "monospace", color: "#0A2246" }}>[TECH]</span>
                    </div>
                    {/* Content */}
                    <div style={{ display: "flex", flexDirection: "column", gap: "3px", width: "100%", marginTop: "2px" }}>
                      {/* Job Title Line */}
                      <div style={{ height: "4px", background: "#1A2D58", width: "55%", borderRadius: "1px" }} />
                      
                      {/* Section 1 Heading with Left Accent Bar */}
                      <div style={{ display: "flex", gap: "3px", alignItems: "center", marginTop: "1px" }}>
                        <div style={{ width: "1.5px", background: "#1A2D58", height: "5px", borderRadius: "0.5px" }} />
                        <div style={{ height: "3.5px", background: "#0A2246", width: "30%", borderRadius: "1px" }} />
                      </div>
                      {/* Section 1 Content */}
                      <div style={{ height: "2.5px", background: "#f5f5f5", width: "90%", marginLeft: "4.5px", borderRadius: "1px" }} />
                      
                      {/* Section 2 Heading with Left Accent Bar */}
                      <div style={{ display: "flex", gap: "3px", alignItems: "center", marginTop: "1px" }}>
                        <div style={{ width: "1.5px", background: "#1A2D58", height: "5px", borderRadius: "0.5px" }} />
                        <div style={{ height: "3.5px", background: "#0A2246", width: "35%", borderRadius: "1px" }} />
                      </div>
                      {/* Section 2 Content */}
                      <div style={{ height: "2.5px", background: "#f5f5f5", width: "80%", marginLeft: "4.5px", borderRadius: "1px" }} />
                    </div>
                  </div>
                )
              }
            ].map((t) => {
              const active = (currentJD.metadata?.template || "default") === t.id || ((currentJD.metadata?.template || "default") === "default" && t.id === "corporate");
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    onChange({
                      ...currentJD,
                      metadata: {
                        ...(currentJD.metadata ?? {}),
                        template: t.id
                      }
                    });
                  }}
                  style={{
                    background: "var(--surface-2)",
                    border: active ? "2px solid var(--color-navy-dark, #0b3c5d)" : "1px solid var(--border)",
                    borderRadius: "8px",
                    padding: "8px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.2s ease",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    alignItems: "stretch",
                    boxShadow: active ? "0 4px 12px rgba(11, 60, 93, 0.12)" : "none",
                    outline: "none"
                  }}
                >
                  {/* Card Visual Mock */}
                  <div style={{
                    borderRadius: "4px",
                    overflow: "hidden",
                    border: "1px solid var(--border)",
                    display: "flex"
                  }}>
                    {t.preview}
                  </div>
                  {/* Label */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                    <span style={{
                      fontSize: "11px",
                      fontWeight: "700",
                      color: active ? "var(--color-navy-dark, #0b3c5d)" : "var(--text)"
                    }}>
                      {t.name}
                    </span>
                    <span style={{ fontSize: "9px", color: "var(--text-secondary)", lineHeight: "1.2" }}>
                      {t.desc}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        </>
        )}

        {!canPublish && (
          <div className="review-publish-gate">
            <strong>Resolve Improve this JD items</strong>
            <p className="muted small">Continue to Publish is available once these quality gaps are resolved.</p>
            <div className="quality-suggestion-list">
              {improvementSuggestions.map((item) => (
                <div className="quality-suggestion-item" key={item}>
                  <span />
                  <p>{item}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <button className="primary-button" disabled={!canPublish} onClick={onNext}>Continue to Publish</button>
      </div>

      <aside className="review-sidebar">
        <div className="panel stack">
          <h2>Refine</h2>
          <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Example: make this Senior Engineer focused" rows={5} />
          {error && <p className="error">{error}</p>}
          <button className="secondary-button" disabled={loading || instruction.trim().length < 5} onClick={handleRefine}>
            {loading ? "Refining..." : "Apply refinement"}
          </button>
        </div>

        <div className="panel quality-suggestions">
          <strong>Improve this JD</strong>
          {improvementSuggestions.length > 0 ? (
            <div className="quality-suggestion-list">
              {improvementSuggestions.map((item) => (
                <div className="quality-suggestion-item" key={item}>
                  <span />
                  <p>{item}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted small">This draft has the core details recruiters need.</p>
          )}
        </div>

        <div className="panel">
          <SkillGraph jd={currentJD} />
        </div>
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
  const mustHaveSkills = listFromUnknown(metadata.must_have_skills);
  const preferredSkills = listFromUnknown(metadata.preferred_skills);
  const domain = metadata.industry_or_domain ?? metadata.domain ?? metadata.project_domain;

  if (isMissingContext(getExperience(jd))) suggestions.push("Add a clear experience range, for example 8-12 years.");
  if (isMissingContext(metadata.location)) suggestions.push("Add the job location or hiring geography.");
  if (isMissingContext(metadata.work_mode)) suggestions.push("Add mode of work such as Hybrid, Remote, or Onsite.");
  if (mustHaveSkills.length < 3 && (jd.skills ?? []).length < 3) suggestions.push("List the recruiter-confirmed must-have technical skills.");
  if ((jd.responsibilities ?? []).length < 5) suggestions.push("Add at least 5 role-specific responsibilities.");
  if ((jd.requirements ?? []).length < 5) suggestions.push("Add more required qualifications tied to the role.");
  if (!jd.summary || jd.summary.length < 120) suggestions.push("Add a sharper job summary with project or team context.");
  if ((jd.nice_to_have ?? []).length < 2 && preferredSkills.length < 2) suggestions.push("Add good-to-have skills or domain preferences.");
  if (isMissingContext(domain)) suggestions.push("Add domain, client, product, or project context if relevant.");

  return uniqueSuggestions(suggestions).slice(0, 6);
}

function isMissingContext(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  const text = String(value).trim().toLowerCase();
  return !text || ["n/a", "na", "none", "unknown", "unspecified", "not specified", "to be decided", "tbd", "flexible"].includes(text);
}

function listFromUnknown(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") return value.split(",").map((item) => item.trim()).filter(Boolean);
  return [];
}

function uniqueSuggestions(items: string[]): string[] {
  return Array.from(new Set(items));
}
