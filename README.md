# Sunday Vault

A working NFL fantasy Deal or No Deal application built from [the production specification](deal_or_no_deal/NFL_Fantasy_Deal_or_No_Deal_Production_Spec.md).

Next.js / TypeScript / Tailwind frontend, FastAPI backend, Supabase Postgres and Auth, ESPN projections/schedules/results, and manual CSV fallback. No deployment has been performed.

## Run locally

Requirements: Node.js 20.9+ and Python 3.12+. Commands below are for PowerShell, from this directory.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e './backend[dev]'
npm install
```

### Live Supabase + ESPN application

The supplied database connection is stored only in ignored `backend/.env`. Application tables and RLS have been migrated. `frontend/.env.local` contains the project URL and API URL.

The Supabase publishable key is configured locally and was accepted by the authentication service. Email signup is enabled and requires email verification. For a fresh checkout, set the Supabase **publishable key** (or legacy **anon** key) in:

- `frontend/.env.local`: `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `backend/.env`: `SUPABASE_PUBLISHABLE_KEY` (needed only for legacy HS256 JWT verification)

Never put the database password or service-role key in a `NEXT_PUBLIC_` variable. All database writes happen in FastAPI; the browser uses Supabase only for authentication.

In Supabase Auth URL configuration, allow `http://127.0.0.1:3000/auth/callback` and `http://127.0.0.1:3000/reset-password` (and the `localhost` equivalents if using that hostname). Email/password authentication and email verification use the project's configured email delivery.

```powershell
npm run dev
```

Open **http://127.0.0.1:3000**. FastAPI runs on **http://127.0.0.1:8000**; interactive API docs are at `/docs`. Sign up, verify your email, then choose a unique username and favorite NFL team in Profile. Profile and Head-to-head are in the sidebar; Head-to-head appears above My history.

Use `backend/.env.example` and `frontend/.env.example` for a fresh checkout. The database password must be URL-encoded (`@` becomes `%40`). Do not commit `.env` files.

### Local practice, without any credentials

```powershell
npm run dev -- --practice
```

Practice uses **separate local SQLite storage**, synthetic projections, sample player/team associations, and a local-only identity. A persistent banner identifies it. The regular game engine, API transitions, persistence, and UI are the same. Practice data can never be seeded into Postgres, and practice authentication refuses to start in production. Practice is always open for local testing and does not represent the real weekly contest.

Only one mode can run on ports 3000/8000 at a time. Stop the running launcher with Ctrl+C before switching modes. Practice progress persists in `backend/practice.db`.

## Accounts and profiles

Signup asks for email, password, and password confirmation. Signup, reset-password, and profile password changes share the policy: at least 8 characters, an uppercase letter, a lowercase letter, a number, and an ASCII special character. Sign-in still accepts existing passwords. After verification, profile setup requires a unique case-insensitive username (3–24 letters/numbers/underscores) and a favorite NFL team. All Play routes, including saved game links, redirect incomplete profiles to setup before showing gameplay. The API also checks a valid saved username and team before creating entries or starting/continuing games. Taken usernames return checked suggestions; availability is only reserved upon saving. Username changes preserve the immutable account ID and all lineup/rivalry history.

Profile includes username, optional display name, favorite team, email change, and password change. Sensitive account changes reauthenticate with the current password. Email changes require the provider's confirmation flow; email/passwords are not stored in public profile tables. The backend also checks the trusted Supabase email-confirmation timestamp before allowing profile writes.

