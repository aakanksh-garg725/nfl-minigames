"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { validatePassword } from "@/lib/password";
import { PasswordFields } from "./password-fields";
import { practice, supabase } from "@/lib/supabase";
import { ErrorNotice } from "./ui";

export function AuthForm({
  mode,
}: {
  mode: "login" | "signup" | "reset" | "update";
}) {
  const router = useRouter();
  const [error, setError] = useState<Error | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const titles = {
    login: "Welcome back.",
    signup: "Your Sunday starts here.",
    reset: "Back in the game.",
    update: "A fresh start.",
  };
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage("");
    setBusy(true);
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") || ""),
      password = String(data.get("password") || "");
    try {
      if (mode === "signup" || mode === "update")
        validatePassword(password, String(data.get("confirm_password") || ""));
      if (!supabase)
        throw new Error(
          "Account sign-in is not configured yet. Please contact the app owner.",
        );
      if (mode === "signup") {
        const result = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback`,
          },
        });
        if (result.error) throw result.error;
        if (result.data.session) {
          router.push("/profile");
        } else
          setMessage(
            "Check your inbox to verify your email. Then choose your username and favorite NFL team to finish your profile.",
          );
      } else if (mode === "login") {
        const result = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (result.error) throw result.error;
        const profile = await api<Profile>("/profile");
        router.push(profile.profile_complete ? "/play" : "/profile");
      } else if (mode === "reset") {
        const result = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
        });
        if (result.error) throw result.error;
        setMessage(
          "If an account exists for that address, a password-reset link is on its way.",
        );
      } else {
        const result = await supabase.auth.updateUser({ password });
        if (result.error) throw result.error;
        setMessage("Your password has been updated.");
      }
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Please try again."));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <div className="auth-pitch">
        <div className="eyebrow">SUNDAY VAULT</div>
        <h1>
          YOUR PICKS.
          <br />
          YOUR NERVE.
          <br />
          <span>YOUR GAME.</span>
        </h1>
        <p>
          There’s a great lineup in those cases.
          <br />
          Let’s find yours.
        </p>
        <div>
          <ShieldCheck size={18} /> Free to play. Built for football fans.
        </div>
      </div>
      <section className="auth-card panel">
        <div className="eyebrow">
          {mode === "signup" ? "JOIN THE FIELD" : "TAKE YOUR SEAT"}
        </div>
        <h2>{titles[mode]}</h2>
        <p>
          {mode === "login"
            ? "Sign in to pick up right where you left off."
            : mode === "signup"
              ? "Create an account. Make your first great call."
              : "We’ll help you get back to your lineup."}
        </p>
        {practice ? (
          <div className="info-notice">
            Local practice is ready.{" "}
            <Link href="/play">
              Continue to the game <ArrowRight size={15} />
            </Link>
          </div>
        ) : (
          <form onSubmit={submit}>
            {mode !== "update" && (
              <label>
                Email address
                <input
                  type="email"
                  name="email"
                  autoComplete="email"
                  required
                  placeholder="you@example.com"
                />
              </label>
            )}
            {(mode === "signup" || mode === "update") && (
              <PasswordFields
                label={mode === "update" ? "New password" : "Password"}
              />
            )}
            {mode === "login" && (
              <label>
                Password
                <input
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  required
                />
              </label>
            )}
            {mode === "login" && (
              <Link className="forgot-link" href="/forgot-password">
                Forgot your password?
              </Link>
            )}
            <ErrorNotice error={error} />
            {message && (
              <div className="success-notice" role="status">
                {message}
              </div>
            )}
            <button className="button primary" disabled={busy}>
              {busy
                ? "One moment…"
                : {
                    login: "Sign in",
                    signup: "Create my account",
                    reset: "Send reset link",
                    update: "Update password",
                  }[mode]}
              <ArrowRight size={17} />
            </button>
          </form>
        )}
        {mode === "login" ? (
          <div className="auth-switch">
            New to the game? <Link href="/signup">Create an account</Link>
          </div>
        ) : (
          <div className="auth-switch">
            Already on the field? <Link href="/login">Sign in</Link>
          </div>
        )}
      </section>
    </div>
  );
}
