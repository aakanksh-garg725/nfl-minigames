# NFL Fantasy Football Deal or No Deal
## Production Requirements & Technical Implementation Specification

**Document purpose:** Production-ready handoff for Claude Code  
**Version:** 1.0  
**Product:** NFL weekly fantasy minigame platform  
**First minigame:** Fantasy Football Deal or No Deal  
**Primary scoring:** Full PPR  
**Frontend:** Next.js + TypeScript + Tailwind CSS  
**Backend:** FastAPI + Python  
**Database/Auth:** Supabase Postgres + Supabase Auth  
**Status:** V1 specification

---

# 1. Product Overview

Build a web application centered around repeatable NFL fantasy football minigames. The first game is a fantasy-football adaptation of *Deal or No Deal*.

Each NFL week, a logged-in user constructs a six-player fantasy lineup by playing six separate Deal-or-No-Deal-style games. Rather than cases containing dollar values, each case contains an NFL skill-position player. The player pool is generated from the week's projected full-PPR fantasy points.

The user is trying to assemble the strongest possible lineup while deciding whether to accept a guaranteed player offered by the Dealer or continue opening cases in hopes that their selected case contains a better player.

The player's **weekly projection is used only to build and play the minigame**. The user's leaderboard score is determined by each selected player's **actual full-PPR fantasy points scored during that NFL week**.

The platform must be architected so additional NFL minigames can be added later without rebuilding authentication, player data ingestion, weekly scoring, accounts, history, or leaderboards.

---

# 2. Core Product Goals

V1 must:

1. Let users create an account and maintain a public leaderboard identity.
2. Open a new weekly game every Tuesday at 9:00 AM America/New_York.
3. Let each user build exactly one weekly six-player lineup.
4. Use six independent Deal-or-No-Deal subgames to fill the lineup.
5. Generate 12-player case boards using the entire eligible weekly player pool split into 12 projection tiers.
6. Use a Dealer offer algorithm calibrated to historical U.S. *Deal or No Deal* banker behavior.
7. Convert every numeric Dealer offer target into a real NFL player.
8. Track actual full-PPR points as NFL games are played.
9. Show a live/final weekly leaderboard.
10. Show a season leaderboard and each user's weekly history.
11. Prevent client-side discovery or manipulation of hidden case assignments.
12. Support projection/stat provider replacement without changing game logic.

---

# 3. V1 Lineup

Each weekly lineup contains exactly six players:

| Slot | Eligible positions |
|---|---|
| RB1 | RB |
| RB2 | RB |
| WR1 | WR |
| WR2 | WR |
| TE | TE |
| FLEX | RB / WR / TE |

There are intentionally no QB, K, or DST slots.

Recommended V1 slot order:

1. RB1
2. RB2
3. WR1
4. WR2
5. TE
6. FLEX

The user completes one Deal-or-No-Deal game for each slot.

A player already acquired by the user in the current weekly lineup is excluded from all later case pools and Dealer offers.

The FLEX pool combines all eligible RBs, WRs, and TEs into one ranked list and applies the same 12-tier selection algorithm as the position-specific pools.

---

# 4. Weekly Availability and Player Locking

## 4.1 Weekly window

The weekly contest opens:

**Tuesday at 9:00 AM America/New_York**

The weekly contest closes:

**Sunday at 1:00 PM America/New_York**

The entire six-player lineup must be completed before the Sunday 1:00 PM ET deadline to be leaderboard-eligible.

Use timezone-aware datetimes. Do not store naive local timestamps. Store UTC in the database and convert to `America/New_York` for rule evaluation/display.

## 4.2 NFL game kickoff locks

A player becomes ineligible for any newly created case pool or Dealer offer as soon as that player's real NFL game kicks off.

This naturally handles:

- Thursday Night Football
- Saturday games
- international Sunday morning games
- Sunday 1 PM games
- unusual schedule changes

Example:

- User plays Tuesday: Thursday players may still be eligible.
- User starts a new subgame Friday: players from Thursday's completed game are excluded.
- User starts Sunday at 10:00 AM: players from a 9:30 AM international game are excluded.
- No new actions are allowed once the global Sunday 1:00 PM ET contest deadline is reached.

## 4.3 In-progress subgame expiration

Every Deal subgame is created from a frozen projection/player snapshot.

Set:

`subgame.expires_at = min(global_week_deadline, earliest_kickoff_among_any_player_that_can_affect_the_subgame)`

At minimum this must include the 12 case players. Preferably include the active Dealer candidate pool as well.

If the subgame expires before completion:

- Do not award a player.
- Mark the subgame `EXPIRED`.
- If the global weekly deadline has not passed, allow the user to restart that lineup slot using currently eligible players.
- The new game receives a fresh case board.

This prevents a user from starting before Thursday kickoff, waiting to see the Thursday result, and then completing a game containing a Thursday player afterward.

---

# 5. Player Data and Projection Eligibility

## 5.1 Required player fields

Normalize provider data into an internal `players` table containing at least:

- internal player UUID
- provider player ID(s)
- full name
- first name
- last name
- NFL team abbreviation
- primary fantasy position
- eligible fantasy positions
- active status
- jersey number if available
- team logo URL or team identifier
- provider metadata JSON

## 5.2 Weekly projection record

Each player-week projection must contain:

- season
- NFL week
- player ID
- projected full-PPR points
- projection provider
- fetched_at
- projection_snapshot_id
- opponent
- kickoff_at
- NFL game ID
- source payload JSON for debugging

Only players with:

`projected_ppr_points > 0`

are eligible for a case/Dealer pool, subject to position and kickoff rules.

## 5.3 Projection snapshots

Do not read changing projections directly while a game is being played.

When a user starts a lineup-slot subgame:

1. Resolve the most recent successful projection snapshot.
2. Filter for currently eligible players.
3. Freeze the selected snapshot ID onto the subgame.
4. Use that same snapshot for:
   - ranking players,
   - tier creation,
   - case selection,
   - case-board display projections,
   - Dealer EV,
   - Dealer-player matching.

This ensures a projection update cannot alter the value of an active game.

---

# 6. Creating the 12-Player Case Board

This is a core game rule and should be implemented as a pure, well-tested service function.

## 6.1 Build eligible pool

For a slot:

### RB1 / RB2
Include all eligible RBs.

### WR1 / WR2
Include all eligible WRs.

### TE
Include all eligible TEs.

### FLEX
Include all eligible RBs + WRs + TEs together.

For every slot exclude:

- players with projection <= 0
- players already in the user's weekly lineup
- players whose NFL game has already kicked off
- invalid/deactivated player records

Do not manually filter players because they are injured if the provider still gives them a projection greater than zero. The projection feed is the source of truth for V1 eligibility.

## 6.2 Sort

Sort eligible players by:

