"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import ConfirmDialog from "@/components/dashboard/ConfirmDialog";
import Footer from "@/components/dashboard/Footer";
import Header from "@/components/dashboard/Header";
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
      <ConfirmDialog
        open={isModalOpen}
        title="Unsaved draft changes"
        message="You have an unsaved JD draft. If you leave this page, your draft will be permanently lost."
        confirmLabel="Discard and leave"
        tone="danger"
        onCancel={handleCancel}
        onConfirm={handleConfirm}
      />
    </div>
  );
}
