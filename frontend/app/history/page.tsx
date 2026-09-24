"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { api, points } from "@/lib/api";
import type { Lineup } from "@/lib/types";
import {
  Empty,
  ErrorNotice,
  Loading,
  PageTitle,
  RequireAuth,
  TeamLogo,
} from "@/components/ui";

function History() {
  const query = useQuery({
    queryKey: ["history"],
    queryFn: () => api<Lineup[]>("/history"),
  });
  return (
    <>
      <PageTitle eyebrow="YOUR TRACK RECORD" title="Every call has a story.">
        Past picks, bold decisions, and the points to show for them.
      </PageTitle>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorNotice error={query.error} retry={query.refetch} />
      ) : !query.data?.length ? (
        <Empty
          title="Your story starts with one case"
          href="/play"
          action="Play this week"
        >
          Your completed lineups and game decisions will be waiting here.
        </Empty>
      ) : (
        <div className="history-grid">
          {query.data.map(
            ({ entry, slots }) =>
              entry && (
                <Link
                  className="panel history-card"
                  key={entry.id}
                  href={`/history/${entry.season}/${entry.week}`}
                >
                  <div className="history-card-top">
                    <span className="eyebrow">
                      {entry.season} REGULAR SEASON
                    </span>
                    <ArrowUpRight size={19} />
                  </div>
                  <h2>Week {entry.week.toString().padStart(2, "0")}</h2>
                  <div className="history-team-logos">
                    {slots
                      .filter((s) => s.player)
                      .map((s) => (
                        <TeamLogo
                          key={s.slot}
                          team={s.player!.team}
                          size={36}
                        />
                      ))}
                  </div>
                  <div className="history-score">
                    <strong>
                      {points(entry.score)}
                      <small>PPR POINTS</small>
                    </strong>
                    <span>
                      {entry.final_rank
                        ? `#${entry.final_rank} FINAL RANK`
                        : entry.status.replaceAll("_", " ")}
                    </span>
                  </div>
                </Link>
              ),
          )}
        </div>
      )}
    </>
  );
}
export default function HistoryPage() {
  return (
    <RequireAuth>
      <History />
    </RequireAuth>
  );
}