1. projected PPR points descending
2. stable player ID ascending as deterministic tiebreaker

## 6.3 Split the entire pool into twelfths

Split the full sorted list into 12 contiguous, approximately equal buckets.

Use `numpy.array_split` behavior or equivalent.

Example with 72 RBs:

- Tier 1 = ranks 1-6
- Tier 2 = ranks 7-12
- ...
- Tier 12 = ranks 67-72

Example with 77 players:

- The first buckets will contain one more player than later buckets as needed.
- Every eligible player must belong to exactly one tier.
- No player can occur in multiple tiers.

This is **not** "select the top 12 players."

## 6.4 Select one player per tier

Randomly select exactly one player from each of the 12 tiers.

The 12 selected players become the game's prize board.

Persist for each selected player:

- tier number 1-12
- source rank in full eligible pool
- projection
- player ID
- snapshot ID

## 6.5 Rank the selected 12 for display

After selection, sort the chosen 12 again by projected points descending.

Assign:

`board_rank = 1..12`

This displayed rank is different from the source tier number.

The left-side board shows the 12 selected players in this display order.

## 6.6 Assign players to hidden cases

Generate 12 case numbers:

`1..12`

Shuffle the 12 selected players and assign exactly one to each case.

The mapping must exist only on the server/database.

Never return the hidden `case_number -> player_id` mapping to the client before a case is legitimately revealed.

---

# 7. Randomness and Reproducibility

Use server-side cryptographically secure randomness.

Recommended:

- Python `secrets` for seed creation
- seeded local `random.Random(seed)` for reproducible tier selection and case shuffling after seed creation

For each subgame store:

- random seed encrypted or server-only, OR
- seed value in a backend-only table
- seed hash for audit
- algorithm version

Do not expose the seed or hidden player IDs to the browser.

Every game action should be reproducible from the stored server state for debugging/admin audit.

---

# 8. Deal-or-No-Deal Game Flow

There are 12 cases.

## 8.1 Initial case selection

The user first selects one case as "My Case."

That case stays sealed throughout normal elimination rounds.

State:

`AWAITING_CASE_SELECTION -> ROUND_1`

## 8.2 Round schedule

The user then eliminates cases in this exact sequence:

| Offer round | Cases opened during round | Total cases remaining afterward | Dealer offer |
|---|---:|---:|---|
| Round 1 | 4 | 8 | Yes |
| Round 2 | 3 | 5 | Yes |
| Round 3 | 2 | 3 | Yes |
| Round 4 | 1 | 2 | Yes |

The cases remaining count includes the user's selected case.

After every required group of eliminations, stop case selection and present the Dealer offer.

The user cannot open extra cases.

## 8.3 Open-case behavior

When a non-user case is clicked:

1. Validate game state on backend.
2. Validate this case is unopened.
3. Validate it is not the user's selected case.
4. Reveal the player stored in that case.
5. Mark the case opened/eliminated.
6. Mark that player's row on the left prize board as eliminated/dimmed.
7. Increment the round's opened-case count.
8. If the round opening quota is reached, immediately transition to Dealer-offer state.

Case reveals should happen one at a time so the UI can animate each reveal.

## 8.4 Dealer decision

At each offer:

**DEAL**
- User receives the offered NFL player.
- Add that player to the current lineup slot.
- Mark the subgame complete with outcome `DEAL`.
- Optionally reveal "What was in your case?" on the completion screen.
- Proceed to next lineup slot.

**NO DEAL**
- Mark offer declined.
- Move to the next elimination round.
- After the fourth offer, declining transitions to final keep/swap choice.

## 8.5 Final two cases

If the fourth Dealer offer is rejected, exactly two cases remain:

- the user's original case
- one other unopened case

Ask:

**Keep Your Case** or **Swap Cases**

### Keep
Award the player in the user's original case.

### Swap
Award the player in the other remaining case.

Reveal both cases after the selection and save the complete result.

Outcome values:

- `FINAL_KEEP`
- `FINAL_SWAP`

---

# 9. Dealer Offer Research and V1 Algorithm

## 9.1 Important research conclusion

There is no publicly documented exact NBC production formula that can truthfully be described as the one official Banker formula.

However, published research analyzing the American NBC television version shows a strong relationship between:

1. the expected value of the remaining cases, and
2. the round/cases remaining.

A 2010 paper by David Ritcey and Pritam Ranjan, *Statistical Models for the Banker's Offer in Deal or No Deal*, fit a proportion-based model to American television episodes.

For the U.S. television sample, estimated average Banker offers were:

- Round 4: 50.88% of EV
- Round 6: 73.52% of EV
- Round 8: 92.77% of EV
- Round 9: 95.64% of EV

The original U.S. game has exactly:

- 8 cases remaining after Round 4
- 5 cases remaining after Round 6
- 3 cases remaining after Round 8
- 2 cases remaining after Round 9

Our custom game reaches exactly those same four remaining-case counts.

Therefore V1 should map the offer percentage by **number of cases remaining**, giving a historically calibrated U.S.-TV-style Banker without falsely claiming access to a secret production formula.

## 9.2 Expected value calculation

At offer time, define:

`remaining_cases = all unopened cases including My Case`

For each remaining case, use the frozen projected full-PPR points for the player behind it.

Then:

```text
EV = sum(remaining_case_projections) / number_of_remaining_cases
```

## 9.3 V1 Dealer coefficients

Use this exact configuration:

```python
DEALER_EV_MULTIPLIER = {
    8: 0.5088,
    5: 0.7352,
    3: 0.9277,
    2: 0.9564,
}
```

Then:

```python
target_offer_projection = EV * DEALER_EV_MULTIPLIER[cases_remaining]
```

Round target to two decimal places for logging only.

Do not show the hidden EV or multiplier to the user during normal gameplay.

## 9.4 Converting the numeric offer into a real player

The Dealer never offers abstract fantasy points. The Dealer offers a real eligible NFL player.

Build a Dealer candidate pool from the same frozen projection snapshot.

Candidate rules:

- projection > 0
- correct slot eligibility
- NFL game has not kicked off as of subgame creation
- not already on the user's weekly lineup
- not previously offered by the Dealer in this same subgame

A Dealer candidate **may be one of the 12 case-board players or may be a player who is not on the case board.**

The Dealer pool is independent from whether a case-board player has already been revealed. This implements the product requirement that the Dealer may offer any otherwise eligible player.

Select:

```python
offered_player = argmin(
    candidates,
    key=lambda player: (
        abs(player.projected_ppr - target_offer_projection),
        0 if player.projected_ppr <= target_offer_projection else 1,
        player.projected_ppr,
        player.id,
    )
)
```

The intended tiebreak behavior is:

1. closest projection to target
2. if equally close, prefer the player at or below the target rather than above it
3. stable deterministic fallback

