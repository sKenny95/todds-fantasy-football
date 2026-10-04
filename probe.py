"""Temporary: look at what else ESPN returns for this login. Prints shapes and counts only."""
import json, os
from espn_api.football import League

swid = os.environ["ESPN_SWID"].strip()
if not swid.startswith("{"):
    swid = "{" + swid.strip("{}") + "}"
lg = League(league_id=1241185, year=2026, espn_s2=os.environ["ESPN_S2"].strip(), swid=swid)
req, week = lg.espn_request, lg.current_week
J = lambda v, n=500: json.dumps(v, default=str)[:n]
d = req.league_get(params={"view": "mRoster"})
me = next(t for t in d["teams"] if t["id"] == 2)
for e in me["roster"]["entries"][:6]:
    p = e["playerPoolEntry"]["player"]
    print("\n==", p["fullName"], "acq", e.get("acquisitionType"), "ratings", J(e["playerPoolEntry"].get("ratings")), "own", J(p.get("ownership")))
    for s in sorted(p.get("stats", []), key=lambda s: (s.get("seasonId"), s.get("scoringPeriodId"), s.get("statSourceId"), s.get("statSplitTypeId"))):
        print("  stat", s.get("seasonId"), "period", s.get("scoringPeriodId"), "source", s.get("statSourceId"), "split", s.get("statSplitTypeId"),
              "total", round(s.get("appliedTotal", 0), 1), "avg", round(s.get("appliedAverage", 0), 2) if s.get("appliedAverage") is not None else None)
    r = p.get("rankings") or {}
    print("  rankings wk", week, J(r.get(str(week)), 900))
lp = next(t for t in lg.teams if t.team_id == 2).roster[:6]
print([(p.name, p.posRank, p.projected_avg_points, p.avg_points, p.projected_total_points, p.total_points, p.acquisitionType) for p in lp])
print("draft sample", [(p.round_num, p.round_pick, p.team.team_id, p.playerId, p.playerName, p.keeper_status) for p in lg.draft[:3]])
hdr = {"x-fantasy-filter": json.dumps({"transactions": {"filterType": {"value": ["WAIVER", "WAIVER_ERROR"]}}})}
for wk in range(1, week + 1):
    tx = req.league_get(params={"view": "mTransactions2", "scoringPeriodId": wk}, headers=hdr).get("transactions") or []
    print("waiver wk", wk, [(t.get("teamId"), t.get("type"), t.get("status"), t.get("executionType"), str(t.get("memberId"))[:8] == "NightlyL", len(t.get("items") or [])) for t in tx])
