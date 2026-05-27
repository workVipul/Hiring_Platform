"use client";

import { useState, useRef, useMemo } from "react";

import CandidateList from "@/components/sourcing/CandidateList";
import { jdApi } from "@/services/jdApi";
import { useJDs } from "@/hooks/useJDs";
import { useAuthStore } from "@/store/authStore";

type ViewMode = "landing" | "existing" | "candidates";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function resolveFileUrl(fileUrl: string | null): string | null {
  if (!fileUrl) return null;
  if (fileUrl.startsWith("http")) return fileUrl;
  const cleanPath = fileUrl.startsWith("/") ? fileUrl.substring(1) : fileUrl;
  return `${BACKEND_URL}/${cleanPath}`;
}

export default function SourcingPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("landing");
  const [selectedJD, setSelectedJD] = useState<{ id: number; title: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const userId = useAuthStore((state) => state.userId);
  const { jds, loading, error } = useJDs();
  const [visibilityOption, setVisibilityOption] = useState<string>("all-public-first");

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

  const processedJDs = useMemo(() => {
    // Filter down to only JDs the user is authorized to see (Public JDs + User's own JDs)
    let result = jds.filter((jd) => jd.ownership === "public" || jd.created_by === userId);

    // Apply visibility filter
    if (visibilityOption === "public-only") {
      result = result.filter((jd) => jd.ownership === "public");
    } else if (visibilityOption === "private-only") {
      result = result.filter((jd) => jd.ownership === "personal");
    }

    // Apply visibility sorting
    result.sort((a, b) => {
      const aIsPublic = a.ownership === "public";
      const bIsPublic = b.ownership === "public";

      if (visibilityOption === "all-public-first") {
        if (aIsPublic && !bIsPublic) return -1;
        if (!aIsPublic && bIsPublic) return 1;
      } else if (visibilityOption === "all-private-first") {
        if (!aIsPublic && bIsPublic) return -1;
        if (aIsPublic && !bIsPublic) return 1;
      }
      return 0;
    });

    return result;
  }, [jds, visibilityOption, userId]);

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
                <span className="dropzone-icon">PDF</span>
                <div className="dropzone-text">
                  <strong>Drag and drop</strong> or click to upload
                </div>
                <div className="dropzone-subtext">Supports PDF or TXT up to 10MB</div>
              </div>

              <div 
                className="sourcing-card"
                onClick={() => setViewMode("existing")}
              >
                <span className="sourcing-card-icon">JD</span>
                <h3>Pull from Existing JDs</h3>
                <p>Browse personal and shared job descriptions already parsed in the system.</p>
              </div>
            </div>
          )}
        </div>
      )}

      {viewMode === "existing" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button className="ghost-button" onClick={() => setViewMode("landing")}>
              &larr; Back to Options
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <label htmlFor="visibility-sort-filter" style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: "500" }}>
                Filter:
              </label>
              <select
                id="visibility-sort-filter"
                value={visibilityOption}
                onChange={(e) => setVisibilityOption(e.target.value)}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  background: "var(--background)",
                  color: "var(--foreground)",
                  fontSize: "0.85rem",
                  outline: "none",
                  cursor: "pointer"
                }}
              >
                <option value="all-public-first">All JDs (Public First)</option>
                <option value="all-private-first">All JDs (Personal First)</option>
                <option value="public-only">Public Only</option>
                <option value="private-only">Personal Only</option>
              </select>
            </div>
          </div>

          {loading && <div className="empty-state">Loading job descriptions...</div>}
          {error && <div className="error-box">Failed to load job descriptions: {error}</div>}

          {!loading && !error && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>JD Name</th>
                    <th>Visibility</th>
                    <th>Skills</th>
                    <th>PDF</th>
                    <th>Sourcing</th>
                  </tr>
                </thead>
                <tbody>
                  {processedJDs.map((jd) => {
                    const fileUrl = resolveFileUrl(jd.pdf_url);
                    return (
                      <tr key={jd.id}>
                        <td><strong>{jd.title}</strong></td>
                        <td>
                          <span className={`badge ${jd.ownership === "public" ? "badge-public" : "badge-private"}`}>
                            {jd.ownership === "public" ? "Public" : "Personal"}
                          </span>
                        </td>
                        <td>{jd.skills?.join(", ") || "-"}</td>
                        <td>
                          {fileUrl ? (
                            <a href={fileUrl} target="_blank" rel="noreferrer" className="pdf-button">
                              Open
                            </a>
                          ) : (
                            "-"
                          )}
                        </td>
                        <td>
                          <button
                            className="primary-button"
                            style={{ padding: "6px 12px", fontSize: "0.8rem", width: "auto" }}
                            onClick={() => handleSelectJD(jd.id, jd.title)}
                          >
                            Source
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {processedJDs.length === 0 && (
                <div className="empty-state">No job descriptions found matching the filter.</div>
              )}
            </div>
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


