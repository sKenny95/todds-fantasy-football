"""Temporary: look at what else ESPN returns for this login. Prints shapes and counts only."""
import json, os
from collections import Counter
from espn_api.football import League

swid = os.environ["ESPN_SWID"].strip()
if not swid.startswith("{"):
    swid = "{" + swid.strip("{}") + "}"
lg = League(league_id=1241185, year=2026, espn_s2=os.environ["ESPN_S2"].strip(), swid=swid)
req, week = lg.espn_request, lg.current_week
J = lambda v, n=500: json.dumps(v, default=str)[:n]

def section(name, fn):
    print(f"\n===== {name} =====")
    try:
        fn()
    except Exception as exc:
        print("FAILED", type(exc).__name__, exc)

def s_team():
    d = req.league_get(params={"view": "mTeam"})
    print("top keys", sorted(d))
    print("team keys", sorted(d["teams"][0]))
    print("member keys", sorted(d["members"][0]))
    for t in d["teams"]:
        print(t["id"], "block", J(t.get("tradeBlock"), 400), "| counter", J(t.get("transactionCounter"), 500),
              "| projRank", t.get("currentProjectedRank"), "draftDayRank", t.get("draftDayProjectedRank"),
              "| sim", J(t.get("currentSimulationResults"), 300))

def s_pending():
    d = req.league_get(params={"view": "mPendingTransactions"})
    tx = d.get("pendingTransactions") or []
    print("count", len(tx), Counter((t.get("type"), t.get("status"), t.get("teamId")) for t in tx))
    if tx:
        print("keys", sorted(tx[0]))

def s_tx():
    for wk in range(1, week + 1):
        d = req.league_get(params={"view": "mTransactions2", "scoringPeriodId": wk})
        tx = d.get("transactions") or []
        print("week", wk, "count", len(tx), dict(Counter((t.get("type"), t.get("status")) for t in tx)))
        failed = [t for t in tx if t.get("type") == "WAIVER"]
        print("  waiver by team/status", dict(Counter((t.get("teamId"), t.get("status")) for t in failed)))
        if failed:
            print("  sample waiver", J(failed[0], 900))
        if tx:
            print("  keys", sorted(tx[0]))

def s_draft():
    d = req.league_get(params={"view": "mDraftDetail"})
    dd = d.get("draftDetail", {})
    print("keys", sorted(dd), "picks", len(dd.get("picks", [])))
    print("sample", J(dd.get("picks", [None])[0], 600))

def s_roster():
    d = req.league_get(params={"view": "mRoster"})
    pend = Counter()
    for t in d["teams"]:
        for e in t["roster"]["entries"]:
            if e.get("pendingTransactionIds"):
                pend[t["id"]] += 1
    e = d["teams"][0]["roster"]["entries"][0]
    print("entry keys", sorted(e))
    print("entry sample", J({k: v for k, v in e.items() if k != "playerPoolEntry"}, 600))
    ppe = e["playerPoolEntry"]
    print("ppe keys", sorted(ppe))
    print("ppe sample", J({k: v for k, v in ppe.items() if k != "player"}, 600))
    p = ppe["player"]
    print("player keys", sorted(p))
    print("ownership", J(p.get("ownership"), 600))
    print("stat entries", sorted({(s.get("seasonId"), s.get("scoringPeriodId"), s.get("statSourceId"), s.get("statSplitTypeId")) for s in p.get("stats", [])}))
    print("rankings keys", J({k: len(v) for k, v in (p.get("rankings") or {}).items()}), "draftRanks", J(p.get("draftRanksByRankType"), 300))
    print("outlooks", J(p.get("outlooks"), 300), "| seasonOutlook", J(p.get("seasonOutlook"), 200))
    print("entries with pendingTransactionIds by team", dict(pend))

def s_kona():
    filt = {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS"]}, "limit": 3, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
    d = req.league_get(params={"view": "kona_player_info", "scoringPeriodId": week}, headers={"x-fantasy-filter": json.dumps(filt)})
    pl = d.get("players", [])
    print("count", len(pl))
    if pl:
        x = pl[0]
        print("keys", sorted(x), "| status", x.get("status"), "| waiverProcessDate", x.get("waiverProcessDate"), "| ratings", J(x.get("ratings"), 300))
        p = x["player"]
        print("player keys", sorted(p))
        print("ownership", J(p.get("ownership"), 600))
        print("stat entries", sorted({(s.get("seasonId"), s.get("scoringPeriodId"), s.get("statSourceId"), s.get("statSplitTypeId")) for s in p.get("stats", [])}))
        print("statuses", [(q["player"]["fullName"], q.get("status"), q.get("waiverProcessDate")) for q in pl])

def s_status():
    d = req.league_get(params={"view": "mStatus"})
    print(J(d.get("status"), 2500))

def s_pro():
    d = req.get_pro_schedule()
    teams = d if isinstance(d, list) else d.get("settings", {}).get("proTeams", [])
    print("type", type(d).__name__, "n", len(teams))
    if teams:
        print("keys", sorted(teams[0]), "bye", [(t.get("abbrev"), t.get("byeWeek")) for t in teams][:40])

def s_lib():
    print("league attrs", [a for a in dir(lg) if not a.startswith("_")])
    me = next(t for t in lg.teams if t.team_id == 2)
    p = me.roster[0]
    print("player attrs", [a for a in dir(p) if not a.startswith("_")])
    print(p.name, "stats weeks", {k: sorted(v) for k, v in p.stats.items()})
    print("schedule", J(getattr(p, "schedule", None), 500))
    print("team attrs", [a for a in dir(me) if not a.startswith("_")])
    box = lg.box_scores(1)
    b = box[0]
    print("box attrs", [a for a in dir(b) if not a.startswith("_")])
    print("wk1 lineup sample", [(x.name, x.slot_position, x.points, x.projected_points) for x in b.home_lineup][:20])

def s_settings():
    d = req.league_get(params={"view": "mSettings"})
    s = d.get("settings", {})
    print("keys", sorted(s))
    print("trade", J(s.get("tradeSettings"), 600))
    print("acq", J(s.get("acquisitionSettings"), 800))
    print("schedule keys", sorted(s.get("scheduleSettings", {})))

for name, fn in [("mTeam", s_team), ("pending", s_pending), ("transactions", s_tx), ("draft", s_draft), ("roster", s_roster),
                 ("kona", s_kona), ("status", s_status), ("pro schedule", s_pro), ("library", s_lib), ("settings", s_settings)]:
    section(name, fn)
