"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: number | null;
  userName: string | null;
  accessType: "admin" | "normal" | null;
  hydrated: boolean;
  setHydrated: (hydrated: boolean) => void;
  setAuth: (token: string, userId: number, userName: string, accessType: "admin" | "normal") => void;
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
      setHydrated: (hydrated) => set({ hydrated }),
      setAuth: (token, userId, userName, accessType) => set({ token, userId, userName, accessType }),
      logout: () => set({ token: null, userId: null, userName: null, accessType: null }),
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
