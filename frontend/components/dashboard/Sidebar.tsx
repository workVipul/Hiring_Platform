"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";

export default function Sidebar() {
  const pathname = usePathname();
  const { userName, accessType, signOut } = useAuth();
  const nav = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/dashboard/jd-generator", label: "JD Generator" },
    { href: "/dashboard/sourcing", label: "Sourcing" },
    { href: "/dashboard/ownership", label: accessType === "admin" || accessType === "manager" ? "Ownership" : "My Candidates" },
  ];

  return (
    <aside className="sidebar">
      <Link href="/dashboard" className="brand">
        <span className="brand-mark">N</span>
        <span>NinjaForge</span>
      </Link>

      <nav className="nav-list">
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={pathname === item.href ? "nav-link active" : "nav-link"}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer">
        <p className="muted small">{userName}</p>
        <p><span className="badge">{accessType ?? "normal"}</span></p>
        <button className="ghost-button" onClick={signOut}>Sign out</button>
      </div>
    </aside>
  );
}
