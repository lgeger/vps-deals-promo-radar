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

from providers import load_providers

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
    providers = load_providers()
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
            elif provider['id'] == 'dreamhost':
                pattern = r'(Stack \d+) \| .*?First (\d+) months at \| \$(\d+\.\d{2}) \| /mo \| SAVE \| \d+% \| Sign Up Now \| Auto-renews at \| \$(\d+\.\d{2}) \| /mo after (\d+) months\.'
                for match in re.finditer(pattern, text):
                    if match[2] != match[5]:
                        continue
                    found.append(dict(name='DreamHost '+match[1], kind='listed_price', price=match[3], currency='USD', billing_period='month', evidence=match[0], terms='官方月付促销：前 '+match[2]+' 个月每月 $'+match[3]+'，随后每月 $'+match[4]+' 自动续费；结账另计税费，以官网实际订单为准。'))
            elif provider['id'] == 'akamai':
                match = re.search(r'Get up to US\$[\d,]+ in cloud credits\* \| .*?Offer available to new and existing enterprise customers\.', text)
                if match:
                    found.append(dict(name=match[0].split(' | ')[0], kind='credit', price=None, currency=None, billing_period=None, evidence=match[0], terms='面向新老企业客户，需申请及资格审核；额度不是现金或主机价格。'))
            elif provider['id'] == 'inmotion':
                pattern = r'(VPS \d+ vCPU)(?: \|[^|]*)*? \| You Save \| (\d+)% \| \$([\d.]+) \| /mo \| For (\d+) month term \| Renews at \| \$([\d.]+) \| /mo'
                for match in re.finditer(pattern, text):
                    found.append(dict(name='InMotion '+match[1], kind='listed_price', price=match[3], currency='USD', billing_period='month', evidence=match[0], terms='官方促销价：'+match[4]+' 个月期每月 $'+match[3]+'，官网标注优惠 '+match[2]+'%，到期按每月 $'+match[5]+' 续费；税费与地区以结账页为准。'))
            elif provider['id'] == 'contabo':
                pattern = r'(Cloud VPS \d+) \| €(\d+\.\d{2}) \| \d+ \| \d+ \| / month'
                seen = set()
                for match in re.finditer(pattern, text):
                    if match[1] in seen:
                        continue
                    seen.add(match[1])
                    found.append(dict(name='Contabo '+match[1], kind='listed_price', price=match[2], currency='EUR', billing_period='month', evidence=match[0], terms='官方欧元标价：每月 €'+match[2]+'；页面同行的具体配置数字本次未做可靠提取，配置以官方 VPS 页为准，税费、地区与期限以结账页为准。'))
            elif provider['id'] == 'upcloud':
                upcloud_patterns = [
                    (r'Standard performance SSD storage \| Previous-gen AMD CPUs \| IPv4 included \| 99\.99% SLA \| Starting from \| €(\d+)/mo \| Global price', 'UpCloud Cloud Server Standard'),
                    (r'MaxIOPS high performance storage \| 1000 Mbps Internet & IPv4 included \| Starting from \| €(\d+)/mo \| Global price', 'UpCloud Cloud Server MaxIOPS'),
                    (r'Choice of MaxIOPS, Standard or Archive storage \| 1000 Mbps Internet \| Server stopped, no charges \| 99\.999% SLA \| Transfer Included \| Starting from \| €(\d+)/mo \| Global price', 'UpCloud Cloud Server 灵活计费'),
                ]
                for up_pattern, up_name in upcloud_patterns:
                    match = re.search(up_pattern, text)
                    if match:
                        found.append(dict(name=up_name, kind='listed_price', price=match[1], currency='EUR', billing_period='month', evidence=match[0], terms='官方 Global 价目表该系列起价：每月 €'+match[1]+' 起；同页另有更高配置档位，实际配置与地区价格以官方定价页为准。托管数据库、Kubernetes、对象存储等非 VPS 产品未收录。'))
            elif provider['id'] == 'ultahost':
                pattern = r'(VPS [A-Za-z]+) \| ([^|]+) \| \$([\d.]+) \| Save (\d+)% \| \$([\d.]+) \| /mo \| Billed for (\d+) month term\.'
                for match in re.finditer(pattern, text):
                    found.append(dict(name='UltaHost '+match[1], kind='listed_price', price=match[5], currency='USD', billing_period='month', evidence=match[0], terms='官方促销价：原价 $'+match[3]+'，优惠 '+match[4]+'% 后 '+match[6]+' 个月期每月 $'+match[5]+'；税费、续费与取消条件以官网订单页为准。'))
            elif provider['id'] == 'hostpapa':
                pattern = r'VPS Hosting from \$([\d.]+)/mo'
                seen = set()
                for match in re.finditer(pattern, text):
                    if match[1] in seen:
                        continue
                    seen.add(match[1])
                    found.append(dict(name='HostPapa VPS Hosting', kind='listed_price', price=match[1], currency='USD', billing_period='month', evidence=match[0], terms='官方 VPS 页面起价：每月 $'+match[1]+' 起；官网正文注明该起价对应 36 个月期，Managed 方案起价更高，以结账页为准。'))
            elif provider['id'] == 'knownhost':
                pattern = r'Starting at \$([\d.]+)/mo \| Explore ([A-Za-z]+) VPS'
                for match in re.finditer(pattern, text):
                    found.append(dict(name='KnownHost '+match[2]+' VPS', kind='listed_price', price=match[1], currency='USD', billing_period='month', evidence=match[0], terms='官方 '+match[2]+' VPS 起价：每月 $'+match[1]+' 起；配置、地区与期限以官网方案页为准。'))
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
