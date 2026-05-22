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
  const [requiredSkills, setRequiredSkills] = useState<string[]>([]);
  const [experienceRequirement, setExperienceRequirement] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const perPage = 6;
  const totalPages = Math.max(1, Math.ceil(candidates.length / perPage));
  const visibleCandidates = candidates.slice((page - 1) * perPage, page * perPage);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await jdApi.sourceCandidates(jdId);
        if (!active) return;
        setCandidates(res.candidates);
        setPage(1);
        setRequiredSkills(res.required_skills || res.search_skills || []);
        setExperienceRequirement(res.experience_requirement || null);
        setExpandedIds(new Set(res.candidates.slice(0, 1).map((candidate: Candidate) => candidate.id)));
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load candidates");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [jdId]);

  function toggleExpand(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function initials(name: string) {
    const parts = name.trim().split(/\s+/);
    return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? parts[0]?.[1] ?? "")).toUpperCase() || "NA";
  }

  return (
    <div className="candidate-page">
      <div className="candidate-toolbar">
        <button className="secondary-button compact-button" onClick={onClose}>
          Back to Job Descriptions
        </button>
        <div>
          <p className="eyebrow">Candidate Matches</p>
          <h2>{jdTitle}</h2>
        </div>
      </div>

      {(requiredSkills.length > 0 || experienceRequirement) && (
        <div className="sourcing-requirements-card">
          <div>
            <span className="muted small">Reviewer checklist</span>
            <h3>Required skills and experience</h3>
          </div>
          {experienceRequirement && (
            <div className="requirement-block">
              <strong>Experience</strong>
              <span>{experienceRequirement}</span>
            </div>
          )}
          {requiredSkills.length > 0 && (
            <div className="requirement-chip-list">
              {requiredSkills.slice(0, 12).map((skill) => (
                <span key={skill}>{skill}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="candidate-grid">
          {[1, 2, 3].map((n) => (
            <div key={n} className="candidate-card candidate-card-skeleton" />
          ))}
        </div>
      )}

      {error && (
        <div className="error-box">
          <p><strong>Error sourcing candidates:</strong> {error}</p>
          <button className="secondary-button" onClick={onClose}>Return to List</button>
        </div>
      )}

      {!loading && !error && candidates.length === 0 && (
        <div className="panel empty-state">
          <p>No candidates found in your Zoho Recruit portal matching the required criteria.</p>
        </div>
      )}

      {!loading && !error && candidates.length > 0 && (
        <>
          <div className="candidate-grid">
            {visibleCandidates.map((candidate) => (
              <CandidateCard
                key={candidate.id}
                candidate={candidate}
                expanded={expandedIds.has(candidate.id)}
                initials={initials(candidate.full_name)}
                onToggle={() => toggleExpand(candidate.id)}
              />
            ))}
          </div>
          <div className="candidate-pagination">
            <button className="secondary-button compact-button" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
              Previous
            </button>
            <span className="muted small">
              Page {page} of {totalPages} · {candidates.length} candidates
            </span>
            <button className="secondary-button compact-button" disabled={page >= totalPages} onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}>
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function CandidateCard({
  candidate,
  expanded,
  initials,
  onToggle,
}: {
  candidate: Candidate;
  expanded: boolean;
  initials: string;
  onToggle: () => void;
}) {
  const matchedSkills = candidate.skills.filter((skill) => !candidate.missing_skills.includes(skill));
  const fitTone = candidate.match_percentage >= 80 ? "strong" : candidate.match_percentage >= 50 ? "possible" : "weak";

  return (
    <article className="candidate-card">
      <div className="candidate-card-top">
        <div className="candidate-avatar">{initials}</div>
        <div className="candidate-identity">
          <div className="candidate-title-row">
            <h3>{candidate.full_name}</h3>
            <span className="rank-badge">#{candidate.rank_position}</span>
          </div>
          <p>{candidate.location}</p>
          <span>{candidate.experience_level}</span>
        </div>
        <div className={`fit-score ${fitTone}`}>
          <strong>{candidate.match_percentage}%</strong>
          <span>{fitTone === "strong" ? "Strong Fit" : fitTone === "possible" ? "Possible Fit" : "Weak Fit"}</span>
        </div>
      </div>

      <div className="candidate-metrics">
        <div>
          <span>Skill match</span>
          <strong>{candidate.skill_match_score}%</strong>
        </div>
        <div>
          <span>Experience</span>
          <strong>{candidate.experience_synergy}%</strong>
        </div>
      </div>

      <div className="candidate-skill-band">
        {matchedSkills.slice(0, 5).map((skill) => (
          <span className="skill-chip matched" key={skill}>{skill}</span>
        ))}
        {candidate.missing_skills.slice(0, 3).map((skill) => (
          <span className="skill-chip missing" key={skill}>{skill}</span>
        ))}
        {matchedSkills.length > 5 && <span className="skill-chip neutral">+{matchedSkills.length - 5} more</span>}
      </div>

      <div className="candidate-contact">
        <span>{candidate.email}</span>
        <span>{candidate.mobile}</span>
      </div>

      <button className="candidate-toggle" onClick={onToggle}>
        {expanded ? "Hide analysis" : "View analysis"}
      </button>

      {expanded && (
        <div className="candidate-analysis">
          <strong>Fit analysis</strong>
          <p>{candidate.fit_analysis}</p>
          {candidate.missing_skills.length > 0 && (
            <>
              <strong>Missing skills</strong>
              <div className="candidate-skill-band">
                {candidate.missing_skills.map((skill) => (
                  <span className="skill-chip missing" key={skill}>{skill}</span>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </article>
  );
}
