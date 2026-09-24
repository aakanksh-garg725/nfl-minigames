"use client";
import { useQuery } from "@tanstack/react-query";
import { api, points } from "@/lib/api";
import type { Lineup } from "@/lib/types";
import { useWeek } from "@/components/providers";
import {
  Empty,
  ErrorNotice,
  Loading,
  PageTitle,
  RequireAuth,
} from "@/components/ui";
import { LineupCards } from "@/components/lineup";

function CurrentLineup() {
  const week = useWeek();
  const query = useQuery({
    queryKey: ["lineup"],
    queryFn: () => api<Lineup>("/lineup/current"),
    refetchInterval: 30_000,
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return <ErrorNotice error={query.error} retry={query.refetch} />;
  const data = query.data;
  return (
    <>
      <PageTitle
        eyebrow={
          week.data
            ? `WEEK ${week.data.week} · ${week.data.season}`
            : "YOUR WEEKLY SIX"
        }
        title="This is your Sunday."
      >
        Your calls are made. Now it’s their turn.
      </PageTitle>
      {!data?.entry ? (
        <Empty
          title="Your roster is waiting"
          href="/play"
          action="Build my lineup"
        >
          Play six games to assemble your weekly team.
        </Empty>
      ) : (
        <>
          <div className="score-summary panel">
            <div>
              <span className="eyebrow">ACTUAL FULL-PPR POINTS</span>
              <strong>{points(data.entry.score)}</strong>
            </div>
            <div>
              <small>TOTAL PROJECTED PPR</small>
              <strong>
                {points(
                  data.slots.reduce(
                    (total, slot) => total + (slot.player?.projection ?? 0),
                    0,
                  ),
                )}
              </strong>
            </div>
            <div>
              <small>WEEKLY RANK</small>
              <strong>{data.rank ? `#${data.rank}` : "—"}</strong>
            </div>
            <div>
              <small>LINEUP STATUS</small>
              <span className="status-pill open">
                {data.entry.status.replaceAll("_", " ")}
              </span>
              <p>{data.slots.filter((s) => s.player).length}/6 spots filled</p>
            </div>
          </div>
          <LineupCards
            slots={data.slots}
            current={week.data?.next_slot}
            scored
          />
          <p className="footnote">
            Scores refresh automatically. Live results are provisional until the
            week is finalized.
          </p>
        </>
      )}
    </>
  );
}
export default function LineupPage() {
  return (
    <RequireAuth>
      <CurrentLineup />
    </RequireAuth>
  );
}
