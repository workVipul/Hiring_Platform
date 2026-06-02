"use client";

import { useMemo, useState, useEffect } from "react";

import GenerateTab from "@/components/jd-generator/GenerateTab";
import PublishTab from "@/components/jd-generator/PublishTab";
import ReviewTab from "@/components/jd-generator/ReviewTab";
import type { GeneratedJD, JD } from "@/types/jd";

import { useAuthStore } from "@/store/authStore";

type Tab = "generate" | "review" | "publish";

const tabs: Tab[] = ["generate", "review", "publish"];

export default function JDGeneratorPage() {
  const [active, setActive] = useState<Tab>("generate");
  const [generatedJD, setGeneratedJD] = useState<GeneratedJD | null>(null);
  const [savedJD, setSavedJD] = useState<JD | null>(null);
  const { setHasUnsavedJD, setPendingNavigationAction } = useAuthStore();

  // Sync global unsaved draft status
  useEffect(() => {
    setHasUnsavedJD(Boolean(generatedJD && !savedJD));
    return () => setHasUnsavedJD(false);
  }, [generatedJD, savedJD, setHasUnsavedJD]);


  // Prompt user on browser reload / exit if they have unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (generatedJD && !savedJD) {
        e.preventDefault();
        e.returnValue = "You have an unsaved JD draft. Are you sure you want to leave?";
        return e.returnValue;
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [generatedJD, savedJD]);

  // Intercept browser back/forward buttons using the PopState event
  useEffect(() => {
    if (!generatedJD || savedJD) return;

    // Push a dummy history state so we have a token to pop
    window.history.pushState(null, "", window.location.href);

    const handlePopState = () => {
      // Re-push a state to lock user on current page while confirming
      window.history.pushState(null, "", window.location.href);

      setPendingNavigationAction(() => {
        setGeneratedJD(null);
        window.history.go(-2);
      });
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [generatedJD, savedJD, setPendingNavigationAction]);


  const content = useMemo(() => {
    if (active === "generate") {
      return <GenerateTab onGenerated={(jd) => { setGeneratedJD(jd); setActive("review"); }} />;
    }
    if (active === "review") {
      return <ReviewTab jd={generatedJD} onChange={setGeneratedJD} onNext={() => setActive("publish")} />;
    }
    return <PublishTab jd={generatedJD} savedJD={savedJD} onChange={setGeneratedJD} onPublished={setSavedJD} />;
  }, [active, generatedJD, savedJD]);

  const handleTabClick = (tab: Tab) => {
    if (generatedJD && !savedJD && tab === "generate") {
      setPendingNavigationAction(() => {
        setGeneratedJD(null);
        setActive(tab);
      });
    } else {
      setActive(tab);
    }
  };


  return (
    <section className="page-section">
      <div className="page-heading">
        <p className="eyebrow">JD Generator</p>
        <h1>Generate, Review, Publish</h1>
        <p className="muted">Keep drafts in memory until you deliberately publish.</p>
      </div>

      <div className="tabs">
        {tabs.map((tab) => (
          <button key={tab} className={active === tab ? "tab active" : "tab"} onClick={() => handleTabClick(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {content}
    </section>
  );
}

