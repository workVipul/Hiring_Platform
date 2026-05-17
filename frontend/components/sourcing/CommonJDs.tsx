"use client";

import { useMemo } from "react";

import { useJDs } from "@/hooks/useJDs";

export default function CommonJDs() {
  const { jds, loading, error } = useJDs();
  const rows = useMemo(() => jds.filter((jd) => jd.ownership === "public"), [jds]);

  if (loading) return <div className="empty-state">Loading shared job descriptions...</div>;
  if (error) return <div className="error-box">Failed to load shared job descriptions: {error}</div>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>Common JD</th><th>Score</th><th>Skills</th><th>PDF</th></tr>
        </thead>
        <tbody>
          {rows.map((jd) => (
            <tr key={jd.id}>
              <td><strong>{jd.title}</strong></td>
              <td>{jd.jd_score ?? "-"}</td>
              <td>{jd.skills?.join(", ") || "-"}</td>
              <td>{jd.pdf_url ? "Available" : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <div className="empty-state">No shared job descriptions found.</div>}
    </div>
  );
}
