"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  ArrowLeftRight,
  BriefcaseBusiness,
  Check,
  Clock3,
  Phone,
  ShieldCheck,
  Trophy,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, easternTime, points, post } from "@/lib/api";
import type { DealGame, Player } from "@/lib/types";
import { useWeek } from "./providers";
import { SlotProgress } from "./lineup";
import { ErrorNotice, Loading, PlayerMatchup, TeamLogo } from "./ui";

function Countdown({ until }: { until: string }) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.max(
    0,
    Math.floor((new Date(until).getTime() - now) / 1000),
  );
  const h = Math.floor(seconds / 3600),
    m = Math.floor(seconds / 60) % 60;
  return (
    <span>
      {now
        ? `${h}h ${m.toString().padStart(2, "0")}m ${String(seconds % 60).padStart(2, "0")}s`
        : "—"}
    </span>
  );
}

function PlayerBoard({ players }: { players: Player[] }) {
  const remaining = players.filter((p) => !p.eliminated).length;
  return (
    <section className="player-board panel">
      <div className="panel-heading">
        <div>
          <div className="eyebrow">THE POSSIBILITIES</div>
          <h2>Player board</h2>
        </div>
        <span className="count-badge">{remaining}/12</span>
      </div>
      <div className="board-column-labels">
        <span>PLAYER / TEAM</span>
        <span>PROJ.</span>
      </div>
      <div className="board-rows">
        {players.map((player) => (
          <div
            key={player.id}
            className={`board-row rank-${player.board_rank} ${player.eliminated ? "eliminated" : ""}`}
          >
            <span className="board-rank">
              {player.eliminated ? (
                <X size={12} />
              ) : (
                String(player.board_rank).padStart(2, "0")
              )}
            </span>
            <TeamLogo team={player.team} size={28} />
            <div className="board-player">
              <strong>{player.name}</strong>
              <small>
                {player.team} · {player.position}
                <PlayerMatchup player={player} />
                {player.eliminated && " · OUT"}
              </small>
            </div>
            <strong className="board-points">
              {points(player.projection)}
            </strong>
          </div>
        ))}
      </div>
      <div className="board-note">
        Projected full-PPR points
        <br />
        <span>Actual game-day points determine your score.</span>
      </div>
    </section>
  );
}

