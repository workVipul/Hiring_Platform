"use client";

import { useEffect, useMemo, useState } from "react";

import { jdApi, type CandidateRejection } from "@/services/jdApi";
import { ownershipApi, type CandidateOwnership, type RecruiterOption, type SLARule } from "@/services/ownershipApi";
import { useAuthStore } from "@/store/authStore";

type OwnershipTab = "my" | "all" | "rejected" | "sla";

const BLUEPRINT_ORDER = ["SCR", "R1/R2", "T1/T2", "CSCR", "CR1", "CR2", "OFR", "JOIN", "REJ", "ARC"];

export default function OwnershipPage() {
  const accessType = useAuthStore((state) => state.accessType);
  const canManage = accessType === "admin" || accessType === "manager";
  const [rules, setRules] = useState<SLARule[]>([]);
  const [myOwnerships, setMyOwnerships] = useState<CandidateOwnership[]>([]);
  const [allOwnerships, setAllOwnerships] = useState<CandidateOwnership[]>([]);
  const [rejectedCandidates, setRejectedCandidates] = useState<CandidateRejection[]>([]);
  const [recruiters, setRecruiters] = useState<RecruiterOption[]>([]);
  const [newBlueprint, setNewBlueprint] = useState("SCR");
  const [newStageName, setNewStageName] = useState("");
  const [newDurationDays, setNewDurationDays] = useState(7);
  const [activeTab, setActiveTab] = useState<OwnershipTab>("my");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const groupedRules = useMemo(() => groupRules(rules), [rules]);

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage]);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [ruleRows, mineRows, allRows, recruiterRows] = await Promise.all([
        ownershipApi.listSlaRules(false),
        ownershipApi.listMyOwnerships(),
        canManage ? ownershipApi.listActiveOwnerships() : Promise.resolve([]),
        canManage ? ownershipApi.listRecruiters() : Promise.resolve([]),
      ]);
      const rejectedRows = canManage ? await jdApi.listCandidateRejections() : [];
      setRules(sortRules(ruleRows));
      setMyOwnerships(mineRows);
      setAllOwnerships(allRows);
      setRejectedCandidates(rejectedRows);
      setRecruiters(recruiterRows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load ownership data");
    } finally {
      setLoading(false);
    }
  }

  async function updateRule(rule: SLARule, patch: Partial<Pick<SLARule, "blueprint" | "stage_name" | "duration_days" | "active">>) {
    setSavingId(rule.id);
    setError(null);
    try {
      const updated = await ownershipApi.updateSlaRule(rule.id, patch);
      setRules((prev) => sortRules(prev.map((item) => item.id === updated.id ? updated : item)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update SLA stage");
    } finally {
      setSavingId(null);
    }
  }

  async function createRule() {
    if (!newStageName.trim()) return;
    setSavingId("new");
    setError(null);
    try {
      const created = await ownershipApi.createSlaRule({
        blueprint: newBlueprint,
        stage_name: newStageName.trim(),
        duration_days: newDurationDays,
        active: true,
      });
      setRules((prev) => sortRules([...prev, created]));
      setNewStageName("");
      setNewDurationDays(7);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create SLA stage");
    } finally {
      setSavingId(null);
    }
  }

  async function changeStage(ownership: CandidateOwnership, stageId: number) {
    setSavingId(ownership.zoho_candidate_id);
    setError(null);
    try {
      const updated = await ownershipApi.changeStage(ownership.zoho_candidate_id, stageId);
      replaceOwnership(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to change SLA stage");
    } finally {
      setSavingId(null);
    }
  }

  async function release(ownership: CandidateOwnership) {
    setSavingId(ownership.zoho_candidate_id);
    setError(null);
    try {
      await ownershipApi.release(ownership.zoho_candidate_id);
      removeOwnership(ownership.zoho_candidate_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to release ownership");
    } finally {
      setSavingId(null);
    }
  }

  async function reassign(candidateId: string, recruiterId: number) {
    setSavingId(candidateId);
    setError(null);
    try {
      const updated = await ownershipApi.reassign(candidateId, recruiterId);
      replaceOwnership(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reassign ownership");
    } finally {
      setSavingId(null);
    }
  }

  async function restoreRejectedCandidate(rejection: CandidateRejection) {
    setSavingId(`rejection-${rejection.id}`);
    setError(null);
    try {
      await jdApi.restoreCandidateRejection(rejection.id);
      setRejectedCandidates((prev) => prev.filter((row) => row.id !== rejection.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to restore rejected candidate");
    } finally {
      setSavingId(null);
    }
  }

  function replaceOwnership(updated: CandidateOwnership) {
    setMyOwnerships((prev) => prev.map((item) => item.zoho_candidate_id === updated.zoho_candidate_id ? updated : item));
    setAllOwnerships((prev) => prev.map((item) => item.zoho_candidate_id === updated.zoho_candidate_id ? updated : item));
  }

  function removeOwnership(candidateId: string) {
    setMyOwnerships((prev) => prev.filter((item) => item.zoho_candidate_id !== candidateId));
    setAllOwnerships((prev) => prev.filter((item) => item.zoho_candidate_id !== candidateId));
  }

  const visibleOwnerships = activeTab === "all" ? allOwnerships : myOwnerships;

  return (
    <section className="page-section">
      <div className="page-heading ownership-page-heading">
        <div>
          <p className="eyebrow">Ownership</p>
          <h1>{canManage ? "Candidate Ownership & SLA" : "My Accepted Candidates"}</h1>
          <p className="muted">
            {canManage
              ? "Maintain candidate locks, recruiter assignment, and the full Zoho SLA lifecycle."
              : "Maintain candidates you have accepted from sourcing, update SLA stages, or release ownership."}
          </p>
        </div>
        <button className="secondary-button compact-button" onClick={loadAll}>Refresh</button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <div className="empty-state">Loading ownership workspace...</div>}

      {!loading && (
        <>
          <div className="segmented ownership-tabs">
            <button className={activeTab === "my" ? "active" : ""} onClick={() => setActiveTab("my")}>
              My Candidates
            </button>
            {canManage && (
              <button className={activeTab === "all" ? "active" : ""} onClick={() => setActiveTab("all")}>
                All Ownership
              </button>
            )}
            {canManage && (
              <button className={activeTab === "rejected" ? "active" : ""} onClick={() => setActiveTab("rejected")}>
                Rejected Candidates
              </button>
            )}
            {canManage && (
              <button className={activeTab === "sla" ? "active" : ""} onClick={() => setActiveTab("sla")}>
                SLA Stages
              </button>
            )}
          </div>

          {(activeTab === "my" || activeTab === "all") && (
            <OwnershipTable
              ownerships={visibleOwnerships}
              rules={rules.filter((rule) => rule.active)}
              groupedRules={groupedRules}
              recruiters={recruiters}
              canReassign={canManage && activeTab === "all"}
              savingId={savingId}
              onStageChange={changeStage}
              onRelease={release}
              onReassign={reassign}
            />
          )}

          {activeTab === "rejected" && canManage && (
            <RejectedCandidatesTable
              rejections={rejectedCandidates}
              savingId={savingId}
              onRestore={restoreRejectedCandidate}
            />
          )}

          {activeTab === "sla" && canManage && (
            <div className="panel ownership-admin-panel">
              <div className="ownership-section-heading">
                <div>
                  <p className="eyebrow">SLA Management</p>
                  <h2>Zoho Stage Table</h2>
                </div>
              </div>
              <div className="table-wrap sla-management-table">
                <table>
                  <thead>
                    <tr>
                      <th>Blueprint</th>
                      <th>Stage</th>
                      <th>Period (days)</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((rule) => (
                      <tr key={rule.id}>
                        <td>
                          <input
                            value={rule.blueprint}
                            disabled={savingId === rule.id}
                            onChange={(e) => setRules((prev) => prev.map((item) => item.id === rule.id ? { ...item, blueprint: e.target.value.toUpperCase() } : item))}
                          />
                        </td>
                        <td>
                          <input
                            value={rule.stage_name}
                            disabled={savingId === rule.id}
                            onChange={(e) => setRules((prev) => prev.map((item) => item.id === rule.id ? { ...item, stage_name: e.target.value } : item))}
                          />
                        </td>
                        <td>
                          <div className="period-input">
                            <input
                              type="number"
                              min={0}
                              value={rule.duration_days}
                              disabled={savingId === rule.id}
                              onChange={(e) => setRules((prev) => prev.map((item) => item.id === rule.id ? { ...item, duration_days: Number(e.target.value) } : item))}
                            />
                            <span>days</span>
                          </div>
                        </td>
                        <td><span className="badge">{rule.active ? "Active" : "Inactive"}</span></td>
                        <td className="ownership-table-actions">
                          <button
                            className="primary-button compact-button"
                            disabled={savingId === rule.id}
                            onClick={() => updateRule(rule, {
                              blueprint: rule.blueprint,
                              stage_name: rule.stage_name,
                              duration_days: rule.duration_days,
                              active: rule.active,
                            })}
                          >
                            Save
                          </button>
                          <button className="secondary-button compact-button" disabled={savingId === rule.id} onClick={() => updateRule(rule, { active: !rule.active })}>
                            {rule.active ? "Deactivate" : "Activate"}
                          </button>
                        </td>
                      </tr>
                    ))}
                    <tr>
                      <td><input value={newBlueprint} onChange={(e) => setNewBlueprint(e.target.value.toUpperCase())} /></td>
                      <td><input placeholder="New stage" value={newStageName} onChange={(e) => setNewStageName(e.target.value)} /></td>
                      <td>
                        <div className="period-input">
                          <input type="number" min={0} value={newDurationDays} onChange={(e) => setNewDurationDays(Number(e.target.value))} />
                          <span>days</span>
                        </div>
                      </td>
                      <td><span className="badge">Active</span></td>
                      <td>
                        <button className="primary-button compact-button" disabled={savingId === "new" || !newStageName.trim()} onClick={createRule}>
                          Add Stage
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function RejectedCandidatesTable({
  rejections,
  savingId,
  onRestore,
}: {
  rejections: CandidateRejection[];
  savingId: number | string | null;
  onRestore: (rejection: CandidateRejection) => void;
}) {
  const groupedByJob = useMemo(() => {
    return rejections.reduce<Record<string, CandidateRejection[]>>((groups, rejection) => {
      const key = `${rejection.jd_id}:${rejection.jd_title}`;
      groups[key] = [...(groups[key] ?? []), rejection];
      return groups;
    }, {});
  }, [rejections]);

  return (
    <div className="panel ownership-admin-panel">
      <div className="ownership-section-heading">
        <div>
          <p className="eyebrow">Rejected Candidates</p>
          <h2>{rejections.length} Hidden Candidate Records</h2>
        </div>
      </div>
      <div className="table-wrap rejected-candidates-table">
        <table>
          <thead>
            <tr>
              <th>Candidate / Job</th>
              <th>Recruiter</th>
              <th>Reason</th>
              <th>Rejected</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(groupedByJob).flatMap(([jobKey, rows]) => {
              const jobTitle = jobKey.slice(jobKey.indexOf(":") + 1);
              return [
                <tr key={jobKey} className="rejected-job-row">
                  <td colSpan={5}>{jobTitle}</td>
                </tr>,
                ...rows.map((rejection) => (
                  <tr key={rejection.id}>
                    <td>
                      <strong>{rejection.candidate_name}</strong>
                      <span className="line-clamp">{rejection.zoho_candidate_id}</span>
                      <span className="line-clamp">Zoho Job: {rejection.job_opening_id || "-"}</span>
                    </td>
                    <td>{rejection.recruiter_name}</td>
                    <td><span className="rejection-reason">{rejection.reason}</span></td>
                    <td>{formatDateTime(rejection.rejected_at)}</td>
                    <td>
                      <button
                        className="secondary-button compact-button"
                        disabled={savingId === `rejection-${rejection.id}`}
                        onClick={() => onRestore(rejection)}
                      >
                        Restore
                      </button>
                    </td>
                  </tr>
                )),
              ];
            })}
          </tbody>
        </table>
        {rejections.length === 0 && <div className="empty-state">No rejected candidate records yet.</div>}
      </div>
    </div>
  );
}

function OwnershipTable({
  ownerships,
  rules,
  groupedRules,
  recruiters,
  canReassign,
  savingId,
  onStageChange,
  onRelease,
  onReassign,
}: {
  ownerships: CandidateOwnership[];
  rules: SLARule[];
  groupedRules: Record<string, SLARule[]>;
  recruiters: RecruiterOption[];
  canReassign: boolean;
  savingId: number | string | null;
  onStageChange: (ownership: CandidateOwnership, stageId: number) => void;
  onRelease: (ownership: CandidateOwnership) => void;
  onReassign: (candidateId: string, recruiterId: number) => void;
}) {
  return (
    <div className="panel ownership-admin-panel">
      <div className="ownership-section-heading">
        <div>
          <p className="eyebrow">Accepted Candidates</p>
          <h2>{ownerships.length} Active</h2>
        </div>
      </div>
      <div className="table-wrap ownership-workbench-table">
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>SLA / Expiry</th>
              <th>Maintain</th>
              {canReassign && <th>Reassign</th>}
            </tr>
          </thead>
          <tbody>
            {ownerships.map((ownership) => (
              <tr key={ownership.id}>
                <td>
                  <strong>{ownership.candidate_name}</strong>
                  <span className="line-clamp">{ownership.zoho_candidate_id}</span>
                  {canReassign && <span className="line-clamp">Owner: {ownership.owner_recruiter_name}</span>}
                </td>
                <td>
                  <span className="badge">{ownership.sla_stage_name}</span>
                  <span className="line-clamp">Remaining: {formatRemainingTime(ownership.remaining_seconds)}</span>
                  <span className="line-clamp">{formatDateTime(ownership.expires_at)}</span>
                </td>
                <td>
                  <div className="ownership-maintain-controls">
                    <select
                      value={ownership.sla_stage_id}
                      disabled={savingId === ownership.zoho_candidate_id}
                      onChange={(e) => onStageChange(ownership, Number(e.target.value))}
                    >
                      {Object.entries(groupedRules).map(([blueprint, stageRules]) => (
                        <optgroup key={blueprint} label={blueprint}>
                          {stageRules.filter((rule) => rule.active).map((rule) => (
                            <option key={rule.id} value={rule.id}>
                              {rule.stage_name} ({formatPeriod(rule.duration_days)})
                            </option>
                          ))}
                        </optgroup>
                      ))}
                      {rules.length === 0 && <option value={ownership.sla_stage_id}>No active SLA stages</option>}
                    </select>
                    <button className="ghost-button compact-button" disabled={savingId === ownership.zoho_candidate_id} onClick={() => onRelease(ownership)}>
                      Release
                    </button>
                  </div>
                </td>
                {canReassign && (
                  <td>
                    <select
                      value=""
                      disabled={savingId === ownership.zoho_candidate_id}
                      onChange={(e) => {
                        if (e.target.value) onReassign(ownership.zoho_candidate_id, Number(e.target.value));
                      }}
                    >
                      <option value="">Select recruiter</option>
                      {recruiters.filter((recruiter) => recruiter.id !== ownership.owner_recruiter_id).map((recruiter) => (
                        <option key={recruiter.id} value={recruiter.id}>{recruiter.name}</option>
                      ))}
                    </select>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {ownerships.length === 0 && <div className="empty-state">No active accepted candidates in this view.</div>}
      </div>
    </div>
  );
}

function groupRules(rules: SLARule[]) {
  return sortRules(rules).reduce<Record<string, SLARule[]>>((groups, rule) => {
    const blueprint = rule.blueprint || "Other";
    groups[blueprint] = [...(groups[blueprint] ?? []), rule];
    return groups;
  }, {});
}

function sortRules(rules: SLARule[]) {
  return [...rules].sort((a, b) => {
    const blueprintDelta = blueprintRank(a.blueprint) - blueprintRank(b.blueprint);
    if (blueprintDelta !== 0) return blueprintDelta;
    return a.id - b.id;
  });
}

function blueprintRank(blueprint: string) {
  const index = BLUEPRINT_ORDER.indexOf(blueprint);
  return index === -1 ? BLUEPRINT_ORDER.length : index;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatRemainingTime(totalSeconds: number) {
  if (totalSeconds <= 0) return "Expired";
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  return `${Math.max(1, hours)}h`;
}

function formatPeriod(days: number) {
  if (days === 90) return "3 months";
  if (days === 7) return "1 week";
  if (days === 1) return "1 day";
  return `${days} days`;
}
