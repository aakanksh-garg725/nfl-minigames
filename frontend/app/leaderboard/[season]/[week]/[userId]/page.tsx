import { LeaderboardLineup } from "@/components/leaderboard-lineup";

export default async function PlayerLineupPage({
  params,
}: {
  params: Promise<{ season: string; week: string; userId: string }>;
}) {
  return <LeaderboardLineup {...await params} />;
}
