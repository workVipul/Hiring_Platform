"use client";

import { useMemo, useState } from "react";

import { useJDs } from "@/hooks/useJDs";
import { jdApi } from "@/services/jdApi";
import type { JD } from "@/types/jd";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function resolveFileUrl(fileUrl: string | null): string | null {
  if (!fileUrl) return null;
  if (fileUrl.startsWith("http")) return fileUrl;
  return `/${fileUrl}`;
}

export default function JDTable() {
  const { jds, total, loading, error, setJDs, setTotal } = useJDs();
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () => jds.filter((jd) => jd.title.toLowerCase().includes(query.toLowerCase())),
    [jds, query],
  );

  async function handleDelete(id: number) {
    if (!confirm("Delete this JD?")) return;
    await jdApi.delete(id);
    setJDs((prev) => prev.filter((jd) => jd.id !== id));
    setTotal((prev) => prev - 1);
  }

  if (loading) return <div className="empty-state">Loading JDs...</div>;
  if (error) return <div className="error-box">Failed to load JDs: {error}</div>;

  return (
    <div className="table-wrap">
      <div className="table-tools">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search job descriptions" />
        <span className="muted small">{filtered.length} of {total} records</span>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">No JDs found.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Ownership</th>
              <th>Score</th>
              <th>Skills</th>
              <th>Created By</th>
              <th>PDF</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filtered.map((jd) => <JDRow key={jd.id} jd={jd} onDelete={() => handleDelete(jd.id)} />)}
          </tbody>
        </table>
      )}
    </div>
  );
}

function JDRow({ jd, onDelete }: { jd: JD; onDelete: () => void }) {
  const fileUrl = resolveFileUrl(jd.pdf_url);

  return (
    <tr>
      <td>
        <strong>{jd.title}</strong>
        <span className="muted small line-clamp">{jd.content}</span>
      </td>
      <td><span className="badge">{jd.ownership}</span></td>
      <td>{jd.jd_score ?? "-"}</td>
      <td>{jd.skills?.slice(0, 3).join(", ") || "-"}</td>
      <td>{jd.created_by ?? "-"}</td>
      <td>{fileUrl ? <a href={fileUrl} target="_blank" rel="noreferrer">Open</a> : "-"}</td>
      <td>{formatDate(jd.created_at)}</td>
      <td><button className="danger-button" onClick={onDelete}>Delete</button></td>
    </tr>
  );
}
