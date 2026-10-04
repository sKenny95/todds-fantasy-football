"""Pull the ESPN fantasy league into data/ as markdown and JSON. Read-only: it never changes anything on ESPN."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from espn_api.football import League

LEAGUE_ID = int(os.environ.get("ESPN_LEAGUE_ID", "1241185"))
SEASON = int(os.environ.get("ESPN_SEASON", "2026"))
MY_TEAM_ID = int(os.environ.get("ESPN_TEAM_ID", "2"))
DATA_DIR = Path(__file__).parent / "data"
ET = ZoneInfo("America/New_York")

FREE_AGENT_COUNTS = {"QB": 15, "RB": 30, "WR": 30, "TE": 15, "K": 10, "D/ST": 10}
FREE_AGENT_SLOT_IDS = {"QB": 0, "RB": 2, "WR": 4, "TE": 6, "D/ST": 16, "K": 17}
WAIVER_TYPES =["WAIVER", "WAIVER_ERROR"]
BYES = {}  # NFL team -> bye week, filled in by gather()
TRADE_TYPES = ["TRADE_PROPOSAL", "TRADE_ACCEPT", "TRADE_DECLINE", "TRADE_UPHOLD", "TRADE_VETO", "TRADE_ERROR"]
SLOT_ORDER = ["QB", "RB", "WR", "TE", "RB/WR/TE", "RB/WR", "WR/TE", "OP", "D/ST", "K", "BE", "IR"]


def et(ms):
    """ESPN timestamps are milliseconds since 1970; show them in US Eastern time."""
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=ET).strftime("%a %b %d, %I:%M %p ET")


def num(value, digits=1):
    return round(value, digits) if isinstance(value, (int, float)) else None


# ---------- gather: ESPN -> plain dict ----------

def player_dict(p):
    status = p.injuryStatus if isinstance(p.injuryStatus, str) else None
    return {
        "id": p.playerId,
        "name": p.name,
        "pos": p.position,
        "nfl": p.proTeam,
        "status": None if status in ("ACTIVE", "NORMAL") else status,
        "slot": getattr(p, "lineupSlot", ""),
        "season_pts": num(getattr(p, "total_points", None)),
        "season_avg": num(getattr(p, "avg_points", None)),
        "proj_season_pts": num(getattr(p, "projected_total_points", None)),
        "proj_avg": num(getattr(p, "projected_avg_points", None)),
        "bye_week": BYES.get(p.proTeam),
        "pct_owned": getattr(p, "percent_owned", None),
        "pct_started": getattr(p, "percent_started", None),
    }


def week_dict(bp):
    """This week's numbers for a player, from a box score or the free agent list."""
    rank = getattr(bp, "pro_pos_rank", 0)
    return {
        "slot": bp.slot_position,
        "proj": num(bp.projected_points),
        "pts": num(bp.points),
        "opp": None if bp.on_bye_week else bp.pro_opponent,
        "opp_rank_vs_pos": rank if rank else None,
        "bye": bp.on_bye_week,
        "game": getattr(bp, "game_date", None),
    }


def owner_names(team):
    names = []
    for owner in team.owners or []:
        names.append(owner.get("firstName") or owner.get("displayName") or "")
    return ", ".join(n.strip() for n in names if n.strip())


def team_dict(team, division_map):
    schedule = []
    for i, opp in enumerate(team.schedule):
        schedule.append({
            "week": i + 1,
            "opponent": getattr(opp, "team_name", str(opp)).strip(),
            "score": team.scores[i] if i < len(team.scores) else None,
            "result": team.outcomes[i] if i < len(team.outcomes) else None,
        })
    return {
        "id": team.team_id,
        "name": team.team_name.strip(),
        "owner": owner_names(team),
        "division": division_map.get(team.division_id, ""),
        "seed": team.standing,
        "wins": team.wins,
        "losses": team.losses,
        "ties": team.ties,
        "points_for": num(team.points_for),
        "points_against": num(team.points_against),
        "streak": f"{team.streak_type[:1]}{team.streak_length}" if team.streak_type else "",
        "waiver_rank": team.waiver_rank,
        "espn_playoff_pct": num(team.playoff_pct),
        "adds": team.acquisitions,
        "drops": team.drops,
        "trades": team.trades,
        "schedule": schedule,
        "roster": [player_dict(p) for p in team.roster],
    }


