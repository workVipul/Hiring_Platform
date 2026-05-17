"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { authApi } from "@/services/authApi";
import { useAuthStore } from "@/store/authStore";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function signIn(loginEmail = email, loginPassword = password) {
    const data = await authApi.login(loginEmail, loginPassword);
    setAuth(data.access_token, data.user_id, data.user_name, data.access_type);
    router.push("/dashboard");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "register") {
        await authApi.register(name.trim(), email.trim(), password);
        setNotice("Account created. Signing you in...");
      }
      await signIn(email.trim(), password);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to continue");
    } finally {
      setLoading(false);
    }
  }

  function switchMode(nextMode: Mode) {
    setMode(nextMode);
    setError(null);
    setNotice(null);
    setName("");
    setEmail("");
    setPassword("");
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div>
          <p className="eyebrow">JDForge</p>
          <h1>{mode === "login" ? "Sign in" : "Create account"}</h1>
          <p className="muted">Generate, review, publish, and source job descriptions.</p>
        </div>

        <div className="segmented">
          <button className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")} type="button">
            Sign in
          </button>
          <button className={mode === "register" ? "active" : ""} onClick={() => switchMode("register")} type="button">
            Create account
          </button>
        </div>

        <form onSubmit={handleSubmit} className="stack">
          {mode === "register" && (
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
            </label>
          )}
          <label>
            Email
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              minLength={6}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
            />
          </label>
          {notice && <p className="success">{notice}</p>}
          {error && <p className="error">{error}</p>}
          <button className="primary-button" disabled={loading || (mode === "register" && name.trim().length < 2)} type="submit">
            {loading ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </section>
    </main>
  );
}
