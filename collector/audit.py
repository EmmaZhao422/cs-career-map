#!/usr/bin/env python3
"""Audit the skill matching.

Fetches the job boards again and, for every skill, reports WHICH words matched
and a few short pieces of surrounding text, so a reviewer can see whether the
pattern is counting the right thing.

The output contains short excerpts of posting text. It is a working file for
reviewers: do not commit it to the main branch or publish it.

    python collector/audit.py /tmp/kwic.json
"""
from __future__ import annotations

import collections
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402

CONTEXT = 45          # characters shown on each side of a match
SAMPLES_PER_SKILL = 7
TOP_STRINGS = 10


def main(argv=None) -> int:
    out = Path((argv or sys.argv[1:] or ["kwic.json"])[0])
    roles_config = collect.load_json(collect.CONFIG / "roles.json")
    skills = collect.load_json(collect.CONFIG / "taxonomy.json")["skills"]
    companies = collect.load_json(collect.CONFIG / "companies.json")["companies"]
    classifier = collect.RoleClassifier(roles_config)
    matcher = collect.SkillMatcher(skills)
    rng = random.Random(7)

    strings = {s["id"]: collections.Counter() for s in skills}
    contexts = {s["id"]: [] for s in skills}
    postings = collections.Counter()
    titles = collections.defaultdict(list)

    for company in companies:
        fetcher = collect.FETCHERS.get(company["source"])
        try:
            jobs = fetcher(company["board"])
        except Exception:
            continue
        for job in jobs:
            role_id = classifier.classify(job["title"])
            if role_id is None:
                continue
            postings[role_id] += 1
            titles[role_id].append(job["title"])
            text = job["title"] + "\n" + job["text"]
            for skill_id, rx in matcher._compiled:
                m = rx.search(text)
                if not m:
                    continue
                strings[skill_id][m.group(0).strip().lower()] += 1
                start, end = max(0, m.start() - CONTEXT), min(len(text), m.end() + CONTEXT)
                snippet = " ".join((text[start:m.start()] + "[[" + m.group(0) + "]]" + text[m.end():end]).split())
                contexts[skill_id].append(f"{role_id[:2]}| {snippet}")
        time.sleep(0.3)

    report = {"postings": dict(postings), "skills": {}, "title_samples": {}}
    for role_id, role_titles in titles.items():
        report["title_samples"][role_id] = rng.sample(sorted(set(role_titles)), min(40, len(set(role_titles))))
    for skill in skills:
        sid = skill["id"]
        total = sum(strings[sid].values())
        if not total:
            continue
        report["skills"][sid] = {
            "matches": total,
            "strings": strings[sid].most_common(TOP_STRINGS),
            "contexts": rng.sample(contexts[sid], min(SAMPLES_PER_SKILL, len(contexts[sid]))),
        }
    collect.dump_json(out, report)
    print(f"audited {sum(postings.values())} postings, {len(report['skills'])} skills -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