Store both:

- `target_offer_projection`
- offered player's real projection

Only display the real offered player and that player's projection.

Example:

```text
Remaining case projections:
22.4, 19.1, 16.7, 14.9, 12.2

EV = 17.06
5 cases left multiplier = 0.7352
Dealer target = 12.54

Closest eligible player projection = 12.6

DEALER OFFER:
Player X — 12.6 projected points
```

## 9.5 Why no random Dealer noise in V1

The television Banker has meaningful offer variation around the average.

Do **not** add random offer noise in V1.

Reasons:

- leaderboard fairness
- reproducibility
- easier debugging
- easier testing
- case/player randomness already creates substantial variation
- no need to add undocumented randomness to a historically calibrated model

Future version may add a seeded `banker_personality` modifier behind a feature flag.

---

# 10. Prize Board UI

## 10.1 Desktop layout

Primary gameplay screen uses a three-column layout.

### Left column: Player Board

Show all 12 possible case players from the beginning, sorted by `board_rank`.

Each row contains:

- rank `1-12`
- NFL team logo
- player name
- projected full-PPR points

Example:

```text
1   [BAL logo]  Derrick Henry       20.4
2   [PHI logo]  Saquon Barkley      19.8
3   [ATL logo]  Bijan Robinson      18.9
...
12  [team logo] Player Name          4.7
```

### Fixed medal styling

Only original displayed board ranks get medal styling:

- #1 = gold
- #2 = silver
- #3 = bronze

This styling is **not dynamic**.

If #1 is eliminated, #4 does not become bronze.

When a player is eliminated:

- dim row opacity
- strike through or visually mark name/projection
- keep original row position
- maintain medal color underneath/dimmed if it was rank 1-3

Do not remove eliminated rows from the list.

### Center column: Cases

Display 12 hidden numbered case tiles in a `4 x 3` grid on desktop.

Closed case shows only:

- case number
- closed visual state

Do not use an NFL team logo on a closed case because that would reveal information.

When a case opens:

- animate flip/reveal
- show team logo
- player name
- projection
- board rank if useful

"My Case" must have a distinctive persistent outline/badge and cannot be opened during elimination rounds.

### Right column: Past Offers

Show all Dealer offers from the current subgame, newest or chronological.

Each offer row should contain:

- offer number
- team logo
- player name
- projection
- result: DEAL / NO DEAL / pending

Example:

```text
Offer 1
Chris Olave — 13.4
NO DEAL
```

## 10.2 Header/status

Show:

- NFL season + week
- current lineup slot, e.g. `WR1 of 6`
- weekly completion progress
- round instruction, e.g. `Open 3 cases`
- global weekly deadline
- next relevant player-lock countdown when useful

## 10.3 Dealer offer presentation

At the end of each round:

- disable case input
- display prominent Dealer overlay/modal/card
- show offered player's team logo
- show player name
- show projected full-PPR points
- large buttons:
  - `DEAL`
  - `NO DEAL`

Do not display:
- internal EV
- target projection
- multiplier
- unrevealed cases

## 10.4 Responsive layout

Mobile must remain playable.

Recommended mobile order:

1. status/header
2. compact case grid
3. Dealer offer area when active
4. collapsible "Players Remaining" board
5. collapsible "Past Offers"

Use 3 or 4 columns for case tiles depending on viewport width.

## 10.5 Accessibility

- All case tiles must be keyboard-accessible buttons.
- Use `aria-label`, e.g. `Open case 7`.
- Never communicate status only by color.
- Medal ranks should include visible rank numbers/icons.
- Honor `prefers-reduced-motion`.
- Modal focus must be trapped correctly.
- Provide sufficient contrast in eliminated/dimmed rows.

---

# 11. Weekly Lineup Screen

Route:

`/lineup`

Display all six slots.

For each slot show:

- lineup position
- NFL team logo
- player name
- projection at time acquired
- opponent
- acquisition method:
  - Dealer Offer
  - Kept Case
  - Swapped Case
- current/final actual full-PPR points
- game status:
  - Not Started
  - Live
  - Final

At top show:

- weekly total actual points
- current weekly leaderboard rank if lineup is complete
- lineup completion status

Before the player's game begins, actual points display `0.0` or `—`.

---

# 12. Actual Fantasy Scoring

## 12.1 Source of truth

Use provider-supplied full-PPR weekly fantasy points when available.

The normalized field should be:

`actual_ppr_points`

Do not derive leaderboard scoring from the projection.

Projection and actual points must be separately stored.

## 12.2 Live and final states

Recommended states:

- `NOT_STARTED`
- `LIVE`
- `FINAL`
- `CORRECTED`

Refresh stats periodically during game windows.

A user's current weekly score is:

```text
sum(actual_ppr_points for all 6 lineup players)
```

Only completed six-player lineups appear on the competitive leaderboard.

## 12.3 Stat corrections

The leaderboard can be marked `LIVE` until the weekly scoring period is finalized.

Recommended finalization:

- Continue accepting provider stat corrections after Monday Night Football.
- Finalize the prior week before the next Tuesday 9:00 AM game opens, or at a configured Tuesday cutoff.
- If the provider applies a later correction, support an admin recompute.

---

# 13. Accounts and Authentication

Use Supabase Auth.

V1 account requirements:

- email/password
- unique public username/display name
- password reset
- email verification recommended
- logout
- account profile

Optional V1 OAuth:
- Google

Do not expose the Supabase service role key to the frontend.

Profile fields:

- user_id
- username
- display_name
- avatar_url optional
- created_at
- updated_at

Leaderboard displays public username/display name, not email.

---

# 14. Leaderboards

## 14.1 Weekly leaderboard

Route:

`/leaderboard?season=YYYY&week=N`

Show:

- rank
- username
- weekly actual points
- lineup status
- optional mini lineup preview

Sort by:

1. total actual PPR points descending

For exact score ties, use shared rank rather than an arbitrary competitive tiebreaker.

Do not use lineup completion time as a scoring tiebreaker.

## 14.2 Season leaderboard

Provide a season tab.

Primary season score:

```text
sum(final weekly scores across completed weekly entries)
```

Also display:

- weeks played
- average points per completed week

This helps distinguish cumulative participation from per-week performance without changing the primary cumulative leaderboard.

## 14.3 Live status

Clearly label leaderboards:

- LIVE
- FINAL

Never present live scores as final.

---

# 15. History

Route:

`/history`

Show all previous weekly entries for the user.

For each week:

- season/week
- total final score
- final weekly rank
- six-player lineup
- each player's projection when acquired
- each player's actual result
- acquisition method

Detailed route:

`/history/{season}/{week}`

Optional but recommended:
allow the user to inspect each position's full Deal game history:

