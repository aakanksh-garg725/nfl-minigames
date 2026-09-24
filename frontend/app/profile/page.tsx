"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { practice, supabase } from "@/lib/supabase";
import { validatePassword } from "@/lib/password";
import type { Profile } from "@/lib/types";
import { useAuth } from "@/components/providers";
import { PasswordFields } from "@/components/password-fields";
import {
  ErrorNotice,
  Loading,
  PageTitle,
  RequireAuth,
  TeamLogo,
} from "@/components/ui";

function AccountSettings() {
  const auth = useAuth();
  const [error, setError] = useState<Error | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [passwordFormKey, setPasswordFormKey] = useState(0);
  async function update(
    event: React.FormEvent<HTMLFormElement>,
    kind: "email" | "password",
  ) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setError(null);
    setMessage("");
    setBusy(true);
    try {
      if (!supabase || !auth.user?.email)
        throw new Error("Please sign in again to manage your account.");
      const password = String(data.get("password") || "");
      if (kind === "password")
        validatePassword(password, String(data.get("confirm_password") || ""));
      // Reauthenticate before changing sensitive account details; passwords never reach our database.
      const signedIn = await supabase.auth.signInWithPassword({
        email: auth.user.email,
        password: String(data.get("current_password")),
      });
      if (signedIn.error) throw signedIn.error;
      const result = await supabase.auth.updateUser(
        kind === "email"
          ? { email: String(data.get("email")).trim() }
          : {
              password,
              current_password: String(data.get("current_password")),
            },
        { emailRedirectTo: `${window.location.origin}/auth/callback` },
      );
      if (result.error) throw result.error;
      form.reset();
      if (kind === "password") setPasswordFormKey((value) => value + 1);
      setMessage(
        kind === "email"
          ? "Email change requested. Follow the confirmation links sent by Supabase (check both your current and new inbox). Your current email remains active until confirmed."
          : "Your password has been updated.",
      );
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Please try again."));
    } finally {
      setBusy(false);
    }
  }
  if (practice)
    return (
      <section className="panel profile-card">
        <h2>Account security</h2>
        <p className="profile-description">
          Email and password changes are available when signed in to a real
          account, not in practice mode.
        </p>
      </section>
    );
  return (
    <section className="panel profile-card account-settings">
      <h2>Account security</h2>
      <p className="profile-description">
        Signed in as {auth.user?.email}. Re-enter your current password to
        change account details.
      </p>
      <ErrorNotice error={error} />
      {message && (
        <div className="success-notice" role="status">
          {message}
        </div>
      )}
      <form onSubmit={(e) => update(e, "email")}>
        <h3>Change email</h3>
        <label>
          New email address
          <input name="email" type="email" autoComplete="email" required />
        </label>
        <label>
          Current password
          <input
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        <button className="button secondary" disabled={busy}>
          Change email
        </button>
      </form>
      <form key={passwordFormKey} onSubmit={(e) => update(e, "password")}>
        <h3>Change password</h3>
        <label>
          Current password
          <input
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        <PasswordFields label="New password" />
        <button className="button primary" disabled={busy}>
          Change password
        </button>
        <Link href="/forgot-password" className="text-link">
          Forgot your current password?
        </Link>
      </form>
    </section>
  );
}

