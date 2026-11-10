"""Copy the automated results into the public site.

Usage: python3 job/live_update.py <repo_dir> [--out <job_out_dir>] [--news <news_json>]

--out   reads latest.json and alerts.json written by daily.py and writes
          <repo_dir>/live/latest.json  - latest positions, destination forecast and point check for every ship
          <repo_dir>/live/alerts.json  - daily alert documents, newest first, at most 30 days
--news  reads one daily news document {"date", "summary", "items": [...]} and writes
          <repo_dir>/live/news.json    - daily news documents, newest first, at most 60 days
The public page (index.html) reads these files when it is not running inside claude.ai.
(The older form `live_update.py <repo_dir> <job_out_dir>` still works.)"""
import json, os, sys

def merge_days(fn, doc, keep):
    days = json.load(open(fn)) if os.path.exists(fn) else []
    days = [d for d in days if d.get('date') != doc.get('date')]
    return sorted([doc] + days, key=lambda d: d.get('date', ''), reverse=True)[:keep]

def main(argv):
    repo = argv[0]; out = news = None; rest = argv[1:]
    if rest and not rest[0].startswith('--'): out = rest.pop(0)
    while rest:
        k = rest.pop(0)
        if k == '--out': out = rest.pop(0)
        elif k == '--news': news = rest.pop(0)
        else: sys.exit('unknown argument ' + k)
    if not out and not news: sys.exit(__doc__)
    live = os.path.join(repo, 'live'); os.makedirs(live, exist_ok=True)
    if out:
        latest = json.load(open(os.path.join(out, 'latest.json'))); alerts = json.load(open(os.path.join(out, 'alerts.json')))
        if not latest.get('positions'):
            print('latest.json has no positions; live/latest.json and live/alerts.json left unchanged')
        else:
            days = merge_days(os.path.join(live, 'alerts.json'), alerts, 30)
            json.dump(latest, open(os.path.join(live, 'latest.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
            json.dump(days, open(os.path.join(live, 'alerts.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
            print('live/latest.json positions', len(latest['positions']), 'data_end', latest.get('data_end'),
                  '| live/alerts.json days', len(days), 'today', alerts.get('date'), 'alerts', alerts.get('count'))
    if news:
        doc = json.load(open(news))
        if not doc.get('date'): sys.exit('news document has no date')
        days = merge_days(os.path.join(live, 'news.json'), doc, 60)
        json.dump(days, open(os.path.join(live, 'news.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        print('live/news.json days', len(days), 'today', doc['date'], 'items', len(doc.get('items') or []))

if __name__ == '__main__':
    main(sys.argv[1:])
