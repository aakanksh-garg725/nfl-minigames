export const SLOTS = ["RB1", "RB2", "WR1", "WR2", "TE", "FLEX"] as const;
export type Slot = (typeof SLOTS)[number];
export type Player = {
  id: string;
  name: string;
  team: string;
  position: string;
  projection: number;
  opponent?: string | null;
  is_home?: boolean | null;
  board_rank?: number;
  eliminated?: boolean;
};
export type Case = {
  case_number: number;
  status: string;
  is_user_case: boolean;
  player?: Player;
};
export type Offer = {
  offer_number: number;
  decision: "PENDING" | "DEAL" | "NO_DEAL";
  player: Player;
};
export type DealGame = {
  id: string;
  slot: Slot;
  status: string;
  version: number;
  expires_at: string;
  current_round: number;
  round_open_count: number;
  selected_case_number: number | null;
  board: Player[];
  cases: Case[];
  offers: Offer[];
  instruction: string;
  outcome: string | null;
  awarded_player: Player | null;
};
export type LineupSlot = {
  slot: Slot;
  player: Player | null;
  actual_ppr: number;
  game_status: string;
  acquisition_method: string | null;
  deal_game_id: string | null;
  opponent?: string | null;
  is_home?: boolean | null;
  kickoff_at?: string;
};
export type Entry = {
  id: string;
  season: number;
  week: number;
  status: string;
  score: number;
  final_rank: number | null;
};
export type Lineup = {
  entry: Entry | null;
  slots: LineupSlot[];
  rank?: number | null;
};
export type Week = Lineup & {
  season: number;
  week: number;
  opens_at: string;
  closes_at: string;
  status: string;
  is_open: boolean;
  data_ready: boolean;
  next_slot: Slot | null;
  active_game_id: string | null;
  mode: string;
};
export type Leaderboard = {
  season: number;
  week?: number;
  status: string;
  rows: {
    rank: number;
    user_id: string;
    username: string;
    display_name: string;
    score: number;
    weeks_played: number;
    average?: number;
  }[];
};
export type Profile = {
  user_id: string;
  username: string;
  display_name: string;
  favorite_team: string | null;
  profile_complete: boolean;
  teams: { code: string; name: string }[];
  is_admin: boolean;
};
