"use client";

import { useEffect, useState } from "react";
import { jdApi } from "@/services/jdApi";

interface Candidate {
  id: string;
  full_name: string;
  email: string;
  mobile: string;
  skills: string[];
  experience_level: string;
  location: string;
  skill_match_score: number;
  experience_synergy: number;
  fit_analysis: string;
  missing_skills: string[];
  match_percentage: number;
  rank_position: number;
}

export default function CandidateList({
  jdId,
  jdTitle,
  onClose,
}: {
  jdId: number;
  jdTitle: string;
  onClose: () => void;
}) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [searchSkills, setSearchSkills] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await jdApi.sourceCandidates(jdId);
        if (active) {
          setCandidates(res.candidates);
          setSearchSkills(res.search_skills || []);
          const initialExpanded = new Set<string>();
          res.candidates.slice(0, 3).forEach((c: Candidate) => initialExpanded.add(c.id));
          setExpandedIds(initialExpanded);
        }
      } catch (e) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load candidates");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [jdId]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const getInitials = (name: string) => {
    const parts = name.trim().split(" ");
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  const CircularProgress = ({ percentage }: { percentage: number }) => {
    const radius = 22;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percentage / 100) * circumference;
    const color = percentage >= 80 ? "#00b894" : percentage >= 50 ? "#f39c12" : "#e74c3c";

    return (
      <div style={{ position: "relative", width: "56px", height: "56px", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <svg width="56" height="56" style={{ transform: "rotate(-90deg)" }}>
          <circle cx="28" cy="28" r={radius} fill="transparent" stroke="#f1f2f6" strokeWidth="4" />
          <circle
            cx="28" cy="28" r={radius} fill="transparent" stroke={color} strokeWidth="4"
            strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          />
        </svg>
        <span style={{ position: "absolute", fontSize: "0.85rem", fontWeight: "bold", color }}>{percentage}%</span>
      </div>
    );
  };

  return (
    <div className="stack" style={{ gap: "var(--space-lg)", marginTop: "var(--space-md)" }}>
      <div className="row justify-between align-center" style={{ flexWrap: "wrap", gap: "var(--space-sm)" }}>
        <div className="stack" style={{ gap: "4px" }}>
          <button className="secondary-button" style={{ width: "fit-content", padding: "6px 12px", fontSize: "0.85rem" }} onClick={onClose}>
            &larr; Back to Job Descriptions
          </button>
          <h2 style={{ margin: "var(--space-sm) 0 0 0" }}>Source Candidates: {jdTitle}</h2>
          {searchSkills.length > 0 && (
            <p className="muted small" style={{ margin: 0 }}>
              Queried Zoho Recruit using criteria: {searchSkills.map((s) => `"${s}"`).join(", ")}
            </p>
          )}
        </div>
      </div>

      {loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "24px" }}>
          {[1, 2, 3].map((n) => (
            <div key={n} className="panel skeleton-loading" style={{ height: "400px", borderRadius: "12px" }} />
          ))}
        </div>
      )}

      {error && (
        <div className="error-box">
          <p><strong>Error sourcing candidates:</strong> {error}</p>
          <button className="secondary-button" onClick={() => onClose()}>Return to List</button>
        </div>
      )}

      {!loading && !error && candidates.length === 0 && (
        <div className="panel empty-state">
          <p>No candidates found in your Zoho Recruit portal matching the required criteria.</p>
        </div>
      )}

      {!loading && !error && candidates.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "24px", alignItems: "start" }}>
          {candidates.map((candidate) => {
            const isExpanded = expandedIds.has(candidate.id);
            const fitLabel = candidate.match_percentage >= 80 ? "Strong Fit" : candidate.match_percentage >= 50 ? "Possible Fit" : "Weak Fit";
            const fitColor = candidate.match_percentage >= 80 ? "#00b894" : candidate.match_percentage >= 50 ? "#f39c12" : "#e74c3c";
            const fitBg = candidate.match_percentage >= 80 ? "#e8f8f5" : candidate.match_percentage >= 50 ? "#fef9e7" : "#fdf2f2";
            
            // Derive matched skills (skills they have that we didn't mark as missing)
            // Just for UI mockup purposes, we show some generic skills as matches
            const matchedSkills = candidate.skills.filter(s => !candidate.missing_skills.includes(s));
            const displayMatched = matchedSkills.slice(0, 4);
            const displayMissing = candidate.missing_skills.slice(0, 2);
            const extraCount = matchedSkills.length > 4 ? matchedSkills.length - 4 : 0;

            // Generate an avatar color based on rank
            const avatarColors = ["#4f46e5", "#0ea5e9", "#2563eb", "#6366f1", "#8b5cf6"];
            const avatarColor = avatarColors[candidate.rank_position % avatarColors.length];

            return (
              <div
                key={candidate.id}
                className="panel stack"
                style={{
                  padding: "24px",
                  borderRadius: "16px",
                  border: "1px solid #e5e7eb",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
                  gap: "16px",
                  backgroundColor: "#ffffff"
                }}
              >
                {/* Header Profile Area */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                    <div style={{
                      width: "48px", height: "48px", borderRadius: "50%",
                      backgroundColor: avatarColor, color: "white",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontWeight: "bold", fontSize: "1.1rem"
                    }}>
                      {getInitials(candidate.full_name)}
                    </div>
                    <div className="stack" style={{ gap: "2px" }}>
                      <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#111827" }}>{candidate.full_name}</h3>
                      <div style={{ color: "#6b7280", fontSize: "0.85rem" }}>
                        Software Engineer {/* Generic title since we don't have it from API */}
                      </div>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "4px" }}>
                        <span style={{ fontSize: "0.75rem", color: "#6b7280", display: "flex", alignItems: "center", gap: "4px" }}>
                          <span style={{ fontSize: "0.9rem" }}>📄</span> {candidate.experience_level}
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "4px" }}>
                        <span style={{
                          backgroundColor: "#f3e8ff", color: "#7e22ce", padding: "2px 6px",
                          borderRadius: "4px", fontSize: "0.7rem", fontWeight: "bold"
                        }}>
                          #{candidate.rank_position}
                        </span>
                        <span style={{ fontSize: "0.7rem", color: "#9ca3af" }}>ZR_{candidate.id.slice(-4)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="stack align-center" style={{ gap: "4px" }}>
                    <CircularProgress percentage={candidate.match_percentage} />
                    <span style={{
                      backgroundColor: fitBg, color: fitColor, border: `1px solid ${fitColor}33`,
                      padding: "2px 8px", borderRadius: "12px", fontSize: "0.7rem", fontWeight: "bold"
                    }}>
                      {fitLabel}
                    </span>
                  </div>
                </div>

                {/* Score Pills */}
                <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
                  <div style={{
                    display: "flex", alignItems: "center", gap: "4px", backgroundColor: "#f3f4f6",
                    padding: "4px 8px", borderRadius: "6px", fontSize: "0.8rem", fontWeight: "500", color: "#4b5563"
                  }}>
                    <span style={{ color: "#ef4444" }}>🎯</span> Skill {candidate.skill_match_score}%
                  </div>
                  <div style={{
                    display: "flex", alignItems: "center", gap: "4px", backgroundColor: "#f3f4f6",
                    padding: "4px 8px", borderRadius: "6px", fontSize: "0.8rem", fontWeight: "500", color: "#4b5563"
                  }}>
                    <span style={{ color: "#3b82f6" }}>🗓️</span> Exp {candidate.experience_synergy}%
                  </div>
                </div>

                {/* Skills Preview */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {displayMatched.map((skill, i) => (
                    <span key={i} style={{
                      backgroundColor: "#ecfdf5", color: "#059669", border: "1px solid #a7f3d0",
                      padding: "2px 8px", borderRadius: "12px", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "4px"
                    }}>
                      ✓ {skill}
                    </span>
                  ))}
                  {displayMissing.map((skill, i) => (
                    <span key={i} style={{
                      backgroundColor: "#fef2f2", color: "#ef4444", border: "1px solid #fecaca",
                      padding: "2px 8px", borderRadius: "12px", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "4px"
                    }}>
                      ✕ {skill}
                    </span>
                  ))}
                  {extraCount > 0 && (
                    <span style={{
                      backgroundColor: "#f3f4f6", color: "#6b7280", padding: "2px 8px", borderRadius: "12px", fontSize: "0.75rem"
                    }}>
                      +{extraCount} more
                    </span>
                  )}
                </div>

                {/* Contact Info */}
                <div className="stack" style={{ gap: "8px", marginTop: "8px", paddingBottom: "16px", borderBottom: "1px solid #f3f4f6" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#4b5563", fontSize: "0.8rem" }}>
                    <span style={{ color: "#9ca3af" }}>✉</span> {candidate.email}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#4b5563", fontSize: "0.8rem" }}>
                    <span style={{ color: "#ec4899" }}>📞</span> {candidate.mobile}
                  </div>
                </div>

                {/* Expand Toggle */}
                <button
                  onClick={() => toggleExpand(candidate.id)}
                  style={{
                    background: "none", border: "none", color: "#6b7280", fontSize: "0.85rem",
                    textAlign: "left", cursor: "pointer", padding: "0", display: "flex", alignItems: "center", gap: "4px"
                  }}
                >
                  {isExpanded ? "▴ Hide details" : "▾ View full analysis"}
                </button>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="stack" style={{ gap: "16px", marginTop: "8px" }}>
                    <div className="stack" style={{ gap: "4px" }}>
                      <div style={{ fontSize: "0.7rem", fontWeight: "bold", color: "#9ca3af", letterSpacing: "0.05em" }}>FIT ANALYSIS</div>
                      <div style={{ fontStyle: "italic", fontSize: "0.85rem", color: "#4b5563", lineHeight: "1.5" }}>
                        "{candidate.fit_analysis}"
                      </div>
                    </div>

                    <div className="stack" style={{ gap: "4px" }}>
                      <div style={{ fontSize: "0.7rem", fontWeight: "bold", color: "#9ca3af", letterSpacing: "0.05em" }}>MATCHED SKILLS ({matchedSkills.length})</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                        {matchedSkills.map((skill, i) => (
                          <span key={i} style={{
                            backgroundColor: "#ecfdf5", color: "#059669", border: "1px solid #a7f3d0",
                            padding: "2px 8px", borderRadius: "12px", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "4px"
                          }}>
                            ✓ {skill}
                          </span>
                        ))}
                      </div>
                    </div>

                    {candidate.missing_skills.length > 0 && (
                      <div className="stack" style={{ gap: "4px" }}>
                        <div style={{ fontSize: "0.7rem", fontWeight: "bold", color: "#9ca3af", letterSpacing: "0.05em" }}>MISSING SKILLS ({candidate.missing_skills.length})</div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                          {candidate.missing_skills.map((skill, i) => (
                            <span key={i} style={{
                              backgroundColor: "#fef2f2", color: "#ef4444", border: "1px solid #fecaca",
                              padding: "2px 8px", borderRadius: "12px", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "4px"
                            }}>
                              ✕ {skill}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem", color: "#6b7280", marginTop: "8px" }}>
                      <div>Overall Match: <strong style={{ color: "#374151" }}>{candidate.match_percentage}%</strong> &nbsp;&nbsp; Skill Match: <strong style={{ color: "#374151" }}>{candidate.skill_match_score}%</strong></div>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem", color: "#6b7280" }}>
                      <div>Experience: <strong style={{ color: "#374151" }}>{candidate.experience_synergy}%</strong> &nbsp;&nbsp; Rank: <strong style={{ color: "#374151" }}>#{candidate.rank_position}</strong></div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
