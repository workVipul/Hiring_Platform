"use client";

import { useMemo, useState } from "react";

import { useJDs } from "@/hooks/useJDs";
import { jdApi } from "@/services/jdApi";
import type { JD } from "@/types/jd";
import ConfirmDialog from "./ConfirmDialog";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function resolveFileUrl(fileUrl: string | null): string | null {
  if (!fileUrl) return null;
  if (fileUrl.startsWith("http")) return fileUrl;
  const cleanPath = fileUrl.startsWith("/") ? fileUrl.substring(1) : fileUrl;
  return `${BACKEND_URL}/${cleanPath}`;
}

export default function JDTable() {
  const [page, setPage] = useState(1);
  const perPage = 12;
  const { jds, total, loading, error, setJDs, setTotal } = useJDs(page, perPage);
  const [query, setQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<JD | null>(null);

  const filtered = useMemo(
    () => jds.filter((jd) => jd.title.toLowerCase().includes(query.toLowerCase())),
    [jds, query],
  );
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  async function handleDelete(id: number) {
    await jdApi.delete(id);
    setJDs((prev) => prev.filter((jd) => jd.id !== id));
    setTotal((prev) => prev - 1);
    setDeleteTarget(null);
  }

  if (loading) return <div className="empty-state">Loading JDs...</div>;
  if (error) return <div className="error-box">Failed to load JDs: {error}</div>;

  return (
    <>
      <div className="table-wrap">
        <div className="table-tools">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search job descriptions" />
          <span className="muted small">{filtered.length} of {total} records</span>
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">No JDs found.</div>
        ) : (
          <table className="jd-dashboard-table">
            <colgroup>
              <col className="jd-col-title" />
              <col className="jd-col-owner" />
              <col className="jd-col-skills" />
              <col className="jd-col-creator" />
              <col className="jd-col-pdf" />
              <col className="jd-col-created" />
              <col className="jd-col-actions" />
            </colgroup>
            <thead>
              <tr>
                <th>Title</th>
                <th>Ownership</th>
                <th>Skills</th>
                <th>Created By</th>
                <th>PDF</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((jd) => <JDRow key={jd.id} jd={jd} onDelete={() => setDeleteTarget(jd)} />)}
            </tbody>
          </table>
        )}
        <div className="table-pagination">
          <button className="secondary-button" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
            Previous
          </button>
          <span className="muted small">Page {page} of {totalPages}</span>
          <button className="secondary-button" disabled={page >= totalPages} onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}>
            Next
          </button>
        </div>
      </div>
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete job description?"
        message={deleteTarget ? `This will permanently remove "${deleteTarget.title}" from your workspace.` : ""}
        confirmLabel="Delete"
        tone="danger"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && handleDelete(deleteTarget.id)}
      />
    </>
  );
}

function getJDSummary(jd: JD): string {
  if (jd.context) return jd.context;
  if (!jd.content) return "";
  try {
    const parsed = JSON.parse(jd.content);
    if (parsed && typeof parsed === "object") {
      return parsed.summary || parsed.content || jd.content;
    }
  } catch {
    // Return raw content if it fails to parse
  }
  return jd.content;
}

function JDRow({ jd, onDelete }: { jd: JD; onDelete: () => void }) {
  const fileUrl = resolveFileUrl(jd.pdf_url);

  return (
    <tr>
      <td className="jd-title-cell">
        <strong>{jd.title}</strong>
        <span className="muted small line-clamp">{getJDSummary(jd)}</span>
      </td>
      <td><span className="badge">{jd.ownership}</span></td>
      <td className="truncate-cell" title={jd.skills?.join(", ") || "-"}>{jd.skills?.slice(0, 3).join(", ") || "-"}</td>
      <td className="truncate-cell" title={jd.created_by_name || "-"}>{jd.created_by_name || "-"}</td>
      <td>{fileUrl ? <a href={fileUrl} target="_blank" rel="noreferrer" className="pdf-button">Preview</a> : "-"}</td>
      <td>{formatDate(jd.created_at)}</td>
      <td><button className="danger-button" onClick={onDelete}>Delete</button></td>
    </tr>
  );
}