- 12-player board
- chosen case
- eliminated cases/order
- Dealer offers
- deal/no-deal decisions
- final keep/swap
- awarded player

This replay/audit data makes the product more engaging and helps diagnose disputes.

---

# 16. Data Provider Architecture

Do not tightly couple the game engine to ESPN or Sleeper response formats.

Create a provider interface.

Example Python protocol/interface:

```python
class FantasyDataProvider(Protocol):
    async def get_nfl_state(self) -> NFLState: ...
    async def get_schedule(self, season: int, week: int) -> list[NFLGame]: ...
    async def get_players(self) -> list[Player]: ...
    async def get_week_projections(
        self, season: int, week: int
    ) -> list[PlayerProjection]: ...
    async def get_week_results(
        self, season: int, week: int
    ) -> list[PlayerResult]: ...
```

Implement adapters:

- `SleeperProvider`
- `ESPNProvider`

The rest of the application uses only normalized internal models.

## 16.1 Sleeper note

Sleeper's official public API documents league/player/state endpoints and states that the API is free for non-commercial use, while commercial use requires contacting Sleeper.

The official public documentation does not prominently document weekly projection/stat endpoints. Community client documentation references Sleeper projection/stat endpoints such as:

```text
https://api.sleeper.com/projections/nfl/{season}/{week}
https://api.sleeper.com/stats/nfl/{season}/{week}
```

Treat undocumented/internal endpoints as potentially unstable.

Do not make the app depend on an undocumented endpoint without:

- integration tests
- caching
- graceful failure
- provider fallback
- checking permitted production/commercial usage

## 16.2 ESPN note

ESPN fantasy endpoints used by community projects are also commonly undocumented/private interfaces.

Use the same adapter/caching strategy.

## 16.3 Required fallback

Add an admin/manual import capability for weekly projections/results.

At minimum support CSV import with:

```text
provider_player_id
player_name
team
position
opponent
kickoff_at
projected_ppr_points
actual_ppr_points
```

This prevents a provider change/outage from making the entire game unusable.

---

# 17. Recommended Database Schema

Use Supabase Postgres migrations.

Use UUIDs for internal IDs unless provider IDs are clearly external-string columns.

## 17.1 `profiles`

```text
user_id uuid PK -> auth.users.id
username text UNIQUE NOT NULL
display_name text
avatar_url text
created_at timestamptz
updated_at timestamptz
```

## 17.2 `nfl_weeks`

```text
id uuid PK
season int NOT NULL
week int NOT NULL
opens_at timestamptz NOT NULL
closes_at timestamptz NOT NULL
scoring_status enum('UPCOMING','OPEN','LIVE','FINAL')
projection_snapshot_id uuid nullable
created_at timestamptz
updated_at timestamptz

UNIQUE(season, week)
```

## 17.3 `nfl_games`

```text
id uuid PK
provider_game_id text
season int
week int
away_team text
home_team text
kickoff_at timestamptz
status text
created_at timestamptz
updated_at timestamptz
```

## 17.4 `players`

```text
id uuid PK
sleeper_id text UNIQUE nullable
espn_id text UNIQUE nullable
full_name text
position text
fantasy_positions text[]
team text
jersey_number int nullable
active boolean
team_logo_url text nullable
provider_metadata jsonb
created_at timestamptz
updated_at timestamptz
```

## 17.5 `projection_snapshots`

```text
id uuid PK
provider text
season int
week int
fetched_at timestamptz
status enum('SUCCESS','PARTIAL','FAILED')
source_version text nullable
created_at timestamptz
```

## 17.6 `player_week_projections`

```text
id uuid PK
snapshot_id uuid FK
player_id uuid FK
season int
week int
position text
team text
opponent text
nfl_game_id uuid FK
kickoff_at timestamptz
projected_ppr numeric(8,3)
raw_payload jsonb
created_at timestamptz

UNIQUE(snapshot_id, player_id)
```

Index:
- `(snapshot_id, position, projected_ppr DESC)`
- `(season, week, player_id)`

## 17.7 `player_week_results`

```text
id uuid PK
player_id uuid FK
season int
week int
actual_ppr numeric(8,3)
game_status text
provider text
fetched_at timestamptz
raw_payload jsonb
created_at timestamptz
updated_at timestamptz

UNIQUE(player_id, season, week)
```

## 17.8 `weekly_entries`

One row per user/week.

```text
id uuid PK
user_id uuid FK
season int
week int
status enum('NOT_STARTED','IN_PROGRESS','COMPLETE','EXPIRED','FINAL')
started_at timestamptz nullable
completed_at timestamptz nullable
actual_score numeric(8,3) default 0
final_rank int nullable
created_at timestamptz
updated_at timestamptz

UNIQUE(user_id, season, week)
```

## 17.9 `lineup_slots`

```text
id uuid PK
entry_id uuid FK
slot enum('RB1','RB2','WR1','WR2','TE','FLEX')
player_id uuid FK nullable
projection_when_acquired numeric(8,3) nullable
acquisition_method enum('DEAL','FINAL_KEEP','FINAL_SWAP') nullable
deal_game_id uuid nullable
actual_ppr numeric(8,3) default 0
created_at timestamptz
updated_at timestamptz

UNIQUE(entry_id, slot)
UNIQUE(entry_id, player_id) WHERE player_id IS NOT NULL
```

## 17.10 `deal_games`

```text
id uuid PK
entry_id uuid FK
slot text
projection_snapshot_id uuid FK
status enum(
  'AWAITING_CASE_SELECTION',
  'ROUND_1',
  'OFFER_1',
  'ROUND_2',
  'OFFER_2',
  'ROUND_3',
  'OFFER_3',
  'ROUND_4',
  'OFFER_4',
  'FINAL_CHOICE',
  'COMPLETE',
  'EXPIRED'
)
selected_case_number int nullable
current_round int default 0
round_open_count int default 0
cases_remaining int default 12
outcome text nullable
awarded_player_id uuid nullable
seed_hash text
algorithm_version text
started_at timestamptz
expires_at timestamptz
completed_at timestamptz nullable
created_at timestamptz
updated_at timestamptz
```

## 17.11 `deal_game_cases`

Backend-only hidden data.

```text
id uuid PK
deal_game_id uuid FK
case_number int
player_id uuid FK
tier_number int
full_pool_rank int
board_rank int
projection numeric(8,3)
is_user_case boolean default false
status enum('CLOSED','ELIMINATED','FINAL_SELECTED','FINAL_OTHER')
opened_order int nullable
opened_at timestamptz nullable

UNIQUE(deal_game_id, case_number)
UNIQUE(deal_game_id, player_id)
```

**Security requirement:** direct client reads of unrevealed `player_id` values must be impossible.

## 17.12 `deal_game_offers`

