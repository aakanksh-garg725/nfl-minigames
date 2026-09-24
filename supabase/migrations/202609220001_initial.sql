-- Generated initial schema. Applied atomically; never drops existing tables.


CREATE TABLE nfl_games (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(24) NOT NULL, 
	provider_game_id VARCHAR(40) NOT NULL, 
	season INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	home_team VARCHAR(8) NOT NULL, 
	away_team VARCHAR(8) NOT NULL, 
	kickoff_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (provider, provider_game_id)
)

;

CREATE INDEX ix_nfl_games_season ON nfl_games (season);

ALTER TABLE public."nfl_games" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."nfl_games" FROM anon, authenticated;


CREATE TABLE nfl_weeks (
	id VARCHAR(36) NOT NULL, 
	season INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	opens_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	closes_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	scoring_status VARCHAR(16) NOT NULL, 
	projection_snapshot_id VARCHAR(36), 
	PRIMARY KEY (id), 
	UNIQUE (season, week)
)

;

ALTER TABLE public."nfl_weeks" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."nfl_weeks" FROM anon, authenticated;


CREATE TABLE players (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(24) NOT NULL, 
	provider_player_id VARCHAR(40) NOT NULL, 
	full_name VARCHAR(100) NOT NULL, 
	first_name VARCHAR(60) NOT NULL, 
	last_name VARCHAR(60) NOT NULL, 
	position VARCHAR(8) NOT NULL, 
	fantasy_positions JSON NOT NULL, 
	team VARCHAR(8) NOT NULL, 
	active BOOLEAN NOT NULL, 
	jersey_number INTEGER, 
	provider_metadata JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (provider, provider_player_id)
)

;

ALTER TABLE public."players" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."players" FROM anon, authenticated;


CREATE TABLE profiles (
	user_id VARCHAR(36) NOT NULL, 
	username VARCHAR(24) NOT NULL, 
	display_name VARCHAR(60) NOT NULL, 
	avatar_url TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id), 
	UNIQUE (username)
)

;

ALTER TABLE public."profiles" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."profiles" FROM anon, authenticated;


CREATE TABLE projection_snapshots (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(24) NOT NULL, 
	season INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	source_version VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id)
)

;

ALTER TABLE public."projection_snapshots" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."projection_snapshots" FROM anon, authenticated;


CREATE TABLE provider_runs (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(24) NOT NULL, 
	operation VARCHAR(32) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	message TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

ALTER TABLE public."provider_runs" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."provider_runs" FROM anon, authenticated;


CREATE TABLE rate_buckets (
	key VARCHAR(100) NOT NULL, 
	"window" INTEGER NOT NULL, 
	count INTEGER NOT NULL, 
	PRIMARY KEY (key)
)

;

ALTER TABLE public."rate_buckets" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."rate_buckets" FROM anon, authenticated;


CREATE TABLE player_week_projections (
	id VARCHAR(36) NOT NULL, 
	snapshot_id VARCHAR(36) NOT NULL, 
	player_id VARCHAR(36) NOT NULL, 
	season INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	position VARCHAR(8) NOT NULL, 
	team VARCHAR(8) NOT NULL, 
	opponent VARCHAR(8) NOT NULL, 
	nfl_game_id VARCHAR(36) NOT NULL, 
	kickoff_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	projected_ppr NUMERIC(10, 3) NOT NULL, 
	raw_payload JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (snapshot_id, player_id), 
	FOREIGN KEY(snapshot_id) REFERENCES projection_snapshots (id), 
	FOREIGN KEY(player_id) REFERENCES players (id), 
	FOREIGN KEY(nfl_game_id) REFERENCES nfl_games (id)
)

;

CREATE INDEX projection_pool_idx ON player_week_projections (snapshot_id, position, projected_ppr);

ALTER TABLE public."player_week_projections" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."player_week_projections" FROM anon, authenticated;


CREATE TABLE player_week_results (
	id VARCHAR(36) NOT NULL, 
	player_id VARCHAR(36) NOT NULL, 
	season INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	actual_ppr NUMERIC(10, 3) NOT NULL, 
	game_status VARCHAR(24) NOT NULL, 
	provider VARCHAR(24) NOT NULL, 
	fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	raw_payload JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (player_id, season, week), 
	FOREIGN KEY(player_id) REFERENCES players (id)
)

;

ALTER TABLE public."player_week_results" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."player_week_results" FROM anon, authenticated;


CREATE TABLE weekly_entries (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	game_type VARCHAR(24) NOT NULL, 
	season INTEGER NOT NULL, 
	week INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	actual_score NUMERIC(10, 3) NOT NULL, 
	final_rank INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, season, week, game_type), 
	FOREIGN KEY(user_id) REFERENCES profiles (user_id)
)

;

CREATE INDEX ix_weekly_entries_user_id ON weekly_entries (user_id);

ALTER TABLE public."weekly_entries" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."weekly_entries" FROM anon, authenticated;


