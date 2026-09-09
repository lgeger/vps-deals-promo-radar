"""Public official HTML only. No inference, third-party dependencies or API keys."""
import hashlib
import json
import re
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
UA = 'VPSDealsRadar/1.0'

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'): self.skip = max(0, self.skip - 1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(' '.join(data.split()))

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=30) as r:
        if urlsplit(r.url).hostname != urlsplit(url).hostname:
            raise ValueError('Cross-host redirect requires source review')
        return r.read(4_000_000).decode('utf-8')

def scrape():
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    providers = json.loads((ROOT / 'data/providers.json').read_text())
    offers, checks = [], []
    for provider in providers:
        url = provider['source_url']
        check = dict(provider=provider['id'], source_url=url, checked_at=now)
        try:
            origin = '{0.scheme}://{0.netloc}'.format(urlsplit(url))
            robot = urllib.robotparser.RobotFileParser()
            robot.parse(fetch(origin + '/robots.txt').splitlines())
            if not robot.can_fetch(UA, url): raise ValueError('robots.txt disallows crawling')
            raw = fetch(url)
            parser = TextParser(); parser.feed(raw)
            text = ' | '.join(parser.parts)
            found = []
            if provider['id'] == 'ovhcloud':
                pattern = r'(VPS-\d+) \| From \| \$(\d+(?:\.\d+)?) \| /month \| Configure \| (.*?)(?= \| (?:202\d|VPS-\d+|New VPS range)|$)'
                for match in re.finditer(pattern, text):
                    found.append(dict(name=match[1], kind='listed_price', price=match[2], currency='USD', billing_period='month', evidence=match[0][:650], terms='官方 World/USD 页面起价；税费、地区、期限和续费以结账页为准。'))
            elif provider['id'] == 'akamai':
                match = re.search(r'Get up to US\$[\d,]+ in cloud credits\* \| .*?Offer available to new and existing enterprise customers\.', text)
                if match:
                    found.append(dict(name=match[0].split(' | ')[0], kind='credit', price=None, currency=None, billing_period=None, evidence=match[0], terms='面向新老企业客户，需申请及资格审核；额度不是现金或主机价格。'))
            for item in found:
                item.update(id=provider['id']+'-'+hashlib.sha256(item['name'].encode()).hexdigest()[:10], provider=provider['id'], offer_url=url, source_url=url, verified_at=now, valid_from=None, valid_until=None, source_sha256=hashlib.sha256(raw.encode()).hexdigest())
                offers.append(item)
            check.update(status='ok' if found else 'no_verified_offer', count=len(found))
        except Exception as exc:
            check.update(status='unavailable', count=0, error=str(exc)[:200])
        checks.append(check)
        print(provider['id'], check['status'], check['count'])
    # Never silently preserve old offers when today's source cannot be verified.
    result = dict(updated_at=now, offers=offers, checks=checks)
    target = ROOT / 'data/offers.json'
    tmp = target.with_suffix('.tmp'); tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n'); tmp.replace(target)
    return result

if __name__ == '__main__':
    scrape()
