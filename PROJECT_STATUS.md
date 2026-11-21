# Project status

For the maintainer and for AI coding agents picking the project up. Marks: ✓ checked, ⚠ not yet checked.

## Where things stand (21 November 2026)

- ✓ **Live.** Site: <https://emmazhao422.github.io/cs-career-map/>. Repository: <https://github.com/EmmaZhao422/cs-career-map>.
- ✓ **Real data.** The collector runs on GitHub Actions every Monday and whenever `config/` or the collector changes. First run: 21 November 2026. Current counts are on the site; `data/run_report.json` lists every board read.
- ✓ **136 company boards** confirmed by a real run (Greenhouse and Lever). Boards that could not be read were removed from `config/companies.json`.
- ✓ **Matching audited twice** on 21 November 2026 and fixed; see [AUDIT.md](AUDIT.md). The review was done by Claude from match-in-context samples. ⚠ No person has repeated it yet.
- ✓ **29 tests** pass (`python -m unittest discover -s collector`), including one that fails if any skill lacks a guide.
- ✓ **All 72 skills have a learning guide.** Every resource link was opened on 21 November 2026. Official documentation and university courses come first; a few community courses and one YouTube lecture series are included where they are the standard reference.
- ✓ **Nine notes from the hiring side**, each a summary of a public page by GitLab, Stripe or Anthropic, with its link. They are labeled as summaries of public pages. No note is written in a person's voice.
- ✓ **Job board terms read.** Greenhouse's Job Board API documentation says the data is public and GET requests need no authentication, and states no restriction on reading it. Lever's Postings API README says published postings are public and may be read by third parties.
- ✓ **Coach skill dry-run** on the real data for three sample students (data analyst intern, AI engineer, software engineer new grad). It found one gap, now fixed: prerequisites that postings rarely name.
- ✓ Site checked in a browser at desktop and phone width.

## Not done yet

- ⚠ A person should spot-check the matching: open ten postings per job from the site and compare with the skills shown.
- ⚠ Data Analyst has by far the smallest sample. Related titles such as analytics engineer are not counted.
- ⚠ The coach skill has not been used by a real student, and has not been loaded through the Claude app's skill system. The dry run above was Claude following `SKILL.md` step by step.
- ⚠ No notes sent in by practitioners yet. The issue form is in place; only real people can fill it.
- ⚠ The hiring-side notes cover three companies. Two of the Stripe pages are several years old and say so.
- ⚠ Companies with their own careers systems (several of the largest) are not covered.

## Next

1. Human spot-check of the matching; fix what it finds, with a test for each fix.
2. Decide which analyst titles Data Analyst should include, or add "Analytics Engineer" as its own job.
3. First notes from real practitioners: ask three to five people who hire for these jobs.
4. Second batch of jobs: Forward Deployed / Solutions Engineer, AI Product Manager.
5. More boards (other hiring systems with public job board APIs).

## Decisions

Made by Emma: the idea and audience (CS students), English, organised by job rather than by technology, data from job postings plus notes from practitioners, the first three jobs.

Made by Claude on her instruction to proceed without asking, all open to change: the name `cs-career-map`; no web framework; standard-library Python; store links and skill names but not posting text; keep a posting for 120 days after it was last seen; count the same title at one company once; count each company once and band skills at 60%, 30% and 10% of companies; MIT license; weekly refresh; practitioner notes through an issue form without names by default.

## Who wrote what

The first version (collector, tests, site, skill, guides, docs) was written by Claude. Contributions by Emma and others are listed here as they land.

## Log

- 2026-11-21: first version; repository created; first real collection; two audits and fixes; boards expanded from 40 to 136; site published.
- 2026-11-21 (later): guides for all 72 skills; nine hiring-side notes from public pages; job board terms read; coach skill dry-run and fix.
