"""Combine established sources with reviewed rollout configuration."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def load_providers():
    providers = json.loads((ROOT/'data/providers.json').read_text())
    known = {p['id'] for p in providers}
    config = json.loads((ROOT/'.ilang/site.ilang').read_text())
    for key, entry in config['PROVIDERS'].items():
        if key not in known and entry.get('source_url'):
            providers.append(dict(entry, id=key))
    return providers
