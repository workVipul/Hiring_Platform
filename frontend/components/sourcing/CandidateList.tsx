"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { jdApi } from "@/services/jdApi";
import { ownershipApi, type CandidateOwnership, type SLARule } from "@/services/ownershipApi";
import { useAuthStore } from "@/store/authStore";
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
  ownership?: CandidateOwnership | null;
}

type CandidateFilters = {
  query: string;
  location: string;
  experience: string;
  selectedSkills: string[];
  rawField: string;
  rawValue: string;
  fit: "all" | "strong" | "possible" | "weak";
  sort: "rank" | "match_desc" | "skill_desc" | "experience_desc" | "name_asc";
};

type SourceFilters = {
  skills: string[];
  goodSkills: string[];
  locations: string[];
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
  const [sourceFilters, setSourceFilters] = useState<SourceFilters>({ skills: [], goodSkills: [], locations: [], recency: "all" });
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [candidateDecisions, setCandidateDecisions] = useState<Record<string, CandidateDecision>>({});
  const [filters, setFilters] = useState<CandidateFilters>(defaultFilters);
  const [slaRules, setSlaRules] = useState<SLARule[]>([]);
  const [ownershipError, setOwnershipError] = useState<string | null>(null);
  const [ownershipSavingId, setOwnershipSavingId] = useState<string | null>(null);
  const [acceptCandidate, setAcceptCandidate] = useState<Candidate | null>(null);
  const [acceptSlaStageId, setAcceptSlaStageId] = useState<number | "">("");
  const [rejectCandidate, setRejectCandidate] = useState<Candidate | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectSavingId, setRejectSavingId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const currentUserName = useAuthStore((state) => state.userName);
  const accessType = useAuthStore((state) => state.accessType);
  const acceptSlaRules = useMemo(() => {
    if (accessType === "admin" || accessType === "manager") return slaRules;
    return slaRules.filter((rule) => rule.blueprint === "SCR");
  }, [accessType, slaRules]);
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
          locations: cityListFromLocation(inferredLocation),
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

  useEffect(() => {
    let active = true;
    async function loadOwnershipControls() {
      try {
        const stages = await ownershipApi.listSlaRules(true);
        if (!active) return;
        setSlaRules(stages);
        const availableAcceptStages = accessType === "admin" || accessType === "manager"
          ? stages
          : stages.filter((rule) => rule.blueprint === "SCR");
        setAcceptSlaStageId(availableAcceptStages[0]?.id ?? stages[0]?.id ?? "");
      } catch (e) {
        if (active) setOwnershipError(e instanceof Error ? e.message : "Failed to load SLA controls");
      }
    }
    loadOwnershipControls();
    return () => {
      active = false;
    };
  }, [accessType]);

  async function fetchCandidates(allCandidates = false) {
    setLoading(true);
    setError(null);
    setSourceStarted(true);
    try {
      const res = await jdApi.sourceCandidates(jdId, 1, 100, {
        skills: allCandidates ? [] : sourceFilters.skills,
        location: allCandidates ? undefined : sourceFilters.locations.join(",") || undefined,
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

  function updateCandidateOwnership(candidateId: string, ownership: CandidateOwnership | null) {
    setCandidates((prev) => prev.map((candidate) => (
      candidate.id === candidateId ? { ...candidate, ownership } : candidate
    )));
  }

  function openAcceptModal(candidate: Candidate) {
    setOwnershipError(null);
    setAcceptCandidate(candidate);
    setAcceptSlaStageId(acceptSlaRules[0]?.id ?? "");
  }

  async function submitAccept() {
    if (!acceptCandidate || !acceptSlaStageId) return;
    setOwnershipSavingId(acceptCandidate.id);
    setOwnershipError(null);
    try {
      const ownership = await ownershipApi.accept({
        zoho_candidate_id: acceptCandidate.id,
        candidate_name: acceptCandidate.full_name,
        job_opening_id: String(jd?.metadata?.zoho_recruit_id ?? jdId),
        sla_stage_id: Number(acceptSlaStageId),
      });
      updateCandidateOwnership(acceptCandidate.id, ownership);
      setCandidateDecision(acceptCandidate.id, "accepted");
      setAcceptCandidate(null);
    } catch (e) {
      setOwnershipError(e instanceof Error ? e.message : "Failed to accept candidate");
    } finally {
      setOwnershipSavingId(null);
    }
  }

  function openRejectModal(candidate: Candidate) {
    setOwnershipError(null);
    setRejectCandidate(candidate);
    setRejectReason("");
  }

  async function submitReject() {
    if (!rejectCandidate || rejectReason.trim().length < 3) return;
    setRejectSavingId(rejectCandidate.id);
    setOwnershipError(null);
    try {
      await jdApi.rejectCandidate({
        jd_id: jdId,
        zoho_candidate_id: rejectCandidate.id,
        candidate_name: rejectCandidate.full_name,
        job_opening_id: String(jd?.metadata?.zoho_recruit_id ?? jdId),
        reason: rejectReason.trim(),
      });
      setCandidates((prev) => prev.filter((candidate) => candidate.id !== rejectCandidate.id));
      setCandidateDecisions((prev) => {
        const next = { ...prev };
        delete next[rejectCandidate.id];
        return next;
      });
      setRejectCandidate(null);
      setRejectReason("");
    } catch (e) {
      setOwnershipError(e instanceof Error ? e.message : "Failed to reject candidate");
    } finally {
      setRejectSavingId(null);
    }
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

      {ownershipError && (
        <div className="error-box ownership-error">
          <p>{ownershipError}</p>
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
                      saving={ownershipSavingId === candidate.id || rejectSavingId === candidate.id}
                      onToggle={() => toggleExpand(candidate.id)}
                      onDecision={(decision) => setCandidateDecision(candidate.id, decision)}
                      onAccept={() => openAcceptModal(candidate)}
                      onReject={() => openRejectModal(candidate)}
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

      {acceptCandidate && (
        <div className="confirm-overlay">
          <div className="confirm-dialog ownership-dialog">
            <div className="confirm-copy">
              <h3>Accept candidate</h3>
              <p>Select the SLA stage to lock ownership for this candidate.</p>
            </div>
            <div className="ownership-form-grid">
              <label>
                Candidate Name
                <input value={acceptCandidate.full_name} disabled />
              </label>
              <label>
                Candidate ID
                <input value={acceptCandidate.id} disabled />
              </label>
              <label>
                Job ID
                <input value={String(jd?.metadata?.zoho_recruit_id ?? jdId)} disabled />
              </label>
              <label>
                Recruiter Name
                <input value={currentUserName ?? "Recruiter"} disabled />
              </label>
              <label className="ownership-dialog-stage">
                SLA Stage
                <select value={acceptSlaStageId} onChange={(e) => setAcceptSlaStageId(Number(e.target.value))}>
                  {acceptSlaRules.map((rule) => (
                    <option key={rule.id} value={rule.id}>
                      {rule.stage_name} ({rule.duration_days} days)
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="confirm-actions">
              <button className="ghost-button" onClick={() => setAcceptCandidate(null)} disabled={Boolean(ownershipSavingId)}>
                Cancel
              </button>
              <button className="primary-button" onClick={submitAccept} disabled={!acceptSlaStageId || Boolean(ownershipSavingId)}>
                Confirm Accept
              </button>
            </div>
          </div>
        </div>
      )}

      {rejectCandidate && (
        <div className="confirm-overlay">
          <div className="confirm-dialog ownership-dialog">
            <div className="confirm-copy">
              <h3>Reject candidate</h3>
              <p>This candidate will be hidden for you on this job only. Other recruiters can still source the candidate unless they reject them too.</p>
            </div>
            <div className="ownership-form-grid">
              <label>
                Candidate Name
                <input value={rejectCandidate.full_name} disabled />
              </label>
              <label>
                Candidate ID
                <input value={rejectCandidate.id} disabled />
              </label>
              <label>
                Job ID
                <input value={String(jd?.metadata?.zoho_recruit_id ?? jdId)} disabled />
              </label>
              <label>
                Recruiter Name
                <input value={currentUserName ?? "Recruiter"} disabled />
              </label>
              <label className="ownership-dialog-stage">
                Rejection Reason
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Add a short reason for rejecting this candidate"
                  rows={4}
                />
              </label>
            </div>
            <div className="confirm-actions">
              <button className="ghost-button" onClick={() => setRejectCandidate(null)} disabled={Boolean(rejectSavingId)}>
                Cancel
              </button>
              <button className="danger-button" onClick={submitReject} disabled={rejectReason.trim().length < 3 || Boolean(rejectSavingId)}>
                Reject Candidate
              </button>
            </div>
          </div>
        </div>
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
  const locationOptions = buildSourceLocationOptions(jd, filters.locations);

  return (
    <div className="source-filter-panel">
      <div className="source-filter-copy">
        <p className="eyebrow">Pre-source filters</p>
        <h3>Choose Zoho filters before ranking</h3>
        <p className="muted">
          Must-have skills are combined with AND. Selected city locations are combined with OR before candidates are sent to ranking.
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
        <div className="source-filter-field">
          <span>City locations</span>
          <CheckboxMultiSelect
            label="City locations"
            options={locationOptions}
            selectedValues={filters.locations}
            placeholder="All cities"
            onChange={(locations) => onChange({ ...filters, locations })}
          />
        </div>
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
            <span className="muted small">Click to select or deselect preferred skills used as scoring signals after hard filtering.</span>
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

function CheckboxMultiSelect({
  label,
  options,
  selectedValues,
  placeholder,
  onChange,
}: {
  label: string;
  options: string[];
  selectedValues: string[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!dropdownRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  function toggleValue(value: string) {
    const nextValues = selectedValues.includes(value)
      ? selectedValues.filter((item) => item !== value)
      : [...selectedValues, value];
    onChange(uniqueSorted(nextValues));
  }

  const selectedLabel = selectedValues.length === 0
    ? placeholder
    : selectedValues.length <= 2
      ? selectedValues.join(", ")
      : `${selectedValues.slice(0, 2).join(", ")} +${selectedValues.length - 2}`;

  return (
    <div className="checkbox-multiselect" ref={dropdownRef}>
      <button
        type="button"
        className={open ? "checkbox-multiselect-trigger active" : "checkbox-multiselect-trigger"}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className={selectedValues.length === 0 ? "placeholder" : ""}>{selectedLabel}</span>
        <span className="checkbox-multiselect-caret">v</span>
      </button>

      {open && (
        <div className="checkbox-multiselect-menu" role="listbox" aria-label={label}>
          <div className="checkbox-multiselect-actions">
            <button type="button" onClick={() => onChange(options)}>
              Select all
            </button>
            <button type="button" onClick={() => onChange([])}>
              Clear
            </button>
          </div>
          <div className="checkbox-multiselect-options">
            {options.map((option) => {
              const checked = selectedValues.includes(option);
              return (
                <label key={option} className="checkbox-multiselect-option">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleValue(option)}
                  />
                  <span>{option}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
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

      <button className="ghost-button" onClick={onReset}>Reset filters</button>
    </aside>
  );
}

function buildFilterOptions(candidates: Candidate[]) {
  const locations = uniqueSorted(candidates.map((candidate) => candidateCity(candidate)).filter(isUsefulValue));
  const experienceLevels = uniqueSorted(candidates.map((candidate) => candidate.experience_level).filter(isUsefulValue));
  const skills = uniqueSorted(candidates.flatMap((candidate) => candidate.skills || []).filter(isUsefulValue));
  const rawFields = uniqueSorted(candidates.flatMap((candidate) => Object.keys(candidate.raw_profile || {})).filter(isUsefulValue));
  return { locations, experienceLevels, skills, rawFields };
}

function applyCandidateFilters(candidates: Candidate[], filters: CandidateFilters) {
  const query = filters.query.trim().toLowerCase();
  const filtered = candidates.filter((candidate) => {
    if (filters.location !== "all" && candidateCity(candidate) !== filters.location) return false;
    if (filters.experience !== "all" && candidate.experience_level !== filters.experience) return false;
    if (filters.selectedSkills && filters.selectedSkills.length > 0) {
      if (!filters.selectedSkills.every((s) => candidate.skills.includes(s))) return false;
    }
    if (filters.rawField !== "all" && filters.rawValue.trim()) {
      const rawValue = String(candidate.raw_profile?.[filters.rawField] ?? "").toLowerCase();
      if (!rawValue.includes(filters.rawValue.trim().toLowerCase())) return false;
    }
    if (filters.fit !== "all" && fitBand(candidate) !== filters.fit) return false;
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

function candidateCity(candidate: Candidate): string {
  const rawCity = candidate.raw_profile?.City;
  if (typeof rawCity === "string" && rawCity.trim()) return rawCity.trim();
  return firstCityToken(candidate.location);
}

function firstCityToken(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.split(",")[0].trim();
}

function cityListFromLocation(value: string): string[] {
  return firstCityToken(value) ? [firstCityToken(value)] : [];
}

function buildSourceLocationOptions(jd: JD, selectedLocations: string[]): string[] {
  const jdCity = cityListFromLocation(stringFromUnknown(jd.metadata?.location));
  return uniqueSorted([
    ...jdCity,
    ...selectedLocations,
    "Bengaluru",
    "Bangalore",
    "Hyderabad",
    "Pune",
    "Mumbai",
    "Delhi",
    "Chennai",
    "Noida",
    "Gurugram",
  ]);
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
  saving,
  onToggle,
  onDecision,
  onAccept,
  onReject,
}: {
  candidate: Candidate;
  expanded: boolean;
  initials: string;
  decision?: CandidateDecision;
  saving: boolean;
  onToggle: () => void;
  onDecision: (decision: CandidateDecision) => void;
  onAccept: () => void;
  onReject: () => void;
}) {
  const matchedSkills = candidate.skills.filter((skill) => !candidate.missing_skills.includes(skill));
  const fitTone = candidate.match_percentage >= 80 ? "strong" : candidate.match_percentage >= 50 ? "possible" : "weak";
  const ownership = candidate.ownership;
  const lockedByOther = Boolean(ownership?.is_locked_by_other);

  return (
    <article className={lockedByOther ? "candidate-card candidate-card-locked" : "candidate-card"}>
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

      {ownership ? (
        <div className={lockedByOther ? "ownership-band ownership-band-actions locked" : "ownership-band ownership-band-actions owned"}>
          <div>
            <strong>{lockedByOther ? `Owned by ${ownership.owner_recruiter_name}` : "Ownership active"}</strong>
            <span>{ownership.sla_stage_name ?? "SLA stage"} - {formatRemainingTime(ownership.remaining_seconds)} remaining</span>
          </div>
        </div>
      ) : (
        <div className="candidate-decision-actions">
          <button
            className={decision === "rejected" ? "danger-button active" : "danger-button"}
            type="button"
            disabled={saving}
            onClick={() => {
              onDecision("rejected");
              onReject();
            }}
          >
            Reject
          </button>
          <button
            className={decision === "accepted" ? "primary-button active" : "secondary-button"}
            type="button"
            disabled={saving}
            onClick={onAccept}
          >
            Accept
          </button>
        </div>
      )}

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

function formatRemainingTime(totalSeconds: number): string {
  if (totalSeconds <= 0) return "Expired";
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  const minutes = Math.max(1, Math.floor((totalSeconds % 3600) / 60));
  return `${hours}h ${minutes}m`;
}
