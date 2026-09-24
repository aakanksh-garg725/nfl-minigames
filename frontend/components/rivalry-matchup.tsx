"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, points } from "@/lib/api";
import { SLOTS, type LineupSlot } from "@/lib/types";
import {
  ErrorNotice,
  Loading,
  PageTitle,
  PlayerMatchup,
  RequireAuth,
  TeamLogo,
} from "./ui";

type MatchupTeam = {
  username: string;
  favorite_team: string | null;
  score: number;
  slots: Pick<LineupSlot, "slot" | "player" | "actual_ppr" | "game_status">[];
};
type Matchup = {
  season: number;
  week: number;
  weeks: number[];
  status: string;
  you: MatchupTeam;
  opponent: MatchupTeam;
};

function TeamHeading({ team, yours }: { team: MatchupTeam; yours: boolean }) {
  return (
    <div
      className={`matchup-team-heading ${yours ? "your-team" : "opponent-team"}`}
    >
      <span className="eyebrow">{yours ? "YOUR TEAM" : "OPPONENT"}</span>
      <strong
        className="matchup-total"
        aria-label={`${yours ? "Your" : "Opponent"} total points`}
      >
        {points(team.score)}
      </strong>
      <span className="matchup-score-label">TOTAL POINTS</span>
      <TeamLogo team={team.favorite_team || "NFL"} size={44} />
      <h2>@{team.username}</h2>
      <small>
        {team.slots.filter((s) => s.player).length}/6 filled · Full PPR
      </small>
    </div>
  );
}

function PlayerRow({ slot }: { slot?: MatchupTeam["slots"][number] }) {
  const player = slot?.player;
  return (
    <div className={`matchup-player ${player ? "" : "empty"}`}>
      <div className="matchup-player-details">
        {player ? (
          <>
            <strong>{player.name}</strong>
            <span>
              {player.team} · {player.position}
              <PlayerMatchup player={player} />
            </span>
            <small>{slot?.game_status.replaceAll("_", " ")}</small>
          </>
        ) : (
          <>
            <strong>Empty slot</strong>
            <span>No player locked in</span>
          </>
        )}
      </div>
      <div className="matchup-player-points">
        <strong>{points(slot?.actual_ppr ?? 0)}</strong>
        <small>Proj. {points(player?.projection ?? 0)}</small>
      </div>
    </div>
  );
}

function MatchupView({ id, week }: { id: string; week: string }) {
  const router = useRouter();
  const query = useQuery({
    queryKey: ["rivalry-matchup", id, week],
    queryFn: () =>
      api<Matchup>(
        `/rivalries/${encodeURIComponent(id)}/matchups/${encodeURIComponent(week)}`,
      ),
    refetchInterval: 30_000,
  });
  const data = query.data;
  return (
    <>
      <Link href="/head-to-head" className="text-button">
        ← Back to rivalries
      </Link>
      <PageTitle
        eyebrow={
          data ? `${data.season} SEASON · WEEK ${data.week}` : "HEAD-TO-HEAD"
        }
        title="The weekly showdown."
      />
      {query.isPending ? (
        <Loading label="Loading both lineups…" />
      ) : query.error ? (
        <ErrorNotice error={query.error} retry={query.refetch} />
      ) : (
        data && (
          <>
            <div className="matchup-toolbar">
              <label>
                Matchup week{" "}
                <select
                  aria-label="Matchup week"
                  value={data.week}
                  onChange={(e) =>
                    router.push(
                      `/head-to-head/${encodeURIComponent(id)}/${e.target.value}`,
                    )
                  }
                >
                  {data.weeks.map((number) => (
                    <option key={number} value={number}>
                      Week {number}
                    </option>
                  ))}
                </select>
              </label>
              <span className="outlined-tag">{data.status}</span>
            </div>
            <section
              className="panel matchup-arena"
              aria-label="Head-to-head lineups"
            >
              <div className="matchup-teams">
                <TeamHeading team={data.you} yours />
                <span className="matchup-versus">VS</span>
                <TeamHeading team={data.opponent} yours={false} />
              </div>
              <div className="matchup-roster-labels">
                <span>YOUR LINEUP</span>
                <span>OPPONENT LINEUP</span>
              </div>
              {SLOTS.map((slot) => (
                <div
                  className="matchup-player-pair"
                  key={slot}
                  aria-label={`${slot} matchup`}
                >
                  <PlayerRow
                    slot={data.you.slots.find((s) => s.slot === slot)}
                  />
                  <span className="matchup-slot">{slot}</span>
                  <PlayerRow
                    slot={data.opponent.slots.find((s) => s.slot === slot)}
                  />
                </div>
              ))}
            </section>
            <p className="footnote">
              Empty slots score zero. Projections are shown as a reference;
              actual full-PPR points decide the winner. Scores refresh every 30
              seconds and remain provisional until finalized.
            </p>
          </>
        )
      )}
    </>
  );
}

export function RivalryMatchup(props: { id: string; week: string }) {
  return (
    <RequireAuth>
      <MatchupView {...props} />
    </RequireAuth>
  );
}