export function GameView({ gameId }: { gameId: string }) {
  const queryClient = useQueryClient();
  const { data: week } = useWeek();
  const query = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => api<DealGame>(`/deal-games/${gameId}`),
    refetchInterval: 30_000,
  });
  const g = query.data;
  const [revealPause, setRevealPause] = useState<{
    gameId: string;
    version: number;
  } | null>(null);
  const revealing =
    revealPause?.gameId === gameId && revealPause?.version === g?.version;
  const focusRef = useRef<HTMLHeadingElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const activeOffer = g?.status.startsWith("OFFER_")
    ? g.offers.find((o) => o.decision === "PENDING")
    : undefined;
  const popupKey = revealing
    ? undefined
    : activeOffer
      ? `offer-${activeOffer.offer_number}`
      : g?.status === "FINAL_CHOICE"
        ? "final-choice"
        : g?.status === "COMPLETE" && g.awarded_player
          ? "player-locked"
          : undefined;
  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: object }) =>
      post<DealGame>(`/deal-games/${gameId}/${path}`, {
        ...body,
        version: g?.version,
      }),
    onSuccess: (data, { path }) => {
      // Let the final opened case render before covering it with a decision.
      // Resuming an existing offer or declining one needs no extra pause.
      if (
        /^cases\/\d+\/open$/.test(path) &&
        (data.status.startsWith("OFFER_") || data.status === "FINAL_CHOICE")
      ) {
        setRevealPause({ gameId, version: data.version });
      }
      queryClient.setQueryData(["game", gameId], data);
      queryClient.invalidateQueries({ queryKey: ["week"] });
      queryClient.invalidateQueries({ queryKey: ["lineup"] });
    },
    onError: () => {
      query.refetch();
    },
  });
  useEffect(() => {
    if (!revealPause || revealPause.gameId !== gameId) return;
    const timer = setTimeout(() => setRevealPause(null), 3000);
    return () => clearTimeout(timer);
  }, [revealPause, gameId]);
  useEffect(() => {
    if (g?.status.startsWith("ROUND_"))
      focusRef.current?.focus({ preventScroll: true });
  }, [g?.status]);
  useEffect(() => {
    if (!popupKey) return;
    popupRef.current?.focus({ preventScroll: true });
    popupRef.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [popupKey, g?.id]);
  if (query.isPending) return <Loading label="Opening your vault…" />;
  if (!g || query.error)
    return <ErrorNotice error={query.error} retry={query.refetch} />;
  const selecting = g.status === "AWAITING_CASE_SELECTION";
  const canOpen = g.status.startsWith("ROUND_");
  const final = g.status === "FINAL_CHOICE";
  const completed = g.status === "COMPLETE";
  const closed = g.cases.filter((c) => c.status === "CLOSED");
  const other = closed.find((c) => !c.is_user_case);
  const visibleOffers = g.offers.filter(
    (offer) => !revealing || offer.decision !== "PENDING",
  );
  return (
    <div className="game-page">
      <div className="game-topline">
        <Link href="/play" className="text-link">
          <ArrowLeft size={15} /> My lineup
        </Link>
        <span>
          WEEK {week?.week || "—"} <span className="muted">/</span> {g.slot}{" "}
          GAME
        </span>
        <span className="game-expiry" title={easternTime(g.expires_at)}>
          <Clock3 size={14} /> Player lock in <Countdown until={g.expires_at} />
        </span>
      </div>
      <div className="game-title-row">
        <div>
          <div className="eyebrow">TRUST YOUR NEXT MOVE</div>
          <h1>
            {g.slot}
            <span> / </span>DEAL OR NO DEAL
          </h1>
        </div>
        <span className="outlined-tag">FULL PPR</span>
      </div>
      <SlotProgress slots={week?.slots || []} current={g.slot} />
      {!popupKey && <ErrorNotice error={action.error} />}
      <div className="game-layout">
        <div className="board-column">
          <PlayerBoard players={g.board} />
        </div>
        <section className="cases-area">
          <div className="round-heading" aria-live="polite">
            <div className="round-indicator">
              {selecting
                ? "THE FIRST CALL"
                : completed
                  ? "PLAYER ACQUIRED"
                  : final
                    ? "THE FINAL CALL"
                    : `ROUND ${g.current_round} OF 4`}
            </div>
            <h2 ref={focusRef} tabIndex={-1}>
              {g.instruction}
            </h2>
            <p>
              {selecting
                ? "Pick one to keep sealed. Your next player could be inside."
                : canOpen
                  ? "Every reveal brings you closer to your next offer."
                  : activeOffer
                    ? "A sure thing, or a little more faith in your case?"
                    : completed
                      ? "One more piece of your Sunday, locked in."
                      : final
                        ? "Your original pick, or one last change of heart?"
                        : "The player lock has passed. You can restart this unfilled slot."}
            </p>
          </div>
          <div className="cases-stage">
            <div className="case-grid" aria-label="Twelve player cases">
              {g.cases.map((c) => {
                const canClick =
                  !action.isPending &&
                  (selecting ||
                    (canOpen && !c.is_user_case && c.status === "CLOSED"));
                return (
                  <button
                    key={c.case_number}
                    className={`case-tile ${c.player ? "revealed" : "sealed"} ${c.is_user_case ? "my-case" : ""} ${c.status === "ELIMINATED" ? "eliminated-case" : ""}`}
                    disabled={!canClick}
                    aria-label={
                      c.player
                        ? `Case ${c.case_number}: ${c.player.name}, ${points(c.player.projection)} projected points`
                        : `${selecting ? "Choose" : c.is_user_case ? "Your" : "Open"} case ${c.case_number}`
                    }
                    onClick={() =>
                      action.mutate(
                        selecting
                          ? {
                              path: "select-case",
                              body: { case_number: c.case_number },
                            }
                          : { path: `cases/${c.case_number}/open` },
                      )
                    }
                  >
                    {!c.player && <div className="tile-handle" />}
                    {c.is_user_case && (
                      <span className="my-case-label">MY CASE</span>
                    )}
                    {c.player ? (
                      <>
                        <TeamLogo team={c.player.team} size={29} />
                        <span className="revealed-name">{c.player.name}</span>
                        <span className="revealed-points">
                          {points(c.player.projection)} <small>PTS</small>
                        </span>
                        <span className="revealed-case-number">
                          {String(c.case_number).padStart(2, "0")}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="case-number">
                          {String(c.case_number).padStart(2, "0")}
                        </span>
                        <span className="tile-corner left" />
                        <span className="tile-corner right" />
                      </>
                    )}
                  </button>
                );
              })}
            </div>
            {activeOffer && !revealing && (
              <div className="game-popup-overlay banker-offer-overlay">
                <div
                  className="dealer-card game-popup-dialog banker-offer-dialog"
                  role="dialog"
                  aria-label={`Banker offer ${activeOffer.offer_number}`}
                  aria-describedby="banker-offer-prompt"
                  aria-busy={action.isPending}
                  tabIndex={-1}
                  ref={popupRef}
                >
                  <div className="dealer-heading">
                    <Phone size={17} />
                    <span>THE DEALER IS CALLING</span>
                    <span className="offer-number">
                      OFFER {activeOffer.offer_number}
                    </span>
                  </div>
                  <div className="dealer-player">
                    <TeamLogo team={activeOffer.player.team} size={55} />
                    <div>
                      <h3>{activeOffer.player.name}</h3>
                      <span>
                        {activeOffer.player.team} ·{" "}
                        {activeOffer.player.position}
                        <PlayerMatchup player={activeOffer.player} />
                      </span>
                    </div>
                    <div className="dealer-points">
                      {points(activeOffer.player.projection)}
                      <small>PROJECTED PPR</small>
                    </div>
                  </div>
                  <p id="banker-offer-prompt" className="banker-offer-prompt">
                    Take the guaranteed player or keep opening cases.
                  </p>
                  <ErrorNotice error={action.error} />
                  <div className="decision-buttons">
                    <button
                      className="button primary"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({
                          path: `offers/${activeOffer.offer_number}/decision`,
                          body: { decision: "DEAL" },
                        })
                      }
                    >
                      <Check size={18} /> DEAL
                    </button>
                    <button
                      className="button secondary"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({
                          path: `offers/${activeOffer.offer_number}/decision`,
                          body: { decision: "NO_DEAL" },
                        })
                      }
                    >
                      <X size={18} /> NO DEAL
                    </button>
                  </div>
                </div>
              </div>
            )}
            {final && !revealing && (
              <div className="game-popup-overlay">
                <div
                  className="dealer-card final-choice game-popup-dialog"
                  role="dialog"
                  aria-labelledby="final-choice-title"
                  aria-describedby="final-choice-prompt"
                  aria-busy={action.isPending}
                  tabIndex={-1}
                  ref={popupRef}
                >
                  <ArrowLeftRight size={27} />
                  <h3 id="final-choice-title">Stay loyal or switch sides?</h3>
                  <p id="final-choice-prompt">
                    Both cases are sealed. The choice is yours.
                  </p>
                  <ErrorNotice error={action.error} />
                  <div className="decision-buttons">
                    <button
                      disabled={action.isPending}
                      className="button primary"
                      onClick={() =>
                        action.mutate({
                          path: "final-choice",
                          body: { choice: "KEEP" },
                        })
                      }
                    >
                      Keep case #{g.selected_case_number}
                    </button>
                    <button
                      disabled={action.isPending}
                      className="button secondary"
                      onClick={() =>
                        action.mutate({
                          path: "final-choice",
                          body: { choice: "SWAP" },
                        })
                      }
                    >
                      Swap for #{other?.case_number}
                    </button>
                  </div>
                </div>
              </div>
            )}
            {completed && g.awarded_player && (
              <div className="game-popup-overlay">
                <div
                  className="complete-card game-popup-dialog"
                  role="dialog"
                  aria-labelledby="player-locked-title"
                  aria-describedby="player-locked-prompt"
                  tabIndex={-1}
                  ref={popupRef}
                >
                  <div className="complete-badge" id="player-locked-title">
                    <Trophy size={19} /> {g.slot} LOCKED IN
                  </div>
                  <div className="dealer-player">
                    <TeamLogo team={g.awarded_player.team} size={54} />
                    <div>
                      <h3>{g.awarded_player.name}</h3>
                      <span>
                        {g.awarded_player.team} ·{" "}
                        {points(g.awarded_player.projection)} projected PPR
                        <PlayerMatchup player={g.awarded_player} />
                      </span>
                    </div>
                  </div>
                  <p id="player-locked-prompt">
                    Your score will use his actual points on game day.
                  </p>
                  <Link href="/play" className="button primary">
                    {week?.next_slot ? "Next lineup slot" : "View your lineup"}
                    <ArrowRight size={17} />
                  </Link>
                </div>
              </div>
            )}
          </div>
          <div className="game-decision-area" aria-live="polite">
            {revealing && (
              <div className="case-hint">
                <Clock3 size={16} />
                <span>
                  Take a look at your last reveal. Your next decision is coming
                  up.
                </span>
              </div>
            )}
            {g.status === "EXPIRED" && (
              <div className="info-notice">
                No player was awarded.{" "}
                <Link href="/play">
                  Return to your lineup to restart this slot{" "}
                  <ArrowRight size={14} />
                </Link>
              </div>
            )}
            {(selecting || canOpen) && (
              <div className="case-hint">
                <ShieldCheck size={16} />
                <span>
                  {selecting
                    ? "Every case is a mystery. Pick your number."
                    : `Case #${g.selected_case_number} is yours. Keep it sealed.`}
                </span>
              </div>
            )}
          </div>
        </section>
        <aside className="offers-column">
          <div className="panel offers-panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">THE NEGOTIATION</div>
                <h2>Past offers</h2>
              </div>
              <Phone size={17} />
            </div>
            {visibleOffers.length === 0 ? (
              <div className="no-offers">
                <BriefcaseBusiness size={31} />
                <h3>Good things take nerve.</h3>
                <p>
                  Open your first four cases.
                  <br />
                  Then hear what the Dealer has in mind.
                </p>
                <span className="dashed-line" />
              </div>
            ) : (
              <div className="offer-history">
                {visibleOffers.map((offer) => (
                  <div
                    className={`offer-history-item ${offer.decision === "PENDING" ? "pending" : ""}`}
                    key={offer.offer_number}
                  >
                    <div>
                      <span>OFFER {offer.offer_number}</span>
                      <span
                        className={`offer-decision ${offer.decision.toLowerCase()}`}
                      >
                        {offer.decision.replace("_", " ")}
                      </span>
                    </div>
                    <div className="past-player">
                      <TeamLogo team={offer.player.team} size={27} />
                      <strong>{offer.player.name}</strong>
                    </div>
                    <p>
                      {points(offer.player.projection)}{" "}
                      <span>PROJECTED PPR</span>
                      <PlayerMatchup player={offer.player} />
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="game-tip">
            <span className="eyebrow">A LITTLE GAME THEORY</span>
            <p>A great lineup is built one decision at a time.</p>
            <small>
              The Dealer can offer any eligible player—even one outside your
              board.
            </small>
          </div>
        </aside>
      </div>
    </div>
  );
}
