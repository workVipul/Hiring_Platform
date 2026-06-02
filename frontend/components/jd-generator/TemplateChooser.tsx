"use client";

import type React from "react";

import type { GeneratedJD } from "@/types/jd";

type TemplateOption = {
  id: string;
  name: string;
  desc: string;
  preview: React.ReactNode;
};

const templates: TemplateOption[] = [
  {
    id: "corporate",
    name: "Corporate Classic",
    desc: "Standard Wissen presentation",
    preview: (
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
    ),
  },
  {
    id: "modern",
    name: "Modern Minimalist",
    desc: "Clean and compact text layout",
    preview: (
      <div className="template-preview template-preview-modern">
        <div className="template-preview-header template-preview-header-right">
          <span>WISSEN</span>
        </div>
        <div className="template-preview-title compact" />
        <div className="template-preview-line wide" />
        <div className="template-preview-line wide" />
        <div className="template-preview-line medium" />
        <div className="template-preview-line short" />
      </div>
    ),
  },
  {
    id: "executive",
    name: "Executive Serif",
    desc: "Centered editorial design",
    preview: (
      <div className="template-preview template-preview-executive">
        <div className="template-preview-header template-preview-header-center">
          <span>WISSEN</span>
        </div>
        <div className="template-preview-centered">
          <div className="template-preview-title centered" />
          <div className="template-preview-line medium" />
          <div className="template-preview-line medium" />
          <div className="template-preview-line wide" />
        </div>
      </div>
    ),
  },
  {
    id: "tech",
    name: "Clean Tech",
    desc: "Tech-focused code layout",
    preview: (
      <div className="template-preview template-preview-tech">
        <div className="template-preview-header template-preview-header-split">
          <span>WISSEN</span>
          <span className="template-preview-code">[TECH]</span>
        </div>
        <div className="template-preview-title" />
        <div className="template-preview-section">
          <span />
          <div />
        </div>
        <div className="template-preview-line medium indented" />
        <div className="template-preview-section">
          <span />
          <div />
        </div>
        <div className="template-preview-line short indented" />
      </div>
    ),
  },
];

export default function TemplateChooser({
  jd,
  onChange,
}: {
  jd: GeneratedJD;
  onChange: (jd: GeneratedJD) => void;
}) {
  const activeTemplate = String(jd.metadata?.template || "corporate");

  return (
    <section className="template-chooser">
      <div>
        <h3>Select PDF Template</h3>
        <p className="muted small">Choose the layout style before previewing or publishing.</p>
      </div>
      <div className="template-options-grid">
        {templates.map((template) => {
          const active = activeTemplate === template.id || (activeTemplate === "default" && template.id === "corporate");
          return (
            <button
              key={template.id}
              type="button"
              className={active ? "template-card active" : "template-card"}
              onClick={() => {
                onChange({
                  ...jd,
                  metadata: {
                    ...(jd.metadata ?? {}),
                    template: template.id,
                  },
                });
              }}
            >
              <span className="template-card-preview">{template.preview}</span>
              <span className="template-card-copy">
                <strong>{template.name}</strong>
                <span>{template.desc}</span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
