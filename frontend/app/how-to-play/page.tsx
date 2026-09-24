import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PageTitle } from "@/components/ui";
export default function RulesPage() {
  return (
    <>
      <PageTitle
        eyebrow="THE PLAYBOOK"
        title="A good lineup starts with a good call."
      >
        Everything you need to know before opening your first case.
      </PageTitle>
      <div className="rules-grid">
        {[
          [
            "01",
            "Build your six",
            "Play one game for each slot: RB1, RB2, WR1, WR2, TE, and FLEX, in that order. FLEX can be an RB, WR, or TE. A player can only appear once in your lineup.",
          ],
          [
            "02",
            "Choose your case",
            "Players projected for at least 3.0 points are ranked and split into 10 tiers. Each tier contributes one player, with an additional unique player from tier 2 and tier 4, for 12 jerseys total. Pick one numbered case to keep sealed. Only the server knows who is inside.",
          ],
          [
            "03",
            "Open. Consider. Decide.",
            "Open 4 cases, then hear the first offer. Say NO DEAL to open 3 more, then 2, then 1. After each round, the Dealer offers a real player. A DEAL immediately locks that player into your slot.",
          ],
          [
            "04",
            "Keep it or swap it",
            "Turn down all four offers and two cases remain. Keep your original case or swap for the other. The player in your final case joins your lineup.",
          ],
          [
            "05",
            "Beat the clock",
            "The weekly contest opens Tuesday at 9 AM ET and closes Sunday at 1 PM ET. Players become unavailable at their real NFL kickoff. In-progress games expire at the earliest relevant kickoff; unfinished slots can restart before the weekly deadline.",
          ],
          [
            "06",
            "Let football settle it",
            "Projections set the board and value Dealer offers. Your leaderboard score is the sum of your six players’ actual full-PPR points. Finish all six slots to qualify. Ties share a rank. Season standings sum finalized weeks.",
          ],
        ].map(([number, title, text]) => (
          <section className="panel rule-card" key={number}>
            <span>{number}</span>
            <h2>{title}</h2>
            <p>{text}</p>
          </section>
        ))}
      </div>
      <div className="rules-fine panel">
        <h2>A few things worth knowing</h2>
        <p>
          Both jerseys and Dealer offers require at least 3.0 projected full-PPR
          points. The Dealer can select from the full eligible pool across all
          10 tiers. Every player on your board is unique.
        </p>
        <p>
          Starting a game freezes its projections. A later injury or projection
          update does not change your board. The Dealer may offer a player who
          isn’t on your board—or one whose case has already been opened. A
          declined player won’t be offered again in that game.
        </p>
        <p>
          Full-PPR scoring: 1 point per reception, 0.1 per rushing/receiving
          yard, 6 per rushing/receiving touchdown, 4 per passing touchdown, 0.04
          per passing yard, −2 per interception or lost fumble, 2 per two-point
          conversion, and 6 per return touchdown. Stat corrections may change
          scores.
        </p>
        <Link href="/play" className="button primary">
          I’m ready. Let’s play.
          <ArrowRight size={17} />
        </Link>
      </div>
    </>
  );
}
