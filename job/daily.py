"""Daily CCG AIS check. Self-contained: python3 daily.py baseline.json OUTDIR
Fetches the last DAYS of Global Fishing Watch port-visit and loitering events for every ship in the
baseline (the GFW token is injected by the environment's network proxy), finds each ship's latest
position, compares new activity with the ship's historical baseline and writes:
  OUTDIR/latest.json   -> db doc live/latest
  OUTDIR/alerts.json   -> db doc alerts/<date>
"""
import math, json, sys, math, os, time, datetime as dt, collections, re
import requests
from concurrent.futures import ThreadPoolExecutor

BASE = "https://gateway.api.globalfishingwatch.org/v3"
H = {"Authorization": "Bearer proxy-injected"}
DAYS = 10

def get(path, params):
    for i in range(5):
        try:
            r = requests.get(BASE + path, params=params, headers=H, timeout=90)
        except Exception:
            time.sleep(5 * (i + 1)); continue
        if r.status_code in (429,) or r.status_code >= 500:
            time.sleep(5 * (i + 1)); continue
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code} {r.text[:200]}")
        return r.json()
    raise RuntimeError("retries exhausted")

def T(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
def km(la1, lo1, la2, lo2):
    p = math.pi / 180; a = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))
TW = [(121.0,25.3),(121.55,25.3),(121.95,25.0),(121.85,24.6),(121.6,24.0),(121.4,23.2),(121.0,22.4),(120.85,21.9),(120.7,22.0),(120.6,22.4),(120.25,22.65),(120.1,23.0),(120.15,23.6),(120.35,24.2),(120.7,24.65),(121.0,25.05)]
def pip(x, y, poly):
    c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def dist_tw(la, lo):
    if pip(lo, la, TW): return 0
    best = 1e9
    for i in range(len(TW)):
        (x1, y1), (x2, y2) = TW[i], TW[(i + 1) % len(TW)]
        for t in [k / 10 for k in range(11)]:
            best = min(best, km(la, lo, y1 + (y2 - y1) * t, x1 + (x2 - x1) * t))
    return best
ZONES = [
 ("釣魚台列嶼", lambda la, lo: min(km(la, lo, 25.745, 123.47), km(la, lo, 25.925, 124.56)) <= 60),
 ("金門", lambda la, lo: km(la, lo, 24.44, 118.37) <= 25),
 ("馬祖", lambda la, lo: km(la, lo, 26.16, 119.95) <= 30 or km(la, lo, 26.37, 120.48) <= 20),
 ("澎湖", lambda la, lo: km(la, lo, 23.57, 119.58) <= 40),
 ("東沙島", lambda la, lo: km(la, lo, 20.70, 116.73) <= 60),
 ("台灣本島周邊(24浬內)", lambda la, lo: dist_tw(la, lo) <= 45),
 ("台灣周邊(24-80浬)", lambda la, lo: dist_tw(la, lo) <= 150 and lo > 119.8),
 ("台灣外圍(80-200浬)", lambda la, lo: dist_tw(la, lo) <= 370 and 19.0 <= la <= 26.0 and lo >= 118.5 and not (lo < 120.0 and la > 23.0)),
 ("黃岩島", lambda la, lo: km(la, lo, 15.15, 117.76) <= 60),
 ("仁愛礁/仙賓礁", lambda la, lo: min(km(la, lo, 9.73, 115.86), km(la, lo, 9.76, 116.52)) <= 40),
 ("南沙群島(其他)", lambda la, lo: 4 <= la <= 12.5 and 109 <= lo <= 118.5),
 ("西沙群島", lambda la, lo: 15.3 <= la <= 17.5 and 110.8 <= lo <= 113.0),
 ("北部灣", lambda la, lo: 17.5 <= la <= 22 and 105.5 <= lo <= 109.8),
 ("黃海/渤海", lambda la, lo: la >= 33.5 and lo <= 126.5),
 ("東海(其他)", lambda la, lo: 26 <= la < 33.5 and lo >= 120.5),
 ("台灣海峽(其他)", lambda la, lo: 22.5 <= la < 26 and 117 <= lo <= 120.6),
 ("南海北部近岸(廣東/海南)", lambda la, lo: 17.5 <= la <= 23.5 and 109.5 <= lo <= 117.5),
]
def zone(la, lo):
    for n, f in ZONES:
        if f(la, lo): return n
    return "其他"
