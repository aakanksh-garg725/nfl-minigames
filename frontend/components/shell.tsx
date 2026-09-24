"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BriefcaseBusiness,
  ChevronRight,
  CircleHelp,
  History,
  House,
  LayoutGrid,
  LogOut,
  Shield,
  Trophy,
  UserRound,
  Swords,
} from "lucide-react";
import { useAuth, useWeek } from "./providers";
import { practice } from "@/lib/supabase";

const nav = [
  { href: "/", name: "Home", icon: House },
  { href: "/play", name: "Play the game", icon: BriefcaseBusiness },
  { href: "/lineup", name: "My lineup", icon: LayoutGrid },
  { href: "/leaderboard", name: "Leaderboard", icon: Trophy },
  { href: "/head-to-head", name: "Head-to-head", icon: Swords },
  { href: "/history", name: "My history", icon: History },
  { href: "/profile", name: "Profile", icon: UserRound },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const auth = useAuth();
  const { data: week } = useWeek();
  const showGuestActions = !auth.loading && !auth.signedIn && !practice;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="Sunday Vault home">
          <span className="brand-mark">
            <Shield size={27} strokeWidth={1.7} />
            <span>V</span>
          </span>
          <span>
            SUNDAY
            <span className="brand-vault">
              VAULT<span className="brand-dot">.</span>
            </span>
          </span>
        </Link>
        <div className="sidebar-label">YOUR GAME DAY</div>
        <nav className="main-nav" aria-label="Main navigation">
          {nav.map(({ href, name, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={
                (href === "/" ? path === href : path.startsWith(href))
                  ? "active"
                  : ""
              }
            >
              <Icon size={19} />
              <span>{name}</span>
              {href === "/play" && <span className="nav-new">PLAY</span>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Link href="/how-to-play" className="help-link">
            <CircleHelp size={18} /> Rules & scoring
          </Link>
          <Link
            href={auth.signedIn ? "/profile" : "/login"}
            className="account-link"
          >
            <span className="avatar">
              <UserRound size={19} />
            </span>
            <span>
              {practice
                ? "Local Player"
                : auth.signedIn
                  ? "My account"
                  : "Join the game"}
              <small>
                {practice
                  ? "Practice session"
                  : auth.signedIn
                    ? "Manage your profile"
                    : "Sign in / Create account"}
              </small>
            </span>
            <ChevronRight size={16} />
          </Link>
        </div>
      </aside>
      <div className="app-main">
        <header className={`topbar${showGuestActions ? " topbar-guest" : ""}`}>
          <div className="topbar-title">
            <span className="football-dot">◆</span> FANTASY FOOTBALL{" "}
            <span className="divider">/</span>{" "}
            <span className="muted">DEAL OR NO DEAL</span>
          </div>
          <div className="topbar-right">
            <span className="season-label">
              {week ? `${week.season} SEASON` : "THE WEEKLY FANTASY GAME"}
            </span>
            {week && (
              <span className="week-tag">
                WEEK {week.week.toString().padStart(2, "0")}
              </span>
            )}
            {auth.signedIn && !practice && (
              <button
                title="Sign out"
                aria-label="Sign out"
                className="icon-button"
                onClick={auth.signOut}
              >
                <LogOut size={16} />
              </button>
            )}
            {showGuestActions && (
              <div className="header-auth-actions">
                <Link href="/login" className="button primary">
                  Sign in
                </Link>
              </div>
            )}
          </div>
        </header>
        {practice && (
          <div className="practice-banner">
            PRACTICE MODE{" "}
            <span>
              Synthetic projections and sample rosters. Scores are not live.
            </span>
          </div>
        )}
        <main id="main-content" className="main-content">
          {children}
        </main>
        <footer className="site-footer">
          <span>© {new Date().getFullYear()} Sunday Vault</span>
          <span>
            Made for the love of the game. <span className="footer-dot">•</span>{" "}
            Not affiliated with the NFL or ESPN.
          </span>
        </footer>
      </div>
      <nav className="mobile-nav" aria-label="Mobile navigation">
        {nav.map(({ href, name, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={
              (href === "/" ? path === href : path.startsWith(href))
                ? "active"
                : ""
            }
          >
            <Icon size={19} />
            <span>
              {name === "Play the game"
                ? "Play"
                : name === "Head-to-head"
                  ? "H2H"
                  : name.replace("My ", "")}
            </span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
