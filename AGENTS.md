# Fantasy football league data

This repo holds a live snapshot of Sina's ESPN fantasy football league so any AI assistant can answer questions about it: who to start, who to pick up, who to target in trades, what offers are out there.

## Who you're helping

- Sina owns **team id 2** in ESPN league 1241185 (season 2026). The current team name is in `data/overview.md` under "My team".
- Sina is not a developer. Answer in plain language, takeaway first, one recommendation with a short reason.

## Where the data is

Everything is in `data/`, rewritten on every pull:

| File | What's in it |
|---|---|
| `data/overview.md` | Standings, this week's matchups, my schedule, league rules and scoring |
| `data/rosters.md` | Every team's roster with this week's slot, opponent, projection, injury status and season points |
| `data/free_agents.md` | Top unrostered players by position |
| `data/activity.md` | Trade offers and decisions ESPN shows, waiver claims managers cancelled, plus recent adds, drops and completed trades |
| `data/league.json` | All of the above as structured data, for calculations. Also holds what the markdown leaves out: every team's lineup and points for each finished week (`history`), the draft (`draft`), all waiver claims (`waiver_claims`), completed trades (`completed_trades`), and per player how they were acquired, ESPN's preseason projection and season rank at the position |
| `data/league.js` | The same data wrapped as a script for `dashboard.html`. Read `league.json` instead |

## Before you answer

1. **Check freshness.** The "Updated" line at the top of each file is the pull time. Data refreshes about hourly (every 15 minutes on Sunday mornings US Eastern). If it's more than 3 hours old, say so, because the pull may be broken (usually expired ESPN cookies).
2. **Refresh if the decision is time-sensitive.** Run `gh workflow run pull.yml`, wait about a minute, then `git pull`. If you can't, tell Sina to open the repo's Actions tab on GitHub, choose "Pull league data", and press "Run workflow".
3. **Check `data/overview.md` for a "Problems in this pull" note.** Sections listed there may be empty or stale.

## Rules for advice

- **Advice only.** Never try to change anything on ESPN (lineups, claims, trades). Sina makes every move by hand in the ESPN app.
- **Fit the league rules** in `data/overview.md`: roster slots, scoring, waiver type, trade deadline.
- **Respect position limits.** Each roster can hold only so many players per position (listed under League rules in `data/overview.md`, and per team in `data/rosters.md`). Before suggesting any trade or pickup, count the position on the receiving roster after the move, for Sina and for the other team. If it would go over, the move is not allowed unless a player at that position is dropped or sent back, so say which one. A player in the IR slot does not count. As of October 2026 the limits add up to exactly the roster size and every team is full, so in practice a trade has to swap the same positions (a running back for a running back, or a running back and a receiver for a running back and a receiver) and a pickup means dropping a player at the same position.
- **Respect roster size.** A roster holds 9 starters plus the bench. A trade that brings back more players than it sends needs a named drop.
- **IR slot:** one slot, only for a player ESPN marks Out or IR. A pickup cannot go straight to IR: he has to be added to a normal roster spot first (which may need a drop), then moved to IR. Never suggest "add him to your IR".
- **Projections here are ESPN's.** If you have web search, check current injury news and other rankings before a start/sit or trade call, and say when you couldn't.
- **Trade ideas need to work for both sides.** Look at the other team's roster in `data/rosters.md` for what they need and can spare.
- **Trade offers:** `data/activity.md` lists offers across the whole league. ESPN shows this login the players on Sina's own offers and on offers other teams sent and then withdrew. Offers other teams accepted or declined appear only as a decision record with no players, so match accepted trades by date to the TRADE rows in the recent-moves table. It is not yet confirmed whether a still-open offer between two other teams shows up.
- **"ESPN proj/gm"** (`proj_avg`) is ESPN's current projected points per game, the best single number here for a player's value going forward.

## How it works

`dashboard.html` is Sina's own view of this data (lineup check, trade ideas, waiver picks, league table). It reads `data/league.js` and does its sums in the browser, so change it there if Sina asks for a dashboard change.

`pull_league.py` runs on GitHub Actions (`.github/workflows/pull.yml`), reads the league from ESPN using two login cookies stored as repo secrets (`ESPN_S2`, `ESPN_SWID`), and commits the files in `data/`. It is read-only. Never print, log or commit those cookie values.
