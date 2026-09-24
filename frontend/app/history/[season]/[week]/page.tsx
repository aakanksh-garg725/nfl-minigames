"use client";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, points } from "@/lib/api";
import type { Lineup } from "@/lib/types";
import { ErrorNotice, Loading, PageTitle, RequireAuth } from "@/components/ui";
import { LineupCards } from "@/components/lineup";

function Detail({ season, week }: { season: string; week: string }) {
  const query = useQuery({
    queryKey: ["history", season, week],
    queryFn: () => api<Lineup>(`/history/${season}/${week}`),
  });
  if (query.isPending) return <Loading />;
  if (query.error || !query.data) return <ErrorNotice error={query.error} />;
  return (
    <>
      <PageTitle
        eyebrow={`${season} SEASON · YOUR HISTORY`}
        title={`Week ${week}, in the books.`}
      >
        {points(query.data.entry?.score)} actual PPR points ·{" "}
        {query.data.entry?.status}
        {query.data.entry?.final_rank
          ? ` · Final rank #${query.data.entry.final_rank}`
          : ""}
      </PageTitle>
      <LineupCards slots={query.data.slots} scored />
    </>
  );
}
export default function HistoryDetail({
  params,
}: {
  params: Promise<{ season: string; week: string }>;
}) {
  const { season, week } = use(params);
  return (
    <RequireAuth>
      <Detail season={season} week={week} />
    </RequireAuth>
  );
}
