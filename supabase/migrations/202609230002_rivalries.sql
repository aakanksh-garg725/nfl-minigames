CREATE TABLE public.rivalries (
  id varchar(36) PRIMARY KEY,
  season integer NOT NULL,
  user_low varchar(36) NOT NULL REFERENCES public.profiles(user_id),
  user_high varchar(36) NOT NULL REFERENCES public.profiles(user_id),
  invited_by varchar(36) NOT NULL REFERENCES public.profiles(user_id),
  status varchar(16) NOT NULL DEFAULT 'PENDING',
  start_week integer,
  created_at timestamptz NOT NULL,
  accepted_at timestamptz,
  UNIQUE(season, user_low, user_high),
  CHECK(user_low < user_high),
  CHECK(invited_by IN (user_low, user_high)),
  CHECK(status IN ('PENDING','ACCEPTED','DECLINED','CANCELED')),
  CHECK(start_week IS NULL OR start_week BETWEEN 1 AND 18)
);
CREATE INDEX ix_rivalries_season ON public.rivalries(season);
CREATE INDEX ix_rivalries_user_low ON public.rivalries(user_low);
CREATE INDEX ix_rivalries_user_high ON public.rivalries(user_high);
CREATE TABLE public.rivalry_matchups (
  id varchar(36) PRIMARY KEY,
  rivalry_id varchar(36) NOT NULL REFERENCES public.rivalries(id),
  week integer NOT NULL CHECK(week BETWEEN 1 AND 18),
  status varchar(16) NOT NULL DEFAULT 'UPCOMING',
  low_score numeric(12,3) NOT NULL DEFAULT 0,
  high_score numeric(12,3) NOT NULL DEFAULT 0,
  winner_id varchar(36) REFERENCES public.profiles(user_id),
  updated_at timestamptz NOT NULL,
  UNIQUE(rivalry_id, week),
  CHECK(status IN ('UPCOMING','LIVE','FINAL'))
);
CREATE INDEX ix_rivalry_matchups_rivalry_id ON public.rivalry_matchups(rivalry_id);
ALTER TABLE public.rivalries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rivalry_matchups ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.rivalries, public.rivalry_matchups FROM anon, authenticated;
-- All reads and writes go through participant-authorized FastAPI endpoints.
