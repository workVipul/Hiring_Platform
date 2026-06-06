"use client";

import { useEffect, useMemo, useState } from "react";

import { jdApi } from "@/services/jdApi";
import type { JD } from "@/types/jd";

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
  raw_profile?: Record<string, unknown>;
}

type CandidateFilters = {
  query: string;
  location: string;
  experience: string;
  selectedSkills: string[];
  rawField: string;
  rawValue: string;
  fit: "all" | "strong" | "possible" | "weak";
  missingOnly: boolean;
  sort: "rank" | "match_desc" | "skill_desc" | "experience_desc" | "name_asc";
};

type SourceFilters = {
  skills: string[];
  goodSkills: string[];
  location: string;
  recency: string;
};

type CandidateDecision = "accepted" | "rejected";

const defaultFilters: CandidateFilters = {
  query: "",
  location: "all",
  experience: "all",
  selectedSkills: [],
  rawField: "all",
  rawValue: "",
  fit: "all",
  missingOnly: false,
  sort: "rank",
};

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
  const [jd, setJd] = useState<JD | null>(null);
  const [requiredSkills, setRequiredSkills] = useState<string[]>([]);
  const [goodToHaveSkills, setGoodToHaveSkills] = useState<string[]>([]);
  const [experienceRequirement, setExperienceRequirement] = useState<string | null>(null);
  const [loadingJD, setLoadingJD] = useState(true);
  const [loading, setLoading] = useState(false);
  const [sourceStarted, setSourceStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchNotice, setSearchNotice] = useState<string | null>(null);
  const [searchStrategy, setSearchStrategy] = useState<string | null>(null);
  const [pipelineCounts, setPipelineCounts] = useState<{
    retrieved_from_zoho: number;
    deterministic_filtered: number;
    sent_to_scoring: number;
    sent_to_llm: number;
    returned: number;
  } | null>(null);
  const [filterRejections, setFilterRejections] = useState<Record<string, number>>({});
  const [sourceFilters, setSourceFilters] = useState<SourceFilters>({ skills: [], goodSkills: [], location: "", recency: "all" });
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [candidateDecisions, setCandidateDecisions] = useState<Record<string, CandidateDecision>>({});
  const [filters, setFilters] = useState<CandidateFilters>(defaultFilters);
  const [page, setPage] = useState(1);
  const perPage = 6;
  const filterOptions = useMemo(() => buildFilterOptions(candidates), [candidates]);
  const filteredCandidates = useMemo(() => applyCandidateFilters(candidates, filters), [candidates, filters]);
  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / perPage));
  const visibleCandidates = filteredCandidates.slice((page - 1) * perPage, page * perPage);

  useEffect(() => {
    let active = true;
    async function loadJD() {
      setLoadingJD(true);
      setError(null);
      try {
        const loadedJD = await jdApi.get(jdId);
        if (!active) return;
        const metadata = loadedJD.metadata || {};
        const inferredMustHave = uniqueSorted(listFromUnknown(metadata.must_have_skills).length ? listFromUnknown(metadata.must_have_skills) : loadedJD.skills || []);
        const inferredGoodToHave = uniqueSorted([
          ...listFromUnknown(metadata.preferred_skills),
          ...listFromContentField(loadedJD.content, "nice_to_have"),
        ]);
        const inferredLocation = stringFromUnknown(metadata.location);
        const inferredSeniority = stringFromUnknown(metadata.seniority);
        const inferredExperience = stringFromUnknown(metadata.experience_years) || stringFromUnknown(metadata.experience);
        setJd(loadedJD);
        setRequiredSkills(inferredMustHave);
        setGoodToHaveSkills(inferredGoodToHave);
        setExperienceRequirement(inferredExperience || inferredSeniority || null);
        setSourceFilters({
          skills: inferredMustHave.slice(0, 8),
          goodSkills: inferredGoodToHave.slice(0, 8),
          location: inferredLocation,
          recency: "all",
        });
        setCandidates([]);
        setSourceStarted(false);
        setSearchNotice(null);
        setSearchStrategy(null);
        setPipelineCounts(null);
        setFilterRejections({});
        setCandidateDecisions({});
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load job description");
      } finally {
        if (active) setLoadingJD(false);
      }
    }
    loadJD();
    return () => {
      active = false;
    };
  }, [jdId]);

  async function fetchCandidates(allCandidates = false) {
    setLoading(true);
    setError(null);
    setSourceStarted(true);
    try {
      const res = await jdApi.sourceCandidates(jdId, 1, 100, {
        skills: allCandidates ? [] : sourceFilters.skills,
        location: allCandidates ? undefined : sourceFilters.location.trim() || undefined,
        allCandidates,
        recency: allCandidates ? undefined : sourceFilters.recency !== "all" ? sourceFilters.recency : undefined,
        goodSkills: allCandidates ? [] : sourceFilters.goodSkills,
      });
      setCandidates(res.candidates);
      setCandidateDecisions({});
      setFilters(defaultFilters);
      setPage(1);
      setRequiredSkills(res.required_skills || res.search_skills || []);
      setGoodToHaveSkills(res.good_to_have_skills || []);
      setExperienceRequirement(res.experience_requirement || res.search_seniority || null);
      setSearchNotice(res.search_notice || null);
      setSearchStrategy(res.search_strategy || null);
      setPipelineCounts(res.pipeline_counts || null);
      setFilterRejections(res.filter_rejections || {});
      setExpandedIds(new Set(res.candidates.slice(0, 1).map((candidate: Candidate) => candidate.id)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load candidates");
      setCandidates([]);
      setSearchNotice(null);
      setSearchStrategy(null);
      setPipelineCounts(null);
      setFilterRejections({});
    } finally {
      setLoading(false);
    }
  }

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

  function updateFilter<K extends keyof CandidateFilters>(key: K, value: CandidateFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }

  function setCandidateDecision(candidateId: string, decision: CandidateDecision) {
    setCandidateDecisions((prev) => ({ ...prev, [candidateId]: decision }));
  }

  return (
    <div className="candidate-page">
      <div className="candidate-toolbar">
        <button className="secondary-button compact-button" onClick={onClose}>
          Back to Job Descriptions
        </button>
        <div>
          <p className="eyebrow">
            Candidate Matches {jd?.metadata?.zoho_recruit_id ? `(Zoho Recruit ID: ${jd.metadata.zoho_recruit_id})` : ""}
          </p>
          <h2>{jdTitle}</h2>
        </div>
      </div>

      {(requiredSkills.length > 0 || goodToHaveSkills.length > 0 || experienceRequirement) && (
        <div className="sourcing-requirements-band">
          <span className="muted small">Reviewer checklist</span>
          <div className="requirement-chip-list">
            {experienceRequirement && <span className="experience-chip">Experience: {experienceRequirement}</span>}
            {requiredSkills.slice(0, 12).map((skill) => (
              <span key={skill}>Must: {skill}</span>
            ))}
            {goodToHaveSkills.slice(0, 8).map((skill) => (
              <span className="optional-chip" key={skill}>Good: {skill}</span>
            ))}
          </div>
        </div>
      )}

      {loadingJD && (
        <div className="panel empty-state">
          <p>Loading JD sourcing requirements...</p>
        </div>
      )}

      {!loadingJD && !sourceStarted && !error && jd && (
        <SourceFilterPanel
          jd={jd}
          availableSkills={requiredSkills}
          goodToHaveSkills={goodToHaveSkills}
          filters={sourceFilters}
          onChange={setSourceFilters}
          onStart={() => fetchCandidates(false)}
          onStartAll={() => fetchCandidates(true)}
        />
      )}

      {loading && (
        <div className="candidate-grid">
          {[1, 2, 3].map((n) => (
            <div key={n} className="candidate-card candidate-card-skeleton" />
          ))}
        </div>
      )}

      {sourceStarted && !loading && !error && (searchNotice || searchStrategy || pipelineCounts || Object.keys(filterRejections).length > 0) && (
        <div className="source-search-summary">
          {searchStrategy && <strong>Search used: {searchStrategy}</strong>}
          {searchNotice && <p>{searchNotice}</p>}

          {pipelineCounts && (
            <p>
              Pipeline: {pipelineCounts.retrieved_from_zoho} retrieved, {pipelineCounts.deterministic_filtered} passed filters, {pipelineCounts.sent_to_scoring} scored, {pipelineCounts.sent_to_llm} sent to LLM, {pipelineCounts.returned} returned.
            </p>
          )}
          {Object.keys(filterRejections).length > 0 && (
            <div className="filter-rejection-list">
              <strong>Why candidates were rejected</strong>
              {Object.entries(filterRejections).slice(0, 5).map(([reason, count]) => (
                <span key={reason}>{count} - {reason}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="error-box">
          <p><strong>Error sourcing candidates:</strong> {error}</p>
          <button className="secondary-button" onClick={onClose}>Return to List</button>
        </div>
      )}

      {sourceStarted && !loading && !error && candidates.length === 0 && (
        <div className="panel empty-state">
          <p>No candidates found in your Zoho Recruit portal matching the selected filters.</p>
        </div>
      )}

      {sourceStarted && !loading && !error && candidates.length > 0 && (
        <>
          <div className="candidate-results-layout">
            <CandidateFilterSidebar
              filters={filters}
              options={filterOptions}
              totalCount={candidates.length}
              filteredCount={filteredCandidates.length}
              onChange={updateFilter}
              onReset={() => {
                setFilters(defaultFilters);
                setPage(1);
              }}
              requiredSkills={requiredSkills}
              goodToHaveSkills={goodToHaveSkills}
            />
            <div className="candidate-results-stack">
              {visibleCandidates.length > 0 ? (
                <div className="candidate-grid">
                  {visibleCandidates.map((candidate) => (
                    <CandidateCard
                      key={candidate.id}
                      candidate={candidate}
                      expanded={expandedIds.has(candidate.id)}
                      initials={initials(candidate.full_name)}
                      decision={candidateDecisions[candidate.id]}
                      onToggle={() => toggleExpand(candidate.id)}
                      onDecision={(decision) => setCandidateDecision(candidate.id, decision)}
                    />
                  ))}
                </div>
              ) : (
                <div className="panel empty-state">
                  <p>No candidates match the selected filters.</p>
                </div>
              )}
            </div>
          </div>
          <div className="candidate-pagination">
            <button className="secondary-button compact-button" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
              Previous
            </button>
            <span className="muted small">
              Page {page} of {totalPages} - {filteredCandidates.length} of {candidates.length} candidates
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

function SourceFilterPanel({
  jd,
  availableSkills,
  goodToHaveSkills,
  filters,
  onChange,
  onStart,
  onStartAll,
}: {
  jd: JD;
  availableSkills: string[];
  goodToHaveSkills: string[];
  filters: SourceFilters;
  onChange: (filters: SourceFilters) => void;
  onStart: () => void;
  onStartAll: () => void;
}) {
  return (
    <div className="source-filter-panel">
      <div className="source-filter-copy">
        <p className="eyebrow">Pre-source filters</p>
        <h3>Choose Zoho filters before ranking</h3>
        <p className="muted">
          Must-have skills are combined with OR. Good-to-have skills and JD/recruiter locations are combined with OR before candidates are sent to ranking.
        </p>
      </div>

      <div className="source-filter-grid">
        <label>
          JD title
          <input value={jd.title} disabled />
        </label>
        {Boolean(jd.metadata?.zoho_recruit_id) && (
          <label>
            Zoho Job ID
            <input value={String(jd.metadata.zoho_recruit_id)} disabled />
          </label>
        )}
        <label>
          Location
          <select
            value={filters.location}
            onChange={(e) => onChange({ ...filters, location: e.target.value })}
            style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }}
          >
            <option value="">All locations</option>
            <option value="Bangalore">Bangalore</option>
            <option value="Delhi">Delhi</option>
            <option value="Mumbai">Mumbai</option>
            <option value="Pune">Pune</option>
            <option value="Hyderabad">Hyderabad</option>
            <option value="Chennai">Chennai</option>
          </select>
        </label>
        <label>
          Recency
          <select value={filters.recency} onChange={(e) => onChange({ ...filters, recency: e.target.value })}>
            <option value="all">Anytime</option>
            <option value="3_months">Updated last 3 months</option>
            <option value="6_months">Updated last 6 months</option>
          </select>
        </label>
      </div>

      <div className="source-skill-picker">
        <div>
          <strong>Must-have skills</strong>
          <span className="muted small">These are required and will be included in the search criteria.</span>
        </div>
        <div className="requirement-chip-list">
          {availableSkills.map((skill) => (
            <span key={skill} className="source-skill-chip active" style={{ cursor: "default" }}>
              {skill}
            </span>
          ))}
        </div>
      </div>

      {goodToHaveSkills.length > 0 && (
        <div className="source-skill-picker">
          <div>
            <strong>Good-to-have skills</strong>
            <span className="muted small">Click to select or deselect preferred skills to narrow the Zoho result set.</span>
          </div>
          <div className="requirement-chip-list">
            {goodToHaveSkills.map((skill) => {
              const isActive = filters.goodSkills.includes(skill);
              return (
                <button
                  key={skill}
                  className={isActive ? "source-skill-chip active" : "source-skill-chip optional"}
                  type="button"
                  onClick={() => {
                    const exists = filters.goodSkills.includes(skill);
                    const newGoodSkills = exists
                      ? filters.goodSkills.filter((item) => item !== skill)
                      : [...filters.goodSkills, skill];
                    onChange({
                      ...filters,
                      goodSkills: newGoodSkills,
                    });
                  }}
                >
                  {skill}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="source-filter-actions">
        <button className="primary-button" onClick={onStart}>
          Fetch filtered candidates
        </button>
        <button className="secondary-button" onClick={onStartAll}>
          Source all candidates
        </button>
      </div>
    </div>
  );
}

function CandidateFilterSidebar({
  filters,
  options,
  totalCount,
  filteredCount,
  onChange,
  onReset,
  requiredSkills,
  goodToHaveSkills,
}: {
  filters: CandidateFilters;
  options: ReturnType<typeof buildFilterOptions>;
  totalCount: number;
  filteredCount: number;
  onChange: <K extends keyof CandidateFilters>(key: K, value: CandidateFilters[K]) => void;
  onReset: () => void;
  requiredSkills: string[];
  goodToHaveSkills: string[];
}) {
  return (
    <aside className="candidate-filter-sidebar">
      <div className="candidate-filter-header">
        <div>
          <p className="eyebrow">Filters</p>
          <h3>Refine candidates</h3>
        </div>
        <span className="muted small">{filteredCount}/{totalCount}</span>
      </div>

      <label>
        Search
        <input value={filters.query} onChange={(e) => onChange("query", e.target.value)} placeholder="Name, email, skill, location" />
      </label>

      <label>
        Location
        <select value={filters.location} onChange={(e) => onChange("location", e.target.value)}>
          <option value="all">All locations</option>
          {options.locations.map((location) => <option key={location} value={location}>{location}</option>)}
        </select>
      </label>

      <label>
        Experience
        <select value={filters.experience} onChange={(e) => onChange("experience", e.target.value)}>
          <option value="all">All experience levels</option>
          {options.experienceLevels.map((experience) => <option key={experience} value={experience}>{experience}</option>)}
        </select>
      </label>

      <div className="skills-filter-group" style={{ marginBottom: "16px", marginTop: "12px" }}>
        <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-secondary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>
          Filter by Skills
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "150px", overflowY: "auto", paddingRight: "4px" }}>
          {uniqueSorted([...requiredSkills, ...goodToHaveSkills]).map((skill) => {
            const isChecked = filters.selectedSkills?.includes(skill) ?? false;
            return (
              <label key={skill} className="filter-checkbox" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer", fontWeight: "normal" }}>
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={(e) => {
                    const newSkills = e.target.checked
                      ? [...(filters.selectedSkills || []), skill]
                      : (filters.selectedSkills || []).filter((s) => s !== skill);
                    onChange("selectedSkills", newSkills);
                  }}
                />
                {skill}
              </label>
            );
          })}
        </div>
      </div>

      <label>
        Zoho field
        <select value={filters.rawField} onChange={(e) => onChange("rawField", e.target.value)}>
          <option value="all">Any field</option>
          {options.rawFields.map((field) => <option key={field} value={field}>{formatZohoField(field)}</option>)}
        </select>
      </label>

      <label>
        Field contains
        <input
          value={filters.rawValue}
          onChange={(e) => onChange("rawValue", e.target.value)}
          placeholder="Filter raw Zoho values"
          disabled={filters.rawField === "all"}
        />
      </label>

      <label>
        Fit band
        <select value={filters.fit} onChange={(e) => onChange("fit", e.target.value as CandidateFilters["fit"])}>
          <option value="all">All fit bands</option>
          <option value="strong">Strong fit</option>
          <option value="possible">Possible fit</option>
          <option value="weak">Weak fit</option>
        </select>
      </label>

      <label>
        Sort by
        <select value={filters.sort} onChange={(e) => onChange("sort", e.target.value as CandidateFilters["sort"])}>
          <option value="rank">Current rank</option>
          <option value="match_desc">Best overall match</option>
          <option value="skill_desc">Best skill match</option>
          <option value="experience_desc">Best experience fit</option>
          <option value="name_asc">Name A-Z</option>
        </select>
      </label>

      <label className="filter-checkbox">
        <input type="checkbox" checked={filters.missingOnly} onChange={(e) => onChange("missingOnly", e.target.checked)} />
        Show candidates with missing skills
      </label>

      <button className="ghost-button" onClick={onReset}>Reset filters</button>
    </aside>
  );
}

function buildFilterOptions(candidates: Candidate[]) {
  const locations = uniqueSorted(candidates.map((candidate) => candidate.location).filter(isUsefulValue));
  const experienceLevels = uniqueSorted(candidates.map((candidate) => candidate.experience_level).filter(isUsefulValue));
  const skills = uniqueSorted(candidates.flatMap((candidate) => candidate.skills || []).filter(isUsefulValue));
  const rawFields = uniqueSorted(candidates.flatMap((candidate) => Object.keys(candidate.raw_profile || {})).filter(isUsefulValue));
  return { locations, experienceLevels, skills, rawFields };
}

function applyCandidateFilters(candidates: Candidate[], filters: CandidateFilters) {
  const query = filters.query.trim().toLowerCase();
  const filtered = candidates.filter((candidate) => {
    if (filters.location !== "all" && candidate.location !== filters.location) return false;
    if (filters.experience !== "all" && candidate.experience_level !== filters.experience) return false;
    if (filters.selectedSkills && filters.selectedSkills.length > 0) {
      if (!filters.selectedSkills.every((s) => candidate.skills.includes(s))) return false;
    }
    if (filters.rawField !== "all" && filters.rawValue.trim()) {
      const rawValue = String(candidate.raw_profile?.[filters.rawField] ?? "").toLowerCase();
      if (!rawValue.includes(filters.rawValue.trim().toLowerCase())) return false;
    }
    if (filters.fit !== "all" && fitBand(candidate) !== filters.fit) return false;
    if (filters.missingOnly && candidate.missing_skills.length === 0) return false;
    if (!query) return true;
    return searchableCandidateText(candidate).includes(query);
  });

  return [...filtered].sort((a, b) => {
    if (filters.sort === "match_desc") return b.match_percentage - a.match_percentage;
    if (filters.sort === "skill_desc") return b.skill_match_score - a.skill_match_score;
    if (filters.sort === "experience_desc") return b.experience_synergy - a.experience_synergy;
    if (filters.sort === "name_asc") return a.full_name.localeCompare(b.full_name);
    return a.rank_position - b.rank_position;
  });
}

function fitBand(candidate: Candidate): CandidateFilters["fit"] {
  if (candidate.match_percentage >= 80) return "strong";
  if (candidate.match_percentage >= 50) return "possible";
  return "weak";
}

function searchableCandidateText(candidate: Candidate): string {
  const rawValues = candidate.raw_profile ? Object.values(candidate.raw_profile).map((value) => String(value)) : [];
  return [
    candidate.full_name,
    candidate.email,
    candidate.mobile,
    candidate.location,
    candidate.experience_level,
    candidate.fit_analysis,
    ...(candidate.skills || []),
    ...(candidate.missing_skills || []),
    ...rawValues,
  ].join(" ").toLowerCase();
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function isUsefulValue(value: string): value is string {
  return Boolean(value && value !== "N/A");
}

function formatZohoField(field: string): string {
  return field.replace(/_/g, " ");
}

function listFromUnknown(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") return value.split(",").map((item) => item.trim()).filter(Boolean);
  return [];
}

function listFromContentField(content: string | null, key: string): string[] {
  if (!content) return [];
  try {
    const parsed = JSON.parse(content);
    return parsed && typeof parsed === "object" ? listFromUnknown(parsed[key]) : [];
  } catch {
    return [];
  }
}

function stringFromUnknown(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") return String(value);
  return "";
}

function CandidateCard({
  candidate,
  expanded,
  initials,
  decision,
  onToggle,
  onDecision,
}: {
  candidate: Candidate;
  expanded: boolean;
  initials: string;
  decision?: CandidateDecision;
  onToggle: () => void;
  onDecision: (decision: CandidateDecision) => void;
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
          <span>Experience fit</span>
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

      <div className="candidate-decision-actions">
        <button
          className={decision === "rejected" ? "danger-button active" : "danger-button"}
          type="button"
          onClick={() => onDecision("rejected")}
        >
          Reject
        </button>
        <button
          className={decision === "accepted" ? "primary-button active" : "secondary-button"}
          type="button"
          onClick={() => onDecision("accepted")}
        >
          Accept
        </button>
      </div>

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
