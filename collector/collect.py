#!/usr/bin/env python3
"""CS Career Map collector.

Reads public job boards (Greenhouse, Lever), keeps the postings whose title
matches one of our roles, records which skills each posting mentions, and
writes the numbers the website shows.

Standard library only, so it runs anywhere Python 3.9+ runs.

    python collector/collect.py collect   # fetch boards, then build site data
    python collector/collect.py build     # rebuild site data from stored postings

We store a link and the list of skills for each posting. We do not store the
posting text.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
SITE_DATA = ROOT / "docs" / "data"
SKILL_DATA = ROOT / "skill" / "cs-career-coach" / "data"

USER_AGENT = "cs-career-map-collector (+https://github.com/EmmaZhao422/cs-career-map)"
RETENTION_DAYS = 120  # a posting stays in the sample this long after we last saw it
REQUEST_PAUSE = 0.5  # seconds between boards
TIERS = [("most", 40.0), ("many", 15.0), ("some", 5.0)]  # share of postings, in percent


# ---------------------------------------------------------------- files

def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- text

_BLOCK_END = re.compile(r"(?i)<(?:br|/p|/li|/div|/h[1-6]|/tr)[^>]*>")
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[ \t ]+")


def html_to_text(raw: str | None) -> str:
    """Turn (possibly entity-escaped) HTML into plain text."""
    text = html.unescape(raw or "")
    text = _BLOCK_END.sub("\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    return _SPACE.sub(" ", text).strip()


# ---------------------------------------------------------------- skills

class SkillMatcher:
    """Finds which taxonomy skills a piece of text mentions."""

    def __init__(self, skills: list[dict]):
        self.skills = skills
        self._compiled = []
        for skill in skills:
            parts = "|".join(f"(?:{p})" for p in skill["patterns"])
            if skill.get("raw"):
                rx = re.compile(parts)
            else:
                rx = re.compile(r"(?<![A-Za-z0-9])(?:" + parts + r")(?![A-Za-z0-9])", re.IGNORECASE)
            self._compiled.append((skill["id"], rx))

    def match(self, text: str) -> list[str]:
        return [skill_id for skill_id, rx in self._compiled if rx.search(text)]


# ---------------------------------------------------------------- roles

class RoleClassifier:
    """Assigns a job title to one of our roles, or to none."""

    def __init__(self, config: dict):
        self._senior = re.compile(config["seniority_exclude"])
        self._entry = re.compile(config["entry_level"])
        self.roles = config["roles"]
        self._rules = [
            (
                role["id"],
                [re.compile(p) for p in role["include"]],
                [re.compile(p) for p in role.get("exclude", [])],
            )
            for role in self.roles
        ]

    def classify(self, title: str) -> str | None:
        t = title.lower()
        if self._senior.search(t):
            return None
        for role_id, include, exclude in self._rules:
            if any(rx.search(t) for rx in exclude):
                continue
            if any(rx.search(t) for rx in include):
                return role_id
        return None

    def level(self, title: str) -> str:
        return "entry" if self._entry.search(title.lower()) else "open"


# ---------------------------------------------------------------- job boards

def http_json(url: str, timeout: int = 30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_greenhouse(board: str) -> list[dict]:
    payload = http_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    jobs = []
    for job in payload.get("jobs", []):
        jobs.append({
            "key": f"greenhouse:{board}:{job.get('id')}",
            "title": job.get("title") or "",
            "url": job.get("absolute_url"),
            "location": (job.get("location") or {}).get("name"),
            "posted_at": job.get("first_published") or job.get("updated_at"),
            "text": html_to_text(job.get("content")),
        })
    return jobs


def fetch_lever(site: str) -> list[dict]:
    payload = http_json(f"https://api.lever.co/v0/postings/{site}?mode=json")
    jobs = []
    for job in payload if isinstance(payload, list) else []:
        parts = [job.get("descriptionPlain") or html_to_text(job.get("description"))]
        for block in job.get("lists") or []:
            parts.append(block.get("text") or "")
            parts.append(html_to_text(block.get("content")))
        parts.append(job.get("additionalPlain") or html_to_text(job.get("additional")))
        created = job.get("createdAt")
        posted = None
        if isinstance(created, (int, float)):
            posted = datetime.fromtimestamp(created / 1000, timezone.utc).replace(microsecond=0).isoformat()
        jobs.append({
            "key": f"lever:{site}:{job.get('id')}",
            "title": job.get("text") or "",
            "url": job.get("hostedUrl"),
            "location": (job.get("categories") or {}).get("location"),
            "posted_at": posted,
            "text": "\n".join(p for p in parts if p),
        })
    return jobs


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever}


# ---------------------------------------------------------------- collect

def collect(companies: list[dict], classifier: RoleClassifier, matcher: SkillMatcher, today: str,
            pause: float = REQUEST_PAUSE) -> tuple[dict[str, list[dict]], list[dict]]:
    """Fetch every board. Returns ({role_id: [posting records]}, per-board report)."""
    found: dict[str, list[dict]] = {role["id"]: [] for role in classifier.roles}
    report = []
    for company in companies:
        entry = {"name": company["name"], "source": company["source"], "board": company["board"]}
        fetcher = FETCHERS.get(company["source"])
        if fetcher is None:
            entry.update(status="unknown_source")
            report.append(entry)
            continue
        try:
            jobs = fetcher(company["board"])
        except urllib.error.HTTPError as err:
            entry.update(status="not_found" if err.code == 404 else f"http_{err.code}")
            report.append(entry)
            continue
        except Exception as err:  # network trouble, bad JSON: note it and move on
            entry.update(status="error", detail=f"{type(err).__name__}: {err}"[:200])
            report.append(entry)
            continue
        kept = 0
        for job in jobs:
            role_id = classifier.classify(job["title"])
            if role_id is None or not job.get("url"):
                continue
            found[role_id].append({
                "key": job["key"],
                "company": company["name"],
                "title": job["title"].strip(),
                "url": job["url"],
                "location": job.get("location"),
                "level": classifier.level(job["title"]),
                "posted_at": job.get("posted_at"),
                "first_seen": today,
                "last_seen": today,
                "skills": matcher.match(job["title"] + "\n" + job["text"]),
            })
            kept += 1
        entry.update(status="ok", jobs=len(jobs), kept=kept)
        report.append(entry)
        if pause:
            time.sleep(pause)
    return found, report


def merge(old: list[dict], new: list[dict], today: str, retention_days: int = RETENTION_DAYS) -> list[dict]:
    """Add today's postings to the stored ones. Keeps closed postings for a while
    so the sample grows; drops demo rows as soon as real ones arrive."""
    cutoff = (datetime.fromisoformat(today) - timedelta(days=retention_days)).date().isoformat()
    by_key = {p["key"]: p for p in old if not p["key"].startswith("demo:")}
    for posting in new:
        previous = by_key.get(posting["key"])
        if previous:
            posting["first_seen"] = previous["first_seen"]
        by_key[posting["key"]] = posting
    kept = [p for p in by_key.values() if p["last_seen"] >= cutoff]
    kept.sort(key=lambda p: (p["company"].lower(), p["title"].lower(), p["key"]))
    return kept


# ---------------------------------------------------------------- aggregate

def tier_for(pct: float) -> str:
    for name, floor in TIERS:
        if pct >= floor:
            return name
    return "rare"


def aggregate(role: dict, postings: list[dict], skills: list[dict]) -> dict:
    total = len(postings)
    companies: dict[str, int] = {}
    for p in postings:
        companies[p["company"]] = companies.get(p["company"], 0) + 1
    entry_total = sum(1 for p in postings if p["level"] == "entry")

    rows = []
    for skill in skills:
        hits = [p for p in postings if skill["id"] in p["skills"]]
        if not hits:
            continue
        pct = round(100 * len(hits) / total, 1) if total else 0.0
        rows.append({
            "id": skill["id"],
            "name": skill["name"],
            "category": skill["category"],
            "count": len(hits),
            "pct": pct,
            "tier": tier_for(pct),
            "companies": len({p["company"] for p in hits}),
            "entry_count": sum(1 for p in hits if p["level"] == "entry"),
        })
    rows.sort(key=lambda r: (-r["count"], r["name"].lower()))

    seen = [p["last_seen"] for p in postings]
    return {
        "id": role["id"],
        "title": role["title"],
        "blurb": role["blurb"],
        "demo": any(p["key"].startswith("demo:") for p in postings),
        "postings": total,
        "companies": len(companies),
        "entry_postings": entry_total,
        "last_seen_from": min(seen) if seen else None,
        "last_seen_to": max(seen) if seen else None,
        "skills": rows,
        "company_counts": sorted(([n, c] for n, c in companies.items()), key=lambda x: (-x[1], x[0].lower())),
        "sample": [
            {k: p.get(k) for k in ("company", "title", "url", "location", "level", "last_seen")}
            for p in postings
        ],
    }


def build_site_data(generated_at: str | None = None) -> dict:
    """Rebuild everything under docs/data from config/ and data/."""
    roles_config = load_json(CONFIG / "roles.json")
    skills = load_json(CONFIG / "taxonomy.json")["skills"]
    guides = load_json(DATA / "skill_guides.json", {})
    notes = load_json(DATA / "practitioner_notes.json", [])
    generated_at = generated_at or now_iso()

    index_roles = []
    any_demo = False
    for role in roles_config["roles"]:
        postings = load_json(DATA / "postings" / f"{role['id']}.json", [])
        agg = aggregate(role, postings, skills)
        agg["generated_at"] = generated_at
        any_demo = any_demo or agg["demo"]
        dump_json(SITE_DATA / "roles" / f"{role['id']}.json", agg)
        index_roles.append({
            "id": agg["id"], "title": agg["title"], "blurb": agg["blurb"],
            "postings": agg["postings"], "companies": agg["companies"],
            "entry_postings": agg["entry_postings"],
            "top_skills": [{"name": s["name"], "pct": s["pct"]} for s in agg["skills"][:5]],
        })

    skill_meta = {}
    for skill in skills:
        guide = guides.get(skill["id"], {})
        skill_meta[skill["id"]] = {
            "name": skill["name"],
            "category": skill["category"],
            "prereqs": skill.get("prereqs", []),
            "level": guide.get("level"),
            "project": guide.get("project"),
            "resources": guide.get("resources", []),
        }

    index = {
        "generated_at": generated_at,
        "demo": any_demo,
        "tiers": {name: floor for name, floor in TIERS},
        "roles": index_roles,
    }
    dump_json(SITE_DATA / "index.json", index)
    dump_json(SITE_DATA / "skills.json", skill_meta)
    dump_json(SITE_DATA / "notes.json", notes)

    # The Claude skill ships with its own copy of the numbers (without the posting list).
    for role in index_roles:
        agg = load_json(SITE_DATA / "roles" / f"{role['id']}.json")
        slim = {k: v for k, v in agg.items() if k not in ("sample", "company_counts")}
        dump_json(SKILL_DATA / "roles" / f"{role['id']}.json", slim)
    dump_json(SKILL_DATA / "index.json", index)
    dump_json(SKILL_DATA / "skills.json", skill_meta)
    dump_json(SKILL_DATA / "notes.json", notes)
    return index


# ---------------------------------------------------------------- commands

def cmd_collect(_args) -> int:
    roles_config = load_json(CONFIG / "roles.json")
    skills = load_json(CONFIG / "taxonomy.json")["skills"]
    companies = load_json(CONFIG / "companies.json")["companies"]
    classifier = RoleClassifier(roles_config)
    matcher = SkillMatcher(skills)
    today = datetime.now(timezone.utc).date().isoformat()

    found, report = collect(companies, classifier, matcher, today)
    ok = [r for r in report if r["status"] == "ok"]
    dump_json(DATA / "run_report.json", {"ran_at": now_iso(), "boards_ok": len(ok),
                                         "boards_failed": len(report) - len(ok), "boards": report})
    if not ok:
        print("No job board could be read. Stored data left unchanged. See data/run_report.json.", file=sys.stderr)
        return 1

    for role_id, postings in found.items():
        path = DATA / "postings" / f"{role_id}.json"
        merged = merge(load_json(path, []), postings, today)
        dump_json(path, merged)
        print(f"{role_id}: {len(postings)} open today, {len(merged)} in sample")
    failed = [f"{r['board']} ({r['status']})" for r in report if r["status"] != "ok"]
    if failed:
        print("Boards that could not be read: " + ", ".join(failed))
    build_site_data()
    return 0


def cmd_build(_args) -> int:
    index = build_site_data()
    for role in index["roles"]:
        print(f"{role['id']}: {role['postings']} postings, {role['companies']} companies")
    if index["demo"]:
        print("Note: the stored postings are demo rows, not real ones.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("collect", help="fetch job boards, then rebuild the site data").set_defaults(func=cmd_collect)
    sub.add_parser("build", help="rebuild the site data from stored postings").set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