def settings_dict(s):
    return {
        "name": s.name,
        "teams": s.team_count,
        "regular_season_weeks": s.reg_season_count,
        "playoff_teams": s.playoff_team_count,
        "playoff_seeding": s.playoff_seed_tie_rule,
        "scoring_type": s.scoring_type,
        "trade_deadline": et(s.trade_deadline),
        "trade_review_hours": s.trade_revision_hours,
        "veto_votes_required": s.veto_votes_required,
        "faab": s.faab,
        "faab_budget": s.acquisition_budget if s.faab else None,
        "season_add_limit": s.acquisition_limit,
        "waiver_process_days": s.waiver_process_days,
        "roster_slots": {k: v for k, v in s.position_slot_counts.items() if v},
        "scoring": sorted(
            ({"label": i["label"], "points": i["points"]} for i in s.scoring_format if i["points"]),
            key=lambda i: i["label"],
        ),
    }


def trade_dict(t, team_names, player_map):
    items = []
    for item in t.get("items") or []:
        items.append({
            "player": player_map.get(item.get("playerId"), item.get("playerId")),
            "from": team_names.get(item.get("fromTeamId"), item.get("fromTeamId")),
            "to": team_names.get(item.get("toTeamId"), item.get("toTeamId")),
            "type": item.get("type"),
        })
    return {
        "id": t.get("id"),
        "type": t.get("type"),
        "status": t.get("status"),
        "team": team_names.get(t.get("teamId"), t.get("teamId")),
        "proposed_ms": t.get("proposedDate") or 0,
        # ESPN leaves old offers marked PENDING after they lapse, so check the expiry ourselves
        "expired": bool(t.get("expirationDate")) and t["expirationDate"] < datetime.now(timezone.utc).timestamp() * 1000,
        "proposed": et(t.get("proposedDate")),
        "processed": et(t.get("processDate")),
        "expires": et(t.get("expirationDate")),
        "week": t.get("scoringPeriodId"),
        "related_id": t.get("relatedTransactionId"),
        "comment": t.get("comment"),
        "items": items,
    }


def fetch_trades(league, week, team_names):
    """Trade proposals and decisions ESPN shows this login, season to date."""
    seen, trades = set(), []
    headers = {"x-fantasy-filter": json.dumps({"transactions": {"filterType": {"value": TRADE_TYPES}}})}
    raw = []
    for wk in range(1, week + 1):
        data = league.espn_request.league_get(
            params={"view": "mTransactions2", "scoringPeriodId": wk}, headers=headers
        )
        raw += [t for t in data.get("transactions", []) if t.get("type") in TRADE_TYPES]
    data = league.espn_request.league_get(params={"view": "mPendingTransactions"})
    raw += [t for t in data.get("pendingTransactions") or [] if str(t.get("type", "")).startswith("TRADE")]
    for t in raw:
        if t.get("id") in seen:
            continue
        seen.add(t.get("id"))
        trades.append(trade_dict(t, team_names, league.player_map))
    return sorted(trades, key=lambda t: t["proposed_ms"], reverse=True)


def fetch_waivers(league, week, team_names):
    """Waiver claims ESPN shows this login: ones that went through, and ones a manager placed and then cancelled."""
    headers = {"x-fantasy-filter": json.dumps({"transactions": {"filterType": {"value": WAIVER_TYPES}}})}
    seen, claims = set(), []
    for wk in range(1, week + 1):
        data = league.espn_request.league_get(params={"view": "mTransactions2", "scoringPeriodId": wk}, headers=headers)
        for t in data.get("transactions", []):
            if t.get("type") not in WAIVER_TYPES or t.get("id") in seen:
                continue
            seen.add(t.get("id"))
            items = t.get("items") or []
            claims.append({
                "team": team_names.get(t.get("teamId"), t.get("teamId")),
                "status": t.get("status"),
                "when_ms": t.get("proposedDate") or 0,
                "when": et(t.get("proposedDate")),
                "week": wk,
                "add": [league.player_map.get(i.get("playerId"), i.get("playerId")) for i in items if i.get("type") == "ADD"],
                "drop": [league.player_map.get(i.get("playerId"), i.get("playerId")) for i in items if i.get("type") == "DROP"],
            })
    return sorted(claims, key=lambda c: c["when_ms"], reverse=True)


