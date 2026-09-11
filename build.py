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
def build():
    data = json.loads((ROOT/'data/offers.json').read_text())
    providers = load_providers()
    affiliates = json.loads((ROOT/'.ilang/site.ilang').read_text())['PROVIDERS']
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    names = {p['id']: p['name'] for p in providers}
    stamp = data['updated_at']
    offers = data['offers']
    visible = {p['id'] for p in providers if not p.get('require_offers') or any(o['provider'] == p['id'] for o in offers)}
    def cards(items):
        return ''.join('<article><div class="meta">'+esc(names[o['provider']])+' · '+('官方标价' if o['kind']=='listed_price' else '申请型额度')+'</div><h3><a href="/deals/'+o['id']+'/">'+esc(o['name'])+'</a></h3><p class="price">'+(esc(o['currency'])+' '+esc(o['price'])+' <small>/ 月起</small>' if o['price'] else '企业资格审核')+'</p><p>'+esc(o['terms'])+'</p><a class="detail" href="/deals/'+o['id']+'/">查看条件与来源 ↗</a></article>' for o in items) or '<p class="notice">本次没有可核验条目。请查看供应商官网，勿依据过期价格下单。</p>'
    paths = []
    def page(path, template, title, **kw):
        body = Template((ROOT/'templates'/template).read_text()).substitute(**kw)
        html = Template((ROOT/'templates/base.html').read_text()).substitute(title=esc(title), body=body, updated=esc(stamp), canonical=BASE+'/'+path+('/' if path else ''))
        target = OUT/path/'index.html'; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(html)
        paths.append('/'+path+('/' if path else ''))
    status_labels = {'ok':'已核验', 'no_verified_offer':'未提取到可核验优惠', 'unavailable':'本次无法访问'}
    check_by = {c['provider']: c for c in data['checks']}
    def note_for(pid):
        c = check_by.get(pid)
        if not c:
            return '本次未执行抓取检查。'
        base = '本次抓取状态：'+status_labels[c['status']]+'。来源页：'+c['source_url']+'；抓取时间：'+c['checked_at']+'。'
        if c['status'] == 'ok':
            return base+'共 '+str(c['count'])+' 条，逐条附官方原文证据。'
        if c['status'] == 'unavailable':
            return base+'具体返回：'+str(c.get('error') or '未记录')+'。此次未能取得官方页面，不代表该厂商没有优惠。'
        return base+'官方页面可访问，但本次未提取到可核验条目；不代表该厂商没有优惠。'
    checks = ''.join('<li><a href="/providers/'+c['provider']+'/">'+esc(names[c['provider']])+'</a><span>'+status_labels[c['status']]+'</span></li>' for c in data['checks'] if c['provider'] in visible)
    page('', 'index.html', 'VPS Deals · 官方主机优惠观察', cards=cards(offers), checks=checks, count=len(offers))
    for p in providers:
        if p['id'] not in visible: continue
        link = affiliates.get(p['id'])
        if link and not link.get('url'): link = None
        page('providers/'+p['id'],'provider.html',p['name']+' · VPS Deals', name=esc(p['name']), source=safe_url(link['url'] if link else p['source_url']), rel='sponsored nofollow noopener' if link else 'noopener', disclosure='此链接为联盟链接，成交后本站可能获得佣金。' if link else '', status_note=esc(note_for(p['id'])), cards=cards([o for o in offers if o['provider']==p['id']]))
    for o in offers:
        link = affiliates.get(o['provider'])
        if link and not link.get('url'): link = None
        href = link['url'] if link else o['offer_url']
        page('deals/'+o['id'],'deal.html',o['name']+' · VPS Deals', name=esc(o['name']), provider=esc(names[o['provider']]), terms=esc(o['terms']), evidence=esc(o['evidence']), source=safe_url(o['source_url']), url=safe_url(href), rel='sponsored nofollow noopener' if link else 'noopener', disclosure='此链接为联盟链接，成交后本站可能获得佣金。' if link else '官方直链：本站未配置该供应商的联盟佣金。', verified=esc(o['verified_at']))
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
    print('Built',len(paths),'pages;',len(offers),'verified entries')
if __name__ == '__main__': build()
