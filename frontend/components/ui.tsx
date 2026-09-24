"use client";

import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  LoaderCircle,
  LockKeyhole,
} from "lucide-react";
import { useState } from "react";
import { teamLogo } from "@/lib/teams";
import type { Player } from "@/lib/types";
import { useAuth } from "./providers";

export function PlayerMatchup({ player }: { player: Player }) {
  if (!player.opponent || typeof player.is_home !== "boolean") return null;
  return (
    <span className="player-matchup">
      {` · ${player.is_home ? "vs" : "@"} ${player.opponent}`}
    </span>
  );
}

export function TeamLogo({ team, size = 36 }: { team: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className="team-logo" style={{ width: size, height: size }}>
      {failed || team === "NFL" ? (
        <span>{team}</span>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={teamLogo(team)}
          alt={`${team} team logo`}
          width={size}
          height={size}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
    </span>
  );
}
export function Loading({ label = "Loading your game…" }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle size={24} className="spin" />
      <p>{label}</p>
    </div>
  );
}
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={19} />
      <span>
        {error instanceof Error ? error.message : "Something went wrong."}
      </span>
      {retry && (
        <button onClick={retry} className="text-button">
          Try again
        </button>
      )}
    </div>
  );
}
export function Empty({
  title,
  children,
  href,
  action,
}: {
  title: string;
  children: React.ReactNode;
  href?: string;
  action?: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <LockKeyhole size={28} />
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
      {href && (
        <Link className="button primary" href={href}>
          {action}
          <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  if (auth.loading) return <Loading />;
  if (!auth.signedIn)
    return (
      <Empty
        title="Your lineup starts here"
        href="/login"
        action="Sign in to play"
      >
        Sign in to save your cases, build your weekly lineup, and join the
        leaderboard.
      </Empty>
    );
  return children;
}
export function PageTitle({
  eyebrow,
  title,
  children,
  aside,
}: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <header className="page-title">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {aside}
    </header>
  );
}
