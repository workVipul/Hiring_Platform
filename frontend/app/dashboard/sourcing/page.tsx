"use client";

import { useState } from "react";

import CommonJDs from "@/components/sourcing/CommonJDs";
import MyJDs from "@/components/sourcing/MyJDs";

export default function SourcingPage() {
  const [active, setActive] = useState<"my" | "common">("my");

  return (
    <section className="page-section">
      <div className="page-heading">
        <p className="eyebrow">Sourcing</p>
        <h1>Candidate Sourcing</h1>
        <p className="muted">Review personal and shared job descriptions available for sourcing workflows.</p>
      </div>

      <div className="tabs">
        <button className={active === "my" ? "tab active" : "tab"} onClick={() => setActive("my")}>My JDs</button>
        <button className={active === "common" ? "tab active" : "tab"} onClick={() => setActive("common")}>Common JDs</button>
      </div>

      {active === "my" ? <MyJDs /> : <CommonJDs />}
    </section>
  );
}
