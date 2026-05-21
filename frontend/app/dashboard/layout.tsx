"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import Header from "@/components/dashboard/Header";
import Footer from "@/components/dashboard/Footer";
import { useAuth } from "@/hooks/useAuth";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) router.push("/login");
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return (
    <div className="dashboard-shell-new">
      <Header />
      <main className="dashboard-main-new">{children}</main>
      <Footer />
    </div>
  );
}
