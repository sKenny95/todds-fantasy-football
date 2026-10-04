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
| `data/activity.md` | Trade offers and decisions ESPN shows, plus recent adds, drops and completed trades |
| `data/league.json` | All of the above as structured data, for calculations |

## Before you answer

1. **Check freshness.** The "Updated" line at the top of each file is the pull time. Data refreshes about hourly (every 15 minutes on Sunday mornings US Eastern). If it's more than 3 hours old, say so, because the pull may be broken (usually expired ESPN cookies).
2. **Refresh if the decision is time-sensitive.** Run `gh workflow run pull.yml`, wait about a minute, then `git pull`. If you can't, tell Sina to open the repo's Actions tab on GitHub, choose "Pull league data", and press "Run workflow".
3. **Check `data/overview.md` for a "Problems in this pull" note.** Sections listed there may be empty or stale.

## Rules for advice

- **Advice only.** Never try to change anything on ESPN (lineups, claims, trades). Sina makes every move by hand in the ESPN app.
- **Fit the league rules** in `data/overview.md`: roster slots, scoring, waiver type, trade deadline.
- **Projections here are ESPN's.** If you have web search, check current injury news and other rankings before a start/sit or trade call, and say when you couldn't.
- **Trade ideas need to work for both sides.** Look at the other team's roster in `data/rosters.md` for what they need and can spare.
- **Trade offers:** `data/activity.md` only lists what ESPN shows Sina's login. Offers between two other teams may be hidden until accepted.

## How it works

`pull_league.py` runs on GitHub Actions (`.github/workflows/pull.yml`), reads the league from ESPN using two login cookies stored as repo secrets (`ESPN_S2`, `ESPN_SWID`), and commits the files in `data/`. It is read-only. Never print, log or commit those cookie values.
