"use client";

import { useEffect, useState, useMemo } from "react";
import { jdApi } from "@/services/jdApi";
import type { JD } from "@/types/jd";

/* ─── helpers ─────────────────────────────────────────────────── */
function resolveFile(url: string) {
  if (url.startsWith("http")) return url;
  return `http://localhost:8000/${url}`;
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

function initials(name: string) {
  return name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

/* ─── small atoms ──────────────────────────────────────────────── */
function Badge({ label }: { label: string }) {
  const colors: Record<string, string> = {
    Engineering: "#6c63ff", Product: "#f59e0b",
    Design: "#22c55e", Marketing: "#ec4899", Default: "#7a7a8e",
  };
  const key = Object.keys(colors).find(k => label.toLowerCase().includes(k.toLowerCase())) ?? "Default";
  const c = colors[key];
  return (
    <span style={{
      background: c + "18", color: c, border: `1px solid ${c}30`,
      fontSize: 11, fontFamily: "'DM Mono', monospace",
      padding: "2px 8px", borderRadius: 4, letterSpacing: "0.04em",
    }}>
      {label.split(" ").slice(-1)[0]}
    </span>
  );
}

/* ─── main page ────────────────────────────────────────────────── */
export default function Home() {
  const [jds, setJds] = useState<JD[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    jdApi.list()
      .then(d => { setJds(d.items); setTotal(d.total); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() =>
    jds.filter(j => j.name.toLowerCase().includes(search.toLowerCase())),
    [jds, search]
  );

  async function handleDelete(id: number) {
    if (!confirm("Remove this JD?")) return;
    setDeletingId(id);
    await jdApi.delete(id);
    setJds(p => p.filter(j => j.id !== id));
    setTotal(p => p - 1);
    setDeletingId(null);
  }

  return (
    <div style={{ minHeight: "100vh", padding: "0 0 80px" }}>

      {/* ── topbar ── */}
      <header style={{
        borderBottom: "1px solid var(--border)",
        padding: "0 40px",
        height: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        backdropFilter: "blur(12px)",
        background: "rgba(10,10,15,0.85)",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 28, height: 28,
            background: "var(--accent)",
            borderRadius: 6,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 800,
          }}>J</div>
          <span style={{ fontWeight: 700, fontSize: 16, letterSpacing: "-0.02em" }}>JDForge</span>
          <span style={{
            fontSize: 11, color: "var(--text-muted)", fontFamily: "'DM Mono', monospace",
            background: "var(--border)", borderRadius: 4, padding: "2px 6px", marginLeft: 4,
          }}>BETA</span>
        </div>

        <button
          onClick={() => alert("JD Generation coming soon!")}
          style={{
            background: "var(--accent)",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            padding: "8px 18px",
            fontFamily: "'Syne', sans-serif",
            fontWeight: 600,
            fontSize: 13,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 7,
            letterSpacing: "-0.01em",
            boxShadow: "0 0 20px var(--accent-glow)",
            transition: "opacity 0.15s",
          }}
          onMouseEnter={e => (e.currentTarget.style.opacity = "0.85")}
          onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
        >
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
          Generate JD
        </button>
      </header>

      {/* ── main content ── */}
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "40px 24px 0" }}>

        {/* page heading */}
        <div style={{ marginBottom: 32 }}>
          <h1 style={{
            fontSize: 28, fontWeight: 800, letterSpacing: "-0.04em",
            background: "linear-gradient(135deg, var(--text-primary) 40%, var(--text-secondary))",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            marginBottom: 6,
          }}>
            Job Descriptions
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>
            Manage and track all generated JDs across your hiring pipeline.
          </p>
        </div>

        {/* ── stats row ── */}
        <div style={{ display: "flex", gap: 12, marginBottom: 28, flexWrap: "wrap" }}>
          {[
            { label: "Total JDs", value: total, accent: "var(--accent)" },
            { label: "This Month", value: jds.filter(j => new Date(j.created_at).getMonth() === new Date().getMonth()).length, accent: "var(--green)" },
            { label: "Search results", value: search ? filtered.length : "—", accent: "var(--amber)" },
          ].map(stat => (
            <div key={stat.label} style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: var_radius_lg,
              padding: "14px 20px",
              minWidth: 140,
              flex: "0 0 auto",
            }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: stat.accent, letterSpacing: "-0.03em" }}>
                {stat.value}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2, fontFamily: "'DM Mono', monospace" }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* ── search bar ── */}
        <div style={{ position: "relative", marginBottom: 20 }}>
          <svg
            style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }}
            width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search job descriptions…"
            style={{
              width: "100%",
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: "12px 16px 12px 42px",
              color: "var(--text-primary)",
              fontFamily: "'Syne', sans-serif",
              fontSize: 14,
              outline: "none",
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onFocus={e => {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.boxShadow = "0 0 0 3px var(--accent-dim)";
            }}
            onBlur={e => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "none";
            }}
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              style={{
                position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                background: "var(--border)", border: "none", color: "var(--text-secondary)",
                borderRadius: 4, width: 20, height: 20, cursor: "pointer",
                fontSize: 12, display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >✕</button>
          )}
        </div>

        {/* ── table section ── */}
        <div style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: var_radius_lg,
          overflow: "hidden",
        }}>
          {/* table header row */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "48px 1fr 200px 120px 80px",
            padding: "12px 20px",
            borderBottom: "1px solid var(--border)",
            background: "rgba(255,255,255,0.02)",
          }}>
            {["#", "Job Description", "File", "Created", ""].map(h => (
              <span key={h} style={{
                fontSize: 11, color: "var(--text-muted)",
                fontFamily: "'DM Mono', monospace",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
              }}>{h}</span>
            ))}
          </div>

          {/* states */}
          {loading && (
            <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--text-muted)" }}>
              <LoadingDots />
            </div>
          )}

          {error && (
            <div style={{
              padding: "32px 20px", textAlign: "center",
              color: "var(--red)", fontFamily: "'DM Mono', monospace", fontSize: 13,
            }}>
              ⚠ {error} — is the backend running at localhost:8000?
            </div>
          )}

          {!loading && !error && filtered.length === 0 && (
            <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
              {search ? `No JDs matching "${search}"` : "No JDs yet — click Generate JD to create one."}
            </div>
          )}

          {/* rows */}
          {!loading && !error && filtered.map((jd, i) => (
            <JDRow
              key={jd.id}
              jd={jd}
              index={i}
              isDeleting={deletingId === jd.id}
              onDelete={() => handleDelete(jd.id)}
            />
          ))}

          {/* footer count */}
          {!loading && !error && filtered.length > 0 && (
            <div style={{
              padding: "12px 20px",
              borderTop: "1px solid var(--border)",
              fontSize: 12,
              color: "var(--text-muted)",
              fontFamily: "'DM Mono', monospace",
              display: "flex",
              justifyContent: "space-between",
            }}>
              <span>
                {search
                  ? `${filtered.length} of ${total} results`
                  : `${total} job description${total !== 1 ? "s" : ""}`}
              </span>
              <span style={{ color: "var(--green)", display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 6, height: 6, background: "var(--green)", borderRadius: "50%", display: "inline-block" }} />
                Connected · localhost:8000
              </span>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

/* ─── table row ───────────────────────────────────────────────── */
function JDRow({ jd, index, isDeleting, onDelete }: {
  jd: JD; index: number; isDeleting: boolean; onDelete: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "grid",
        gridTemplateColumns: "48px 1fr 200px 120px 80px",
        padding: "14px 20px",
        borderBottom: "1px solid var(--border)",
        background: hovered ? "var(--bg-hover)" : "transparent",
        transition: "background 0.12s",
        alignItems: "center",
        opacity: isDeleting ? 0.4 : 1,
      }}
    >
      {/* id */}
      <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "var(--text-muted)" }}>
        {String(jd.id).padStart(3, "0")}
      </span>

      {/* name + badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8, flexShrink: 0,
          background: `linear-gradient(135deg, ${avatarColor(jd.name)})`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, fontWeight: 700, color: "#fff",
        }}>
          {initials(jd.name)}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {jd.name}
          </div>
        </div>
        <Badge label={jd.name} />
      </div>

      {/* source button — opens PDF */}
      <div>
        <a
          href={resolveFile(jd.file_url)}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            background: "var(--bg)", border: "1px solid var(--border-bright)",
            color: "var(--text-secondary)",
            borderRadius: 6, padding: "5px 10px",
            fontSize: 12, fontFamily: "'DM Mono', monospace",
            textDecoration: "none",
            transition: "border-color 0.12s, color 0.12s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = "var(--accent)";
            e.currentTarget.style.color = "var(--accent)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = "var(--border-bright)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }}
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          Source
        </a>
      </div>

      {/* created date */}
      <span style={{ fontSize: 12, color: "var(--text-secondary)", fontFamily: "'DM Mono', monospace" }}>
        {fmt(jd.created_at)}
      </span>

      {/* delete */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={onDelete}
          disabled={isDeleting}
          style={{
            background: "transparent", border: "none",
            color: "var(--text-muted)", cursor: "pointer",
            padding: "4px 6px", borderRadius: 4,
            fontSize: 13, transition: "color 0.12s",
          }}
          onMouseEnter={e => (e.currentTarget.style.color = "var(--red)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--text-muted)")}
          title="Delete"
        >
          {isDeleting ? "…" : "✕"}
        </button>
      </div>
    </div>
  );
}

/* ─── loading dots ─────────────────────────────────────────────── */
function LoadingDots() {
  return (
    <div style={{ display: "flex", gap: 6, justifyContent: "center", alignItems: "center", height: 48 }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 7, height: 7,
          background: "var(--accent)",
          borderRadius: "50%",
          animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
      <style>{`@keyframes pulse { 0%,100%{opacity:.2;transform:scale(.8)} 50%{opacity:1;transform:scale(1)} }`}</style>
    </div>
  );
}

/* ─── utils ────────────────────────────────────────────────────── */
const var_radius_lg = "var(--radius-lg)";

function avatarColor(name: string): string {
  const palettes = [
    "#6c63ff, #9d97ff",
    "#f59e0b, #fbbf24",
    "#22c55e, #4ade80",
    "#ec4899, #f472b6",
    "#3b82f6, #60a5fa",
    "#8b5cf6, #a78bfa",
  ];
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % palettes.length;
  return palettes[h];
}