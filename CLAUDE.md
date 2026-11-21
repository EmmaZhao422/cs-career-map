# CS Career Map: instructions for AI coding agents

Read `PROJECT_STATUS.md` first. It says what is done, what is blocked, and what to do next.

## What this project is

An open-source, English-language career map for CS students. For each job it shows how many real job postings mention each skill, a short learning guide per skill, and notes from people who hire. It ships as a static website (`docs/`) and a Claude skill (`skill/cs-career-coach/`), both reading the same data.

Owner: Emma Zhao (GitHub `EmmaZhao422`). Decisions and their history are recorded in her Notion page "CS 职业学习地图｜项目说明与日志" and summarised in `PROJECT_STATUS.md`.

## Rules that do not bend

- **Never invent a number, a company, a link or a quote.** Counts come only from `collector/collect.py`. Demo rows must stay labeled as demo (`key` starts with `demo:`), which makes the site show its banner.
- **Never add a link you have not opened.** Each resource in `data/skill_guides.json` carries the date it was checked.
- **Keep measurements and opinions apart** in the data and on the page: counts versus guides, prerequisites and practitioner notes.
- **Do not store posting text.** Only the link and matched skill ids.
- **Read job boards only through their public job board APIs** (Greenhouse, Lever). Do not scrape LinkedIn, Indeed or sites that forbid automated access.
- The site is in English. Talk to Emma in Chinese, briefly.

## How to work here

- Python standard library only in `collector/`. No build step in `docs/`.
- Run `python -m unittest discover -s collector` before every commit. Add a test when you change a pattern or a rule.
- After changing anything in `config/` or `data/`, run `python collector/collect.py build` so `docs/data/` and the skill's data stay in step.
- Check the site in a browser at desktop and phone width after a UI change.
- When you finish a piece of work, update `PROJECT_STATUS.md` (and the Notion page if you can reach it): what changed, what was verified and how, what is still unverified.

## Commands

```bash
python -m unittest discover -s collector      # tests
python collector/collect.py collect           # read job boards (needs network), rebuild data
python collector/collect.py build             # rebuild docs/data from stored postings
python collector/demo_data.py                 # regenerate labeled demo data
python -m http.server 8000 --directory docs   # preview the site
```