```text
id uuid PK
deal_game_id uuid FK
offer_number int
cases_remaining int
expected_value numeric(8,3)
ev_multiplier numeric(8,5)
target_projection numeric(8,3)
offered_player_id uuid FK
offered_player_projection numeric(8,3)
decision enum('PENDING','DEAL','NO_DEAL')
created_at timestamptz
decided_at timestamptz nullable

UNIQUE(deal_game_id, offer_number)
```

The frontend API must not return hidden math fields unless an admin/debug mode is authorized.

## 17.13 `deal_game_events`

Append-only audit log.

```text
id bigserial PK
deal_game_id uuid FK
user_id uuid FK
event_type text
payload jsonb
created_at timestamptz
```

Events:

- GAME_CREATED
- CASE_SELECTED
- CASE_OPENED
- OFFER_CREATED
- OFFER_ACCEPTED
- OFFER_DECLINED
- FINAL_KEEP
- FINAL_SWAP
- GAME_COMPLETED
- GAME_EXPIRED

---

# 18. RLS and Security

Use Supabase RLS.

## 18.1 Principles

Users may read:

- their own profile private fields
- their own weekly entries
- their own completed/revealed game state
- public leaderboard-safe profile fields

Users must never directly read:

- hidden case mappings
- hidden Dealer calculations
- another user's private game-state payloads
- service credentials

## 18.2 Recommended architecture

All game-changing operations go through FastAPI.

FastAPI:

1. verifies Supabase JWT
2. identifies authenticated user
3. executes transaction
4. validates state machine
5. reads backend-only hidden case data
6. returns sanitized response

Do not let the browser directly mutate `deal_games`, `deal_game_cases`, `deal_game_offers`, or `lineup_slots`.

## 18.3 Race protection

For every game action:

- lock current game row using transaction/`SELECT ... FOR UPDATE` equivalent
- validate expected state
- enforce idempotency
- reject duplicate/opened case clicks
- prevent double acceptance
- prevent simultaneous requests from skipping rounds

---

# 19. FastAPI Endpoints

Prefix:

`/api/v1`

## 19.1 Weekly state

### `GET /week/current`

Returns:

- season
- week
- opens_at
- closes_at
- status
- user's entry summary
- next required lineup slot

### `POST /entry/start`

Creates weekly entry and lineup-slot placeholders if necessary.

Idempotent.

## 19.2 Start Deal game

### `POST /deal-games`

Request:

```json
{
  "slot": "RB1"
}
```

Backend:

1. verify weekly window open
2. verify slot is allowed/current
3. verify slot is unfilled
4. obtain current projection snapshot
5. build eligible pool
6. create 12 tiers
7. select one from each
8. assign board ranks
9. shuffle case assignments
10. store backend-only state
11. return sanitized board

Response includes:

- deal_game_id
- slot
- expiration
- 12 displayed player-board rows
- 12 case numbers only
- current instruction
- no case-player mapping

## 19.3 Select My Case

### `POST /deal-games/{id}/select-case`

```json
{
  "case_number": 7
}
```

Transition:
`AWAITING_CASE_SELECTION -> ROUND_1`

## 19.4 Open a case

### `POST /deal-games/{id}/cases/{case_number}/open`

Returns only the legitimately revealed player plus updated public state.

When a round quota is reached, backend creates Dealer offer atomically and response can contain `offer`.

## 19.5 Dealer decision

### `POST /deal-games/{id}/offers/{offer_number}/decision`

```json
{
  "decision": "DEAL"
}
```

or

```json
{
  "decision": "NO_DEAL"
}
```

Server validates that this is the active pending offer.

## 19.6 Final choice

### `POST /deal-games/{id}/final-choice`

```json
{
  "choice": "KEEP"
}
```

or:

```json
{
  "choice": "SWAP"
}
```

## 19.7 Read game state

### `GET /deal-games/{id}`

Return sanitized state suitable for refresh/resume.

Never reveal closed case mappings.

## 19.8 Lineup

### `GET /lineup/current`

### `GET /lineup/{season}/{week}`

## 19.9 Leaderboards

### `GET /leaderboards/weekly?season=YYYY&week=N`

### `GET /leaderboards/season?season=YYYY`

## 19.10 History

### `GET /history`

### `GET /history/{season}/{week}`

---

# 20. Game-State Machine

Implement the state transitions centrally. Do not scatter state logic across route handlers.

```text
AWAITING_CASE_SELECTION
    |
    v
ROUND_1 -- open 4 --> OFFER_1
    |                   |
    |                 DEAL -> COMPLETE
    |                 NO DEAL
    v                   v
ROUND_2 -- open 3 --> OFFER_2
                        |
                      DEAL -> COMPLETE
                      NO DEAL
                        v
ROUND_3 -- open 2 --> OFFER_3
                        |
                      DEAL -> COMPLETE
                      NO DEAL
                        v
ROUND_4 -- open 1 --> OFFER_4
                        |
                      DEAL -> COMPLETE
                      NO DEAL
                        v
                   FINAL_CHOICE
                    /        \
                 KEEP        SWAP
                   \          /
                     COMPLETE
```

Any active state can transition to:

`EXPIRED`

if the game passes its allowed expiry.

---

# 21. Core Backend Service Modules

Recommended FastAPI service layout:

```text
backend/
  app/
    api/
      routes/
        auth.py
        weeks.py
        deal_games.py
        lineups.py
        leaderboards.py
        history.py
        admin.py
    core/
      config.py
      auth.py
      db.py
      time.py
    models/
      domain.py
      api.py
    services/
      eligibility.py
      tiering.py
      randomization.py
      deal_engine.py
      dealer.py
      lineup.py
      scoring.py
      leaderboard.py
      week_manager.py
      providers/
        base.py
        sleeper.py
        espn.py
        csv_provider.py
    jobs/
      sync_players.py
      sync_schedule.py
      sync_projections.py
      sync_results.py
      finalize_week.py
    tests/
      ...
```

Critical pure functions:

```python
build_eligible_pool(...)
split_into_12_tiers(...)
select_one_per_tier(...)
assign_case_numbers(...)
calculate_remaining_ev(...)
calculate_dealer_target(...)
find_closest_offer_player(...)
validate_case_open(...)
transition_game_state(...)
```

Keep these functions deterministic when their inputs/seed are fixed.

---

# 22. Next.js Frontend Structure

Recommended App Router structure:

