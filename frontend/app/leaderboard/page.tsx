"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Trophy } from "lucide-react";
import { api, points } from "@/lib/api";
import type { Leaderboard } from "@/lib/types";
import { useAuth, useWeek } from "@/components/providers";
import { Empty, ErrorNotice, Loading, PageTitle } from "@/components/ui";

export default function LeaderboardPage() {
  const current = useWeek();
  const auth = useAuth();
  const [tab, setTab] = useState("weekly");
  const [season, setSeason] = useState<number | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const year = season ?? current.data?.season;
  const selectedWeek = week ?? current.data?.week;
  const canViewLineups =
    tab === "weekly" &&
    year === current.data?.season &&
    selectedWeek === current.data?.week;
  const query = useQuery({
    queryKey: ["leaderboard", tab, year, selectedWeek],
    queryFn: () =>
      api<Leaderboard>(
        `/leaderboards/${tab}?season=${year}${tab === "weekly" ? `&week=${selectedWeek}` : ""}`,
      ),
    enabled: !!year && !!selectedWeek,
    refetchInterval: 30_000,
  });
  return (
    <>
      <PageTitle
        eyebrow="THE PROVING GROUND"
        title="Let the points talk."
        aside={<Trophy className="title-trophy" size={48} />}
      >
        Six players. Real performances. A place among the best.
      </PageTitle>
      <div className="leaderboard-controls">
        <div
          className="tab-group"
          role="tablist"
          aria-label="Leaderboard period"
        >
          <button
            role="tab"
            aria-selected={tab === "weekly"}
            className={tab === "weekly" ? "active" : ""}
            onClick={() => setTab("weekly")}
          >
            Weekly
          </button>
          <button
            role="tab"
            aria-selected={tab === "season"}
            className={tab === "season" ? "active" : ""}
            onClick={() => setTab("season")}
          >
            Season
          </button>
        </div>
        <div className="filter-group">
          <label>
            Season{" "}
            <input
              aria-label="Season"
              type="number"
              min={2020}
              max={2100}
              value={year || new Date().getFullYear()}
              onChange={(e) => setSeason(Number(e.target.value))}
            />
          </label>
          {tab === "weekly" && (
            <label>
              Week{" "}
              <select
                aria-label="Week"
                value={selectedWeek || 1}
                onChange={(e) => setWeek(Number(e.target.value))}
              >
                {Array.from({ length: 18 }, (_, i) => (
                  <option key={i + 1} value={i + 1}>
                    {i + 1}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>
      <ErrorNotice
        error={current.error || query.error}
        retry={() => {
          current.refetch();
          query.refetch();
        }}
      />
      {!current.error &&
        !query.error &&
        (query.isPending ? (
          <Loading label="Checking the standings…" />
        ) : !query.data?.rows.length ? (
          <Empty
            title="The top spot is up for grabs"
            href="/play"
            action="Build your lineup"
          >
            {tab === "season"
              ? "Season standings include finalized weeks. Check back after the first week is final."
              : "Complete all six lineup slots before the deadline to join the weekly standings."}
          </Empty>
        ) : (
          <div className="panel leaderboard-panel">
            <div className="leaderboard-header">
              <h2>
                {tab === "weekly"
                  ? `Week ${selectedWeek} standings`
                  : `${year} season standings`}
              </h2>
              <span
                className={`status-pill ${query.data.status === "LIVE" ? "open" : ""}`}
              >
                <span />
                {tab === "season" ? "FINALIZED WEEKS" : query.data.status}
              </span>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>RANK</th>
                    <th>PLAYER</th>
                    {tab === "weekly" && (
                      <th className="align-right">PROJECTED PPR</th>
                    )}
                    {tab === "season" && (
                      <>
                        <th>WEEKS</th>
                        <th>AVG. PPR</th>
                      </>
                    )}
                    <th className="align-right">
                      {tab === "weekly" ? "ACTUAL PPR" : "TOTAL PPR"}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.rows.map((row) => (
                    <tr
                      key={row.user_id}
                      className={
                        row.user_id === auth.user?.id ? "your-row" : ""
                      }
                    >
                      <td>
                        <span className={`table-rank rank-${row.rank}`}>
                          {row.rank <= 3 ? <Trophy size={17} /> : null}
                          {row.rank}
                        </span>
                      </td>
                      <td>
                        <div className="leaderboard-user">
                          <span className="avatar">
                            {(row.display_name || row.username)
                              .slice(0, 2)
                              .toUpperCase()}
                          </span>
                          <div>
                            {canViewLineups ? (
                              <Link
                                className="leaderboard-lineup-link"
                                href={`/leaderboard/${year}/${selectedWeek}/${encodeURIComponent(row.user_id)}`}
                                aria-label={`View @${row.username}'s Week ${selectedWeek} lineup`}
                              >
                                <strong>
                                  {row.display_name || row.username}
                                </strong>
                                <span>View lineup ↗</span>
                              </Link>
                            ) : (
                              <strong>
                                {row.display_name || row.username}
                              </strong>
                            )}
                            <small>@{row.username}</small>
                          </div>
                        </div>
                      </td>
                      {tab === "season" && (
                        <>
                          <td>{row.weeks_played}</td>
                          <td>{points(row.average)}</td>
                        </>
                      )}
                      {tab === "weekly" && (
                        <td className="align-right">
                          {points(row.projected_score)}
                        </td>
                      )}
                      <td className="align-right table-score">
                        {points(row.score)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="panel-foot">
              <span>
                {canViewLineups
                  ? "Select a player to view their current-week lineup."
                  : "Equal points share the same rank."}
              </span>
              <span>Full PPR · Ranked by actual points</span>
            </div>
          </div>
        ))}
    </>
  );
}
