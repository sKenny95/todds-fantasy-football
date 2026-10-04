# todds-fantasy-football

A self-updating snapshot of my ESPN fantasy football league, so any AI assistant (Claude, Codex, ChatGPT) can answer questions about it from anywhere.

- **Data:** the `data/` folder, refreshed about every hour by GitHub Actions.
- **Instructions for AI assistants:** [AGENTS.md](AGENTS.md).
- **Refresh now:** Actions tab → "Pull league data" → "Run workflow".

## If the data stops updating

The two ESPN login cookies have probably expired. Get fresh ones and replace the repo secrets:

1. Sign in at fantasy.espn.com in Chrome, press F12, open **Application → Cookies → https://fantasy.espn.com**.
2. Copy the values of `espn_s2` and `SWID`.
3. In this repo: **Settings → Secrets and variables → Actions**, update `ESPN_S2` and `ESPN_SWID`.

Treat those two values like a password. They never belong in a file in this repo.
