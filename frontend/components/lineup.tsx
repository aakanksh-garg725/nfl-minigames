"use client";
import Link from "next/link";
import { ArrowRight, Check, LockKeyhole, Plus } from "lucide-react";
import { SLOTS, type LineupSlot } from "@/lib/types";
import { points } from "@/lib/api";
import { PlayerMatchup, TeamLogo } from "./ui";

export function SlotProgress({
  slots,
  current,
}: {
  slots: LineupSlot[];
  current?: string | null;
}) {
  return (
    <div className="slot-progress" aria-label="Lineup progress">
      {SLOTS.map((slot, i) => {
        const filled = slots.some((s) => s.slot === slot && s.player);
        return (
          <div
            key={slot}
            className={`progress-slot ${filled ? "done" : slot === current ? "current" : ""}`}
          >
            <span className="progress-circle">
              {filled ? <Check size={13} /> : i + 1}
            </span>
            <span>{slot}</span>
            {i < 5 && <span className="progress-line" />}
          </div>
        );
      })}
    </div>
  );
}

export function LineupCards({
  slots,
  current,
  scored = false,
}: {
  slots: LineupSlot[];
  current?: string | null;
  scored?: boolean;
}) {
  return (
    <div className="lineup-cards">
      {SLOTS.map((name, index) => {
        const slot = slots.find((s) => s.slot === name);
        const player = slot?.player;
        return (
          <article
            key={name}
            className={`roster-card ${player ? "filled" : name === current ? "next" : ""}`}
          >
            <div className="roster-card-top">
              <span className="position-tag">{name}</span>
              <span className="small-caps">
                {player ? (
                  <>
                    <Check size={13} /> LOCKED IN
                  </>
                ) : (
                  `PICK ${index + 1} OF 6`
                )}
              </span>
            </div>
            {player && slot ? (
              <>
                <div className="roster-player">
                  <TeamLogo team={player.team} size={60} />
                  <div>
                    <h2>{player.name}</h2>
                    <p>
                      {player.team} <span>•</span> {player.position}
                      <PlayerMatchup player={player} />
                    </p>
                  </div>
                </div>
                <div className="roster-points">
                  <div>
                    <small>{scored ? "ACTUAL PPR" : "PROJECTED PPR"}</small>
                    <strong>
                      {points(scored ? slot.actual_ppr : player.projection)}
                      <span>PTS</span>
                    </strong>
                  </div>
                  <span
                    className={`status-pill ${slot.game_status === "LIVE" ? "open" : ""}`}
                  >
                    {slot.game_status.replaceAll("_", " ")}
                  </span>
                </div>
                <div className="roster-acquisition">
                  <span>
                    {
                      (
                        {
                          DEAL: "Dealer offer",
                          FINAL_KEEP: "Kept your case",
                          FINAL_SWAP: "Swapped cases",
                        } as Record<string, string>
                      )[slot.acquisition_method || ""]
                    }
                  </span>
                  {slot.deal_game_id && (
                    <Link href={`/play/${slot.deal_game_id}`}>
                      View game <ArrowRight size={13} />
                    </Link>
                  )}
                </div>
              </>
            ) : (
              <div className="roster-empty">
                <span>
                  {name === current ? (
                    <Plus size={29} />
                  ) : (
                    <LockKeyhole size={26} />
                  )}
                </span>
                <h2>
                  {name === current
                    ? "You’re on the clock"
                    : "Your next big pick"}
                </h2>
                <p>
                  {name === current
                    ? "Twelve cases. Who will you take home?"
                    : "Complete the previous slot to unlock."}
                </p>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
