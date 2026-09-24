import { RivalryMatchup } from "@/components/rivalry-matchup";

export default async function MatchupPage({
  params,
}: {
  params: Promise<{ id: string; week: string }>;
}) {
  const { id, week } = await params;
  return <RivalryMatchup id={id} week={week} />;
}
