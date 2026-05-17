"use client";

import { useMemo, useState } from "react";

import GenerateTab from "@/components/jd-generator/GenerateTab";
import PublishTab from "@/components/jd-generator/PublishTab";
import ReviewTab from "@/components/jd-generator/ReviewTab";
import type { GeneratedJD, JD } from "@/types/jd";

type Tab = "generate" | "review" | "publish";

const tabs: Tab[] = ["generate", "review", "publish"];

export default function JDGeneratorPage() {
  const [active, setActive] = useState<Tab>("generate");
  const [generatedJD, setGeneratedJD] = useState<GeneratedJD | null>(null);
  const [savedJD, setSavedJD] = useState<JD | null>(null);

  const content = useMemo(() => {
    if (active === "generate") {
      return <GenerateTab onGenerated={(jd) => { setGeneratedJD(jd); setActive("review"); }} />;
    }
    if (active === "review") {
      return <ReviewTab jd={generatedJD} onChange={setGeneratedJD} onNext={() => setActive("publish")} />;
    }
    return <PublishTab jd={generatedJD} savedJD={savedJD} onPublished={setSavedJD} />;
  }, [active, generatedJD, savedJD]);

  return (
    <section className="page-section">
      <div className="page-heading">
        <p className="eyebrow">JD Generator</p>
        <h1>Generate, Review, Publish</h1>
        <p className="muted">Keep drafts in memory until you deliberately publish.</p>
      </div>

      <div className="tabs">
        {tabs.map((tab) => (
          <button key={tab} className={active === tab ? "tab active" : "tab"} onClick={() => setActive(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {content}
    </section>
  );
}
