"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/store/authStore";

export default function Header() {
  const pathname = usePathname();
  const { userName, accessType, signOut } = useAuth();
  const hasUnsavedJD = useAuthStore((state) => state.hasUnsavedJD);
  const setPendingNavigationUrl = useAuthStore((state) => state.setPendingNavigationUrl);
  const setPendingNavigationAction = useAuthStore((state) => state.setPendingNavigationAction);

  const navItems = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/dashboard/jd-generator", label: "JD Generator" },
    { href: "/dashboard/sourcing", label: "Sourcing" },
  ];

  const handleNavigationConfirm = (e: React.MouseEvent, targetHref: string) => {
    if (hasUnsavedJD && pathname !== targetHref) {
      e.preventDefault();
      setPendingNavigationUrl(targetHref);
    }
  };

  const handleSignOutClick = (e: React.MouseEvent) => {
    if (hasUnsavedJD) {
      e.preventDefault();
      setPendingNavigationAction(() => signOut());
    } else {
      signOut();
    }
  };


  return (
    <header className="site-header">
      <div className="site-header-container">
        <Link 
          href="/dashboard" 
          className="site-header-logo-section"
          onClick={(e) => handleNavigationConfirm(e, "/dashboard")}
        >
          <img
            src="/wissen_logo.png"
            alt="Wissen Technology"
            className="site-header-logo"
          />
          <div style={{ display: "flex", alignItems: "center", gap: "8px", borderLeft: "1px solid var(--border)", paddingLeft: "12px", marginLeft: "4px" }}>
            <span style={{ fontSize: "1.15rem", fontWeight: 800, color: "var(--color-navy-dark)", letterSpacing: "-0.02em" }}>NinjaForge</span>
          </div>
        </Link>

        <nav className="site-header-nav">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`site-header-link ${isActive ? "active" : ""}`}
                onClick={(e) => handleNavigationConfirm(e, item.href)}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="site-header-profile">
          <div className="site-header-user-info">
            <p className="site-header-user-name">{userName || "Recruiter"}</p>
            <p className="site-header-user-role">{accessType || "Standard"}</p>
          </div>
          <button 
            className="secondary-button" 
            style={{ padding: "6px 12px", fontSize: "0.85rem", width: "auto" }} 
            onClick={handleSignOutClick}
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

