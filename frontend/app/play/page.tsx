"use client";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowRight, Clock3 } from "lucide-react";
import { api, ApiError, easternTime, post } from "@/lib/api";
import type { DealGame, Profile } from "@/lib/types";
import { useWeek } from "@/components/providers";
import { ErrorNotice, Loading, PageTitle, RequireAuth } from "@/components/ui";
import { LineupCards, SlotProgress } from "@/components/lineup";

function PlayHub() {
  const { data: week, error, isPending, refetch } = useWeek();
  const router = useRouter();
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: async () => {
      if (!week?.next_slot) throw new Error("Your lineup is complete.");
      const profile = await api<Profile>("/profile");
      if (!profile.profile_complete) {
        router.push("/profile");
        return null;
      }
      return post<DealGame>("/deal-games", { slot: week.next_slot });
    },
    onSuccess: (game) => {
      if (game) {
        queryClient.setQueryData(["game", game.id], game);
        router.push(`/play/${game.id}`);
      }
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 428)
        router.push("/profile");
    },
  });
  if (isPending) return <Loading />;
  if (error || !week) return <ErrorNotice error={error} retry={refetch} />;
  const filled = week.slots.filter((s) => s.player).length;
  return (
    <>
      <PageTitle
        eyebrow={`WEEK ${week.week} · ${week.season} SEASON`}
        title="Build your Sunday."
      >
        Six spots. Six games. Every call is yours.
      </PageTitle>
      <div className="hub-banner panel">
        <div>
          <span className="eyebrow">
            {filled === 6 ? "LINEUP COMPLETE" : "YOUR NEXT MOVE"}
          </span>
          <h2>
            {filled === 6
              ? "Your six are set. Let’s play football."
              : `${week.next_slot} is waiting for you.`}
          </h2>
          <p>
            {filled === 6
              ? "Actual full-PPR points will determine your weekly score."
              : "Choose a case, hear the Dealer out, and lock in your player."}
          </p>
        </div>
        {filled === 6 ? (
          <Link href="/lineup" className="button primary">
            View my lineup <ArrowRight size={17} />
          </Link>
        ) : (
          <button
            className="button primary"
            disabled={start.isPending || !week.is_open || !week.data_ready}
            onClick={() => start.mutate()}
          >
            {start.isPending
              ? "Opening the vault…"
              : week.active_game_id
                ? "Resume your game"
                : `Play for ${week.next_slot}`}
            <ArrowRight size={17} />
          </button>
        )}
      </div>
      <ErrorNotice error={start.error} />
      {!week.is_open && (
        <div className="info-notice">
          This week’s lineup window is closed. New contests open Tuesday at 9 AM
          ET.
        </div>
      )}
      <SlotProgress slots={week.slots} current={week.next_slot} />
      <div className="section-subtitle">
        <h2>
          Your roster <span>{filled}/6 players</span>
        </h2>
        <span>
          <Clock3 size={14} /> Locks {easternTime(week.closes_at)}
        </span>
      </div>
      <LineupCards slots={week.slots} current={week.next_slot} />
    </>
  );
}
export default function PlayPage() {
  return (
    <RequireAuth>
      <PlayHub />
    </RequireAuth>
  );
}
