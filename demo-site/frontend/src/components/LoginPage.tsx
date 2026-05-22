import { useState } from "react";
import { API } from "../config/api";

export type SessionUser = { id: string; username: string };

type Props = {
  onLogin: (user: SessionUser) => void;
  pendingInviteToken?: string | null;
  onBack?: () => void;
};

export function LoginPage({ onLogin, pendingInviteToken, onBack }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const url = mode === "signup" ? API.signup() : API.login();
      const body =
        mode === "signup"
          ? { invite_code: inviteCode, username, password }
          : { username, password };
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Failed (${res.status})`);
      }
      const user: SessionUser = await res.json();
      onLogin(user);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-lg shadow border border-gray-200 p-6">
        {onBack && (
          <button onClick={onBack} className="text-xs text-gray-400 hover:text-gray-600 mb-3 flex items-center gap-1">
            ← Back
          </button>
        )}
        <h1 className="text-xl font-semibold text-gray-900 mb-1">DataRoot</h1>
        <p className="text-sm text-gray-500 mb-4">
          {pendingInviteToken
            ? "Sign in or sign up to join the shared project."
            : mode === "signup"
            ? "Create an account with the invite code your demo host gave you."
            : "Welcome back."}
        </p>

        <div className="flex gap-1 mb-4 text-sm">
          <button
            type="button"
            onClick={() => setMode("signup")}
            className={`flex-1 py-1.5 rounded ${
              mode === "signup"
                ? "bg-indigo-50 text-indigo-700 font-medium"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            Sign up
          </button>
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`flex-1 py-1.5 rounded ${
              mode === "login"
                ? "bg-indigo-50 text-indigo-700 font-medium"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            Log in
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          {mode === "signup" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Invite code
              </label>
              <input
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                required
                autoFocus
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                placeholder="DEMO2026"
              />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Username
            </label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus={mode === "login"}
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
              placeholder="alice"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
            />
          </div>
          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full py-1.5 rounded bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60"
          >
            {busy ? "..." : mode === "signup" ? "Create account" : "Log in"}
          </button>
        </form>
      </div>
    </div>
  );
}