```text
frontend/
  app/
    page.tsx
    play/
      page.tsx
      [gameId]/
        page.tsx
    lineup/
      page.tsx
    leaderboard/
      page.tsx
    history/
      page.tsx
      [season]/
        [week]/
          page.tsx
    profile/
      page.tsx
    login/
      page.tsx
    signup/
      page.tsx
  components/
    game/
      PlayerBoard.tsx
      PlayerBoardRow.tsx
      CaseGrid.tsx
      CaseTile.tsx
      DealerOffer.tsx
      OfferHistory.tsx
      RoundStatus.tsx
      SlotProgress.tsx
      FinalChoice.tsx
      GameComplete.tsx
    lineup/
      LineupCard.tsx
      LineupSlot.tsx
    leaderboard/
      LeaderboardTable.tsx
    ui/
      ...
  lib/
    api.ts
    auth.ts
    types.ts
    time.ts
```

Use React Query/TanStack Query or equivalent for server state.

Do not treat hidden case state as client state.

---

# 23. Main Pages

## `/`

Landing page.

Include:

- product name/branding
- current week's availability
- "Play This Week"
- explanation of lineup format
- link to leaderboard
- authentication CTA

## `/play`

Weekly game hub.

Show six lineup slots and statuses:

- completed
- current
- upcoming

Primary CTA:
`Continue with WR2`

## `/play/[gameId]`

Actual Deal game UI.

## `/lineup`

Live weekly lineup/scoring.

## `/leaderboard`

Weekly + season tabs.

## `/history`

User's previous weeks.

## `/profile`

Username/display/avatar/account options.

---

# 24. UI Design Direction

The app should feel like a modern sports game, not a clone of the television show's protected visual identity.

Recommended feel:

- dark sports-broadcast background
- high-contrast cards
- bold condensed headings
- subtle stadium/field texture if original/licensed
- metallic case accents
- team-logo color accents after reveals
- smooth case flip/reveal animation
- strong gold/silver/bronze accents on top player-board rows
- clear red/green or neutral button treatment for Deal/No Deal, with text labels

Do not copy:

- the television show's exact logo
- exact set design
- copyrighted music/sounds
- proprietary animation/graphics
- trademarked title treatment

Treat "Fantasy Football Deal or No Deal" as a working product description until branding/legal clearance. A unique public-facing name is safer for a commercial release.

---

# 25. Team Logos

Use a centralized team asset map.

Example domain model:

```ts
type NFLTeam = {
  code: string;
  name: string;
  logoUrl: string;
};
```

Do not hardcode logo URLs throughout components.

If using ESPN-hosted or another third-party logo CDN, isolate the URL strategy behind one helper so it can be replaced later.

For commercial launch, confirm logo/trademark usage rights.

Always provide text team abbreviation as fallback when an image fails.

---

# 26. Projection and Result Sync Jobs

## 26.1 Player metadata

Sync once daily.

Sleeper's official API specifically recommends not repeatedly downloading the full NFL player map.

## 26.2 Schedule

Refresh at least daily and more often around schedule-change windows.

Kickoff time is critical game logic, not decoration.

## 26.3 Projections

Recommended while weekly contest is open:

- Tuesday morning pre-open
- periodic refresh Tuesday-Sunday
- e.g. every 30-60 minutes depending on provider limits

Each successful ingestion creates an immutable `projection_snapshot`.

Do not update prior snapshots in place.

## 26.4 Live results

During NFL game windows:

- poll provider on a conservative interval, e.g. every 2-5 minutes
- normalize full-PPR actual points
- update user lineup totals

If provider supports more appropriate push/update mechanisms later, replace polling.

## 26.5 Weekly finalization

After the week's games/stat corrections:

1. mark player results final
2. recompute every complete weekly entry
3. rank weekly leaderboard
4. save final rank
5. update season leaderboard aggregates
6. mark NFL week `FINAL`

---

# 27. Admin Tools

V1 should include at least a protected admin interface or CLI for:

- inspect current NFL week
- inspect latest projection snapshot
- rerun projection import
- upload manual CSV
- inspect failed provider requests
- inspect a user's game audit trail
- expire/reset a broken subgame
- recompute weekly scores
- finalize/unfinalize a week
- view provider health

Admin must not be available through normal user role.

---

# 28. Failure Handling

## Provider unavailable

If no valid projection snapshot exists:

- do not create new Deal games
- show "Weekly player data is temporarily unavailable"
- keep existing frozen games playable if their data is already stored and still temporally valid

## Insufficient eligible players

If fewer than 12 eligible players exist for a required position:

- do not silently duplicate players
- log critical data-quality error
- prevent game creation for that slot
- alert admin

## Projection changes after game creation

No effect on an active game.

The active game uses its frozen snapshot.

## Player ruled out after game creation

V1 rule:
- if NFL game has not started and subgame is already active, do not mutate the board
- projection snapshot remains frozen
- the player may still be won
- actual score will be whatever the provider records, potentially 0

This is consistent and avoids changing hidden cases after play begins.

Future version can add injury invalidation rules if desired.

## Postponed NFL game

Admin/provider sync must update kickoff.

If kickoff changes before a new subgame starts, use new kickoff.

For active games, apply configurable league rule. Default V1:
- honor player as long as game remains part of the same NFL scoring week.

## Browser refresh

Game must resume exactly where it left off.

Never regenerate the board on refresh.

## Duplicate actions

All mutating endpoints must be idempotent or safely reject duplicate transitions.

---

# 29. Leaderboard Fairness / Anti-Cheat

Critical rules:

1. Case-player mappings never sent early.
2. Dealer hidden target math never needed client-side.
3. All randomization server-side.
4. All game transitions validated server-side.
5. All player awards committed in a transaction.
6. A user cannot replay a completed slot.
7. An expired unfinished slot can be restarted only according to expiration rules.
8. User cannot change a lineup after acquiring players.
9. No direct client writes to scoring/result tables.
10. Completion must occur before global weekly deadline.

Do not rely on disabled frontend buttons as security.

---

# 30. Observability

Add structured logs for:

- provider sync success/failure
- snapshot IDs
- game creation
- game expiry
- dealer calculations
- score finalization
- API state-transition rejection

Recommended error tracking:
- Sentry or equivalent

Recommended product events:

- weekly_entry_started
- deal_game_started
- case_selected
- case_opened
- dealer_offer_shown
- dealer_offer_accepted
- dealer_offer_declined
- final_keep
- final_swap
- weekly_lineup_completed

Never log hidden case mappings into public/client analytics.

---

# 31. Testing Requirements

## 31.1 Unit tests

### Tiering

Test:

- divisible pool sizes
- non-divisible pool sizes
- every player belongs to exactly one tier
- one player chosen from each tier
- 12 unique selected players
- stable ordering under tied projections

### Dealer EV

Given known remaining projections, assert exact EV.

### Dealer multipliers

Assert:

```text
8 -> 0.5088
5 -> 0.7352
3 -> 0.9277
2 -> 0.9564
```

### Player offer mapping

Test:

- exact projection match
- between two players
- deterministic tie
- target below min candidate
- target above max candidate
- previous offer exclusions
- rostered player exclusion

