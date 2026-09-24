"use client";

import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  Clock3,
  LockKeyhole,
  ShieldCheck,
  Trophy,
  Users,
} from "lucide-react";
import { useWeek } from "@/components/providers";
import { SLOTS } from "@/lib/types";
import { easternTime, points } from "@/lib/api";
import { TeamLogo } from "@/components/ui";

export default function Home() {
  const { data: week, error } = useWeek();
  const filled = week?.slots.filter((s) => s.player).length ?? 0;
  return (
    <div className="home-page">
      <div className="home-heading">
        <div>
          <div className="eyebrow">
            <span className="live-dot" /> THE FIELD IS YOURS
          </div>
          <h1>Make your next great call.</h1>
          <p>A little strategy. A little nerve. A whole lot of football.</p>
        </div>
        <Link href="/how-to-play" className="text-link">
          New here? Learn the rules <ArrowUpRight size={16} />
        </Link>
      </div>
      <section className="hero-card">
        <div className="field-lines" aria-hidden="true" />
        <div className="hero-copy">
          <div className="hero-kicker">
            <span className="outlined-tag">THE WEEKLY CHALLENGE</span>
            <span>01 / DEAL OR NO DEAL</span>
          </div>
          <h2>
            BIG PLAYERS.
            <br />
            TOUGH CALLS.
            <br />
            <span>YOUR LINEUP.</span>
          </h2>
          <p>
            Twelve mystery cases. A Dealer with an offer.
            <br />
            Take the sure thing or back yourself for more.
          </p>
          <Link href="/play" className="button primary large">
            {filled ? "Continue your lineup" : "Let’s make a deal"}
            <ArrowRight size={20} />
          </Link>
          <div className="hero-fine">
            <ShieldCheck size={14} /> Free to play <span>•</span> Full PPR
            scoring <span>•</span> A new game every week
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbital-ring" />
          <div className="floating-label label-top">
            <span className="live-dot" /> YOUR NEXT BIG PICK IS IN HERE.
          </div>
          <div className="art-case case-back">
            <div className="case-handle" />
            <span>04</span>
            <span className="case-rivet a" />
            <span className="case-rivet b" />
          </div>
          <div className="art-case case-front">
            <div className="case-handle" />
            <div className="art-case-inner">
              <BriefcaseBusiness size={22} />
              <span>07</span>
              <small>SUNDAY VAULT</small>
            </div>
            <span className="case-rivet a" />
            <span className="case-rivet b" />
          </div>
          <div className="floating-label label-bottom">
            <LockKeyhole size={15} />
            <div>
              ONE CASE. ANY PLAYER.<small>How far will you take it?</small>
            </div>
            <ArrowUpRight size={20} />
          </div>
          <div className="art-caption">
            THE BEST PICK MIGHT BE THE ONE YOU KEEP.
          </div>
        </div>
      </section>
      <section className="week-strip">
        <div className="week-strip-title">
          <div className="calendar-icon">
            <span>NFL</span>
            <strong>{week?.week.toString().padStart(2, "0") || "—"}</strong>
          </div>
          <div>
            <div className="small-caps">
              {week ? `${week.season} REGULAR SEASON` : "WEEKLY CONTEST"}
            </div>
            <h3>
              {week
                ? `Week ${week.week} is ${week.is_open ? "on the clock" : "locked"}.`
                : "Your next Sunday starts here."}
            </h3>
          </div>
        </div>
        <div className="week-strip-stat">
          <Clock3 size={18} />
          <div>
            <small>LINEUP DEADLINE</small>
            <strong>
              {week ? easternTime(week.closes_at) : "Sunday · 1:00 PM ET"}
            </strong>
          </div>
        </div>
        <div className="week-strip-stat">
          <Users size={18} />
          <div>
            <small>THE FORMAT</small>
            <strong>2 RB · 2 WR · 1 TE · 1 FLEX</strong>
          </div>
        </div>
        <span className={`status-pill ${week?.is_open ? "open" : ""}`}>
          <span />
          {week?.is_open
            ? "OPEN FOR PLAY"
            : error
              ? "AWAITING WEEKLY DATA"
              : "WEEKLY CHALLENGE"}
        </span>
      </section>
      <section className="home-bottom-grid">
        <div className="lineup-preview panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">BUILD SOMETHING GREAT</div>
              <h2>Your weekly lineup</h2>
            </div>
            <span className="progress-count">
              {filled}
              <span> / 6 LOCKED</span>
            </span>
          </div>
          <div className="mini-slots">
            {SLOTS.map((slot, index) => {
              const player = week?.slots.find((s) => s.slot === slot)?.player;
              return (
                <Link
                  key={slot}
                  href={player ? "/lineup" : "/play"}
                  className={`mini-slot ${player ? "filled" : index === filled ? "current" : ""}`}
                >
                  <span className="slot-name">{slot}</span>
                  {player ? (
                    <TeamLogo team={player.team} size={32} />
                  ) : index === filled ? (
                    <span className="slot-plus">+</span>
                  ) : (
                    <LockKeyhole size={19} />
                  )}
                  <span className="slot-bottom">
                    {player
                      ? player.name.split(" ").at(-1)
                      : index === filled
                        ? "UP NEXT"
                        : "LOCKED"}
                  </span>
                  {player && (
                    <span className="slot-points">
                      {points(player.projection)}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
          <div className="panel-foot">
            <span>
              <span className="live-dot" /> Six games. Six players. Your Sunday.
            </span>
            <Link href="/play">
              {filled === 6 ? "View lineup" : "Build my lineup"}
              <ArrowRight size={15} />
            </Link>
          </div>
        </div>
        <div className="how-card panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">THE GAME PLAN</div>
              <h2>Risk it. Reveal it. Roster it.</h2>
            </div>
            <BriefcaseBusiness size={23} />
          </div>
          <div className="how-step">
            <span>01</span>
            <div>
              <h3>Pick your case</h3>
              <p>One of 12 players is waiting inside.</p>
            </div>
          </div>
          <div className="how-step">
            <span>02</span>
            <div>
              <h3>Make the call</h3>
              <p>Take the Dealer’s player or keep playing.</p>
            </div>
          </div>
          <div className="how-step">
            <span>03</span>
            <div>
              <h3>Let Sunday do the talking</h3>
              <p>Real NFL points. Your spot on the board.</p>
            </div>
          </div>
          <Link href="/how-to-play" className="text-link">
            The full playbook <ArrowUpRight size={15} />
          </Link>
        </div>
      </section>
      <section className="home-note">
        <Trophy size={20} />
        <p>
          <strong>
            Projections set the stage. Real points tell the story.
          </strong>{" "}
          Your leaderboard score comes from what your six players actually do on
          the field.
        </p>
        <Link href="/leaderboard">
          See the leaderboard <ArrowRight size={16} />
        </Link>
      </section>
    </div>
  );
}
