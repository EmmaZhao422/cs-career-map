# 项目状态｜CS Career Map

给 Emma 和之后接手的 AI 看。完整的决定记录在 Notion「CS 职业学习地图｜项目说明与日志」。
标记：✓ = 核对过；⚠ = 没核对或没跑过。时间是美东时间（ET）。

## 现在到哪了（2026-11-21 约 02:50 ET）

- ✓ 仓库：<https://github.com/EmmaZhao422/cs-career-map>（private）。代码已推上去。
- ✓ **数据是真的了**。第一次真实采集在 GitHub Actions 上跑成功：40 家公司读到了，3 家地址不对（grammarly、plaid、mistral，已从名单里去掉）。
- ✓ 去重和清理之后的样本：

  | 岗位 | 职位数 | 公司数 | 其中实习/应届 |
  | --- | --- | --- | --- |
  | Software Engineer | 363 | 34 | 62 |
  | AI Engineer | 129 | 28 | 18 |
  | Data Analyst | 9 | 6 | 2 |

- ⚠ **技能匹配还没有人工抽查过**。数字是脚本数出来的，没人点开招聘原文对过。所以网站顶部挂着 "Draft" 提示条，README 也写了。抽查完把 `config/site.json` 里的 `notice` 清空，提示条就消失。
- ⚠ **网站还没公开上线**（Pages 没开）。原因：没抽查过的数字不该用你的名字公开。预览在 Claude 对话里（只有你能看）。
- ⚠ Data Analyst 只有 9 个职位，样本太小，页面上有 "small sample" 提示。原因见下面「已知问题」。

## 第一次真实数据暴露的问题，已修（都加了测试）

1. Data Analyst 混进了一堆 "Operations Analyst"（采购、账单、法务运营），不是数据分析岗。已把 operations 从标题规则里去掉。
2. "Forward Deployed Engineer" 被算进了 Software Engineer / AI Engineer（Palantir 一家就 59 条）。它是第二批要单独做的岗位，现在先排除。
3. "Software Engineer 3" 这种数字级别没被当成资深岗排除。已排除 3 级及以上。
4. 同一个职位在多个城市各挂一条，被重复计数（MongoDB 一个职位算了 13 次）。现在同公司同标题只算一次。
5. "Model evaluation" 会把商业上的 benchmarking 也算进去。规则已收紧。⚠ 这一条要等下一次采集才生效（旧记录没存原文，没法重算）。

## 已知问题

- Data Analyst 样本小：这 40 家公司的分析岗常用别的标题（Data Scientist, Analytics / Analytics Engineer / BI Engineer 等），现在的规则没收。要不要收、收哪些，需要人判断。
- 几个靠关键词容易数多的技能，重点抽查：`Go`、`APIs (REST)`、`Working with non-engineers`（只要出现 cross-functional 或 stakeholder 就算）、`AI agents`、`R`、`C`。
- 只覆盖用 Greenhouse / Lever 的公司，没有 Google、Meta、Amazon、Microsoft、Apple。
- Anthropic 占 AI Engineer 样本的 30%（129 里 39 个），会拉偏结果。
- ⚠ 3 个 GitHub 流程里只有「Refresh job posting data」实际跑过并成功。「Publish website」因为 Pages 没开，还没成功跑过。
- ⚠ skill 没在 Claude 里实际调用测试过。
- ⚠ Greenhouse、Lever 接口的官方使用条款原文还没读。公开前要读。

## 下一步

### Emma 亲手做（你说了不想要纯 AI 代码）

1. **抽查。** 每个岗位在网站上随机点开 10 条招聘，对照页面上匹配到的技能，记下数错的。
2. **修一条规则。** 挑一个数错的技能，改 `config/taxonomy.json` 里它的规则，在 `collector/test_collect.py` 里加一条测试，跑 `python -m unittest discover -s collector`。
3. **决定 Data Analyst 收哪些标题**，改 `config/roles.json`，加测试标题。
4. 抽查满意后：清空 `config/site.json` 的 `notice`，去掉 README 顶部的 pre-launch 提示。

### 然后上线

5. 仓库 Settings → Pages → Source 选 "GitHub Actions"，再到 Actions 页手动跑 "Publish website"。
6. 读 Greenhouse、Lever 使用条款；在 Claude 里调用一次 skill。
7. 把仓库改成 public。找 3–5 位从业者要第一批补充。
8. 第二批岗位：Forward Deployed / Solutions Engineer、AI Product Manager。

## 在本地用 VS Code

在 VS Code 里 clone `https://github.com/EmmaZhao422/cs-career-map`。之后改完在 VS Code 里提交、推送。
`~/Desktop/Emma/cs-career-map` 是第一晚的旧拷贝（演示数据、缺 `.github/`），**已过时**，以 clone 下来的为准。

## 谁写的

- Claude 写的：到 2026-11-21 02:50 ET 为止的全部代码、网站、skill、文档、学习指南内容。
- Emma 定的：做什么、英文、按职业方向、数据来自招聘信息 + 从业者补充、第一版 3 个岗位。
- Emma 写的：（还没有。上面「Emma 亲手做」做完后记在这里）

## Claude 替你定的（你说了不要问，都可以改）

- 项目名和仓库名 `cs-career-map`，网站标题 "CS Career Map"
- 网站不用框架；采集脚本只用 Python 标准库
- 不存招聘原文，只存链接和匹配到的技能名
- 一条招聘在最后一次看到之后保留 120 天；同公司同标题只算一次
- 频率分档：40% 以上 / 15–40% / 5–15% / 5% 以下
- 许可证 MIT；每周一自动采集；从业者补充走 GitHub Issue 表单，默认不显示姓名和公司
- 仓库先 private；没抽查前不开 Pages

## 核对记录

- ✓ 2026-11-21 学习资源链接逐个打开核对：36 个技能用到的全部能打开。2 个地址有跳转，已换成跳转后的地址并重新核对。
- ✓ 2026-11-21 接口字段：打开了 GitLab（Greenhouse）和 Palantir（Lever）接口的真实返回，脚本用到的字段都在。
- ✓ 2026-11-21 第一次真实采集在 GitHub Actions 上跑通，40/43 个公司地址有效。
- ✓ 2026-11-21 测试 22 个全部通过；网站在电脑和手机宽度下用浏览器点过，没报错。
- ⚠ 想用网页读取工具抽查 5 条招聘原文，需要 Emma 批准访问这些链接，当时没人批，没做成。

## 更新记录

- 2026-11-21 约 02:00 ET：第一版全部代码、网站、skill、文档（Claude）。
- 2026-11-21 约 02:20 ET：Emma 连了 GitHub、装了 Claude GitHub App。Claude 在 Emma 的 Chrome 里建了仓库并推送。
- 2026-11-21 约 02:50 ET：第一次真实采集；按真实数据修了 5 个问题；加了 Draft 提示条（Claude）。