### State machine

Test every valid and invalid transition.

Examples:

- cannot open before My Case selected
- cannot open My Case
- cannot open fifth case in Round 1
- cannot open during Dealer offer
- cannot skip offer decision
- cannot final swap before fourth offer rejected
- cannot make an action after completion

### Time locking

Test:

- Tuesday pre-open
- Tuesday 9:00 exactly
- Thursday player before kickoff
- Thursday player after kickoff
- international Sunday game after kickoff
- Sunday 12:59:59 ET
- Sunday 1:00:00 ET

Use timezone-aware test fixtures and DST-safe logic.

## 31.2 Integration tests

- create entry -> fill all six slots
- accept offer in each possible round
- reject all -> keep
- reject all -> swap
- refresh browser between every state
- expire mid-subgame
- provider snapshot update while subgame active
- score update populates lineup/leaderboard

## 31.3 End-to-end tests

Use Playwright.

At minimum:

1. sign up/login
2. start week
3. choose case
4. reveal cases
5. reject/accept offer
6. fill lineup
7. verify lineup
8. verify leaderboard appearance
9. verify history after finalization

---

# 32. Recommended Build Phases for Claude Code

Do not try to build the entire product in one undifferentiated pass.

## Phase 0 — Repository and contracts

- monorepo or clean frontend/backend directories
- environment setup
- linting/formatting
- Supabase project config
- shared domain contract
- migrations
- local test fixtures

**Exit:** apps boot and database migrations run.

## Phase 1 — NFL data layer

- normalized player/team/week/game models
- provider interface
- one working provider adapter
- projection snapshots
- actual results ingestion
- manual CSV fallback
- team-logo mapping

**Exit:** database contains a valid week, players, schedule, projections.

## Phase 2 — Core game engine

Implement and test:

- eligibility
- tiering
- one-per-tier selection
- case assignment
- state machine
- Dealer EV
- Dealer player matching
- expiration logic

No polished UI yet.

**Exit:** full six-slot weekly run can be simulated entirely through backend tests/API.

## Phase 3 — Gameplay frontend

Build:

- player board
- case grid
- reveals
- offer modal
- offer history
- final keep/swap
- slot progress
- resume behavior
- responsive UI

**Exit:** user can complete six slots in browser.

## Phase 4 — Accounts, lineup, history, leaderboards

- Supabase Auth
- profile/username
- current lineup
- history
- weekly leaderboard
- season leaderboard

**Exit:** multiple users can compete.

## Phase 5 — Live scoring

- results polling
- current scores
- finalization
- live/final labels
- stat correction recompute

**Exit:** weekly scoreboard works through completion.

## Phase 6 — Hardening

- RLS audit
- hidden-data security test
- rate limits
- idempotency
- observability
- provider outage UX
- admin tools
- mobile polish
- accessibility

**Exit:** production candidate.

---

# 33. Environment Variables

Example:

```text
# Frontend
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=

# Backend
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_JWKS_URL=
DATABASE_URL=

# Provider
FANTASY_DATA_PROVIDER=sleeper
SLEEPER_BASE_URL=
ESPN_BASE_URL=

# App
APP_TIMEZONE=America/New_York
PUBLIC_APP_URL=

# Optional
SENTRY_DSN=
ADMIN_USER_IDS=
```

Never commit secrets.

---

# 34. API Response Security Example

Bad:

```json
{
  "case_number": 4,
  "player_id": "hidden-player-id",
  "status": "CLOSED"
}
```

This leaks the case.

Correct closed case:

```json
{
  "case_number": 4,
  "status": "CLOSED",
  "is_user_case": false
}
```

Correct revealed case:

```json
{
  "case_number": 4,
  "status": "ELIMINATED",
  "player": {
    "id": "public-player-id",
    "name": "Player Name",
    "team": "BAL",
    "team_logo_url": "...",
    "projection": 13.7,
    "board_rank": 6
  }
}
```

Treat this distinction as a non-negotiable security requirement.

---

# 35. Suggested Domain Types

## TypeScript

```ts
export type LineupSlot =
  | "RB1"
  | "RB2"
  | "WR1"
  | "WR2"
  | "TE"
  | "FLEX";

export type DealGameStatus =
  | "AWAITING_CASE_SELECTION"
  | "ROUND_1"
  | "OFFER_1"
  | "ROUND_2"
  | "OFFER_2"
  | "ROUND_3"
  | "OFFER_3"
  | "ROUND_4"
  | "OFFER_4"
  | "FINAL_CHOICE"
  | "COMPLETE"
  | "EXPIRED";
```

## Python

Mirror enums in backend.

Do not duplicate magic strings in service logic.

---

# 36. UX Copy Examples

Initial:

```text
Choose Your Case
Pick one case to keep sealed. It could contain any of the 12 players on the board.
```

Round:

```text
Open 4 Cases
Eliminate four players before the Dealer makes the first offer.
```

Offer:

```text
THE DEALER IS CALLING

[Team Logo]
Chris Olave
13.4 projected PPR points

DEAL        NO DEAL
```

Final:

```text
Two Cases Remain

Keep Case #7
or
Swap for Case #11
```

Completion:

```text
WR1 Locked In

Chris Olave
13.4 projected points

Your weekly score will use his actual PPR points.
```

---

# 37. V1 Acceptance Criteria

The feature is V1-complete only when all are true:

### Weekly lifecycle
- [ ] New week opens Tuesday 9 AM ET.
- [ ] Weekly lineup closes Sunday 1 PM ET.
- [ ] Kicked-off players are excluded from newly created pools.
- [ ] In-progress games cannot be exploited across player kickoff.

### Case generation
- [ ] Only projection > 0 players included.
- [ ] Full pool is split into 12 contiguous projection tiers.
- [ ] Exactly one random player selected per tier.
- [ ] 12 selected players are randomized behind 12 cases.
- [ ] No duplicate case player.

### UI
- [ ] 12 player board visible from start.
- [ ] Rank 1 gold, rank 2 silver, rank 3 bronze.
- [ ] Medal styling is not dynamic.
- [ ] Rows remain visible after elimination.
- [ ] Closed case never exposes player identity.
- [ ] Cases render 4x3 desktop.
- [ ] Past offers visible on right desktop.
- [ ] Mobile playable.

### Gameplay
- [ ] User picks My Case.
- [ ] Opens 4, offer.
- [ ] Opens 3, offer.
- [ ] Opens 2, offer.
- [ ] Opens 1, offer.
- [ ] Final keep/swap after fourth rejection.
- [ ] Deal immediately awards Dealer player.
- [ ] Completed slot cannot be replayed.

