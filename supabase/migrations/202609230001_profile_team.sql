-- Additive: preserve existing accounts, lineups, and historical identity references.
ALTER TABLE public.profiles ADD COLUMN favorite_team varchar(3);
ALTER TABLE public.profiles ADD CONSTRAINT favorite_team_valid CHECK (
  favorite_team IS NULL OR favorite_team IN (
    'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB',
    'HOU','IND','JAX','KC','LV','LAC','LAR','MIA','MIN','NE','NO','NYG',
    'NYJ','PHI','PIT','SF','SEA','TB','TEN','WAS'
  )
);
