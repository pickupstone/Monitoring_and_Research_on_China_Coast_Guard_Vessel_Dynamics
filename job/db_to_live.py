"""Publish the private site's database (saved with ArtifactData out_dir) into the public site's live/ files.

Usage: python3 job/db_to_live.py <repo_dir> <export_dir>

<export_dir> is the out_dir given to ArtifactData reads, so it holds
  live/latest.json        - the "live" collection, doc "latest"
  alerts/<YYYY-MM-DD>.json - the "alerts" collection
  news/<YYYY-MM-DD>.json   - the "news" collection
Writes <repo_dir>/live/latest.json, live/alerts.json (newest 30 days) and live/news.json (newest 60 days).
Only the fields the public page uses are copied; anything else in a document is dropped."""
import json, os, sys, glob

ALERT_KEYS = ('date', 'updated', 'data_end', 'count', 'items')
ALERT_ITEM = ('hull', 'name', 'ju', 'level', 'kind', 'text', 'lat', 'lon', 't')
NEWS_KEYS = ('date', 'updated', 'summary', 'items')
NEWS_ITEM = ('date', 'source', 'title', 'url', 'summary', 'tags', 'hulls')

def pick(d, keys): return {k: d[k] for k in keys if k in d}

def merge(fn, docs, keep):
    old = json.load(open(fn)) if os.path.exists(fn) else []
    by = {d.get('date'): d for d in old}
    for d in docs: by[d['date']] = d
    return sorted(by.values(), key=lambda d: d.get('date', ''), reverse=True)[:keep]

def main(repo, ex):
    live = os.path.join(repo, 'live'); os.makedirs(live, exist_ok=True); done = []
    lf = os.path.join(ex, 'live', 'latest.json')
    if os.path.exists(lf):
        L = json.load(open(lf))
        if L.get('positions'):
            json.dump(pick(L, ('updated', 'data_end', 'source', 'positions')), open(os.path.join(live, 'latest.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
            done.append(f"latest.json {len(L['positions'])} positions, data_end {L.get('data_end')}")
    A = []
    for f in glob.glob(os.path.join(ex, 'alerts', '*.json')):
        d = json.load(open(f))
        if d.get('date'):
            d = pick(d, ALERT_KEYS); d['items'] = [pick(i, ALERT_ITEM) for i in d.get('items') or []]; A.append(d)
    if A:
        days = merge(os.path.join(live, 'alerts.json'), A, 30)
        json.dump(days, open(os.path.join(live, 'alerts.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        done.append(f"alerts.json {len(days)} days, newest {days[0]['date']} ({days[0].get('count')} alerts)")
    N = []
    for f in glob.glob(os.path.join(ex, 'news', '*.json')):
        d = json.load(open(f))
        if d.get('date'):
            d = pick(d, NEWS_KEYS); d['items'] = [pick(i, NEWS_ITEM) for i in d.get('items') or []]; N.append(d)
    if N:
        days = merge(os.path.join(live, 'news.json'), N, 60)
        json.dump(days, open(os.path.join(live, 'news.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        done.append(f"news.json {len(days)} days, newest {days[0]['date']}")
    print('; '.join(done) or 'nothing to publish')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