### Dealer
- [ ] EV includes every unopened case including My Case.
- [ ] Multipliers are 0.5088 / 0.7352 / 0.9277 / 0.9564.
- [ ] Numeric target maps to nearest real eligible player.
- [ ] Dealer may offer a case-board player or outside player.
- [ ] Previously rostered players excluded.
- [ ] Previously declined offers not repeated in same subgame.

### Weekly lineup
- [ ] 2 RB, 2 WR, 1 TE, 1 FLEX.
- [ ] No duplicate player in lineup.
- [ ] FLEX combines RB/WR/TE.
- [ ] All six slots required for leaderboard eligibility.

### Scoring
- [ ] Projection used only for minigame.
- [ ] Actual full-PPR points determine score.
- [ ] Live total updates.
- [ ] Final weekly score saved.
- [ ] Stat corrections can recompute score.

### Social/account
- [ ] Account/auth.
- [ ] Unique username.
- [ ] Weekly leaderboard.
- [ ] Season leaderboard.
- [ ] User history.

### Security
- [ ] Hidden mappings unavailable to frontend/network payload.
- [ ] Service-role key backend only.
- [ ] Game actions server-validated.
- [ ] RLS enabled.
- [ ] Race/double-click protections tested.

---

# 38. V1 Non-Goals

Do not block launch on:

- QB/K/DST game modes
- custom PPR settings
- private leagues
- head-to-head leagues
- social following
- chat
- prizes/gambling
- paid contests
- push notifications
- native mobile app
- user-created minigames
- custom Dealer personalities
- AI Dealer dialogue
- multi-provider projection averaging

Design architecture so some can be added later, but do not add them to initial scope.

---

# 39. Future Platform Expansion

Because this is intended to become an NFL minigame app rather than a one-off page, preserve reusable platform concepts:

- `GameType`
- weekly NFL data service
- player identity service
- projection snapshots
- weekly entries
- fantasy results
- leaderboard engine
- account/history system

Future minigames should be able to plug into the same weekly player data and scoring platform.

Avoid naming global shared tables/classes specifically around Deal or No Deal when they are genuinely reusable.

---

# 40. Important Implementation Decisions Already Locked

These are product requirements, not open questions:

1. Lineup is exactly 2 RB, 2 WR, 1 TE, 1 FLEX.
2. Scoring is full PPR.
3. Projection chooses/values players; actual weekly performance determines user score.
4. Six independent Deal games fill the lineup.
5. Acquired players cannot appear in later lineup games.
6. FLEX combines RB/WR/TE.
7. Case pool uses every eligible projection > 0 player split into twelfths.
8. Select one random player from each twelfth.
9. Left board shows all 12 possible players from the start.
10. Gold/silver/bronze belong only to original ranks 1/2/3 and never move.
11. Weekly window is Tuesday 9 AM ET through Sunday 1 PM ET.
12. Players are no longer eligible after their real NFL kickoff.
13. Accounts, lineup, leaderboard, and history are V1.
14. Player rows use team logo rather than jersey artwork.
15. Dealer can offer any eligible player, whether or not that player was selected onto the case board.
16. Dealer offer is a player, not abstract fantasy points.

---

# 41. Implementation Assumptions Made in This Spec

These assumptions were chosen to make the requirements internally consistent and production-safe.

## A. Thursday interpretation

Thursday players are eligible before their Thursday kickoff and unavailable afterward.

A user cannot preserve access to a Thursday player by leaving an unfinished subgame open through kickoff.

## B. Case artwork

The 12 center objects are generic numbered case tiles, not player/team jerseys.

This is necessary because showing a team/player asset on a closed case would leak information.

Team logos appear:
- on the left player board
- when a case is revealed
- on Dealer offers
- on lineups/history

## C. Declined Dealer offers

A Dealer player already declined in the same subgame is excluded from later Dealer offers to avoid repetitive offers.

## D. Fixed slot order

V1 uses:

RB1 -> RB2 -> WR1 -> WR2 -> TE -> FLEX

This can later be loosened if desired.

---

# 42. Banker Research Sources

## Primary model source

David Ritcey & Pritam Ranjan (2010),  
**“Statistical Models for the Banker’s Offer in Deal or No Deal”**  
Atlantic Electronic Journal of Mathematics, Volume 4, Number 1.

The paper analyzes both NBC online games and American NBC television episodes. Its proportion-based television model estimates the offer as a round-dependent proportion of the expected value of remaining cases.

Relevant television estimates:

```text
Round 1  17.01%
Round 2  27.29%
Round 3  40.24%
Round 4  50.88%
Round 5  62.16%
Round 6  73.52%
Round 7  82.83%
Round 8  92.77%
Round 9  95.64%
```

Source:
https://studylib.net/doc/18252350/statistical-models-for-the-banker-s-offer

## Supporting academic source

Thierry Post, Martijn J. van den Assem, Guido Baltussen & Richard H. Thaler (2008),  
**“Deal or No Deal? Decision Making under Risk in a Large-Payoff Game Show”**  
American Economic Review 98(1): 38-71.

https://www.aeaweb.org/articles?id=10.1257/aer.98.1.38

## Modern dataset analysis

Matthew Jiwa, **“Deal or No Deal | Part 1: Beating the Banker”**.

Uses historical data from multiple national editions and discusses the progressive EV-proportion structure of Banker offers, including the Post et al. recursive model.

https://matthewjiwa.com/posts/2024-08-01-dondpart1/

---

# 43. Data Source References

Sleeper official API documentation:

https://docs.sleeper.com/

Notable official guidance:
- public API is read-only
- no API token required
- full NFL player list should be cached rather than repeatedly downloaded
- documentation states non-commercial usage is free and directs commercial users to contact Sleeper

Community Sleeper projection endpoint reference:

https://sleeper-api-client.readthedocs.io/en/stable/endpoints/projections.html

Community Sleeper stats endpoint reference:

https://sleeper-api-client.readthedocs.io/en/stable/endpoints/stats.html

Treat community-documented/undocumented provider endpoints as replaceable infrastructure, never as permanent business logic.

---

# 44. Final Instruction to Claude Code

Build this as a real production application, not a static mockup.

Before implementing a phase:

1. inspect the existing repository
2. reuse established patterns when sound
3. create/modify migrations deliberately
4. write tests for core game rules before UI polish
5. never expose hidden case state
6. do not invent alternative game rules when this document specifies one
7. keep provider-specific parsing isolated behind adapters
8. preserve timezone/kickoff rules
9. make every mutation server-authoritative
10. stop and flag only genuinely blocking contradictions; otherwise follow this specification

The most important components to get correct are:

1. player eligibility
2. 12-tier player selection
3. hidden case security
4. exact round state machine
5. Dealer EV/player-offer calculation
6. NFL kickoff locking
7. actual-PPR scoring
8. weekly leaderboard integrity

If UI implementation conflicts with game integrity, game integrity wins.
