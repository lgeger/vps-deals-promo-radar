"""Fail the refresh when published prices have gone stale past a ceiling, or vanished.

Two things can go wrong with an automatic refresh, and they need opposite answers:

1. An entry disappears. That is always wrong: a reader can still buy at that price, and the
   previous run verified it. Blocked unconditionally.
2. An entry survives but stops being re-verified for a long time. That is survivable for a
   while -- scraper.py marks it `stale` and prints the date it was last actually verified -- but
   past MAX_STALE_DAYS the site is publishing prices nobody has confirmed for a week. That is
   where a human should decide instead of the cron job.

So the guard is a decay ceiling, not a one-strike block. A single blocked source no longer
freezes the site; a source blocked for over a week still stops the publish and goes red.
"""
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAX_STALE_DAYS = 7


def previous_snapshot():
    try:
        raw = subprocess.check_output(
            ['git', 'show', 'HEAD:data/offers.json'], cwd=ROOT, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def vanished(current, before):
    """Providers whose previously verified entries are gone from this snapshot."""
    now = Counter(o['provider'] for o in current['offers'])
    checks = {c['provider']: c for c in current.get('checks', [])}
    problems = []
    for provider in sorted(before):
        if before[provider] > 0 and now.get(provider, 0) == 0:
            check = checks.get(provider, {})
            problems.append('vanished: {0} had {1} entr(ies), now 0 | status={2} | {3}'.format(
                provider, before[provider], check.get('status', 'missing check'),
                str(check.get('error') or 'no error recorded')[:160]))
    return problems


def staleness(current, now):
    """Highest age in days of the carried-forward entries, per provider."""
    ages, problems = {}, []
    for offer in current['offers']:
        if not offer.get('stale'):
            continue
        try:
            verified = datetime.fromisoformat(offer['verified_at'])
        except (KeyError, TypeError, ValueError):
            problems.append('stale: {0} entry {1} has no usable verified_at'.format(
                offer.get('provider'), offer.get('id')))
            continue
        days = max(0, (now - verified).days)
        ages[offer['provider']] = max(ages.get(offer['provider'], 0), days)
    return ages, problems


def main():
    current = json.loads((ROOT / 'data/offers.json').read_text())
    now = datetime.now(timezone.utc)
    problems = []

    previous = previous_snapshot()
    if previous is None:
        print('No published snapshot to compare against; nothing to guard for losses.')
    else:
        problems.extend(vanished(current, Counter(o['provider'] for o in previous['offers'])))

    ages, stale_problems = staleness(current, now)
    problems.extend(stale_problems)
    for provider, days in sorted(ages.items()):
        print('  carried: {0} last verified {1} day(s) ago'.format(provider, days))
        if days > MAX_STALE_DAYS:
            problems.append('stale: {0} has not been verifiable for {1} days (ceiling {2})'.format(
                provider, days, MAX_STALE_DAYS))

    if problems:
        print('Guard tripped:')
        for problem in problems:
            print('  - ' + problem)
        print('Refusing to publish. Fix the source access, or publish this snapshot deliberately '
              'by re-running with SKIP_SNAPSHOT_GUARD=1.')
        return 1

    if ages:
        print('Guard passed with {0} carried provider(s), all within {1} days.'.format(
            len(ages), MAX_STALE_DAYS))
    else:
        print('Guard passed: nothing vanished and nothing is stale beyond {0} days.'.format(
            MAX_STALE_DAYS))
    return 0


if __name__ == '__main__':
    sys.exit(0 if os.environ.get('SKIP_SNAPSHOT_GUARD') == '1' else main())