CREATE TABLE deal_games (
	id VARCHAR(36) NOT NULL, 
	entry_id VARCHAR(36) NOT NULL, 
	slot VARCHAR(8) NOT NULL, 
	projection_snapshot_id VARCHAR(36) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	selected_case_number INTEGER, 
	current_round INTEGER NOT NULL, 
	round_open_count INTEGER NOT NULL, 
	outcome VARCHAR(16), 
	awarded_player_id VARCHAR(36), 
	seed VARCHAR(128) NOT NULL, 
	seed_hash VARCHAR(64) NOT NULL, 
	algorithm_version VARCHAR(30) NOT NULL, 
	candidate_ids JSON NOT NULL, 
	version INTEGER NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES weekly_entries (id), 
	FOREIGN KEY(projection_snapshot_id) REFERENCES projection_snapshots (id), 
	FOREIGN KEY(awarded_player_id) REFERENCES players (id)
)

;

CREATE INDEX game_entry_slot_idx ON deal_games (entry_id, slot);

ALTER TABLE public."deal_games" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."deal_games" FROM anon, authenticated;


CREATE TABLE lineup_slots (
	id VARCHAR(36) NOT NULL, 
	entry_id VARCHAR(36) NOT NULL, 
	slot VARCHAR(8) NOT NULL, 
	player_id VARCHAR(36), 
	projection_when_acquired NUMERIC(10, 3), 
	acquisition_method VARCHAR(16), 
	deal_game_id VARCHAR(36), 
	PRIMARY KEY (id), 
	UNIQUE (entry_id, slot), 
	UNIQUE (entry_id, player_id), 
	FOREIGN KEY(entry_id) REFERENCES weekly_entries (id), 
	FOREIGN KEY(player_id) REFERENCES players (id)
)

;

CREATE INDEX ix_lineup_slots_entry_id ON lineup_slots (entry_id);

ALTER TABLE public."lineup_slots" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."lineup_slots" FROM anon, authenticated;


CREATE TABLE deal_game_cases (
	id VARCHAR(36) NOT NULL, 
	deal_game_id VARCHAR(36) NOT NULL, 
	case_number INTEGER NOT NULL, 
	player_id VARCHAR(36) NOT NULL, 
	tier_number INTEGER NOT NULL, 
	full_pool_rank INTEGER NOT NULL, 
	board_rank INTEGER NOT NULL, 
	projection NUMERIC(10, 3) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	opened_order INTEGER, 
	opened_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (deal_game_id, case_number), 
	UNIQUE (deal_game_id, player_id), 
	FOREIGN KEY(deal_game_id) REFERENCES deal_games (id), 
	FOREIGN KEY(player_id) REFERENCES players (id)
)

;

CREATE INDEX ix_deal_game_cases_deal_game_id ON deal_game_cases (deal_game_id);

ALTER TABLE public."deal_game_cases" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."deal_game_cases" FROM anon, authenticated;


CREATE TABLE deal_game_events (
	id VARCHAR(36) NOT NULL, 
	deal_game_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	event_type VARCHAR(40) NOT NULL, 
	payload JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(deal_game_id) REFERENCES deal_games (id)
)

;

CREATE INDEX ix_deal_game_events_deal_game_id ON deal_game_events (deal_game_id);

ALTER TABLE public."deal_game_events" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."deal_game_events" FROM anon, authenticated;


CREATE TABLE deal_game_offers (
	id VARCHAR(36) NOT NULL, 
	deal_game_id VARCHAR(36) NOT NULL, 
	offer_number INTEGER NOT NULL, 
	cases_remaining INTEGER NOT NULL, 
	expected_value NUMERIC(14, 6) NOT NULL, 
	ev_multiplier NUMERIC(8, 5) NOT NULL, 
	target_projection NUMERIC(14, 6) NOT NULL, 
	offered_player_id VARCHAR(36) NOT NULL, 
	offered_player_projection NUMERIC(10, 3) NOT NULL, 
	decision VARCHAR(16) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (deal_game_id, offer_number), 
	FOREIGN KEY(deal_game_id) REFERENCES deal_games (id), 
	FOREIGN KEY(offered_player_id) REFERENCES players (id)
)

;

CREATE INDEX ix_deal_game_offers_deal_game_id ON deal_game_offers (deal_game_id);

ALTER TABLE public."deal_game_offers" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public."deal_game_offers" FROM anon, authenticated;

GRANT SELECT ON public.profiles TO authenticated;

CREATE POLICY profiles_own_read ON public.profiles FOR SELECT TO authenticated USING (auth.uid()::text = user_id);

GRANT SELECT ON public.weekly_entries TO authenticated;

CREATE POLICY entries_own_read ON public.weekly_entries FOR SELECT TO authenticated USING (auth.uid()::text = user_id);

CREATE INDEX active_game_lookup ON public.deal_games(entry_id, slot) WHERE status NOT IN ('COMPLETE', 'EXPIRED');

ALTER TABLE public.profiles ADD CONSTRAINT username_valid CHECK (username ~ '^[a-z0-9_]{3,24}$');

ALTER TABLE public.nfl_weeks ADD CONSTRAINT week_valid CHECK (week BETWEEN 1 AND 18 AND opens_at < closes_at);

ALTER TABLE public.deal_game_cases ADD CONSTRAINT case_number_valid CHECK (case_number BETWEEN 1 AND 12);

ALTER TABLE public.lineup_slots ADD CONSTRAINT slot_valid CHECK (slot IN ('RB1','RB2','WR1','WR2','TE','FLEX'));

REVOKE ALL ON public.sunday_vault_migrations FROM anon, authenticated;

ALTER TABLE public.sunday_vault_migrations ENABLE ROW LEVEL SECURITY;
