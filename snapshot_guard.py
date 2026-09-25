"""Refuse to publish a snapshot that silently drops offers verified in the last published one.

Rationale: a transient source block must never remove already-verified entries from the live
site. build.py still publishes an honest status page for the failing provider, so the failure
is visible; this guard only stops the deployment from overwriting the last good snapshot.
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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


def main():
    current = json.loads((ROOT / 'data/offers.json').read_text())
    previous = previous_snapshot()
    if previous is None:
        print('No published snapshot to compare against; nothing to guard.')
        return 0

    now = Counter(o['provider'] for o in current['offers'])
    before = Counter(o['provider'] for o in previous['offers'])
    reasons = {c['provider']: c for c in current['checks']}
    lost = sorted(p for p, n in before.items() if n > 0 and now.get(p, 0) == 0)
    if not lost:
        print('Guard passed: no provider lost previously verified offers.')
        return 0

    print('Guard tripped: this snapshot would remove offers already verified on the live site.')
    for provider in lost:
        check = reasons.get(provider, {})
        print('  - {0}: {1} -> 0 offers | status={2} | {3}'.format(
            provider, before[provider], check.get('status', 'missing check'),
            str(check.get('error') or 'no error recorded')[:160]))
    print('Refusing to publish. Fix the source access, or publish the status-page-only '
          'snapshot deliberately by re-running with SKIP_SNAPSHOT_GUARD=1.')
    return 1


if __name__ == '__main__':
    import os
    sys.exit(0 if os.environ.get('SKIP_SNAPSHOT_GUARD') == '1' else main())
