# Project status

For the maintainer and for AI coding agents picking the project up. Marks: ✓ checked, ⚠ not yet checked.

## Where things stand (21 November 2026)

- ✓ **Live.** Site: <https://emmazhao422.github.io/cs-career-map/>. Repository: <https://github.com/EmmaZhao422/cs-career-map>.
- ✓ **Real data from 136 company job boards** (Greenhouse and Lever), collected on GitHub Actions every Monday and whenever the rules change. All 136 boards were read in the latest run. Current counts are on the site.
- ✓ **Each company counts once.** The headline number for a skill is the share of companies that mention it; the share of postings is one switch away. A few employers post far more than others, and this keeps them from deciding the result.
- ✓ **84 skills, each with a guide and at least one checked link.** Every link was opened on 21 November 2026.
- ✓ **Nine notes from company hiring pages** (GitLab, Stripe, Anthropic), each a summary with its link.
- ✓ **Four review passes on 21 November 2026**, recorded in [AUDIT.md](AUDIT.md): two audits of the matched text by Claude, then an independent review by two other AI models of the method and of the site, then a second audit of all 84 skills under the new rules. The fixes are tested: `python3 -m unittest discover -s collector`.
- ✓ **Job board terms read.** Greenhouse's Job Board API documentation says the data is public and GET requests need no authentication. Lever's README says published postings are public and may be read by third parties. We keep links and skill names, not posting text.
- ✓ **Site checked in a browser** at desktop and phone width after every round: scripted walkthroughs, numbers on screen compared with the raw data, keyboard use, tap targets.

## Not done yet

- ⚠ **No person has spot-checked the matching.** Every review so far was done by AI models. Open ten postings per job from the site and compare.
- ⚠ **Data Analyst is a small sample** and the site says so. Analyst titles at these companies are few once operations, finance and business-analyst roles are left out.
- ⚠ **Intern and new-grad numbers are thin** for AI Engineer and Data Analyst. The site shows the raw fraction and a warning.
- ⚠ **No notes sent in by practitioners.** The issue form is in place; only real people can fill it.
- ⚠ **The coach skill** has been dry-run by Claude on the real data, not used by a student.
- ⚠ **Coverage.** Companies with their own careers systems, including several of the largest, are not read. The sample leans toward venture-backed technology companies.
- Broad skills ("Working with non-engineers", "AI agents") are loose keyword matches. The site shows the people skills in their own section.

## Next

1. Human spot-check of the matching; a test for each fix.
2. More analyst postings: add boards from industries that hire analysts, or add "Analytics Engineer" as its own job.
3. First notes from real practitioners.
4. Second batch of jobs: Forward Deployed / Solutions Engineer, AI Product Manager.
5. Other hiring systems with public job board APIs.

## Decisions

Made by Emma: the idea and audience (CS students), English, organised by job rather than by technology, data from job postings plus notes from the hiring side, the first three jobs, go live, fill every skill with a guide.

Made by Claude on her instruction to proceed without asking, all open to change: the name `cs-career-map`; no web framework; standard-library Python; keep links and skill names but not posting text; keep a posting for 120 days after it was last seen; count the same title at one company once; count each company once and band skills at 60%, 30% and 10% of companies; an editorial "Start here" order per job in `config/roles.json`; leave embedded, contract, research-only, operations and finance titles out; MIT license; weekly refresh; practitioner notes through an issue form without names by default.

## Who wrote what

The first version and the review fixes (collector, tests, site, skill, guides, docs) were written by Claude and by other AI models working under Claude's direction, to Emma's brief. Contributions by Emma and others are listed here as they land.

## Log

- 2026-11-21: first version; repository created; first real collection; two audits and fixes; boards expanded from 40 to 136; site published.
- 2026-11-21 (later): guides for every skill; nine hiring-side notes from public pages; job board terms read; coach skill dry-run.
- 2026-11-21 (later still): independent review in three rounds. Company-first counting, 12 new skills, title and pattern fixes, safer collector, reworked site with "Start here", deep links and share preview.
