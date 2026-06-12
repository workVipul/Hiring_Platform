"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: number | null;
  userName: string | null;
  accessType: "admin" | "manager" | "normal" | null;
  hydrated: boolean;
  hasUnsavedJD: boolean;
  pendingNavigationUrl: string | null;
  pendingNavigationAction: (() => void) | null;
  setHydrated: (hydrated: boolean) => void;
  setAuth: (token: string, userId: number, userName: string, accessType: "admin" | "manager" | "normal") => void;
  setHasUnsavedJD: (val: boolean) => void;
  setPendingNavigationUrl: (url: string | null) => void;
  setPendingNavigationAction: (action: (() => void) | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      userName: null,
      accessType: null,
      hydrated: false,
      hasUnsavedJD: false,
      pendingNavigationUrl: null,
      pendingNavigationAction: null,
      setHydrated: (hydrated) => set({ hydrated }),
      setAuth: (token, userId, userName, accessType) => set({ token, userId, userName, accessType }),
      setHasUnsavedJD: (val) => set({ hasUnsavedJD: val }),
      setPendingNavigationUrl: (url) => set({ pendingNavigationUrl: url }),
      setPendingNavigationAction: (action) => set({ pendingNavigationAction: action }),
      logout: () =>
        set({
          token: null,
          userId: null,
          userName: null,
          accessType: null,
          hasUnsavedJD: false,
          pendingNavigationUrl: null,
          pendingNavigationAction: null,
        }),
    }),
    {
      name: "ninjaforge-auth",
      partialize: (state) => ({
        token: state.token,
        userId: state.userId,
        userName: state.userName,
        accessType: state.accessType,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    },
  ),
);