function ProfileEditor({ profile }: { profile: Profile }) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState(profile.username);
  const [team, setTeam] = useState(profile.favorite_team || "");
  const [availability, setAvailability] = useState<{
    available: boolean;
    suggestions: string[];
  } | null>(null);
  const [checkError, setCheckError] = useState<Error | null>(null);
  const usernameRef = useRef(username);
  const save = useMutation({
    mutationFn: (body: object) =>
      api<Profile>("/profile", { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: (data) => {
      queryClient.setQueryData(["profile"], data);
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
      queryClient.invalidateQueries({ queryKey: ["rivalries"] });
      setUsername(data.username);
      usernameRef.current = data.username;
      setAvailability(null);
    },
  });
  function changeUsername(value: string) {
    setUsername(value);
    usernameRef.current = value;
    setAvailability(null);
    setCheckError(null);
    save.reset();
  }
  async function checkUsername() {
    const value = usernameRef.current;
    if (!/^[A-Za-z0-9_]{3,24}$/.test(value)) return;
    try {
      const result = await api<{ available: boolean; suggestions: string[] }>(
        `/profile/username-availability?username=${encodeURIComponent(value)}`,
      );
      if (usernameRef.current === value) setAvailability(result);
    } catch (e) {
      if (usernameRef.current === value) setCheckError(e as Error);
    }
  }
  const suggestions =
    save.error instanceof ApiError
      ? save.error.suggestions
      : availability?.suggestions || [];
  return (
    <section className="panel profile-card">
      <h2>
        {profile.profile_complete ? "Your profile" : "Finish your profile"}
      </h2>
      <p className="profile-description">
        Choose a unique username and your favorite NFL team. You can change them
        anytime without losing your lineup or history.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const values = new FormData(e.currentTarget);
          save.mutate({
            username,
            favorite_team: team,
            display_name: values.get("display_name"),
          });
        }}
      >
        <label>
          Username
          <input
            name="username"
            aria-label="Username"
            aria-describedby="username-help"
            autoComplete="username"
            required
            minLength={3}
            maxLength={24}
            pattern="[A-Za-z0-9_]+"
            value={username}
            onChange={(e) => changeUsername(e.target.value)}
            onBlur={checkUsername}
            disabled={save.isPending}
          />
          <small id="username-help">
            3–24 letters, numbers, or underscores. Usernames are not
            case-sensitive.
          </small>
        </label>
        {availability && (
          <p
            role="status"
            className={
              availability.available ? "success-notice" : "info-notice"
            }
          >
            {availability.available
              ? "Username is available (reserved when you save)."
              : "That username is already taken. Please choose a different one."}
          </p>
        )}
        {!!suggestions.length && (
          <div className="username-suggestions">
            <span>Try one of these:</span>
            {suggestions.map((name) => (
              <button
                type="button"
                className="button secondary"
                key={name}
                disabled={save.isPending}
                onClick={() => changeUsername(name)}
              >
                @{name}
              </button>
            ))}
          </div>
        )}
        <ErrorNotice error={checkError} />
        <label>
          Display name (optional)
          <input
            name="display_name"
            maxLength={60}
            defaultValue={profile.display_name}
          />
        </label>
        <label>
          Favorite NFL team
          <select
            name="favorite_team"
            required
            value={team}
            onChange={(e) => {
              setTeam(e.target.value);
              save.reset();
            }}
          >
            <option value="" disabled>
              Choose your team
            </option>
            {profile.teams.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        {team && (
          <div className="favorite-team-preview">
            <TeamLogo team={team} size={40} />
            <span>
              {profile.teams.find((item) => item.code === team)?.name}
            </span>
          </div>
        )}
        <ErrorNotice error={save.error} />
        {save.isSuccess && (
          <div className="success-notice" role="status">
            Profile saved. <Link href="/play">You’re ready to play.</Link>
          </div>
        )}
        <button className="button primary" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save profile"}
        </button>
      </form>
      <div className="profile-links">
        {profile.is_admin && <Link href="/admin">Admin dashboard</Link>}
        <button className="text-button" onClick={auth.signOut}>
          Sign out
        </button>
      </div>
    </section>
  );
}

function ProfileForm() {
  const auth = useAuth();
  const query = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Profile>("/profile"),
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return <ErrorNotice error={query.error} retry={query.refetch} />;
  if (!practice && !auth.user?.email_confirmed_at)
    return (
      <div className="info-notice">
        Verify your email using the link in your inbox before setting up your
        profile.
      </div>
    );
  return (
    <>
      <PageTitle eyebrow="YOUR ACCOUNT" title="Make it your own.">
        Manage your public identity, favorite team, and account security. Your
        email stays private.
      </PageTitle>
      <div className="profile-grid">
        <ProfileEditor key={query.data.user_id} profile={query.data} />
        <AccountSettings />
      </div>
    </>
  );
}
export default function ProfilePage() {
  return (
    <RequireAuth>
      <ProfileForm />
    </RequireAuth>
  );
}
