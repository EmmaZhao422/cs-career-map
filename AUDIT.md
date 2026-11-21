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
| Skills counted from text that a company repeats in every posting | A company intro naming "computer vision" put that skill on all of the company's postings | Lines shared by half or more of a board's distinct job titles are dropped before matching |
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

## 21 November 2026, third pass (independent review)

An independent review of the code, the rules and the stored data, done by Claude (an AI model) on the reviewer's findings. Not yet checked by a person. Every change has a test in `collector/test_collect.py`.

### What changed

**What the numbers mean.** A skill's headline share is now the share of a job's companies that mention it (`company_pct`), and its tier (60%, 30%, 10%) is set from that share. The share of postings (`pct`) is still published. Each job also shows how many companies have intern or new-grad postings (`entry_companies`) and how much of the sample its largest company makes up (`top_company`, `top_company_share`). The job list's headline skills leave out the "Working with people" skills.

**Which postings count as one job.** Before comparing titles at one company, trailing places ("- London", "- Austin, TX"), places in parentheses ("(Remote)"; "(Summer 2027 - Toronto)" keeps the season) and "(m/w/d)"-style markers are removed. Team names after a comma stay distinct. A job listed several times keeps every skill any listing mentions and the newest date.

**Which titles count.**

- Newly matched: "Software Engineering Intern", "Software Development Engineer", "Engineer, Backend/Frontend", "Data Analytics Intern".
- Staff, lead, head, manager and architect drop a title only when they come before the role noun or straight after it, so "Software Engineer, Staff Tools" counts and "Staff Software Engineer" and "Engineering Manager" do not.
- Excluded from every job: contract and contractor titles ("Contract Student Worker", "(Contract)").
- Excluded from Software Engineer, because they are different jobs with different skills: embedded, firmware, flight software (except full-stack and application-software roles on flight-software teams), avionics, FPGA, RF, antenna and battery roles, Salesforce developers, demo engineers, marketing-site and value engineers, and SDET (test roles were already excluded).
- AI Engineer: a research engineer, research scientist or applied scientist title now needs an AI or ML term (for example ML, RL, alignment, pre-training). Security and red-team, growth, people-analytics, customer-success and GPU-programming systems-research titles are excluded.
- Entry level now includes "Engineer I", "Engineer 1", "Engineer-1" and "Grad"; "II" and "2" are not entry. PhD and Master's postings still count in the totals but not in the intern and new-grad counts.

Applied to the stored postings (no new collection was possible for this pass), the title rules change the sample as follows:

| Job | Listings before → after | Distinct jobs before → after | Companies before → after | Intern / new-grad jobs before → after |
| --- | --- | --- | --- | --- |
| Software Engineer | 961 → 916 | 754 → 704 | 85 → 83 | 84 → 83 |
| AI Engineer | 218 → 192 | 190 → 162 | 55 → 50 | 23 → 9 |
| Data Analyst | 38 → 37 | 32 → 30 | 18 → 17 | 7 → 6 |

