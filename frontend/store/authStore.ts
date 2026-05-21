"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  userId: number | null;
  userName: string | null;
  accessType: "admin" | "normal" | null;
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
      setAuth: (token, userId, userName, accessType) => set({ token, userId, userName, accessType }),
      logout: () => set({ token: null, userId: null, userName: null, accessType: null }),
    }),
    { name: "ninjaforge-auth" },
  ),
);
