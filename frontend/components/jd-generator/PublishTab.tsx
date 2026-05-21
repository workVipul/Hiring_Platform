"use client";

import { useState } from "react";

import { jdApi } from "@/services/jdApi";
import type { GeneratedJD, JD } from "@/types/jd";

export default function PublishTab({
  jd,
  savedJD,
  onPublished,
}: {
  jd: GeneratedJD | null;
  savedJD: JD | null;
  onPublished: (jd: JD) => void;
}) {
  const [ownership, setOwnership] = useState<"personal" | "public">("personal");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!jd) return <div className="empty-state">Generate and review a JD before publishing.</div>;

  const currentJD = jd;
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const publishedPdfUrl = savedJD?.pdf_url
    ? savedJD.pdf_url.startsWith("http")
      ? savedJD.pdf_url
      : `${BACKEND_URL}/${savedJD.pdf_url.startsWith("/") ? savedJD.pdf_url.substring(1) : savedJD.pdf_url}`
    : null;

  async function handlePublish() {
    setLoading(true);
    setError(null);
    try {
      const published = await jdApi.publish(savedJD?.id ?? 0, {
        title: currentJD.title,
        content: JSON.stringify(currentJD),
        ownership,
        jd_score: currentJD.jd_score ?? null,
        context: currentJD.summary ?? null,
        skills: currentJD.skills ?? [],
        resume_skills: currentJD.resume_skills ?? [],
        metadata: currentJD.metadata ?? {},
      });
      onPublished(published);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel stack">
      <div>
        <h2>{currentJD.title}</h2>
        <p className="muted">Choose where this JD should live, then publish it to the database.</p>
      </div>
      <div className="segmented">
        {(["personal", "public"] as const).map((value) => (
          <button key={value} className={ownership === value ? "active" : ""} onClick={() => setOwnership(value)}>
            {value}
          </button>
        ))}
      </div>
      {savedJD && (
        <div className="success stack">
          <p>Published as JD #{savedJD.id}</p>
          {publishedPdfUrl && (
            <a href={publishedPdfUrl} target="_blank" rel="noreferrer" className="secondary-button" style={{ width: "fit-content" }}>
              Open
            </a>
          )}
        </div>
      )}
      {error && <p className="error">{error}</p>}
      <button className="primary-button" disabled={loading} onClick={handlePublish}>
        {loading ? "Publishing..." : "Publish JD"}
      </button>
    </div>
  );
}