Software Engineer lost 48 listings to the new exclusions and gained 3 that moved from AI Engineer (AI-security titles). AI Engineer lost 23 listings that now belong to no job, most of them research and applied-scientist titles without an AI term. Data Analyst lost one contract listing. Most of AI Engineer's drop in intern and new-grad jobs is the PhD and Master's rule (12 of its distinct entry-level jobs are PhD or Master's). The new title patterns can only add postings at the next collection, because stored postings are the ones that matched the old rules. A stored posting whose title now belongs to another job moves to that job instead of being deleted.

**Which skills a posting has** (applies from the next collection; see below).

- Skills are matched on the posting body only, not the title. A title such as "Software Engineer, Data Model" names a team.
- False positives fixed: "rag" as a word (now RAG or retrieval-augmented), GitHub Copilot as Git, "Go to market" as Go, "Intel(R)" as R, "Spark joy" and "Swift decisions" at the start of a sentence, "jax" in other words, "transformers" as electrical equipment, "tool use" outside LLM context, shipping "containers" as Docker, "UNIX time" as Linux.
- APIs (REST) now needs REST, RESTful, API design or development, building APIs, web or HTTP APIs. A bare "API" no longer counts.
- Dashboards & reporting no longer counts "monitoring dashboards", "Grafana dashboards", "Datadog dashboards" or "observability dashboards"; those belong to the new Observability skill. Done with a fixed list of preceding words, so other operations dashboards may still count.
- False negatives fixed: Go in "we use Go", "Go-based", "such as Go and Rust"; C in "C, Java", "Embedded C", "written in C."; hyphenated "machine-learning", "deep-learning", "infrastructure-as-code", "natural-language processing"; "ML Ops" and "LLMOps"; "function calling", "tool calling" and "tool-use" as AI agents; "A/B-tests".
- Looker includes Looker Studio, which is a separate free product; the skill carries a note saying so.
- Twelve new skills: Python web frameworks (Django, Flask, FastAPI), Spring (Java), Angular / Vue, gRPC & Protocol Buffers, Observability & monitoring, Jupyter notebooks, Elasticsearch / OpenSearch, Product analytics tools, SAS / SPSS / Stata, Reinforcement learning, GPU programming (CUDA), Agile & Scrum. Each has a level sentence and a project; none had a resource at this pass, because no link had been opened and checked for them. Checked resources were added later the same day.

**Cleaning.**

- Only the board's own display name is blanked, in its own casing, so the word "notion" survives in Notion's postings. Names that are everyday words (Block, Box, Toast, Lattice and a few others) are not blanked at all.
- Repeated-text removal counts a line once per distinct job title, so one job listed in six cities no longer turns its own requirements into "boilerplate". Lines are compared without punctuation. Lines of 20 to 39 characters count as boilerplate only when they appear in at least 60% of a board's distinct titles and in at least 8 of them.

**Robustness.**

- A board that answers with the wrong shape is reported as `bad_payload`, not as read with no jobs. Requests are retried once after 2 seconds on HTTP 429, a 5xx answer or a timeout.
- A collection that reads fewer than 60% of the boards the previous run read is rejected: nothing is written and the command fails.
- `prune-companies` refuses to run when fewer than 60% of the boards were read, and drops a board only after it was not found in two runs in a row (`misses` in `config/companies.json`).
- Data files are written to a temporary file and renamed into place.
- Each posting now records the version of the rules that matched it (`rules`, a hash of `config/roles.json`, `config/taxonomy.json` and the cleaning code version). A closed posting matched under other rules is dropped at the next collection, because without its text its skills cannot be recomputed.

### Knowingly left open

- **The skill changes above do not show in the current numbers.** Stored postings keep no text, so their skills were matched with the old patterns, on title and body. The site's skill shares will change when the next collection reads the boards again. At that collection, every stored posting that is no longer open is dropped, because it has no `rules` version.
- **Tiers read high.** With the 40/15/5 cutoffs then in use applied to company shares, Software Engineer had 23 skills in the top tier (it had 1 when tiers used posting shares). The cutoffs were later raised to 60%, 30% and 10% of companies, the values the site uses now.
- Spark and Swift still count when a capitalised word is used mid-sentence in its ordinary sense ("make Swift progress"). Agile counts the capitalised word anywhere.
- The place list used to merge titles is a fixed list of cities and countries. Places not on it keep titles apart, and regional words such as "LatAm" or "EMEA" are treated as team names.
- An advanced-degree posting is one whose title names a PhD or a Master's and not a bachelor's degree; "BS/MS/PhD" internships still count as entry level.
- The excluded Software Engineer families (embedded, flight software and the rest) are real software jobs. They may deserve a job of their own.

## 21 November 2026, fourth pass (second audit under the new rules)

About 1,200 postings (1,224: 203 AI Engineer, 984 Software Engineer, 37 Data Analyst) were read again under the rules of the third pass. An independent reviewer (Claude, an AI model; not yet a person) read the matched words and up to seven contexts for all 84 skills, and 109 sampled titles (40, 40 and 29 per job). Every change has a test in `collector/test_collect.py`.

### Problems found and fixed

| Problem | Example (own words) | Fix |
| --- | --- | --- |
| GPU skill counted from any GPU and training or inference in one sentence | A large GPU fleet for model training | Only CUDA, Triton, GPU programming, kernels, architecture or optimisation |
| SAS counted as the storage interface | "PCIe, SAS and I2C links" | SAS must sit beside R, Python, SQL, SPSS, Stata or words like macros, Viya |
| "embedding" as a verb counted as RAG | "embedding them into daily practice" | "embeddings", or "embedding" with models, vectors, layers, search, pipelines or stores |
| Any "scalable systems" counted as system design | "building high-quality, scalable systems" | Needs design, architect or build before it |
| GitHub Actions counted as Git | "CI runs on GitHub Actions" | Excluded after "github" (Copilot already was) |
| Agile, the parts-list tool, counted as the method | "tools such as Agile, with revisions" | Not after "such as", "like", "in"; not before PLM or BOM |
| "fine-tuning performance" counted as model fine-tuning | "fine-tuning performance for low latency" | Not before performance, latency or the system |
| "spreadsheets" in a product description counted as Excel | "charts, spreadsheets and other surfaces" | Needs modeling, skills, tools or software after it |
| Using UNIX-like systems counted as OS knowledge | "UNIX-like operating systems and Terraform" | Not after "UNIX-like" or "Linux" |
| A job title echoed in the text counted as dashboards | "As a Business Intelligence Analyst you will" | Not before analyst, engineer, developer or specialist; "observability stack — dashboards" excluded |
| French "Vue" counted as Vue.js | "Vue d'ensemble du projet" | Not before "d'" or "de" |
| Operations, master data, customer success and finance analysts counted as Data Analyst | "Delivery Operations Business Analyst" | Added to the Data Analyst exclusions |
| Mid-level and "(L3)" and above counted as early career | "Business Analyst (Mid-level)", "ML Engineer (L3)" | Added to the seniority rule |
| Consulting and internal enablement counted as AI Engineer | "Technology Consultant", "AI Enablement Engineer" | Added to the AI Engineer exclusions |
| Ambiguous systems titles counted as AI Engineer | "AI Systems Engineer" | Dropped unless the title also says software, ML or machine learning |

Effect on stored postings after `collect.py build`: AI Engineer 203 to 193 (10 dropped, one of them moved to Software Engineer), Data Analyst 37 to 28 (9 dropped), Software Engineer 984 to 984 (one added, one dropped). Skill patterns change only when postings are read again (see the third pass).

### Known and accepted

- **Cross-functional** still counts a bare "stakeholders". About three of seven sampled contexts were weak.
- **A/B testing** counts "experimentation platforms" in a machine learning training sense (one of seven sampled).
- **Object-oriented** counts "design patterns" in a security sense (one of seven sampled).
- **Aerospace software titles** ("Mission", "Orbital", "Collision Avoidance") stay in Software Engineer; they are software jobs.
