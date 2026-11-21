# Matching audit

The counts on the site are only as good as the rules that decide (a) which postings belong to a job and (b) which skills a posting mentions. This file records how those rules were checked and what the checks found.

## How an audit works

`collector/audit.py` reads the job boards again and, for every skill, lists which words matched and a few short pieces of surrounding text. A reviewer reads those and looks for matches that are not really about the skill. The audit file contains excerpts of posting text, so it is a working file: it is written to a side branch, read, and deleted. It is never published.

To run one: push a branch named `audit-request` (or start "Audit skill matching" from the Actions page), read `kwic.json` on the `audit-report` branch, then delete that branch.

## 21 November 2026

Two passes, reviewed by Claude (an AI model), not yet by a person. About 1,200 postings were in scope. The first pass looked at the matched words for all 72 skills and three contexts per skill; the second looked at four contexts for each of the 25 skills that looked doubtful or had been changed.

### Problems found and fixed

| Problem | Example | Fix |
| --- | --- | --- |
| Skills counted from text that a company repeats in every posting | A company intro naming "computer vision" put that skill on all of the company's postings | Lines shared by half or more of a board's postings are dropped before matching |
| A company's own name counted as a skill | "MongoDB" in MongoDB's postings, "GitLab" in GitLab's | The company's name is blanked before matching; `gitlab` is no longer a Git pattern |
| "operating system" used for a product | "an AI-powered operating system" | Only the plural, or phrases such as "operating system internals" |
| "rails" meaning payment rails | "local payment rails" | Requires "Ruby" or "Rails app / framework / ..." |
| "algorithms" in any sense | "autonomy algorithms" | Requires "data structures", "algorithm design", "CS fundamentals" and similar |
| "concurrent", "concurrently" as ordinary words | "ship features concurrently" | Requires "concurrency", "multithreading" and similar |
| "experimentation" in any sense | "experimentation campaigns" at a test range | Requires A/B tests, experiment design, experimentation platforms |
| Business benchmarking counted as model evaluation | "benchmark pricing against competitors" | Requires models or evals |
| Operations analysts counted as data analysts | "Procurement Operations Analyst" | Removed from the title rule |
| Forward-deployed and level 3+ titles counted as early-career engineering | "Software Engineer 3" | Excluded |
| Product names read as AI roles | "Controls Engineer, AI Satellites" | The AI term must describe the engineer, not follow a comma |
| IT and business systems roles counted as software engineers | "People Systems Engineer" | "Systems engineer" removed from the title rule |
| One job listed in many cities counted many times | 13 listings of one title | The same title at one company counts once |

Every fix has a test in `collector/test_collect.py`.

### Known and accepted

- **Broad skills stay broad.** "APIs" matches any mention of an API, "AI agents" includes "agentic" tooling, and "Working with non-engineers" matches "cross-functional" or "stakeholders". These read high because postings use the words loosely.
- **Some repeated company text survives** when a company words its intro differently across postings.
- **A requirement template reused across one company's postings** counts once per distinct title. That is intended: each of those jobs does ask for it.
- **Keyword matching cannot tell required from nice-to-have.**
- **The sample leans toward venture-backed technology companies**, because those are the companies that publish through Greenhouse and Lever.

### Still to do

- A person should repeat the spot-check: open ten postings per job from the site and compare.
- Data Analyst has a small sample. Related titles (analytics engineer, data scientist in analytics teams) are not counted and may deserve their own job.
