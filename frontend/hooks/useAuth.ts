"use client";

import { useRouter } from "next/navigation";

import { useAuthStore } from "@/store/authStore";

export function useAuth() {
  const { token, userName, accessType, logout } = useAuthStore();
  const router = useRouter();

  function signOut() {
    logout();
    router.push("/login");
  }

  return { token, userName, accessType, isAuthenticated: Boolean(token), signOut };
}
