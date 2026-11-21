# 项目状态｜CS Career Map

给 Emma 和之后接手的 AI 看。完整的决定记录在 Notion「CS 职业学习地图｜项目说明与日志」。
标记：✓ = 核对过；⚠ = 没核对或没跑过。时间是美东时间（ET）。

## 现在到哪了（2026-11-21 凌晨，第一晚）

**能用的：**

- ✓ 采集脚本 `collector/collect.py`：读 Greenhouse、Lever 的公开职位接口，按标题归到 3 个岗位，排除 senior 以上，匹配技能，统计次数。只用 Python 标准库。
- ✓ 测试 `collector/test_collect.py`：全部通过。覆盖容易数错的词（Java/JavaScript、Go、R、Excel、React 当动词用等）、标题归类、接口解析、数据合并、统计。
- ✓ 网站 `docs/`：首页、岗位页（可切「只看实习和应届」、按类别筛、点开看学习指南）、方法说明页。在电脑和手机宽度下用浏览器点过一遍，没有报错。
- ✓ 学习资源 `data/skill_guides.json`：36 个技能，每个链接都在 2026-11-21 打开核对过。
- ✓ Claude skill `skill/cs-career-coach/`：读同一份数据当导师。
- ✓ README、贡献说明、3 个 Issue 表单（从业者补充、推荐资源、加公司）。

**还不是真的：**

- ⚠ **网站上的数字全是演示数据**（公司叫 Demo Company A…，数字是占位）。页面顶部有红色提示条。原因：这个代码环境连不上招聘接口（`boards-api.greenhouse.io`、`api.lever.co` 被联网设置挡住）。第一次真实采集成功后，演示数据会被自动删掉，提示条自动消失。
- ⚠ 采集脚本没有对真实接口整体跑过。两个接口返回的字段名对照真实返回核对过（见下面「核对记录」），但完整的一轮采集要等能联网的地方跑。
- ⚠ `config/companies.json` 里 43 家公司，只有 Stripe、GitLab、Airbnb、Palantir 的地址有出处或打开过。其余是候选，第一次采集时会自动验证，找不到的会写进 `data/run_report.json`。
- ⚠ 3 个 GitHub Actions 流程（每周采集、发布网站、跑测试）写好了但没在 GitHub 上跑过。
- ⚠ skill 没有在 Claude 里实际调用测试过；「怎么把文件夹加进 Claude」的具体步骤没查官方文档，README 里只写了大意。
- ⚠ Greenhouse、Lever 接口的官方使用条款原文还没读。公开前要读。

## Emma 要做的（只有你能做）

1. **连 GitHub**：claude.ai → Settings → Connectors。或者在自己电脑的终端里推（见下）。
2. **建仓库**：GitHub 上新建 `cs-career-map`（建议先设成 private，看过再公开）。
3. **开 Pages**：仓库 Settings → Pages → Source 选 "GitHub Actions"。
4. 推上去以后，在仓库 Actions 页手动点一次 "Refresh job posting data"。它在 GitHub 的机器上跑，能联网，会采真实数据并发布网站。

最省事的办法：连好 GitHub、建好空仓库后，回到 Claude 那个对话说一句「推」，那边有完整的一份（含 `.github/`）。

⚠ 电脑上 `~/Desktop/Emma/cs-career-map` 这份**缺 `.github/` 文件夹**（6 个文件：3 个自动流程 + 3 个 Issue 表单）。远程工具不允许往电脑上的 `.github/` 写文件。完整版在对话里发的 `cs-career-map.zip` 里，自己推之前先把 zip 里的 `.github/` 拷进来。

在自己电脑上推的命令（项目在 `~/Desktop/Emma/cs-career-map`）：

```bash
cd ~/Desktop/Emma/cs-career-map
git init -b main
git add -A
git commit -m "First version: collector, site, coach skill, docs (built with Claude)"
git remote add origin https://github.com/EmmaZhao422/cs-career-map.git
git push -u origin main
```

## Claude 替你定的（你说了不要问，都可以改）

- 项目名和仓库名：`cs-career-map`，网站标题 "CS Career Map"
- 第一版 3 个岗位：AI Engineer、Data Analyst、Software Engineer（你确认过）
- 网站不用框架，纯 HTML/CSS/JS，没有构建步骤，方便别人贡献
- 采集脚本只用 Python 标准库
- 不存招聘原文，只存链接和匹配到的技能名
- 一条招聘在最后一次看到之后保留 120 天
- 频率分档：40% 以上 / 15–40% / 5–15% / 5% 以下
- 许可证：MIT
- 每周一自动采集一次
- 从业者补充走 GitHub Issue 表单，默认不显示姓名和公司

## 下一步（按顺序）

1. 推上 GitHub，跑第一次真实采集，看 `data/run_report.json` 里哪些公司地址不对，清理 `config/companies.json`。
2. 抽查真实结果：每个岗位随机点开 10 条招聘，对照页面上匹配到的技能，看有没有数错的。数错的改 `config/taxonomy.json` 并加测试。
3. 读 Greenhouse、Lever 的使用条款。
4. 在 Claude 里实际调用一次 skill，按结果改 `SKILL.md`。
5. 找 3–5 位从业者要第一批补充（冷启动）。
6. 第二批岗位：Forward Deployed / Solutions Engineer、AI Product Manager。
7. 覆盖不用 Greenhouse/Lever 的大公司（Ashby、Workday 等有没有公开接口，待查）。

## 核对记录

- 2026-11-21 学习资源链接 38 个逐个打开：36 个技能用到的全部能打开。其中 2 个地址有跳转，已换成跳转后的地址并重新打开核对（Mode SQL 教程 → thoughtspot.com；Claude 提示词文档 → platform.claude.com）。
- ✓ 2026-11-21 接口字段核对：打开了 GitLab 的 Greenhouse 接口和 Palantir 的 Lever 接口的真实返回，脚本用到的字段都在（Greenhouse：`jobs`、`id`、`title`、`absolute_url`、`location.name`、`first_published`、`updated_at`、`content`，`content` 是转义过的 HTML；Lever：顶层是数组，`text`、`hostedUrl`、`categories.location`、`createdAt` 是数字、`descriptionPlain`、`lists[].text/content`、`additionalPlain`）。这是让网页读取工具读接口后回答的，不是脚本自己跑的。

## 更新记录

- 2026-11-21 02:00 ET 左右：第一版全部代码、网站、skill、文档（Claude 写，Emma 授权不中途确认）。