def seg_km(la, lo, a, b):
    kx = 111.32 * math.cos(math.radians(la)); ky = 110.57
    px, py = lo * kx, la * ky; ax, ay = a[1] * kx, a[0] * ky; bx, by = b[1] * kx, b[0] * ky
    dx, dy = bx - ax, by - ay; t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
ML = ((27.0, 122.0), (23.0, 118.0))
def areas(la, lo):
    out = []; d = dist_tw(la, lo)
    if min(km(la, lo, 25.745, 123.47), km(la, lo, 25.925, 124.56)) <= 60: out.append('釣魚台')
    if 21.3 <= la <= 25.4 and 121.5 <= lo <= 125.0 and d <= 370 and '釣魚台' not in out and not (la > 24.2 and lo < 122.0): out.append('台灣東部海域')
    if seg_km(la, lo, *ML) <= 20: out.append('海峽中線')
    if 22.8 <= la <= 26.6 and lo <= 122 and la < lo - 95 and d > 44 and seg_km(la, lo, *ML) > 20 and km(la, lo, 23.57, 119.58) > 40: out.append('中線以東')
    if km(la, lo, 24.44, 118.37) <= 25: out.append('金門')
    if km(la, lo, 26.16, 119.95) <= 30 or km(la, lo, 26.37, 120.48) <= 20: out.append('馬祖')
    if km(la, lo, 23.57, 119.58) <= 40: out.append('澎湖')
    if 20.6 <= la <= 23.0 and 117.8 <= lo <= 120.9 and km(la, lo, 20.70, 116.73) > 60 and d <= 370: out.append('台灣西南海域')
    if km(la, lo, 20.70, 116.73) <= 60: out.append('東沙')
    if 4 <= la <= 12.5 and 109 <= lo <= 118.5: out.append('南沙')
    if km(la, lo, 15.15, 117.76) <= 60: out.append('黃岩島')
    return out
TAIWAN_AREAS = {'台灣東部海域', '海峽中線', '中線以東', '金門', '馬祖', '澎湖', '台灣西南海域', '東沙'}

def events(vid, ds, start, end):
    out = []; off = 0
    while True:
        j = get("/events", {"datasets[0]": ds, "vessels[0]": vid, "start-date": start, "end-date": end, "limit": 200, "offset": off})
        out += j["entries"]
        if j.get("nextOffset") is None or not j["entries"]: break
        off = j["nextOffset"]
    return out


