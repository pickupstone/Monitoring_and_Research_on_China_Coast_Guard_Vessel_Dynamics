"""Copy the 6-hourly AIS comparison results into the public site.

Usage: python3 job/live_update.py <repo_dir> <job_out_dir>

Reads <job_out_dir>/latest.json and <job_out_dir>/alerts.json written by daily.py and writes
  <repo_dir>/live/latest.json  - latest positions, destination forecast and point check for every ship
  <repo_dir>/live/alerts.json  - list of daily alert documents, newest first, at most 30 days
The public page (index.html) reads these files when it is not running inside claude.ai."""
import json, os, sys

def main(repo, out):
    latest = json.load(open(os.path.join(out, 'latest.json')))
    alerts = json.load(open(os.path.join(out, 'alerts.json')))
    if not latest.get('positions'):
        sys.exit('latest.json has no positions; nothing written')
    live = os.path.join(repo, 'live'); os.makedirs(live, exist_ok=True)
    fn = os.path.join(live, 'alerts.json')
    days = json.load(open(fn)) if os.path.exists(fn) else []
    days = [d for d in days if d.get('date') != alerts.get('date')]
    days = sorted([alerts] + days, key=lambda d: d.get('date', ''), reverse=True)[:30]
    json.dump(latest, open(os.path.join(live, 'latest.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    json.dump(days, open(fn, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('live/latest.json positions', len(latest['positions']), 'data_end', latest.get('data_end'),
          '| live/alerts.json days', len(days), 'today', alerts.get('date'), 'alerts', alerts.get('count'))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
