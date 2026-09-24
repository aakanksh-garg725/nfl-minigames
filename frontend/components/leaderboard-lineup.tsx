"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, points } from "@/lib/api";
import type { LineupSlot } from "@/lib/types";
import { LineupCards } from "./lineup";
import { ErrorNotice, Loading, PageTitle, RequireAuth, TeamLogo } from "./ui";

type SharedLineup = {
  season: number;
  week: number;
  username: string;
  display_name: string;
  favorite_team: string | null;
  score: number;
  status: string;
  slots: Pick<LineupSlot, "slot" | "player" | "actual_ppr" | "game_status">[];
};
type Props = { season: string; week: string; userId: string };

function PlayerLineup({ season, week, userId }: Props) {
  const query = useQuery({
    queryKey: ["leaderboard-lineup", season, week, userId],
    queryFn: () =>
      api<SharedLineup>(
        `/leaderboards/weekly/${encodeURIComponent(season)}/${encodeURIComponent(week)}/lineups/${encodeURIComponent(userId)}`,
      ),
    refetchInterval: 30_000,
  });
  const data = query.data;
  return (
    <>
      <Link href="/leaderboard" className="text-button">
        ← Back to leaderboard
      </Link>
      {query.isPending ? (
        <Loading label="Loading player lineup…" />
      ) : query.error ? (
        <ErrorNotice error={query.error} retry={query.refetch} />
      ) : (
        data && (
          <>
            <PageTitle
              eyebrow={`WEEK ${data.week} · ${data.season} SEASON`}
              title={`@${data.username}'s lineup`}
              aside={<TeamLogo team={data.favorite_team || "NFL"} size={48} />}
            >
              {data.display_name ? `${data.display_name} · ` : ""}Six locked-in
              picks from the current-week leaderboard.
            </PageTitle>
            <section
              className="score-summary panel"
              aria-label="Player lineup summary"
            >
              <div>
                <span className="eyebrow">TOTAL ACTUAL FULL-PPR POINTS</span>
                <strong>{points(data.score)}</strong>
              </div>
              <div>
                <small>TOTAL PROJECTED PPR</small>
                <strong aria-label="Total projected points">
                  {points(
                    data.slots.reduce(
                      (total, slot) => total + (slot.player?.projection ?? 0),
                      0,
                    ),
                  )}
                </strong>
              </div>
              <div>
                <small>WEEK STATUS</small>
                <span
                  className={`status-pill ${data.status === "LIVE" ? "open" : ""}`}
                >
                  {data.status.replaceAll("_", " ")}
                </span>
              </div>
            </section>
            <LineupCards slots={data.slots} scored readOnly />
            <p className="footnote">
              Read-only lineup. Scores refresh every 30 seconds; live results
              are provisional until finalized.
            </p>
          </>
        )
      )}
    </>
  );
}

export function LeaderboardLineup(props: Props) {
  return (
    <RequireAuth>
      <PlayerLineup {...props} />
    </RequireAuth>
  );
}