# ---------- destination prediction (tables built by ccg_predict_export.py, stored in baseline['pred']) ----------
SEASON_OF = lambda mth: ['春', '夏', '秋', '冬'][((mth - 3) % 12) // 3]
def _sm(cnt, prior, b):
    n = sum(cnt.values()); keys = set(prior) | set(cnt)
    return {z: (cnt.get(z, 0) + b * prior.get(z, 0)) / (n + b) for z in keys}
def predict_block(P, h, port, season):
    """Probability that the next/current voyage is a mission (has loitering at sea), and where it goes."""
    hp = P['hp']; port = port or '?'
    base = _sm(P['gp'].get(P['grp'].get(h, '?'), {}), P['prior'], hp['b0'])
    p = _sm(P['fp'].get(port, {}), base, hp['b0']); p = _sm(P['fps'].get(port + '|' + season, {}), p, hp['b0'])
    q = _sm(P['s'].get(h, {}), p, hp['b1']); q = _sm(P['sp'].get(h, {}).get(port, {}), q, hp['b2']); q = _sm(P['sps'].get(h, {}).get(port + '|' + season, {}), q, hp['b3'])
    t = sum(q.values()); q = {z: v / t for z, v in q.items()}
    m1 = P['m1']; g = m1['g'][0] / m1['g'][1]
    a = m1['s'].get(h, [0, 0]); pm = (a[0] + 10 * g) / (a[1] + 10)
    a = m1['sp'].get(h + '|' + port, [0, 0]); pm = (a[0] + 5 * pm) / (a[1] + 5)
    a = m1['sps'].get(h + '|' + port + '|' + season, [0, 0]); pm = (a[0] + 3 * pm) / (a[1] + 3)
    Z = P['Z']; top = sorted(q, key=lambda z: -q[z])[:5]
    return dict(mission=round(pm, 3), top=[[Z[int(z)], round(q[z], 3)] for z in top], probs={Z[int(z)]: v for z, v in q.items()},
                n_hist=round(sum(P['s'].get(h, {}).values()), 1))
def zone_counts(pts):
    c = collections.Counter(zone(la, lo) for la, lo, t in pts); return [[z, n] for z, n in c.most_common()]
def point_check(P, h, r, pts, port, season):
    """Point anomalies for loitering positions since departure. At most one alert per kind:
    the zone with the lowest predicted probability (< p_low), and the position farthest from every 0.5-degree cell
    this ship has loitered in (> cell_km)."""
    out = []; tw = {P['Z'][i] for i in P['tw']}; cs = P['cells'].get(h, [])
    ptxt = '、'.join(f"{z} {round(v*100)}%" for z, v in r['top'][:3])
    worst = None; far = None
    for la, lo, t in pts:
        z = zone(la, lo); pz = r['probs'].get(z, 0)
        if z != '其他' and pz < P['p_low'] and (worst is None or pz < worst[0]): worst = (pz, z, la, lo, t)
        if cs:
            d = min(km(la, lo, float(k.split(',')[0]) + .25, float(k.split(',')[1]) + .25) for k in cs)
            if d > P['cell_km'] and (far is None or d > far[0]): far = (d, z, la, lo, t)
    if worst:
        pz, z, la, lo, t = worst
        out.append([3 if z in tw else 2, '偏離預測區塊', f"{t} 在「{z}」滯留；依出港港口 {P.get('pz', {}).get(port, port) or '不明'}、{season}季、所屬分局與自身習慣，預測此區塊機率僅 {pz*100:.1f}%（預測：{ptxt}）", la, lo, t])
    if far:
        d, z, la, lo, t = far
        out.append([2 if z in tw else 1, '偏離歷史點位', f"{t} 在 {la:.2f}N {lo:.2f}E（{z}）滯留，距這艘船 5 年來任何滯留位置都超過 {d:.0f} 公里", la, lo, t])
    return out

def main(bfile, outdir):
    os.makedirs(outdir, exist_ok=True)
    BL = json.load(open(bfile))
    today = dt.datetime.now(dt.timezone.utc)
    start = (today - dt.timedelta(days=DAYS)).date().isoformat(); end = (today + dt.timedelta(days=1)).date().isoformat()
    jobs = [(h, v, k) for h, s in BL['ships'].items() for v in s['vids'] for k in ("port", "loiter")]
    jobs += [("RV:" + n, v, "loiter") for n, r in BL['rv'].items() for v in r['vids']]
    DS = {"port": "public-global-port-visits-events:latest", "loiter": "public-global-loitering-events:latest"}
    res = collections.defaultdict(lambda: {"port": {}, "loiter": {}})
    def run(j):
        h, v, k = j
        try:
            for e in events(v, DS[k], start, end):
                res[h][k][e["id"]] = e
        except Exception as ex:
            print("ERR", h, v, k, str(ex)[:120], flush=True)
    with ThreadPoolExecutor(10) as ex:
        for i, _ in enumerate(ex.map(run, jobs)):
            if i % 300 == 0: print("events", i, len(jobs), flush=True)
    data_end = max([T(e["end"]) for r in res.values() for k in r for e in r[k].values()] or [today])
    latest = {}; alerts = []; departures = []
    rv_loi = [(h[3:], e) for h, r in res.items() if h.startswith("RV:") for e in r["loiter"].values()]
    for h, b in BL['ships'].items():
        ports = sorted(res[h]["port"].values(), key=lambda e: e["end"]); loi = sorted(res[h]["loiter"].values(), key=lambda e: e["start"])
        evs = [(T(e["end"]), "港口停靠", (e["port_visit"].get("startAnchorage") or {}).get("lat"), (e["port_visit"].get("startAnchorage") or {}).get("lon"), (e["port_visit"].get("startAnchorage") or {}).get("name")) for e in ports]
        evs += [(T(e["end"]), "海上滯留", e["position"]["lat"], e["position"]["lon"], None) for e in loi]
        evs = [x for x in evs if x[2] is not None]
        if not evs: continue
        last = max(evs, key=lambda x: x[0])
        state = "在港" if ports and (data_end - T(ports[-1]["end"])).total_seconds() < 36 * 3600 else "出航"
        dep = T(ports[-1]["end"]) if ports and state == "出航" else None
        latest[h] = dict(t=last[0].isoformat()[:16], kind=last[1], lat=round(last[2], 3), lon=round(last[3], 3), zone=zone(last[2], last[3]), areas=areas(last[2], last[3]),
                         state=state, port=ports[-1]["port_visit"].get("startAnchorage", {}).get("name") if ports else None,
                         dep=dep.isoformat()[:16] if dep else None, sea_days=round((data_end - dep).total_seconds() / 86400, 1) if dep else None)
        PR = BL.get('pred')
        if PR:
            pport = (ports[-1]["port_visit"].get("startAnchorage") or {}).get("name") if ports else PR['last_port'].get(h)
            pseason = SEASON_OF(((dep or data_end) + dt.timedelta(hours=8)).month)
            rp = predict_block(PR, h, pport, pseason)
            ppts = [(e["position"]["lat"], e["position"]["lon"], e["start"][:16]) for e in loi if (not dep) or T(e["start"]) >= dep] if state == "出航" else []
            pa = point_check(PR, h, rp, ppts, pport, pseason) if ppts else []
            latest[h]['pred'] = dict(port=pport, season=pseason, mission=rp['mission'], top=rp['top'][:3], act=zone_counts(ppts), pa=[[x[0], x[1]] for x in pa])
        if state == "出航":   # loitering since departure (within the fetch window), for the map's current-voyage track
            latest[h]['trk'] = [[e["start"][:16], round(e["position"]["lat"], 3), round(e["position"]["lon"], 3), round((T(e["end"]) - T(e["start"])).total_seconds() / 3600, 1)]
                                for e in loi if (not dep) or T(e["start"]) >= dep][-60:]
        def alert(level, kind, text, la=None, lo=None, t=None):
            alerts.append(dict(hull=h, name=b.get('name') or '', ju=b.get('ju') or '', level=level, kind=kind, text=text, lat=la, lon=lo, t=t))
        if PR:
            for lv, kd, tx, la_, lo_, t_ in pa: alert(lv, kd, tx, la_, lo_, t_)
        # new activity compared with the baseline
        for e in loi:
            la, lo = e["position"]["lat"], e["position"]["lon"]; z = zone(la, lo); share = b['zshare'].get(z, 0); ts = e["start"][:16]
            if b['nloi'] >= 15 and z != "其他":
                if share == 0: alert(3, "新海域", f"{ts} 在「{z}」滯留，過去 5 年從未出現在此海域", la, lo, ts)
                elif share < 0.03: alert(2, "少見海域", f"{ts} 在「{z}」滯留，過去僅占 {share*100:.1f}%", la, lo, ts)
            if b.get('hc') and b['hc'][0] is not None and b.get('p95'):
                d = km(la, lo, b['hc'][0], b['hc'][1])
                if d > max(150, b['p95'] * 1.15): alert(2, "異常遠航", f"{ts} 距母港 {d:.0f} 公里（{z}），超過過去 95% 活動範圍 {b['p95']} 公里", la, lo, ts)
            for a in areas(la, lo):
                if a in TAIWAN_AREAS or a == '釣魚台':
                    lvl = 2 if not b['areas'].get(a) else 1
                    alert(lvl, "進入重點海域", f"{ts} 出現在「{a}」" + ("（過去 5 年未曾出現）" if lvl == 2 else f"（過去 {b['areas'][a]} 天有紀錄）"), la, lo, ts)
            for n, r in rv_loi:
                if abs((T(r["start"]) - T(e["start"])).total_seconds()) < 12 * 3600 and km(la, lo, r["position"]["lat"], r["position"]["lon"]) <= 30:
                    alert(2, "科研船同行", f"{ts} 與科研／調查船 {n} 在 30 公里內同時滯留（{z}）", la, lo, ts)
        if dep and b['nvoy'] >= 20:
            hh = (dep + dt.timedelta(hours=8)).hour
            if b['dep_hours'] and not ({hh, (hh + 1) % 24, (hh - 1) % 24} & set(b['dep_hours'])): alert(1, "出港時段異常", f"{dep.isoformat()[:16]} UTC 出港（台北 {hh} 時），過去很少在這個時段前後出港", None, None, dep.isoformat()[:16])
        if dep: departures.append((dep, h, b.get('home') or '', b.get('name') or ''))
        if b.get('maxgap') and b['nvoy'] >= 10:
            gap = (data_end - last[0]).total_seconds() / 86400
            if gap > max(14, b['maxgap']): alert(3, "AIS 沉寂", f"最後事件 {last[0].isoformat()[:16]}，已 {gap:.0f} 天無事件，超過過去最長空窗 {b['maxgap']} 天")
    # group departures: >=3 ships from the same home port leaving within 3 hours
    departures.sort()
    for i, (t0, h0, home, _) in enumerate(departures):
        grp = [d for d in departures if d[2] == home and home and 0 <= (d[0] - t0).total_seconds() <= 3 * 3600]
        if len(grp) >= 3 and grp[0][1] == h0:
            hulls = '、'.join(g[1] for g in grp)
            for g in grp:
                alerts.append(dict(hull=g[1], name=g[3], ju=BL['ships'][g[1]].get('ju') or '', level=2, kind="群體出港", text=f"{t0.isoformat()[:16]} UTC 起 3 小時內，{home} 有 {len(grp)} 艘同時出港：{hulls}", lat=None, lon=None, t=t0.isoformat()[:16]))
    # de-dup alerts per hull+kind (keep highest level, latest)
    best = {}
    for a in alerts:
        k = (a['hull'], a['kind'], (a.get('text') or '')[17:40])
        if k not in best or a['level'] > best[k]['level']: best[k] = a
    alerts = sorted(best.values(), key=lambda a: (-a['level'], a['hull']))
    date = today.date().isoformat()
    json.dump(dict(updated=today.isoformat()[:16], data_end=data_end.isoformat()[:16], source="Global Fishing Watch events (≈72h latency)", positions=latest), open(os.path.join(outdir, "latest.json"), "w"), ensure_ascii=False)
    json.dump(dict(date=date, updated=today.isoformat()[:16], data_end=data_end.isoformat()[:16], count=len(alerts), items=alerts[:400]), open(os.path.join(outdir, "alerts.json"), "w"), ensure_ascii=False)
    print("DONE positions", len(latest), "alerts", len(alerts), collections.Counter(a['kind'] for a in alerts))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
