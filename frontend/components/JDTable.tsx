"use client";

import { useEffect, useState } from "react";
import { jdApi } from "@/services/jdApi";
import type { JD } from "@/types/jd";

// The backend serves local PDFs at /uploads/<filename>.
// In production with S3, file_url will already be a full https:// URL — just use it directly.
function resolveFileUrl(fileUrl: string): string {
  if (fileUrl.startsWith("http")) return fileUrl;                    // already absolute (S3)
  const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  return `${base}/${fileUrl}`;                                       // local: prepend backend origin
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function JDTable() {
  const [jds, setJds] = useState<JD[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    jdApi
      .list()
      .then((data) => {
        setJds(data.items);
        setTotal(data.total);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(id: number) {
    if (!confirm("Delete this JD record?")) return;
    await jdApi.delete(id);
    setJds((prev) => prev.filter((jd) => jd.id !== id));
    setTotal((prev) => prev - 1);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-500">
        Loading JDs…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 border border-red-200 p-4 text-red-700">
        Failed to load JDs: {error}
      </div>
    );
  }

  if (jds.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-gray-300 p-10 text-center text-gray-400">
        No JDs found. Run <code className="font-mono text-sm">python seed.py</code> to add sample data.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 text-sm text-gray-500">{total} record{total !== 1 ? "s" : ""}</div>
      <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
        <table className="min-w-full divide-y divide-gray-100 text-sm">
          <thead className="bg-gray-50">
            <tr>
              {["ID", "Name", "File", "Created", "Actions"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left font-medium text-gray-600 uppercase tracking-wider text-xs"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {jds.map((jd) => (
              <tr key={jd.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 text-gray-400 font-mono">{jd.id}</td>
                <td className="px-4 py-3 font-medium text-gray-800">{jd.name}</td>
                <td className="px-4 py-3">
                  <a
                    href={resolveFileUrl(jd.file_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline font-mono text-xs"
                  >
                    {jd.file_url}
                  </a>
                </td>
                <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                  {formatDate(jd.created_at)}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDelete(jd.id)}
                    className="text-red-500 hover:text-red-700 text-xs font-medium"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
