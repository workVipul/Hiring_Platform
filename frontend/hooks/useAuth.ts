"use client";

import { useRouter } from "next/navigation";

import { useAuthStore } from "@/store/authStore";

export function useAuth() {
  const { token, userName, accessType, hydrated, logout } = useAuthStore();
  const router = useRouter();

  function signOut() {
    logout();
    router.push("/login");
  }

  return { token, userName, accessType, hydrated, isAuthenticated: Boolean(token), signOut };
}
