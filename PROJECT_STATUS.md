# Project status

For the maintainer and for AI coding agents picking the project up. Marks: ✓ checked, ⚠ not yet checked.

## Where things stand (21 November 2026)

- ✓ **Live.** Site: <https://emmazhao422.github.io/cs-career-map/>. Repository: <https://github.com/EmmaZhao422/cs-career-map>.
- ✓ **Real data.** The collector runs on GitHub Actions every Monday and whenever `config/` or the collector changes. First run: 21 November 2026. Current counts are on the site; `data/run_report.json` lists every board read.
- ✓ **136 company boards** confirmed by a real run (Greenhouse and Lever). Boards that could not be read were removed from `config/companies.json`.
- ✓ **Matching audited twice** on 21 November 2026 and fixed; see [AUDIT.md](AUDIT.md). The review was done by Claude from match-in-context samples. ⚠ No person has repeated it yet.
- ✓ **27 tests** pass (`python -m unittest discover -s collector`).
- ✓ **36 skills have a learning guide**; every resource link was opened on 21 November 2026.
- ✓ Site checked in a browser at desktop and phone width.

## Not done yet

- ⚠ A person should spot-check the matching: open ten postings per job from the site and compare with the skills shown.
- ⚠ Data Analyst has by far the smallest sample. Related titles such as analytics engineer are not counted.
- ⚠ The Claude skill in `skill/cs-career-coach/` has not been tried with a real student.
- ⚠ Greenhouse's own terms page for the Job Board API has not been read first-hand. Lever's README says published postings are public and may be read by third parties. We store links and skill names only.
- ⚠ No practitioner notes yet. The issue form is in place.
- ⚠ Companies with their own careers systems (several of the largest) are not covered.
- 36 of 72 skills have no learning guide.

## Next

1. Human spot-check of the matching; fix what it finds, with a test for each fix.
2. Decide which analyst titles Data Analyst should include, or add "Analytics Engineer" as its own job.
3. First practitioner notes: ask three to five people who hire for these jobs.
4. Second batch of jobs: Forward Deployed / Solutions Engineer, AI Product Manager.
5. Guides for the remaining skills.
6. More boards (other hiring systems with public job board APIs).

## Decisions

Made by Emma: the idea and audience (CS students), English, organised by job rather than by technology, data from job postings plus notes from practitioners, the first three jobs.

Made by Claude on her instruction to proceed without asking, all open to change: the name `cs-career-map`; no web framework; standard-library Python; store links and skill names but not posting text; keep a posting for 120 days after it was last seen; count the same title at one company once; tiers at 40%, 15% and 5%; MIT license; weekly refresh; practitioner notes through an issue form without names by default.

## Who wrote what

The first version (collector, tests, site, skill, guides, docs) was written by Claude. Contributions by Emma and others are listed here as they land.

## Log

- 2026-11-21: first version; repository created; first real collection; two audits and fixes; boards expanded from 40 to 136; site published.
