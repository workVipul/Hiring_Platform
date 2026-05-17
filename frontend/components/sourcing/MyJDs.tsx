"use client";

import { useMemo } from "react";

import { useJDs } from "@/hooks/useJDs";
import { useAuthStore } from "@/store/authStore";

export default function MyJDs() {
  const userId = useAuthStore((state) => state.userId);
  const { jds, loading, error } = useJDs();
  const rows = useMemo(() => jds.filter((jd) => jd.created_by === userId), [jds, userId]);

  if (loading) return <div className="empty-state">Loading your job descriptions...</div>;
  if (error) return <div className="error-box">Failed to load job descriptions: {error}</div>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>JD Name</th><th>Visibility</th><th>Score</th><th>Skills</th></tr>
        </thead>
        <tbody>
          {rows.map((jd) => (
            <tr key={jd.id}>
              <td><strong>{jd.title}</strong></td>
              <td><span className="badge">{jd.ownership}</span></td>
              <td>{jd.jd_score ?? "-"}</td>
              <td>{jd.skills?.join(", ") || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <div className="empty-state">No personal job descriptions found.</div>}
    </div>
  );
}
