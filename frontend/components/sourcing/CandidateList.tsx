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
  skill: string;
  rawField: string;
  rawValue: string;
  fit: "all" | "strong" | "possible" | "weak";
  missingOnly: boolean;
  sort: "rank" | "match_desc" | "skill_desc" | "experience_desc" | "name_asc";
};

type SourceFilters = {
  skills: string[];
  location: string;
  seniority: string;
  perPage: number;
};

const defaultFilters: CandidateFilters = {
  query: "",
  location: "all",
  experience: "all",
  skill: "all",
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
  const [experienceRequirement, setExperienceRequirement] = useState<string | null>(null);
  const [loadingJD, setLoadingJD] = useState(true);
  const [loading, setLoading] = useState(false);
  const [sourceStarted, setSourceStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchNotice, setSearchNotice] = useState<string | null>(null);
  const [searchStrategy, setSearchStrategy] = useState<string | null>(null);
  const [sourceFilters, setSourceFilters] = useState<SourceFilters>({ skills: [], location: "", seniority: "", perPage: 20 });
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
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
        const inferredSkills = uniqueSorted([
          ...(loadedJD.skills || []),
          ...listFromUnknown(metadata.must_have_skills),
        ]);
        const inferredLocation = stringFromUnknown(metadata.location);
        const inferredSeniority = stringFromUnknown(metadata.seniority);
        const inferredExperience = stringFromUnknown(metadata.experience_years) || stringFromUnknown(metadata.experience);
        setJd(loadedJD);
        setRequiredSkills(inferredSkills);
        setExperienceRequirement(inferredExperience || inferredSeniority || null);
        setSourceFilters({
          skills: inferredSkills.slice(0, 5),
          location: inferredLocation,
          seniority: inferredSeniority,
          perPage: 20,
        });
        setCandidates([]);
        setSourceStarted(false);
        setSearchNotice(null);
        setSearchStrategy(null);
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
      const res = await jdApi.sourceCandidates(jdId, 1, sourceFilters.perPage, {
        skills: allCandidates ? [] : sourceFilters.skills,
        location: allCandidates ? undefined : sourceFilters.location.trim() || undefined,
        seniority: allCandidates ? undefined : sourceFilters.seniority.trim() || undefined,
        allCandidates,
      });
      setCandidates(res.candidates);
      setFilters(defaultFilters);
      setPage(1);
      setRequiredSkills(res.required_skills || res.search_skills || []);
      setExperienceRequirement(res.experience_requirement || res.search_seniority || null);
      setSearchNotice(res.search_notice || null);
      setSearchStrategy(res.search_strategy || null);
      setExpandedIds(new Set(res.candidates.slice(0, 1).map((candidate: Candidate) => candidate.id)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load candidates");
      setCandidates([]);
      setSearchNotice(null);
      setSearchStrategy(null);
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
        <div className="sourcing-requirements-band">
          <span className="muted small">Reviewer checklist</span>
          <div className="requirement-chip-list">
            {experienceRequirement && <span className="experience-chip">Experience: {experienceRequirement}</span>}
            {requiredSkills.slice(0, 12).map((skill) => (
              <span key={skill}>{skill}</span>
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
          experienceRequirement={experienceRequirement}
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

      {sourceStarted && !loading && !error && (searchNotice || searchStrategy) && (
        <div className="source-search-summary">
          {searchStrategy && <strong>Search used: {searchStrategy}</strong>}
          {searchNotice && <p>{searchNotice}</p>}
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
                      onToggle={() => toggleExpand(candidate.id)}
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
  experienceRequirement,
  filters,
  onChange,
  onStart,
  onStartAll,
}: {
  jd: JD;
  availableSkills: string[];
  experienceRequirement: string | null;
  filters: SourceFilters;
  onChange: (filters: SourceFilters) => void;
  onStart: () => void;
  onStartAll: () => void;
}) {
  function toggleSkill(skill: string) {
    const exists = filters.skills.includes(skill);
    onChange({
      ...filters,
      skills: exists ? filters.skills.filter((item) => item !== skill) : [...filters.skills, skill],
    });
  }

  return (
    <div className="source-filter-panel">
      <div className="source-filter-copy">
        <p className="eyebrow">Pre-source filters</p>
        <h3>Choose Zoho filters before ranking</h3>
        <p className="muted">
          Skills and location narrow the Zoho fetch. Experience is applied during ranking so strong candidates are not discarded because of ATS wording differences.
        </p>
      </div>

      <div className="source-filter-grid">
        <label>
          JD title
          <input value={jd.title} disabled />
        </label>
        <label>
          Location
          <input
            value={filters.location}
            onChange={(e) => onChange({ ...filters, location: e.target.value })}
            placeholder="Example: Bangalore"
          />
        </label>
        <label>
          Experience / seniority for ranking
          <input
            value={filters.seniority}
            onChange={(e) => onChange({ ...filters, seniority: e.target.value })}
            placeholder={experienceRequirement || "Example: Senior"}
          />
        </label>
        <label>
          Candidates to fetch
          <select value={filters.perPage} onChange={(e) => onChange({ ...filters, perPage: Number(e.target.value) })}>
            <option value={10}>Top 10 from Zoho</option>
            <option value={20}>Top 20 from Zoho</option>
            <option value={50}>Top 50 from Zoho</option>
            <option value={100}>Top 100 from Zoho</option>
          </select>
        </label>
      </div>

      <div className="source-skill-picker">
        <div>
          <strong>Skills to include</strong>
          <span className="muted small">Select at least one skill for Zoho search.</span>
        </div>
        <div className="requirement-chip-list">
          {availableSkills.map((skill) => (
            <button
              key={skill}
              className={filters.skills.includes(skill) ? "source-skill-chip active" : "source-skill-chip"}
              type="button"
              onClick={() => toggleSkill(skill)}
            >
              {skill}
            </button>
          ))}
        </div>
      </div>

      <div className="source-filter-actions">
        <button className="primary-button" disabled={filters.skills.length === 0} onClick={onStart}>
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
}: {
  filters: CandidateFilters;
  options: ReturnType<typeof buildFilterOptions>;
  totalCount: number;
  filteredCount: number;
  onChange: <K extends keyof CandidateFilters>(key: K, value: CandidateFilters[K]) => void;
  onReset: () => void;
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

      <label>
        Skill
        <select value={filters.skill} onChange={(e) => onChange("skill", e.target.value)}>
          <option value="all">All skills</option>
          {options.skills.map((skill) => <option key={skill} value={skill}>{skill}</option>)}
        </select>
      </label>

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
    if (filters.skill !== "all" && !candidate.skills.includes(filters.skill)) return false;
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

function stringFromUnknown(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") return String(value);
  return "";
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