**Supabase configuration still requires dashboard confirmation:** in Auth → Email settings, keep email confirmation enabled, set minimum password length to 8, and require lowercase + uppercase + digits + symbols. Frontend validation is implemented, but cannot replace [Supabase's server-side password policy](https://supabase.com/docs/guides/auth/password-security). Keep Secure Email Change enabled so confirmation is required at both addresses. These management settings were not changed through the available tools. Test real email delivery/confirmation with your inbox before deployment.

## Season-long head-to-head

- Click **View matchup** or a week in rivalry history to compare both lineups. Your team stays on the left and your opponent on the right, with actual totals at the top, aligned roster slots, projections, game status, and home/away opponents. A week selector opens earlier or upcoming matchups. Empty slots score zero; scores refresh every 30 seconds. Only the two participants can access an accepted rivalry's matchup, and hidden case/game details are never returned.

- Invite existing users by username; recipients accept or decline in Head-to-head, and senders can cancel pending invites. Multiple opponents are allowed, with at most one pending/active rivalry per pair per season.
- Acceptance before the current week's Sunday 1 PM Eastern lineup lock starts the rivalry in that same week. At or after the lock it starts in the next unlocked week, through regular-season Week 18. The start is determined at acceptance, not invitation time. For example, accepting before September 27, 2026 at 1 PM Eastern starts Week 3. Eastern uses daylight-saving time when applicable, not a fixed UTC offset.
- The same weekly lineup faces every opponent. Actual full-PPR totals decide the winner, empty slots score zero, and equal totals are ties (including two empty lineups).
- Each rivalry stores weekly scores/results and shows both users' W–L–T records, finalized season points, and week-by-week history. Overall season points count each finalized matched week once, not once per opponent. Overall records count each opponent matchup.
- Live scores are provisional. The existing worker polls results every three minutes and attempts weekly finalization at the following Tuesday opening; missing final player results hold the affected matchup open. Recomputations, stat corrections, and unfinalization update records without double-counting.
- Profile changes do not break invitations or history. Reads are participant-only through FastAPI; browser database roles cannot access either rivalry table. Invitations are in-app, not email notifications.

`AUTO_SYNC=true` is enabled in the current local `backend/.env`. The API must remain running for automatic live scoring/finalization; the independent 9 AM task refreshes projections only. For new installations, run `.venv/Scripts/python -m app.cli migrate` before starting the live API. Existing practice databases receive the additive favorite-team column without resetting progress.

## Data and weekly automation

The ESPN adapter uses the fantasy default PPR player feed, explicitly requests the target week's projections, paginates the entire eligible-position pool, and retrieves kickoff/status from ESPN's Core API. The site scoreboard is a fallback. Metadata/projections/results are normalized before reaching game logic. ESPN APIs are unofficial and can change; errors are recorded and the last successful projection snapshot is preserved.

```powershell
.venv/Scripts/python -m app.cli sync --season 2026 --week 3 --operation projections
.venv/Scripts/python -m app.cli sync --season 2026 --week 3 --operation results
```

### Daily 9:00 AM Eastern projection refresh

Windows Task Scheduler task `SundayVault-ESPN-Projections-0900ET` refreshes ESPN projections every day at **9:00 AM Eastern**, automatically discovering the current season/week. It runs silently under your Windows account, independently of the web app, using `backend/.env`. Existing game snapshots remain frozen.

Keep this computer powered on, connected to the internet, and signed in. The task is configured to catch up on missed runs and retry failures three times at 15-minute intervals. Its local-time trigger follows the computer's Eastern timezone; keep Windows set to Eastern Time. See [Windows task settings](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset?view=windowsserver2025-ps).

Logs are written to `artifacts/espn-daily-projections.log`, with rotation. The initial scheduled-task test succeeded on September 23, 2026, importing 338 Week 3 players. The game's minimum 3.0-point eligibility filter still applies separately.

```powershell
Get-ScheduledTaskInfo -TaskName 'SundayVault-ESPN-Projections-0900ET'
# Refresh immediately:
Start-ScheduledTask -TaskName 'SundayVault-ESPN-Projections-0900ET'
# Pause the daily refresh if needed:
Disable-ScheduledTask -TaskName 'SundayVault-ESPN-Projections-0900ET'
```

To register on a new local installation, run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/register_projection_refresh.ps1` under your normal Windows account. The script refuses to overwrite an existing task. This is a local schedule, not a Vercel/cloud job.

### Optional continuous worker

For more frequent projection updates and live results, run a second terminal:

```powershell
.venv/Scripts/python -m app.worker
```

Or set `AUTO_SYNC=true` in `backend/.env` to run the worker with the API. The worker discovers the current week, refreshes projections every 30 minutes before the deadline, polls results every three minutes after kickoff, and attempts finalization at the following Tuesday opening. A PostgreSQL advisory lock prevents overlapping workers. Keep the local machine/process running for automated updates.

Provider-supplied fantasy totals are used when they match full PPR; otherwise points are normalized explicitly from ESPN stat fields. This avoids inheriting custom personal-league scoring. Passing, rushing, receiving, receptions, lost fumbles, two-point conversions, return TDs and offensive fumble-recovery TDs are supported. Long-touchdown/yardage bonuses are not enabled. Projection and actual points are never interchangeable.

`ESPN_LEAGUE_ID`, `ESPN_SWID`, and `ESPN_S2` are optional backend settings if you later use a personal league. Cookies stay server-side.

## Admin and CSV fallback

Add your Supabase user UUID to `ADMIN_USER_IDS` in `backend/.env` and restart the API to unlock `/admin`. Normal users cannot access any admin endpoint. The trusted local CLI also supports:

```powershell
.venv/Scripts/python -m app.cli health
.venv/Scripts/python -m app.cli import --file path/to/weekly.csv --season 2026 --week 3 --operation projections
.venv/Scripts/python -m app.cli import --file path/to/results.csv --season 2026 --week 3 --operation results
.venv/Scripts/python -m app.cli recompute --season 2026 --week 3
.venv/Scripts/python -m app.cli finalize --season 2026 --week 3
.venv/Scripts/python -m app.cli unfinalize --season 2026 --week 3
.venv/Scripts/python -m app.cli audit --game GAME_UUID
.venv/Scripts/python -m app.cli expire --game GAME_UUID
```

Use [the CSV header template](docs/manual-import-template.csv). Player IDs should be ESPN IDs so fallback imports reconcile with existing players. Kickoffs must have an explicit timezone. A projection snapshot requires at least 14 players at each required position projected for at least 3.0 full-PPR points. With 10 balanced tiers, 14 players ensure tiers 2 and 4 each contain two unique players. `game_status` accepts `NOT_STARTED`, `LIVE`, `FINAL`, or `CORRECTED`; use `FINAL` for the schedule when finalizing. Imports are transactional. Finalization rejects unfinished games or missing final results for rostered players.

## Integrity and security

The current rule update below supersedes the original specification's tier split, EV-only Dealer coefficients, and no-random-noise rule, as well as the earlier 14-tier/top-12 variant.

The backend has 142 passing tests, covering game integrity, daily refresh locking, required username onboarding, profile validation, and season-long rivalries. Game coverage includes the exact 3.0 threshold, 10-tier selection with unique extra picks from tiers 2 and 4, population-SD risk premiums, bounded repeatable offer randomness, all four Dealer rounds, home/away matchup display data, and legacy-game expiration without changing completed picks.

- Slots fill in RB1, RB2, WR1, WR2, TE, FLEX order. No player or completed slot can be reused.
- Both cases and Dealer offers require a raw full-PPR projection of at least 3.0. Values below 3.0 are excluded even if they round to 3.0 on screen.
- The full eligible pool is split into 10 contiguous, balanced tiers. Select one player per tier plus an additional unique player from each of tiers 2 and 4, then shuffle the 12 players into cases. Sampling is without replacement; Dealer offers still use the full eligible pool.
- New games use algorithm `risk-v4-10tiers-extra2and4`. Existing boards remain frozen unless an unfinished game contains a case or pending offer below 3.0, in which case it expires and the slot can restart. Completed picks are preserved.
- Each game freezes its projection snapshot and candidate pool. All game actions validate ownership, state, time, and expected version.
- Opening schedule remains 4 / 3 / 2 / 1. Dealer targets are `(remaining EV × multiplier + population SD × risk weight) × random factor`. For 8 / 5 / 3 / 2 unopened cases, multipliers are 0.88 / 0.95 / 1.00 / 1.05 and risk weights are 0.10 / 0.15 / 0.20 / 0.25. The user's sealed case is included.
- The server draws a factor from 0.97–1.03 in 0.0001 increments, deterministically using the private game seed and offer number. It maps the unrounded target to the closest eligible player, retaining roster/declined-player exclusions and existing tie-break rules. Refreshes and retries cannot reroll an offer.
- Each new offer records its SD, risk weight, base target, random factor and Dealer version (`ev-sd-jitter-v1`) in the server-only audit event alongside the saved offer. Existing offers and completed picks are not recalculated; future offers in active games use the new formula. No schema migration is needed.
- PostgreSQL row locks serialize awards and actions. SQLite uses immediate transactions for local practice. Duplicate requests return a safe conflict.
- Expiration covers every Dealer candidate, plus the global Sunday deadline; earlier rescheduled kickoffs also expire active games.
- API serializers never return hidden mappings, seeds, EV, target projections or coefficients. RLS is enabled on every application table; browser roles have no game-table read/write access.
- Auth verifies JWT signature, issuer, audience and expiration using Supabase JWKS; legacy HS256 tokens are verified by Supabase's `/user` endpoint.
- Mutating routes have a per-user, database-backed rate limit. Audit events and provider jobs are logged server-side in structured form.
- Completed lineups alone qualify. Scores use actual results; tied scores share rank. Season scores include only finalized weeks.

Migrations are versioned under `supabase/migrations`. Apply pending migrations with:

```powershell
.venv/Scripts/python -m app.cli migrate
```

The first migration was generated from the ORM models, then reviewed for RLS/client permissions. Future schema changes need a new migration; do not regenerate/overwrite an applied migration.

## Verification

September 23 account/rivalry update: 134 backend tests pass, including per-opponent and overall records, invitation ownership, Sunday-lock boundaries, partial/empty lineups, ties, missing final results, corrections, and deduplicated season points. Profile/head-to-head browser tests and the game regression tests pass. `node scripts/check_auth_ui.mjs` additionally verifies live-mode signup validation, verified-user onboarding, password changes, and email changes with all auth/profile requests mocked (no real users created or changed). Lint and TypeScript checks pass. The migrated Supabase database has RLS enabled and browser writes denied on all 18 tables, including participant-only rivalry data.

Verified locally on September 22, 2026: 58 backend tests pass, the desktop/mobile six-slot browser flow passes, and lint, TypeScript checks, and the Next.js production build pass. The live ESPN Week 3 import contains 339 eligible players (97 RB, 158 WR, 84 TE). A read-only database audit verified RLS and denied browser writes on all 16 application/migration tables. The publishable key was validated against Supabase's authentication settings endpoint; real email signup, login, and password reset still require an end-to-end check with your own email inbox. No deployment has been performed.

```powershell
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/python -m ruff check backend
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The browser test starts separate services on ports 3100/8100 with a fresh test database and separate Next.js build directory on each run. It exercises desktop/mobile layouts, all six slots, refresh/resume, declined and accepted offers, both final keep/swap choices, lineup, leaderboard and history. Banker offers, final choices, and locked-player reveals share case-area overlays that leave the player board and previous offers unobscured; tests cover placement, keyboard focus, mobile controls, and reload persistence. Normal practice progress is preserved. Real email signup/password reset require the project's publishable key and an email inbox, and are not replaced by practice authentication tests. Unit tests also verify JWT signatures, expiration, issuer, audience, and demo-mode isolation.

Screenshots are written to ignored `artifacts/`. `scripts/verify_provider.py` checks real ESPN feeds without printing credentials. `scripts/audit_db.py` performs read-only RLS/permission checks.

## Project layout

```text
frontend/                 Next.js App Router, auth UI, game UI, Playwright
backend/app/core/         Settings, database, authentication, UTC/ET helpers
backend/app/services/     Pure rules, transactional game engine, scoring, imports
backend/app/providers/    ESPN adapter, provider protocol, CSV adapter
backend/tests/            Rules, state transitions, scoring, API and race tests
supabase/migrations/      Versioned PostgreSQL schema and RLS
scripts/                 Local launcher and verification utilities
deal_or_no_deal/          Original production specification
```

## MCP and future Vercel deployment

Supabase MCP is configured and OAuth-authenticated in the user-level Codex configuration. The project `.mcp.json` also contains the Claude-compatible server definition. A newly configured MCP server may need a new Codex session before its tools appear; the current build used the supplied database connection for migrations. Configuration/authentication follows [the official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

The frontend can later deploy to Vercel with `frontend` as its project root. FastAPI needs its own Python runtime (a separate Vercel Python project or another backend host), HTTPS API URL, configured CORS, and Supabase auth redirect URLs. The persistent local worker must become a scheduled job; it must not rely on an in-process loop inside a serverless request. Never enable practice identity/data on that deployment.

Working branding and team logos should be reviewed before a commercial release. This build is for personal use and is not affiliated with the NFL, ESPN, or the television show.

## Source references

- [Production rules](deal_or_no_deal/NFL_Fantasy_Deal_or_No_Deal_Production_Spec.md)
- [Next.js App Router](https://nextjs.org/docs/app)
- [Supabase JWT verification](https://supabase.com/docs/guides/auth/jwts)
- [ESPN fantasy default PPR endpoint](https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leaguedefaults/3?view=kona_player_info)
- [ESPN Core NFL data](https://sports.core.api.espn.com/v2/sports/football/leagues/nfl)
- [Open-source ESPN stat field mapping](https://github.com/cwendt94/espn-api/blob/master/espn_api/football/constant.py)
