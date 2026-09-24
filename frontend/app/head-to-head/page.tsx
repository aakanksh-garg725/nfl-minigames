"use client";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post, points } from "@/lib/api";
import { useWeek } from "@/components/providers";
import {
  ErrorNotice,
  Loading,
  PageTitle,
  RequireAuth,
  TeamLogo,
} from "@/components/ui";

type Record = { wins: number; losses: number; ties: number };
type Rivalry = {
  id: string;
  season: number;
  status: string;
  direction: string;
  start_week: number | null;
  opponent: { username: string; favorite_team: string | null };
  record: Record;
  opponent_record: Record;
  your_total: number;
  opponent_total: number;
  history: {
    week: number;
    status: string;
    your_score: number;
    opponent_score: number;
    outcome: string | null;
    updated_at: string;
  }[];
};
type Rivalries = {
  season: number;
  rivalries: Rivalry[];
  record: Record;
  total_points: number;
  weeks_scored: number;
};
const recordText = (record: Record) =>
  `${record.wins}–${record.losses}–${record.ties}`;

function HeadToHead() {
  const { data: week } = useWeek();
  const [season, setSeason] = useState<number | null>(null);
  const [username, setUsername] = useState("");
  const selectedSeason = season ?? week?.season;
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["rivalries", selectedSeason],
    queryFn: () => api<Rivalries>(`/rivalries?season=${selectedSeason}`),
    enabled: !!selectedSeason,
    refetchInterval: 30_000,
  });
  const action = useMutation({
    mutationFn: ({ id, decision }: { id?: string; decision?: string }) =>
      id
        ? post(`/rivalries/${id}/decision`, { decision })
        : post("/rivalries", { username: username.trim().replace(/^@/, "") }),
    onSuccess: (_data, variables) => {
      client.invalidateQueries({ queryKey: ["rivalries"] });
      if (!variables.id) setUsername("");
    },
  });
  const data = query.data;
  const visibleRivalries =
    data?.rivalries.filter(
      (rivalry) =>
        rivalry.status === "PENDING" || rivalry.status === "ACCEPTED",
    ) ?? [];
  return (
    <>
      <PageTitle
        eyebrow="SEASON-LONG RIVALRIES"
        title="Your Sunday. Head to head."
      >
        Invite by username. One weekly lineup, as many opponents as you like.
      </PageTitle>
      <div className="rivalry-toolbar">
        <label>
          Season{" "}
          <input
            aria-label="Season"
            type="number"
            min={2026}
            max={week?.season || 2026}
            value={selectedSeason || 2026}
            onChange={(e) => {
              const value = Number(e.target.value);
              if (value >= 2026 && value <= (week?.season || 2026))
                setSeason(value);
            }}
          />
        </label>
        <Link href="/play" className="button secondary">
          Build your weekly lineup
        </Link>
      </div>
      <section className="panel rivalry-invite">
        <h2>Invite an opponent</h2>
        <p>
          They must accept before the rivalry begins. Matchups start with the
          current week if accepted before Sunday’s 1 PM Eastern lineup lock;
          otherwise they start the following week. Rivalries run through Week
          18.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            action.mutate({});
          }}
        >
          <label>
            Opponent username
            <input
              name="opponent"
              required
              minLength={3}
              maxLength={25}
              pattern="@?[A-Za-z0-9_]{3,24}"
              placeholder="@username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                action.reset();
              }}
            />
          </label>
          <button
            className="button primary"
            disabled={action.isPending || selectedSeason !== week?.season}
          >
            Send invitation
          </button>
        </form>
        <ErrorNotice error={action.error} />
        {action.isSuccess && (
          <div className="success-notice" role="status">
            {action.variables?.id
              ? "Invitation updated."
              : "Invitation sent. Your opponent can accept it on their Head-to-head page."}
          </div>
        )}
      </section>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorNotice error={query.error} retry={query.refetch} />
      ) : (
        data && (
          <>
            <section className="panel rivalry-summary">
              <div>
                <span>YOUR MATCHUP RECORD</span>
                <strong>{recordText(data.record)}</strong>
                <small>Wins – losses – ties across all opponents</small>
              </div>
              <div>
                <span>SEASON POINTS</span>
                <strong>{points(data.total_points)}</strong>
                <small>
                  {data.weeks_scored} finalized matched weeks · each week
                  counted once
                </small>
              </div>
            </section>
            <p className="profile-description">
              Highest actual full-PPR score wins. Empty slots score zero; equal
              scores are ties. Records and season totals update when weekly
              results are finalized. Live scores are provisional and may change
              after stat corrections.
            </p>
            {!visibleRivalries.length && (
              <div className="info-notice">
                No active rivalries or pending invitations for this season.
                Invite a friend using their profile username.
              </div>
            )}
            <div className="rivalry-list">
              {visibleRivalries.map((rivalry) => (
                <section className="panel rivalry-card" key={rivalry.id}>
                  <header>
                    <div className="rivalry-opponent">
                      <TeamLogo
                        team={rivalry.opponent.favorite_team || "NFL"}
                        size={40}
                      />
                      <h2>@{rivalry.opponent.username}</h2>
                    </div>
                    <span className="outlined-tag">{rivalry.status}</span>
                  </header>
                  {rivalry.status === "PENDING" && (
                    <>
                      <p>
                        {rivalry.direction === "RECEIVED"
                          ? "Invited you to go head-to-head this season."
                          : "Waiting for your opponent to accept."}
                      </p>
                      <div className="decision-buttons">
                        {(rivalry.direction === "RECEIVED"
                          ? ["ACCEPT", "DECLINE"]
                          : ["CANCEL"]
                        ).map((decision) => (
                          <button
                            className={`button ${decision === "ACCEPT" ? "primary" : "secondary"}`}
                            key={decision}
                            disabled={action.isPending}
                            onClick={() =>
                              action.mutate({ id: rivalry.id, decision })
                            }
                          >
                            {decision === "ACCEPT"
                              ? "Accept invitation"
                              : decision === "DECLINE"
                                ? "Decline"
                                : "Cancel invitation"}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                  {rivalry.status === "ACCEPTED" && (
                    <>
                      <p>
                        Weeks {rivalry.start_week}–18 · {rivalry.season} season
                      </p>
                      <div className="rivalry-scoreboard">
                        <div>
                          <span>YOU</span>
                          <strong>{recordText(rivalry.record)}</strong>
                          <small>
                            {points(rivalry.your_total)} season points
                          </small>
                        </div>
                        <div>
                          <span>@{rivalry.opponent.username}</span>
                          <strong>{recordText(rivalry.opponent_record)}</strong>
                          <small>
                            {points(rivalry.opponent_total)} season points
                          </small>
                        </div>
                      </div>
                      <Link
                        className="button primary"
                        href={`/head-to-head/${rivalry.id}/${rivalry.history.find((match) => match.week === week?.week)?.week ?? rivalry.history[0]?.week ?? rivalry.start_week}`}
                      >
                        View matchup
                      </Link>
                      <details>
                        <summary>Week-by-week matchup history</summary>
                        <div className="matchup-table-wrap">
                          <table className="matchup-table">
                            <caption className="sr-only">
                              Weekly scores against {rivalry.opponent.username}
                            </caption>
                            <thead>
                              <tr>
                                <th>Week</th>
                                <th>You</th>
                                <th>Opponent</th>
                                <th>Result</th>
                              </tr>
                            </thead>
                            <tbody>
                              {rivalry.history.map((match) => (
                                <tr key={match.week}>
                                  <th>
                                    <Link
                                      className="matchup-week-link"
                                      href={`/head-to-head/${rivalry.id}/${match.week}`}
                                      aria-label={`View Week ${match.week} matchup against ${rivalry.opponent.username}`}
                                    >
                                      Week {match.week} ↗
                                    </Link>
                                  </th>
                                  <td>
                                    {match.status === "UPCOMING"
                                      ? "—"
                                      : points(match.your_score)}
                                  </td>
                                  <td>
                                    {match.status === "UPCOMING"
                                      ? "—"
                                      : points(match.opponent_score)}
                                  </td>
                                  <td>{match.outcome || match.status}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </details>
                    </>
                  )}
                </section>
              ))}
            </div>
          </>
        )
      )}
    </>
  );
}
export default function HeadToHeadPage() {
  return (
    <RequireAuth>
      <HeadToHead />
    </RequireAuth>
  );
}
