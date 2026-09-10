# VPS Deals

中文 VPS 官方价格与优惠观察站。默认细分：VPS 主机；默认品牌：vps-deals。

仓库：https://github.com/lgeger/vps-deals-promo-radar

正式地址：https://vps.wpxtool.com

2026-09-09 已验证生产站可访问，首次 Actions 抓取、构建、提交成功：https://github.com/lgeger/vps-deals-promo-radar/actions/runs/34330334858

## 本地运行

Python 3.10+，只使用标准库，无需 pip、推理服务或自备 API 密钥。

```sh
python scraper.py
python build.py
python -m http.server 8000 --directory site
```

## 来源与真实性

五家种子及官方网址见 `data/providers.json`：OVHcloud、Akamai/Linode、Hetzner、Vultr、DigitalOcean。抓取前检查 robots.txt；禁止抓取、403、重定向到其他主机、超时均停止该来源，不绕过反爬。首版适配 OVHcloud 官方 VPS 页面价格片段和 Akamai 企业额度原文；其余来源只做可访问性检查，未提取到信息不会生成条目。增加来源需要人工添加确定性适配器，不能保证任意网页自动理解。

每条记录提供 source_url、verified_at、原文 evidence 和页面 SHA256。没有明确日期时 valid_from / valid_until 为 null；抓取时间不是生效日期。列表价不是折扣，企业额度不是售价。页面结构变化时宁可不显示，不猜测数字。金额地区、税费、期限和续费以官方结账页为准。

抓取失败不保留旧报价；公开 checks 记录失败。网站始终显示快照时间。若管线停止，快照时间仍是旧时间，读者应复核官网，不应认为是实时优惠。

## 自动更新与 Pages

GitHub Actions 每天 UTC 18:23（北京时间次日 02:23）执行 scraper.py + build.py 并提交 data/offers.json 与 site/，也可从 Actions 手动 Run workflow。contents:write 使用 GitHub 自动签发的临时 GITHUB_TOKEN，不需自备 secret；并非完全没有平台内部鉴权。

Cloudflare Pages 选择 Git 集成，仓库 lgeger/vps-deals-promo-radar，生产分支 main，构建命令 `python build.py`，输出 `site`，框架 None。构建使用已提交快照，不在 Cloudflare 重复抓取。不要改成 Direct Upload 项目，否则后续 Git 集成需要重建项目。

免费套餐受平台限额和政策约束，定时可能延迟。公开仓库长时间无活动可能被 GitHub 停用 schedule；不能承诺永久无人值守。运营 SOP：每月查看 Actions 与最近一次生产部署；失败查看 checks，再检查 robots 和官方页面；不要为绕过封禁增加反爬。每天最多一次常规更新以控制免费构建额度。

## 变现配置

2026-09-10 已从 Vultr Referral Program 后台核验推广链接，接入厂商页；PayPal 收款设置已保存，最低付款额 $100。后台显示每名合格新付费用户 $10，需活跃超过 30 天且至少支付 $10；并非注册即获佣金，没有收入承诺。

联盟链接唯一配置为 .ilang/site.ilang（JSON 格式）的 PROVIDERS 对象，在其中添加供应商 ID 对应对象（url 为自己的获批 HTTPS 跟踪链接，另可存 terms_url、verified_at）。build.py 自动标注佣金披露并添加 sponsored nofollow。先核实官方联盟条款是否支持持续佣金；按年付费不等于按年分佣，不能编造佣金比例。托管主机可以后续扩展独立来源和对比维度，当前不把 VPS 说成托管服务。

可叠加：真实联盟推广 → 明确标注的赞助位 → 有实际价值的运维选购内容 → 出售域名、代码、品牌及可验证收入史。保留真实流量、成本、结算和内容授权证明，不造回链，不刷量。

EMU 含义未明，本站不实施。如果指虚假转化、模拟用户或联盟作弊，风险包括平台封号/拒付（平台处置）、追偿/损害赔偿（民事）、符合诈骗等犯罪构成时的刑事责任，具体依行为与法域而定，不能当作安全兜底。

## 域名与资产

品牌确定后可尽早注册合适域名，积累持续内容、口碑和可验证经营史。域名年龄本身不保证搜索排名，回链需靠有用内容自然获得。注册完成后在 Pages Custom domains 添加域名并按向导配置 DNS，同时修改 build.py 的 BASE 并重建，更新 README。注册域名和续费不是免费的。
