# Contributing

Thanks for helping. Three rules hold everywhere in this project:

1. **No invented numbers.** Counts come only from the collector.
2. **No unchecked links.** Open a link yourself before adding it, and write the date you checked it.
3. **Keep measurements and opinions apart.** Counts are measurements. Guides, "learn first" links and practitioner notes are opinions and are labeled as such.

## Add a practitioner note

If you hire, interview or work in one of these jobs, open the [practitioner note form](../../issues/new?template=practitioner-note.yml). A maintainer adds accepted notes to `data/practitioner_notes.json` in this shape:

```json
{
  "role": "data-analyst",
  "skill": "sql",
  "note": "We test window functions in the first interview. Tableau we teach on the job.",
  "who": "Analytics manager, consumer fintech",
  "added": "2026-12-01"
}
```

`who` describes your role and kind of company. Your name and employer are left out unless you ask for them to be shown.

There is a second kind of note: a summary of something a company has published about how it hires. Those carry `"kind": "published"`, the page title in `who`, and the link in `source`. Summarise in your own words, keep it to what the page says, and open the link before adding it. Never write a note in someone's voice that they did not send.

## Suggest a learning resource

Guides live in `data/skill_guides.json`. Each skill has at most two resources. A guide may ship with no resources (an empty `resources` list) until someone opens a link, checks it and adds it with the date. Until then the site and the coach say that the map has no checked resource for that skill. To add or replace one, open the [resource form](../../issues/new?template=suggest-resource.yml) or a pull request. A resource should be free or have a free path, teach by doing, and be something you have used yourself.

## Add a company

Edit `config/companies.json`. You need the hiring system and the company's board token:

- Greenhouse: the careers page is `https://boards.greenhouse.io/<token>` (or `job-boards.greenhouse.io/<token>`).
- Lever: the careers page is `https://jobs.lever.co/<token>`.

Set `"checked"` to today's date if you confirmed the page loads. Companies that use another system cannot be read yet.

## Fix a skill pattern

Patterns are in `config/taxonomy.json`. If a skill is over- or under-counted, change the pattern and add a test case to `collector/test_collect.py` showing the text that was wrong. Run:

```bash
python -m unittest discover -s collector
```

## Add a job

Add an entry to `config/roles.json` with title patterns, add test titles to `collector/test_collect.py`, and run the collector. Order matters: a posting goes to the first job whose pattern matches its title.
