"use client";

import type React from "react";
import { useEffect, useRef, useState } from "react";

import { jdApi } from "@/services/jdApi";
import { useAuthStore } from "@/store/authStore";
import type { GeneratedJD, JDTemplate } from "@/types/jd";

export default function TemplateChooser({
  jd,
  onChange,
}: {
  jd: GeneratedJD;
  onChange: (jd: GeneratedJD) => void;
}) {
  const activeTemplate = String(jd.metadata?.template || "corporate");
  const isCustomActive = activeTemplate.startsWith("custom-");
  const accessType = useAuthStore((state) => state.accessType);
  const [customTemplates, setCustomTemplates] = useState<JDTemplate[]>([]);
  const [uploadName, setUploadName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selectedCustomTemplate = customTemplates.find((template) => template.id === activeTemplate) ?? null;

  async function loadTemplates() {
    const result = await jdApi.listTemplates();
    setCustomTemplates((result.items || []).filter((template) => template.is_custom));
  }

  useEffect(() => {
    let active = true;
    async function loadTemplatesIfMounted() {
      try {
        const result = await jdApi.listTemplates();
        if (!active) return;
        setCustomTemplates((result.items || []).filter((template) => template.is_custom));
      } catch {
        if (active) setCustomTemplates([]);
      }
    }
    void loadTemplatesIfMounted();
    return () => {
      active = false;
    };
  }, []);

  function selectClassic() {
    onChange({
      ...jd,
      metadata: {
        ...(jd.metadata ?? {}),
        template: "corporate",
        template_prompt: undefined,
        template_file_url: undefined,
        template_definition_version: undefined,
      },
    });
  }

  function selectCustom(template: JDTemplate) {
    onChange({
      ...jd,
      metadata: {
        ...(jd.metadata ?? {}),
        template: template.id,
        template_prompt: template.prompt ?? undefined,
        template_file_url: template.file_url ?? undefined,
        template_definition_version: template.version ?? undefined,
      },
    });
  }

  async function deleteSelectedCustomTemplate() {
    if (!selectedCustomTemplate || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      const deletedId = selectedCustomTemplate.id;
      await jdApi.deleteTemplate(deletedId);
      selectClassic();
      await loadTemplates();
      setCustomTemplates((prev) => prev.filter((template) => template.id !== deletedId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Template delete failed");
    } finally {
      setDeleting(false);
    }
  }

  async function handleTemplateUpload(file: File | null) {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const uploaded = await jdApi.uploadTemplate(uploadName.trim() || file.name.replace(/\.pdf$/i, ""), file);
      setCustomTemplates((prev) => [uploaded, ...prev]);
      setUploadName("");
      selectCustom(uploaded);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Template upload failed");
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragActive(false);
    void handleTemplateUpload(event.dataTransfer.files?.[0] ?? null);
  }

  return (
    <section className="template-chooser">
      <div className="template-chooser-heading">
        <div>
          <h3>Select PDF Template</h3>
          <p className="muted small">Choose the standard layout or upload a reference PDF template before previewing.</p>
        </div>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="template-choice-grid">
        <button
          type="button"
          className={!isCustomActive ? "template-choice-card active" : "template-choice-card"}
          onClick={selectClassic}
        >
          <span className="template-card-preview">{classicPreview()}</span>
          <span className="template-card-copy">
            <strong>Classic Template</strong>
            <span>Standard Wissen corporate JD with the existing layout and branding.</span>
          </span>
        </button>

        <div className={isCustomActive ? "template-choice-card active" : "template-choice-card"}>
          <div className="template-card-copy">
            <strong>Upload Custom Template</strong>
            <span>Upload a PDF reference so admins can add a reusable JD style for everyone.</span>
          </div>

          {accessType === "admin" && (
            <>
              <input
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                placeholder="Template name"
                aria-label="Template name"
              />
              <div
                className={`dropzone template-dropzone ${isDragActive ? "active" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragActive(true);
                }}
                onDragLeave={() => setIsDragActive(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  hidden
                  disabled={uploading}
                  onChange={(e) => {
                    void handleTemplateUpload(e.target.files?.[0] ?? null);
                    e.currentTarget.value = "";
                  }}
                />
                <span className="dropzone-icon">PDF</span>
                <div className="dropzone-text">
                  <strong>{uploading ? "Uploading template..." : "Drag and drop"}</strong> or click to upload
                </div>
                <div className="dropzone-subtext">Admin-only PDF template upload</div>
              </div>
            </>
          )}

          {accessType !== "admin" && customTemplates.length === 0 && (
            <p className="muted small">Custom templates uploaded by admins will appear here.</p>
          )}

          {customTemplates.length > 0 && (
            <div className="template-custom-select-row">
              <label>
                Custom template
                <select
                  value={selectedCustomTemplate?.id ?? ""}
                  onChange={(event) => {
                    const template = customTemplates.find((item) => item.id === event.target.value);
                    if (template) selectCustom(template);
                  }}
                >
                  <option value="">Select uploaded template</option>
                  {customTemplates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </label>
              {accessType === "admin" && (
                <button
                  type="button"
                  className="danger-button"
                  disabled={!selectedCustomTemplate || deleting}
                  onClick={deleteSelectedCustomTemplate}
                >
                  {deleting ? "Deleting..." : "Delete"}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function classicPreview() {
  return (
    <div className="template-preview template-preview-corporate">
      <div className="template-preview-header template-preview-header-split">
        <span>WISSEN</span>
        <span>...</span>
      </div>
      <div className="template-preview-title" />
      <div className="template-preview-line wide" />
      <div className="template-preview-line medium" />
      <div className="template-preview-line short" />
      <div className="template-preview-line medium" />
    </div>
  );
}
