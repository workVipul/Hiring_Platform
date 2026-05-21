"use client";

import { useState, useRef } from "react";

import CommonJDs from "@/components/sourcing/CommonJDs";
import MyJDs from "@/components/sourcing/MyJDs";
import CandidateList from "@/components/sourcing/CandidateList";
import { jdApi } from "@/services/jdApi";

type ViewMode = "landing" | "existing" | "candidates";

export default function SourcingPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("landing");
  const [activeTab, setActiveTab] = useState<"my" | "common">("my");
  const [selectedJD, setSelectedJD] = useState<{ id: number; title: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Track where candidate list was entered from, so we know where to go back
  const [candidateSource, setCandidateSource] = useState<"landing" | "existing">("existing");

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await uploadFile(e.target.files[0]);
    }
  };

  const uploadFile = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const parsedJD = await jdApi.upload(file);
      setSelectedJD({ id: parsedJD.id, title: parsedJD.title });
      setCandidateSource("landing");
      setViewMode("candidates");
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload and parse job description.");
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = () => {
    setIsDragActive(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await uploadFile(e.dataTransfer.files[0]);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  const handleSelectJD = (id: number, title: string) => {
    setSelectedJD({ id, title });
    setCandidateSource("existing");
    setViewMode("candidates");
  };

  const handleBackFromCandidates = () => {
    setSelectedJD(null);
    setViewMode(candidateSource);
  };

  return (
    <section className="page-section">
      <div className="page-heading">
        <p className="eyebrow">Sourcing</p>
        <h1>Candidate Sourcing</h1>
        <p className="muted">
          {viewMode === "candidates" && selectedJD
            ? `Review top candidates matching "${selectedJD.title}".`
            : "Upload a job description or choose an existing one to match and source the best candidate profiles."}
        </p>
      </div>

      {viewMode === "landing" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {uploadError && (
            <div className="error-box" style={{ margin: 0 }}>
              {uploadError}
            </div>
          )}

          {uploading ? (
            <div className="empty-state" style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "60px" }}>
              <div className="spinner"></div>
              <h3>Parsing Job Description with AI...</h3>
              <p className="muted" style={{ maxWidth: "400px", margin: "0 auto" }}>
                We are extracting skills, experience requirements, and layout parameters to match candidate profiles. This will take just a moment.
              </p>
            </div>
          ) : (
            <div className="sourcing-options-grid">
              <div 
                className={`dropzone ${isDragActive ? "active" : ""}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={triggerFileInput}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  style={{ display: "none" }} 
                  accept=".pdf,.txt"
                  onChange={handleFileChange}
                />
                <span className="dropzone-icon">📄</span>
                <div className="dropzone-text">
                  <strong>Drag and drop</strong> or click to upload
                </div>
                <div className="dropzone-subtext">Supports PDF or TXT up to 10MB</div>
              </div>

              <div 
                className="sourcing-card"
                onClick={() => setViewMode("existing")}
              >
                <span className="sourcing-card-icon">🗂️</span>
                <h3>Pull from Existing JDs</h3>
                <p>Browse personal and shared job descriptions already parsed in the system.</p>
              </div>
            </div>
          )}
        </div>
      )}

      {viewMode === "existing" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <button className="ghost-button" onClick={() => setViewMode("landing")}>
              &larr; Back to Options
            </button>
          </div>

          <div className="tabs">
            <button className={activeTab === "my" ? "tab active" : "tab"} onClick={() => setActiveTab("my")}>My JDs</button>
            <button className={activeTab === "common" ? "tab active" : "tab"} onClick={() => setActiveTab("common")}>Common JDs</button>
          </div>

          {activeTab === "my" ? (
            <MyJDs onSource={handleSelectJD} />
          ) : (
            <CommonJDs onSource={handleSelectJD} />
          )}
        </div>
      )}

      {viewMode === "candidates" && selectedJD && (
        <CandidateList
          jdId={selectedJD.id}
          jdTitle={selectedJD.title}
          onClose={handleBackFromCandidates}
        />
      )}
    </section>
  );
}