def player_extra(entry, week, acquired=None):
    """Details the library leaves out, from ESPN's raw player record."""
    p = entry.get("player") or {}
    own = p.get("ownership") or {}
    expert = [r.get("averageRank") for r in (p.get("rankings") or {}).get(str(week), [])
              if r.get("rankType") == "PPR" and r.get("averageRank")]
    preseason = [s.get("appliedAverage") for s in p.get("stats") or []
                 if (s.get("seasonId"), s.get("scoringPeriodId"), s.get("statSourceId"), s.get("statSplitTypeId")) == (SEASON, 0, 1, 2)]
    return {
        "acquired": acquired,
        "pos_rank": ((entry.get("ratings") or {}).get("0") or {}).get("positionalRanking"),
        "expert_rank": num(expert[0]) if expert else None,
        "pct_change": num(own.get("percentChange"), 2),
        "preseason_avg": num(preseason[0]) if preseason else None,
        "waivers_until": et(entry.get("waiverProcessDate")) if entry.get("status") == "WAIVERS" else None,
    }


def fetch_extras(league, week):
    """Per-player and per-team details from ESPN's raw views, keyed by id."""
    req, players, teams = league.espn_request, {}, {}
    for t in req.league_get(params={"view": "mRoster"}).get("teams", []):
        for e in (t.get("roster") or {}).get("entries", []):
            players[e.get("playerId")] = player_extra(e.get("playerPoolEntry") or {}, week, e.get("acquisitionType"))
    # same per-position lists the library's free_agents() asks for, so the ids line up
    for pos, size in FREE_AGENT_COUNTS.items():
        filt = {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS"]}, "filterSlotIds": {"value": [FREE_AGENT_SLOT_IDS[pos]]},
                            "limit": size, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
        data = req.league_get(params={"view": "kona_player_info", "scoringPeriodId": week}, headers={"x-fantasy-filter": json.dumps(filt)})
        for x in data.get("players", []):
            players[x.get("id")] = player_extra(x, week)
    for t in req.league_get(params={"view": "mTeam"}).get("teams", []):
        teams[t.get("id")] = {
            "espn_proj_rank": t.get("currentProjectedRank"),
            "draft_day_rank": t.get("draftDayProjectedRank"),
            "lineup_moves": (t.get("transactionCounter") or {}).get("moveToActive"),
        }
    return players, teams


def fetch_history(league, week):
    """Every team's lineup and points for each finished week."""
    out = []
    for wk in range(1, week):
        teams = {}
        for box in league.box_scores(wk):
            for team, score, lineup in ((box.home_team, box.home_score, box.home_lineup), (box.away_team, box.away_score, box.away_lineup)):
                if hasattr(team, "team_id"):
                    teams[team.team_id] = {"score": num(score, 2), "players": [
                        {"id": bp.playerId, "name": bp.name, "pos": bp.position, "slot": bp.slot_position,
                         "pts": num(bp.points), "proj": num(bp.projected_points)} for bp in lineup]}
        out.append({"week": wk, "teams": teams})
    return out


def fetch_draft(league):
    return [{"overall": i + 1, "round": p.round_num, "pick": p.round_pick, "team_id": p.team.team_id,
             "player_id": p.playerId, "player": p.playerName} for i, p in enumerate(league.draft)]


def fetch_activity(league):
    out = []
    for act in league.recent_activity(size=40):
        actions = []
        for team, action, player, _bid in act.actions:
            actions.append({
                "team": getattr(team, "team_name", str(team)).strip(),
                "action": action,
                "player": getattr(player, "name", str(player)),
                "pos": getattr(player, "position", ""),
                "nfl": getattr(player, "proTeam", ""),
            })
        out.append({"when": et(act.date), "actions": actions})
    return out


def gather(league):
    week = league.current_week
    snap = {
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_et": datetime.now(ET).strftime("%a %b %d %Y, %I:%M %p ET"),
        "league_id": LEAGUE_ID,
        "season": SEASON,
        "week": week,
        "my_team_id": MY_TEAM_ID,
        "warnings": [],
    }

    def attempt(key, fn, default):
        """One failed section should not sink the whole pull."""
        try:
            snap[key] = fn()
        except Exception as exc:  # noqa: BLE001
            snap[key] = default
            snap["warnings"].append(f"{key}: {type(exc).__name__}: {exc}")

    try:
        pro = league.espn_request.get_pro_schedule()
        BYES.update({t.get("abbrev"): t.get("byeWeek") for t in pro.get("settings", {}).get("proTeams", []) if t.get("byeWeek")})
    except Exception as exc:  # noqa: BLE001
        snap["warnings"].append(f"bye weeks: {type(exc).__name__}: {exc}")

    snap["settings"] = settings_dict(league.settings)
    division_map = league.settings.division_map
    snap["teams"] = [team_dict(t, division_map) for t in sorted(league.teams, key=lambda t: t.standing)]
    team_names = {t["id"]: t["name"] for t in snap["teams"]}

    def matchups():
        out, weekly = [], {}
        for box in league.box_scores(week):
            sides = []
            for team, score, proj, lineup in (
                (box.home_team, box.home_score, box.home_projected, box.home_lineup),
                (box.away_team, box.away_score, box.away_projected, box.away_lineup),
            ):
                if not hasattr(team, "team_id"):
                    continue
                sides.append({"id": team.team_id, "name": team.team_name.strip(), "score": score, "proj": proj if proj and proj > 0 else None})
                for bp in lineup:
                    weekly[bp.playerId] = week_dict(bp)
            if sides:
                out.append(sides)
        # attach this week's slot, projection and opponent to each rostered player
        for team in snap["teams"]:
            for p in team["roster"]:
                p["week"] = weekly.get(p["id"])
        return out

    def free_agents():
        out = {}
        for pos, size in FREE_AGENT_COUNTS.items():
            out[pos] = [{**player_dict(p), "week": week_dict(p)} for p in league.free_agents(week=week, size=size, position=pos)]
        return out

    attempt("matchups", matchups, [])
    attempt("free_agents", free_agents, {})
    attempt("trades", lambda: fetch_trades(league, week, team_names), [])
    attempt("activity", lambda: fetch_activity(league), [])
    attempt("waiver_claims", lambda: fetch_waivers(league, week, team_names), [])
    attempt("history", lambda: fetch_history(league, week), [])
    attempt("draft", lambda: fetch_draft(league), [])

    def extras():
        free = [p for players in snap["free_agents"].values() for p in players]
        players, teams = fetch_extras(league, week)
        for p in [p for t in snap["teams"] for p in t["roster"]] + free:
            p.update(players.get(p["id"], {}))
        for t in snap["teams"]:
            t.update(teams.get(t["id"], {}))
        return True

    attempt("extras", extras, False)
    return snap


# ---------- render: dict -> markdown ----------

def table(headers, rows):
    def cell(v):
        return "" if v is None else str(v).replace("|", "/")
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def header(snap, title):
    return f"# {title}\n\nUpdated: {snap['updated_et']} · NFL week {snap['week']} · {snap['settings']['name']}\n"


def slot_key(p):
    slot = (p.get("week") or {}).get("slot") or p.get("slot") or "BE"
    return SLOT_ORDER.index(slot) if slot in SLOT_ORDER else len(SLOT_ORDER)


def player_row(p, with_slot=True):
    wk = p.get("week") or {}
    opp = "BYE" if wk.get("bye") else wk.get("opp")
    if opp and not wk.get("bye") and wk.get("opp_rank_vs_pos"):
        opp = f"{opp} (#{wk['opp_rank_vs_pos']} vs {p['pos']})"
    row = [f"{p['name']}", p["pos"], p["nfl"], p["status"], opp, wk.get("proj"), wk.get("pts"),
           p["season_avg"], p["season_pts"], p.get("proj_avg"), p.get("expert_rank"), p.get("bye_week"), p["pct_owned"], p.get("pct_change")]
    return ([wk.get("slot") or p.get("slot")] + row) if with_slot else row


PLAYER_HEADERS = ["Player", "Pos", "NFL", "Injury", "Opp this week", "Proj", "Pts so far", "Avg/gm", "Season pts",
                  "ESPN proj/gm", "Expert rank this wk", "Bye wk", "% rostered", "% change"]


def render_overview(snap):
    s = snap["settings"]
    my = next((t for t in snap["teams"] if t["id"] == snap["my_team_id"]), None)
    out = [header(snap, "League overview")]
    if snap["warnings"]:
        out.append("**Problems in this pull (those sections may be empty or stale):**\n" + "\n".join(f"- {w}" for w in snap["warnings"]) + "\n")
    if my:
        out.append(f"**My team:** {my['name']} (team id {my['id']}), {my['wins']}-{my['losses']}-{my['ties']}, seed {my['seed']}, waiver rank {my['waiver_rank']}.\n")

    out.append("## Standings\n")
    out.append(table(
        ["Seed", "Team", "Owner", "Div", "W-L-T", "PF", "PA", "Streak", "Waiver rank", "ESPN playoff %", "ESPN projected finish",
         "Adds", "Trades", "Lineup moves"],
        [[t["seed"], t["name"] + (" **(me)**" if t["id"] == snap["my_team_id"] else ""), t["owner"], t["division"],
          f"{t['wins']}-{t['losses']}-{t['ties']}", t["points_for"], t["points_against"], t["streak"],
          t["waiver_rank"], t["espn_playoff_pct"], t.get("espn_proj_rank"), t["adds"], t["trades"], t.get("lineup_moves")] for t in snap["teams"]],
    ))

    out.append(f"\n## Week {snap['week']} matchups\n")
    out.append("Scores are live points so far; Proj is ESPN's projected final.\n")
    out.append(table(
        ["Team", "Score", "Proj", "vs", "Team", "Score", "Proj"],
        [[m[0]["name"], m[0]["score"], m[0]["proj"], "vs", m[1]["name"], m[1]["score"], m[1]["proj"]]
         if len(m) == 2 else [m[0]["name"], m[0]["score"], m[0]["proj"], "bye", "", "", ""] for m in snap["matchups"]],
    ))

    if my:
        out.append("\n## My schedule\n")
        out.append(table(["Week", "Opponent", "My score", "Result"],
                         [[g["week"], g["opponent"], g["score"] or "", {"U": ""}.get(g["result"], g["result"])] for g in my["schedule"]]))

    out.append("\n## League rules\n")
    slots = ", ".join(f"{k}×{v}" for k, v in s["roster_slots"].items())
    waivers = f"FAAB, ${s['faab_budget']} budget" if s["faab"] else "waiver priority order (no bidding)"
    out.append("\n".join([
        f"- {s['teams']} teams, {s['regular_season_weeks']}-week regular season, {s['playoff_teams']} playoff teams (seeding: {s['playoff_seeding']}).",
        f"- Roster slots: {slots}.",
        f"- Waivers: {waivers}. Process days: {', '.join(s['waiver_process_days']) or 'n/a'}. Season add limit: {s['season_add_limit'] if s['season_add_limit'] not in (None, -1) else 'none'}.",
        f"- Trades: deadline {s['trade_deadline'] or 'none'}, {s['trade_review_hours']}-hour review, {s['veto_votes_required']} veto votes required.",
    ]))
    out.append("\n### Scoring\n")
    out.append(table(["Stat", "Points"], [[i["label"], i["points"]] for i in s["scoring"]]))
    return "\n".join(out) + "\n"


def render_rosters(snap):
    out = [header(snap, "All rosters"), "Proj and Opp are for this week. Avg/gm and Season pts are season to date.\n"]
    for t in snap["teams"]:
        me = " (MY TEAM)" if t["id"] == snap["my_team_id"] else ""
        out.append(f"## {t['name']}{me}\n")
        out.append(f"Owner {t['owner'] or 'n/a'} · {t['wins']}-{t['losses']}-{t['ties']} · seed {t['seed']} · {t['points_for']} PF · waiver rank {t['waiver_rank']}\n")
        out.append(table(["Slot"] + PLAYER_HEADERS, [player_row(p) for p in sorted(t["roster"], key=slot_key)]))
        out.append("")
    return "\n".join(out) + "\n"


def render_free_agents(snap):
    out = [header(snap, "Free agents"), "Unrostered players (free agents and players on waivers), most-rostered first.\n"]
    on_waivers = [f"{p['name']} (until {p['waivers_until']})" for players in snap["free_agents"].values() for p in players if p.get("waivers_until")]
    if on_waivers:
        out.append("**On waivers, so they need a claim:** " + ", ".join(on_waivers) + ". Everyone else can be added right away.\n")
    for pos, players in snap["free_agents"].items():
        out.append(f"## {pos}\n")
        out.append(table(PLAYER_HEADERS, [player_row(p, with_slot=False) for p in players]))
        out.append("")
    return "\n".join(out) + "\n"


def offer_text(t):
    """'Team A gives X, Y; Team B gives Z'."""
    gives = {}
    for i in t["items"]:
        gives.setdefault(i["from"], []).append(str(i["player"]))
    return "; ".join(f"{team} gives {', '.join(players)}" for team, players in gives.items()) or "(players not shown by ESPN)"


def render_activity(snap):
    out = [header(snap, "Trades and recent moves")]
    proposals = [t for t in snap["trades"] if t["type"] == "TRADE_PROPOSAL"]
    open_offers = [t for t in proposals if t["status"] == "PENDING" and not t["expired"]]
    old_offers = [t for t in proposals if t not in open_offers]
    accepted = [t for t in snap["trades"] if t["type"] == "TRADE_ACCEPT"]
    upheld = {t["related_id"]: t for t in snap["trades"] if t["type"] == "TRADE_UPHOLD"}
    declined = [t for t in snap["trades"] if t["type"] == "TRADE_DECLINE"]
    other = [t for t in snap["trades"] if t["type"] in ("TRADE_VETO", "TRADE_ERROR")]

    out.append("## Trade offers\n")
    out.append("Season to date, as ESPN shows them to this login. Offers between other teams are included.\n")
    out.append("### Open offers right now\n")
    out.append(table(["Proposed", "Offered by", "Offer", "Expires"],
                     [[t["proposed"], t["team"], offer_text(t), t["expires"]] for t in open_offers]) if open_offers else "None visible.")
    out.append("\n### Offers that were withdrawn, replaced or expired\n")
    out.append(table(["Proposed", "Offered by", "Offer", "Status"],
                     [[t["proposed"], t["team"], offer_text(t), "EXPIRED" if t["status"] == "PENDING" else t["status"]] for t in old_offers]) if old_offers else "None.")
    out.append("\n### Accepted trades\n")
    out.append("ESPN leaves the players off these records. Match them by date to the TRADE rows in the table below.\n")
    rows = []
    for t in accepted:
        done = upheld.get(t["related_id"])
        rows.append([t["proposed"], t["team"], done["team"] if done else "", f"went through {done['proposed']}" if done else "awaiting review"])
    out.append(table(["Accepted", "Accepted by", "Other team", "Outcome"], rows) if rows else "None.")
    out.append("\n### Declined offers\n")
    out.append("ESPN shows who declined and when, but not the players.\n")
    out.append(table(["Declined", "Declined by"], [[t["proposed"], t["team"]] for t in declined]) if declined else "None.")
    if other:
        out.append("\n### Vetoed or failed\n")
        out.append(table(["When", "Team", "Type", "Offer"], [[t["proposed"], t["team"], t["type"], offer_text(t)] for t in other]))
    out.append("")

    pulled = [c for c in snap.get("waiver_claims", []) if c["status"] == "CANCELED"]
    if pulled:
        out.append("## Waiver claims a manager placed and then cancelled\n")
        out.append("These never show in the ESPN app. They hint at who a team wanted.\n")
        out.append(table(["When", "Team", "Wanted", "Would have dropped"],
                         [[c["when"], c["team"], ", ".join(map(str, c["add"])), ", ".join(map(str, c["drop"]))] for c in pulled]))
        out.append("")

    out.append("## Recent adds, drops and completed trades\n")
    rows = [[a["when"], x["team"], x["action"], x["player"], x["pos"], x["nfl"]] for a in snap["activity"] for x in a["actions"]]
    out.append(table(["When", "Team", "Move", "Player", "Pos", "NFL"], rows))
    return "\n".join(out) + "\n"


def main():
    espn_s2, swid = os.environ.get("ESPN_S2", "").strip(), os.environ.get("ESPN_SWID", "").strip()
    if not espn_s2 or not swid:
        sys.exit("Missing ESPN_S2 or ESPN_SWID. This league is private, so both login cookies are required.")
    if not swid.startswith("{"):
        swid = "{" + swid.strip("{}") + "}"
    try:
        league = League(league_id=LEAGUE_ID, year=SEASON, espn_s2=espn_s2, swid=swid)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Could not load the league from ESPN ({type(exc).__name__}: {exc}). "
                 "If this says not authorized, the ESPN_S2 and ESPN_SWID cookies have probably expired and need re-pasting.")

    snap = gather(league)
    DATA_DIR.mkdir(exist_ok=True)
    files = {
        "overview.md": render_overview(snap),
        "rosters.md": render_rosters(snap),
        "free_agents.md": render_free_agents(snap),
        "activity.md": render_activity(snap),
        "league.json": json.dumps(snap, indent=1, default=str),
        # same data as a script, so dashboard.html can load it straight from disk
        "league.js": "window.LEAGUE = " + json.dumps(snap, default=str) + ";" + chr(10),
    }
    for name, text in files.items():
        (DATA_DIR / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"Week {snap['week']}: {len(snap['teams'])} teams, {sum(len(v) for v in snap['free_agents'].values())} free agents, "
          f"{len(snap['trades'])} trade records, {len(snap['activity'])} recent moves.")
    for w in snap["warnings"]:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
