"use client";

import { useEffect, useState } from "react";

import { jdApi } from "@/services/jdApi";
import type { GeneratedJD, JD } from "@/types/jd";
import TemplateChooser from "./TemplateChooser";

export default function PublishTab({
  jd,
  savedJD,
  onChange,
  onPublished,
}: {
  jd: GeneratedJD | null;
  savedJD: JD | null;
  onChange: (jd: GeneratedJD) => void;
  onPublished: (jd: JD) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);

  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const publishedPdfUrl = savedJD?.pdf_url
    ? savedJD.pdf_url.startsWith("http")
      ? savedJD.pdf_url
      : `${BACKEND_URL}/${savedJD.pdf_url.startsWith("/") ? savedJD.pdf_url.substring(1) : savedJD.pdf_url}`
    : null;

  function payloadFor(ownership: "personal" | "public") {
    if (!jd) throw new Error("No JD available to publish");
    return {
      title: jd.title,
      content: JSON.stringify(jd),
      ownership,
      context: jd.summary ?? null,
      skills: jd.skills ?? [],
      resume_skills: jd.resume_skills ?? [],
      metadata: jd.metadata ?? {},
    };
  }

  function resolvePdfUrl(fileUrl: string | null): string | null {
    if (!fileUrl) return null;
    return fileUrl.startsWith("http")
      ? fileUrl
      : `${BACKEND_URL}/${fileUrl.startsWith("/") ? fileUrl.substring(1) : fileUrl}`;
  }

  useEffect(() => {
    if (!jd) return;
    let active = true;
    async function buildPreview() {
      setPreviewing(true);
      setError(null);
      try {
        const preview = await jdApi.preview(payloadFor("personal"));
        if (active) setPreviewPdfUrl(resolvePdfUrl(preview.pdf_url));
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Preview failed");
      } finally {
        if (active) setPreviewing(false);
      }
    }
    setPreviewPdfUrl(null);
    void buildPreview();
    return () => {
      active = false;
    };
    // Preview should refresh when the reviewed JD changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(jd)]);

  async function handlePublish(ownership: "personal" | "public") {
    setLoading(true);
    setError(null);
    try {
      const published = await jdApi.publish(savedJD?.id ?? 0, payloadFor(ownership));
      onPublished(published);
      setPreviewPdfUrl(resolvePdfUrl(published.pdf_url));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Publish failed");
    } finally {
      setLoading(false);
    }
  }

  if (!jd) return <div className="empty-state">Generate and review a JD before publishing.</div>;

  return (
    <div className="panel stack">
      <div>
        <h2>{jd.title}</h2>
        <p className="muted">Choose a template, then preview and publish the reviewed JD.</p>
      </div>
      <TemplateChooser jd={jd} onChange={onChange} />
      <div className="publish-actions">
        {(previewPdfUrl || publishedPdfUrl) && (
          <a href={previewPdfUrl || publishedPdfUrl || ""} download className="secondary-button">
            Download
          </a>
        )}
        <button className="primary-button" disabled={loading} onClick={() => handlePublish("personal")}>
          {loading ? "Publishing..." : "Publish as Personal"}
        </button>
        <button className="primary-button" disabled={loading} onClick={() => handlePublish("public")}>
          {loading ? "Publishing..." : "Publish as Public"}
        </button>
      </div>
      {previewing && <div className="empty-state">Building PDF preview...</div>}
      {(previewPdfUrl || publishedPdfUrl) && (
        <div className="pdf-preview-frame">
          <iframe title="JD PDF preview" src={previewPdfUrl || publishedPdfUrl || ""} />
        </div>
      )}
      {savedJD && (
        <div className="success stack">
          <p>Published as JD #{savedJD.id}</p>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );


}


