"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import Header from "@/components/dashboard/Header";
import Footer from "@/components/dashboard/Footer";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/store/authStore";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { hydrated, isAuthenticated } = useAuth();

  const {
    pendingNavigationUrl,
    setPendingNavigationUrl,
    pendingNavigationAction,
    setPendingNavigationAction,
  } = useAuthStore();

  useEffect(() => {
    if (hydrated && !isAuthenticated) router.push("/login");
  }, [hydrated, isAuthenticated, router]);

  if (!hydrated || !isAuthenticated) return null;

  const handleConfirm = () => {
    if (pendingNavigationUrl) {
      router.push(pendingNavigationUrl);
    } else if (pendingNavigationAction) {
      pendingNavigationAction();
    }
    setPendingNavigationUrl(null);
    setPendingNavigationAction(null);
  };

  const handleCancel = () => {
    setPendingNavigationUrl(null);
    setPendingNavigationAction(null);
  };

  const isModalOpen = Boolean(pendingNavigationUrl || pendingNavigationAction);

  return (
    <div className="dashboard-shell-new">
      <Header />
      <main className="dashboard-main-new">{children}</main>
      <Footer />

      {isModalOpen && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(10, 15, 30, 0.7)",
          backdropFilter: "blur(8px)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          zIndex: 9999,
        }}>
          <div style={{
            background: "var(--background, #ffffff)",
            border: "1px solid var(--border, rgba(255, 255, 255, 0.1))",
            borderRadius: "16px",
            boxShadow: "0 20px 40px rgba(0, 0, 0, 0.3)",
            width: "90%",
            maxWidth: "420px",
            padding: "24px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            gap: "20px"
          }}>
            <div style={{
              width: "48px",
              height: "48px",
              borderRadius: "50%",
              background: "rgba(239, 68, 68, 0.1)",
              color: "#ef4444",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              margin: "0 auto 8px",
              fontSize: "1.5rem",
              fontWeight: "bold"
            }}>
              ⚠️
            </div>
            <div>
              <h3 style={{ margin: "0 0 8px 0", fontSize: "1.25rem", color: "var(--foreground)" }}>Unsaved Draft Changes</h3>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.95rem", lineHeight: "1.5" }}>
                You have an unsaved JD draft. If you leave this page, your draft will be permanently lost. Are you sure you want to proceed?
              </p>
            </div>
            <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
              <button 
                onClick={handleCancel}
                style={{
                  flex: 1,
                  padding: "10px 16px",
                  borderRadius: "8px",
                  border: "1px solid var(--border)",
                  background: "transparent",
                  color: "var(--foreground)",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "0.9rem"
                }}
              >
                Cancel
              </button>
              <button 
                onClick={handleConfirm}
                style={{
                  flex: 1,
                  padding: "10px 16px",
                  borderRadius: "8px",
                  border: "none",
                  background: "#ef4444",
                  color: "#ffffff",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "0.9rem"
                }}
              >
                Discard & Leave
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

