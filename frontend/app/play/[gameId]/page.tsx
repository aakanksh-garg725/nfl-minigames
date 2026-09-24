"use client";
import { use } from "react";
import { GameView } from "@/components/game";
import { RequireAuth } from "@/components/ui";
export default function GamePage({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  const { gameId } = use(params);
  return (
    <RequireAuth>
      <GameView gameId={gameId} />
    </RequireAuth>
  );
}
