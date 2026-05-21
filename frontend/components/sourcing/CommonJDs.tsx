"use client";

import { useMemo } from "react";

import { useJDs } from "@/hooks/useJDs";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function resolveFileUrl(fileUrl: string | null): string | null {
  if (!fileUrl) return null;
  if (fileUrl.startsWith("http")) return fileUrl;
  const cleanPath = fileUrl.startsWith("/") ? fileUrl.substring(1) : fileUrl;
  return `${BACKEND_URL}/${cleanPath}`;
}

export default function CommonJDs({ onSource }: { onSource: (id: number, title: string) => void }) {
  const { jds, loading, error } = useJDs();
  const rows = useMemo(() => jds.filter((jd) => jd.ownership === "public"), [jds]);

  if (loading) return <div className="empty-state">Loading shared job descriptions...</div>;
  if (error) return <div className="error-box">Failed to load shared job descriptions: {error}</div>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>Common JD</th><th>Score</th><th>Skills</th><th>PDF</th><th>Sourcing</th></tr>
        </thead>
        <tbody>
          {rows.map((jd) => {
            const fileUrl = resolveFileUrl(jd.pdf_url);
            return (
              <tr key={jd.id}>
                <td><strong>{jd.title}</strong></td>
                <td>{jd.jd_score ?? "-"}</td>
                <td>{jd.skills?.join(", ") || "-"}</td>
                <td>{fileUrl ? <a href={fileUrl} target="_blank" rel="noreferrer" className="pdf-button">Open</a> : "-"}</td>
                <td>
                  <button
                    className="primary-button"
                    style={{ padding: "6px 12px", fontSize: "0.8rem", width: "auto" }}
                    onClick={() => onSource(jd.id, jd.title)}
                  >
                    Source
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && <div className="empty-state">No shared job descriptions found.</div>}
    </div>
  );
}
