"""Deterministic static publisher using only the Python standard library."""
import json
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit
from providers import load_providers
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'site'
BASE = 'https://vps.wpxtool.com'
def esc(value): return escape(str(value), quote=True)
def safe_url(value):
    if urlsplit(value).scheme != 'https' or not urlsplit(value).netloc: raise ValueError('HTTPS URL required')
    return esc(value)
NOW = datetime.now(timezone.utc)
def age_days(stamp):
    try: return max(0, (NOW - datetime.fromisoformat(stamp)).days)
    except (TypeError, ValueError): return None
def age_text(stamp):
    days = age_days(stamp)
    return '（'+str(days)+' 天前）' if days is not None else ''
def build():
    data = json.loads((ROOT/'data/offers.json').read_text())
    providers = load_providers()
    affiliates = json.loads((ROOT/'.ilang/site.ilang').read_text())['PROVIDERS']
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    names = {p['id']: p['name'] for p in providers}
    stamp = data['updated_at']
    offers = data['offers']
    checked = {c['provider'] for c in data['checks']}
    visible = {p['id'] for p in providers if p['id'] in checked or not p.get('require_offers') or any(o['provider'] == p['id'] for o in offers)}
    def cards(items):
        out = []
        for o in items:
            badge = ''
            if o.get('stale'):
                badge = '<div class="stale">本次未能重新核验 · 最后核验于 '+esc(str(o.get('verified_at'))[:10])+age_text(o.get('verified_at'))+'</div>'
            out.append('<article><div class="meta">'+esc(names[o['provider']])+' · '+('官方标价' if o['kind']=='listed_price' else '申请型额度')+'</div>'+badge+'<h3><a href="/deals/'+o['id']+'/">'+esc(o['name'])+'</a></h3><p class="price">'+(esc(o['currency'])+' '+esc(o['price'])+' <small>/ 月起</small>' if o['price'] else '企业资格审核')+'</p><p>'+esc(o['terms'])+'</p><a class="detail" href="/deals/'+o['id']+'/">查看条件与来源 ↗</a></article>')
        return ''.join(out) or '<p class="notice">本次没有可核验条目。请查看供应商官网，勿依据过期价格下单。</p>'
    paths = []
    def page(path, template, title, **kw):
        body = Template((ROOT/'templates'/template).read_text()).substitute(**kw)
        html = Template((ROOT/'templates/base.html').read_text()).substitute(title=esc(title), body=body, updated=esc(stamp), canonical=BASE+'/'+path+('/' if path else ''))
        target = OUT/path/'index.html'; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(html)
        paths.append('/'+path+('/' if path else ''))
    status_labels = {'ok':'已核验', 'no_verified_offer':'未提取到可核验优惠', 'unavailable':'本次无法访问'}
    check_by = {c['provider']: c for c in data['checks']}
    carried_by = {}
    for o in offers:
        if o.get('stale'):
            carried_by.setdefault(o['provider'], []).append(o)
    def note_for(pid):
        c = check_by.get(pid)
        if not c:
            return '本次未执行抓取检查。'
        base = '本次抓取状态：'+status_labels[c['status']]+'。来源页：'+c['source_url']+'；抓取时间：'+c['checked_at']+'。'
        if c['status'] == 'ok':
            return base+'共 '+str(c['count'])+' 条，逐条附官方原文证据。'
        held = carried_by.get(pid)
        if held:
            oldest = min(str(o.get('verified_at'))[:10] for o in held)
            return base+'本次未能重新核验该来源，下列 '+str(len(held))+' 条沿用 '+oldest+' '+age_text(oldest)+' 最后一次成功核验的价格，之后可能已经变动，下单前请以官方页面为准。'
        if c['status'] == 'unavailable':
            return base+'具体返回：'+str(c.get('error') or '未记录')+'。此次未能取得官方页面，不代表该厂商没有优惠。'
        return base+'官方页面可访问，但本次未提取到可核验条目；不代表该厂商没有优惠。'
    stale_offers = [o for o in offers if o.get('stale')]
    alert = ''
    if stale_offers:
        affected = sorted({names[o['provider']] for o in stale_offers})
        alert = ('<div class="alert"><b>'+str(len(stale_offers))+' 条目本次未能重新核验</b><span>涉及 '
                 +esc('、'.join(affected))+'。这些条目保留最后一次成功核验的价格并已逐条标注核验日期，'
                 '可能已经变动；其余条目为本次核验。</span></div>')
    checks = ''.join('<li><a href="/providers/'+c['provider']+'/">'+esc(names[c['provider']])+'</a><span>'+status_labels[c['status']]+'</span></li>' for c in data['checks'] if c['provider'] in visible)
    page('', 'index.html', 'VPS Deals · 官方主机优惠观察', cards=cards(offers), checks=checks, count=len(offers), alert=alert)
    for p in providers:
        if p['id'] not in visible: continue
        link = affiliates.get(p['id'])
        if link and not link.get('url'): link = None
        page('providers/'+p['id'],'provider.html',p['name']+' · VPS Deals', name=esc(p['name']), source=safe_url(link['url'] if link else p['source_url']), rel='sponsored nofollow noopener' if link else 'noopener', disclosure='此链接为联盟链接，成交后本站可能获得佣金。' if link else '', status_note=esc(note_for(p['id'])), cards=cards([o for o in offers if o['provider']==p['id']]))
    for o in offers:
        link = affiliates.get(o['provider'])
        if link and not link.get('url'): link = None
        href = link['url'] if link else o['offer_url']
        staleness = ''
        if o.get('stale'):
            staleness = ('本次未能重新核验：此价格是 '+str(o.get('verified_at'))[:10]+age_text(o.get('verified_at'))
                         +' 最后一次成功核验的版本，可能已经变动。未重新核验的原因：'+str(o.get('carry_reason'))+'。')
        page('deals/'+o['id'],'deal.html',o['name']+' · VPS Deals', name=esc(o['name']), provider=esc(names[o['provider']]), terms=esc(o['terms']), evidence=esc(o['evidence']), source=safe_url(o['source_url']), url=safe_url(href), rel='sponsored nofollow noopener' if link else 'noopener', disclosure='此链接为联盟链接，成交后本站可能获得佣金。' if link else '官方直链：本站未配置该供应商的联盟佣金。', verified=esc(o['verified_at']), staleness=esc(staleness))
    rows = ''.join('<tr><td><a href="/deals/'+o['id']+'/">'+esc(names[o['provider']]+' '+o['name'])+'</a></td><td>'+esc(str(o['price'])+' '+str(o['currency'])+'/月起' if o['price'] else '非价格：申请型额度')+'</td><td>'+esc(o['terms'])+'</td></tr>' for o in offers)
    page('compare','compare.html','VPS 对比 · 价格与条件',rows=rows)
    page('privacy','privacy.html','隐私政策 · VPS Deals', updated=esc(stamp))
    page('about','about.html','关于本站 · VPS Deals', updated=esc(stamp))
    page('contact','contact.html','联系方式 · VPS Deals', updated=esc(stamp))
    shutil.copy(ROOT/'templates/style.css',OUT/'style.css')
    (OUT/'data').mkdir(); shutil.copy(ROOT/'data/offers.json',OUT/'data/offers.json')
    (OUT/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+BASE+'/sitemap.xml\n')
    lastmod = esc(datetime.fromisoformat(stamp).isoformat())
    (OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+BASE+p+'</loc><lastmod>'+lastmod+'</lastmod></url>' for p in paths)+'</urlset>')
    (OUT/'404.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>条目已下架</title><h1>此条目不存在或已不再可核验</h1><a href="/">查看最新条目</a></html>')
    (OUT/'_headers').write_text('/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n')
    print('Built',len(paths),'pages;',len(offers),'entries;',len(stale_offers),'not re-verified this run')
if __name__ == '__main__': build()
