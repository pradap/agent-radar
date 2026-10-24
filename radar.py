#!/usr/bin/env python3
"""Dependency-free GitHub radar. Uses the authenticated GitHub CLI."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
CATEGORIES = ['Agents', 'Harnesses', 'Evaluation', 'Security', 'Governance', 'Infrastructure']


def api(endpoint):
    for attempt in range(3):
        result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return json.loads(result.stdout)
        if 'HTTP 404' in result.stderr or 'HTTP 403' in result.stderr or 'HTTP 422' in result.stderr:
            break
        time.sleep(2 ** attempt)
    raise RuntimeError(result.stderr.strip()[:500])


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def collect_one(seed):
    try:
        item = api('repos/' + seed['repository'])
        return dict(seed, repository=item['full_name'], requested_repository=seed['repository'],
                    id=item['id'], url=item['html_url'], description=item.get('description'),
                    stars=item['stargazers_count'], forks=item['forks_count'],
                    open_issues_and_prs=item['open_issues_count'], language=item['language'],
                    license=(item.get('license') or {}).get('spdx_id'), topics=item.get('topics', []),
                    created_at=item['created_at'], pushed_at=item['pushed_at'],
                    archived=item['archived'], fork=item['fork'], fetched_at=now())
    except (RuntimeError, subprocess.TimeoutExpired, KeyError, ValueError) as exc:
        return dict(seed, error=str(exc))


def read_seeds():
    with (ROOT / 'config/seeds.tsv').open() as stream:
        seeds = list(csv.DictReader(stream, delimiter='\t'))
    names = [s['repository'].lower() for s in seeds]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate seed repository')
    for seed in seeds:
        if seed['category'] not in CATEGORIES or len(seed['repository'].split('/')) != 2:
            raise ValueError('Invalid seed: ' + str(seed))
    return seeds


def growth(repo, snapshots, days):
    observed = datetime.fromisoformat(repo['fetched_at'])
    target = observed - timedelta(days=days)
    candidates = []
    for snap in snapshots:
        for old in snap['repositories']:
            if old['id'] != repo['id']:
                continue
            stamp = datetime.fromisoformat(old['fetched_at'])
            # Allow collection timing drift, but never call a short interval a full week.
            if target - timedelta(hours=12) <= stamp <= target:
                candidates.append((stamp, old['stars']))
    if not candidates:
        return None
    return repo['stars'] - max(candidates)[1]


def cell(value):
    return str(value if value is not None else '—').replace('|', '\\|').replace('\n', ' ')


def render(snapshot, previous):
    repos = snapshot['repositories']
    out = ['# Agent Radar — repository baseline', '',
           'Collected: ' + snapshot['collected_at'] + ' (UTC).', '',
           f"{len(repos)} verified repositories across {len(CATEGORIES)} categories; {len(snapshot['errors'])} collection errors.", '',
           'This is a curated discovery baseline, not a trending ranking or a security endorsement. '
           'Within each category, repositories are ordered by total stars. '
           '7-day and 30-day changes are net star differences against stored observations; — means insufficient history. '
           'Newly discovered repositories need their own observation history.', '',
           'The inclusion notes are editorial assessments. GitHub descriptions, metrics, license labels and activity dates '
           'come from the linked repository API records. Governance includes general-purpose authorization tools '
           'and adjacent responsible-AI tooling, explicitly identified below.', '',
           '## Coverage', '', '| Category | Repositories |', '| --- | ---: |']
    for category in CATEGORIES:
        out.append(f"| {category} | {sum(r['category'] == category for r in repos)} |")
    for category in CATEGORIES:
        out += ['', '## ' + category, '', '| Repository | Stars | Δ 7d | Δ 30d | Last push (UTC) | License | Status | Why included |',
                '| --- | ---: | ---: | ---: | --- | --- | --- | --- |']
        for r in sorted((r for r in repos if r['category'] == category), key=lambda x: (-x['stars'], x['repository'])):
            status = 'Archived' if r['archived'] else ('Fork' if r['fork'] else 'Active repository')
            out.append('| ' + ' | '.join([f"[{r['repository']}]({r['url']})", f"{r['stars']:,}",
                cell(growth(r, previous, 7)), cell(growth(r, previous, 30)), (r['pushed_at'] or '')[:10],
                cell(r['license']), status, cell(r['reason'])]) + ' |')
        out += ['', '### Repository descriptions', '']
        for r in sorted((r for r in repos if r['category'] == category), key=lambda x: x['repository'].lower()):
            desc = (r['description'] or 'No description supplied.').replace('\n', ' ')
            out.append(f"- **[{r['repository']}]({r['url']})** — {desc} [Metadata](https://api.github.com/repos/{r['repository']})")
    if snapshot['errors']:
        out += ['', '## Collection errors', '', 'Failed lookups are omitted from the verified baseline; no metrics are invented.', '']
        for error in snapshot['errors']:
            out.append(f"- {error['repository']}: {cell(error['error'])}")
    out += ['', '## Interpretation and limitations', '',
            '- Stars measure attention, not adoption, reliability or safety. Counts can decrease.',
            '- Last push is repository activity, not a release or evidence of maintainer responsiveness.',
            '- Active repository means GitHub has not marked it archived; it does not guarantee active maintenance.',
            '- License is GitHub’s detected SPDX label; NOASSERTION or — needs manual review.',
            '- This seed set is intentionally curated, not exhaustive. Search candidates require review before inclusion.',
            '- No repository code was executed. This baseline verifies metadata and topical fit, not implementation claims.',
            '- Snapshots are immutable and include per-repository collection timestamps; partial failures are recorded.', '']
    return '\n'.join(out)


def collect():
    started = now()
    seeds = read_seeds()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(collect_one, seeds))
    good, errors, seen = [], [], set()
    for result in results:
        if 'error' in result:
            errors.append(result)
        elif result['id'] in seen:
            errors.append(dict(repository=result['requested_repository'], error='Duplicate canonical repository'))
        else:
            good.append(result)
            seen.add(result['id'])
    if not good:
        raise RuntimeError('All lookups failed; existing reports preserved. ' + str(errors[:1]))
    snapshot = dict(schema_version=1, collected_at=started, completed_at=now(), repositories=good, errors=errors)
    history = [json.loads(p.read_text()) for p in sorted((ROOT / 'data/snapshots').glob('*.json'))]
    stamp = datetime.fromisoformat(started).strftime('%Y%m%dT%H%M%S%fZ')
    write_json(ROOT / 'data/snapshots' / (stamp + '.json'), snapshot)
    report = render(snapshot, history)
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / (stamp + '.md')).write_text(report)
    (ROOT / 'reports/latest.md').write_text(report)
    print(f'Collected {len(good)}/{len(seeds)} repositories; {len(errors)} errors. Report: reports/latest.md')
    for error in errors:
        print(error['repository'] + ': ' + error['error'], file=sys.stderr)
    return 1 if errors else 0


def discover():
    from urllib.parse import urlencode
    queries = json.loads((ROOT / 'config/searches.json').read_text())
    seeds = {s['repository'].lower() for s in read_seeds()}
    candidates, errors = {}, []
    for category, searches in queries.items():
        for query in searches:
            try:
                response = api('search/repositories?' + urlencode(dict(q=query, sort='updated', order='desc', per_page=20)))
                if response.get('incomplete_results'):
                    errors.append(dict(query=query, error='GitHub returned incomplete search results'))
                for r in response['items']:
                    if r['full_name'].lower() in seeds or r['fork']:
                        continue
                    entry = candidates.setdefault(str(r['id']), dict(repository=r['full_name'], url=r['html_url'],
                        description=r['description'], stars=r['stargazers_count'], matches=[]))
                    entry['matches'].append(dict(category=category, query=query))
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                errors.append(dict(query=query, error=str(exc)))
            time.sleep(3)  # Stay below GitHub's search request rate limit.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = ROOT / 'data/candidates' / (stamp + '.json')
    write_json(path, dict(collected_at=now(), note='Unreviewed candidates; not automatically added to the baseline. Top 20 most recently updated results per query; not exhaustive.', candidates=list(candidates.values()), errors=errors))
    print(f'{len(candidates)} candidates; {len(errors)} errors. Saved {path.relative_to(ROOT)}')
    return 1 if errors else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect', 'discover'])
    args = parser.parse_args()
    try:
        sys.exit(collect() if args.command == 'collect' else discover())
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
