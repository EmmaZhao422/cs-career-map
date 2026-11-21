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
import hashlib
import html
import json
import os
import re
import socket
import sys
import tempfile
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
TIERS = [("most", 60.0), ("many", 30.0), ("some", 10.0)]  # share of companies, in percent
RETRY_PAUSE = 2.0  # seconds before the one retry after a 429, a 5xx or a timeout
HEALTH_SHARE = 0.6  # a run must read this share of the boards the previous run read
# Bump when the text cleaning (strip_boilerplate, strip_names, html_to_text) changes
# in a way that changes which skills a posting gets. Part of rules_version().
CLEANING_VERSION = "3"
PEOPLE_CATEGORY = "Working with people"


# ---------------------------------------------------------------- files

def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_atomic(path: Path, text: str) -> None:
    """Write to a temporary file next to `path`, then rename it into place, so
    an interrupted run never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def dump_json(path: Path, obj) -> None:
    write_text_atomic(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def rules_version(config_dir: Path | None = None) -> str:
    """A short fingerprint of everything that decides a posting's skills. A
    stored posting made under other rules cannot be recomputed (we keep no
    text), so merge() drops it once it is no longer open."""
    config_dir = config_dir or CONFIG
    digest = hashlib.sha256()
    for name in ("roles.json", "taxonomy.json"):
        digest.update((config_dir / name).read_bytes())
    digest.update(CLEANING_VERSION.encode())
    return digest.hexdigest()[:12]


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


BOILERPLATE_MIN_POSTINGS = 6   # only judge boilerplate when a board has this many postings
BOILERPLATE_SHARE = 0.5        # a long line in this share of a board's distinct titles is boilerplate
BOILERPLATE_MIN_LENGTH = 40    # lines this long or longer are judged by BOILERPLATE_SHARE
BOILERPLATE_SHORT_LENGTH = 20  # lines of 20-39 characters need a stricter test:
BOILERPLATE_SHORT_SHARE = 0.6  #   in this share of distinct titles
BOILERPLATE_SHORT_MIN = 8      #   and in at least this many of them
# Shorter lines ("Python", "SQL and Tableau") are never boilerplate.

_PUNCT = re.compile(r"[^\w]+")


def _norm_line(line: str) -> str:
    return " ".join(_PUNCT.sub(" ", line.lower()).split())


def strip_boilerplate(jobs: list[dict]) -> None:
    """Remove lines that most of a company's jobs share: the company intro,
    benefits, legal text. A skill named there says nothing about one job.

    A line is counted once per distinct job title, so one job listed in six
    cities does not turn its own requirements into boilerplate."""
    if len(jobs) < BOILERPLATE_MIN_POSTINGS:
        return
    lines_by_title: dict[str, set[str]] = {}
    longest: dict[str, int] = {}
    for i, job in enumerate(jobs):
        title = normalize_title(job.get("title") or "") or f"#{i}"
        found = lines_by_title.setdefault(title, set())
        for line in job["text"].split("\n"):
            size = len(line.strip())
            if size >= BOILERPLATE_SHORT_LENGTH:
                norm = _norm_line(line)
                found.add(norm)
                longest[norm] = max(longest.get(norm, 0), size)
    titles = len(lines_by_title)
    counts: dict[str, int] = {}
    for found in lines_by_title.values():
        for line in found:
            counts[line] = counts.get(line, 0) + 1
    long_cutoff = max(3, titles * BOILERPLATE_SHARE)
    short_cutoff = max(BOILERPLATE_SHORT_MIN, titles * BOILERPLATE_SHORT_SHARE)
    common = set()
    for line, n in counts.items():
        cutoff = long_cutoff if longest[line] >= BOILERPLATE_MIN_LENGTH else short_cutoff
        if n >= cutoff:
            common.add(line)
    if not common:
        return
    for job in jobs:
        job["text"] = "\n".join(l for l in job["text"].split("\n")
                                if len(l.strip()) < BOILERPLATE_SHORT_LENGTH or _norm_line(l) not in common)


# Company names that are also everyday words. Blanking them would delete the
# word wherever a posting uses it ("a box of tools", "a lattice"), so they are
# left alone. Figma, Notion and similar names are not on the list: blanking
# them costs nothing.
COMMON_WORD_NAMES = {
    "block", "box", "toast", "medium", "circle", "unity", "render", "bird", "bolt", "lime", "wise",
    "mercury", "lattice", "color", "ramp", "plaid", "chime", "front", "census",
}


def strip_names(text: str, display_name: str | None) -> str:
    """Blank out the company's own name, so 'MongoDB' in a MongoDB posting is
    not counted as a database skill. Only the board's display name is used,
    case-sensitively, so 'Notion' is blanked but 'notion' (the word) is not."""
    name = (display_name or "").strip()
    if len(name) < 3 or name.lower() in COMMON_WORD_NAMES:
        return text
    return re.sub(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", " ", text)


def prepare_board(jobs: list[dict], company: dict) -> str:
    """Clean one board's postings in place and return the company's display name."""
    api_names = [j["company_name"].strip() for j in jobs if j.get("company_name")]
    # The board's own company name is more reliable than the label in our list.
    display_name = max(set(api_names), key=api_names.count) if api_names else company["name"]
    strip_boilerplate(jobs)
    for job in jobs:
        job["text"] = strip_names(job["text"], display_name)
    return display_name


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


# ---------------------------------------------------------------- titles

# Words that, after " - " or in parentheses, name a place rather than a team.
PLACE_WORDS = {
    "remote", "hybrid", "onsite", "on-site", "in-office", "us", "usa", "u.s.", "united states", "uk", "united kingdom",
    "london", "dublin", "ireland", "edinburgh", "cambridge", "oxford", "toronto", "montreal", "vancouver", "canada",
    "sf", "san francisco", "bay area", "nyc", "new york", "new york city", "seattle", "austin", "boston", "chicago",
    "denver", "atlanta", "los angeles", "washington", "washington dc", "dc", "memphis", "hawthorne", "redmond",
    "palo alto", "mountain view", "sunnyvale", "san jose", "san diego", "miami", "dallas", "houston", "pittsburgh",
    "philadelphia", "portland", "salt lake city", "mexico", "mexico city", "brazil", "sao paulo", "são paulo",
    "india", "bangalore", "bengaluru", "hyderabad", "pune", "germany", "berlin", "munich", "paris", "france",
    "tel aviv", "israel", "singapore", "tokyo", "japan", "seoul", "korea", "sydney", "melbourne", "australia",
    "amsterdam", "netherlands", "aarhus", "copenhagen", "denmark", "bulgaria", "sofia", "poland", "warsaw",
    "krakow", "spain", "madrid", "barcelona", "lisbon", "portugal", "zurich", "switzerland", "stockholm", "sweden",
}
_SEASON = re.compile(r"(?:(?:summer|fall|autumn|winter|spring)(?: \d{4})?|\d{4}(?: start)?)")
_GENDER = re.compile(r"\(\s*(?:[mfwdxn]\s*/\s*)+[mfwdxn]\s*\)")
_PAREN = re.compile(r"\(([^()]*)\)")
_CITY_REGION = re.compile(r"[a-z .'-]+, [a-z]{2}")
_TRAILING_DASH = re.compile(r"\s+-\s+([^-]+)$")
_TRAILING_COMMA = re.compile(r",\s*([^,]+)$")


def _is_place(text: str) -> bool:
    text = text.strip(" .")
    if not text:
        return False
    if _CITY_REGION.fullmatch(text):
        return True
    pieces = [p.strip(" .") for p in re.split(r"\s*[/,|&]\s*", text)]
    return all(p in PLACE_WORDS or p.startswith("remote") for p in pieces if p) and any(pieces)


def _clean_group(match: re.Match) -> str:
    pieces = [p.strip() for p in re.split(r"\s*[/,|]\s*|\s+-\s+", match.group(1))]
    pieces = [p for p in pieces if p]
    kept = []
    for piece in pieces:
        if _SEASON.fullmatch(piece):
            kept.append(piece)
        elif not _is_place(piece):
            return match.group(0)  # names something else (a team, a product): leave it alone
    return "(" + " ".join(kept) + ")" if kept else " "


def normalize_title(title: str) -> str:
    """The part of a job title that names the job, for spotting one job listed
    in several places. Drops trailing places ("- London", "- Austin, TX"),
    parenthesised places ("(Remote)"; "(Summer 2027 - Toronto)" keeps the
    season) and "(m/w/d)"-style markers. Team names stay: "Software Engineer,
    Payments" and "Software Engineer, Search" remain two jobs."""
    t = " ".join(title.lower().replace("–", "-").replace("—", "-").split())
    t = _GENDER.sub(" ", t)
    t = _PAREN.sub(_clean_group, t)
    t = " ".join(t.split())
    for pattern in (_TRAILING_DASH, _TRAILING_COMMA):
        while True:
            m = pattern.search(t)
            if not m:
                break
            tail = m.group(1)
            place = _is_place(tail) if pattern is _TRAILING_DASH else tail.strip(" .") in PLACE_WORDS
            if not place:
                break
            t = t[:m.start()].rstrip()
    return t.strip(" -,")


# ---------------------------------------------------------------- roles

_NEVER = r"(?!x)x"


class RoleClassifier:
    """Assigns a job title to one of our roles, or to none."""

    def __init__(self, config: dict):
        self._senior = re.compile(config["seniority_exclude"])
        self._positional = re.compile(config.get("seniority_positional", _NEVER))
        self._nouns = re.compile(config.get("role_nouns", _NEVER))
        self._exclude_all = [re.compile(p) for p in config.get("exclude_all", [])]
        self._entry = re.compile(config["entry_level"])
        self._advanced = re.compile(config.get("advanced_degree", _NEVER))
        self.roles = config["roles"]
        self._rules = [
            (
                role["id"],
                [re.compile(p) for p in role["include"]],
                [re.compile(p) for p in role.get("exclude", [])],
            )
            for role in self.roles
        ]

    def is_senior(self, title: str) -> bool:
        t = title.lower()
        if self._senior.search(t):
            return True
        nouns = list(self._nouns.finditer(t))
        if not nouns:
            return False
        for m in self._positional.finditer(t):
            if m.start() < nouns[0].start():
                return True        # "Staff Software Engineer", "Head of Engineering"
            for n in nouns:
                if n.end() <= m.start() and not t[n.end():m.start()].strip():
                    return True    # "Engineering Manager", "Software Engineer Lead"
        return False               # "Software Engineer, Staff Tools"

    def classify(self, title: str) -> str | None:
        t = title.lower()
        if self.is_senior(t) or any(rx.search(t) for rx in self._exclude_all):
            return None
        for role_id, include, exclude in self._rules:
            if any(rx.search(t) for rx in exclude):
                continue
            if any(rx.search(t) for rx in include):
                return role_id
        return None

    def level(self, title: str) -> str:
        return "entry" if self._entry.search(title.lower()) else "open"

    def advanced_degree(self, title: str) -> bool:
        """PhD or Master's postings: counted in the totals, not in the entry counts."""
        return bool(self._advanced.search(title.lower()))


_DEFAULT_CLASSIFIER: RoleClassifier | None = None


def default_classifier() -> RoleClassifier:
    global _DEFAULT_CLASSIFIER
    if _DEFAULT_CLASSIFIER is None:
        _DEFAULT_CLASSIFIER = RoleClassifier(load_json(CONFIG / "roles.json"))
    return _DEFAULT_CLASSIFIER


# ---------------------------------------------------------------- job boards

class BadPayload(ValueError):
    """The board answered, but not with the shape its API documents."""


def _retryable(err: BaseException) -> bool:
    if isinstance(err, urllib.error.HTTPError):
        return err.code == 429 or 500 <= err.code < 600
    if isinstance(err, (TimeoutError, socket.timeout)):
        return True
    if isinstance(err, urllib.error.URLError):
        return isinstance(err.reason, (TimeoutError, socket.timeout))
    return False


def http_json(url: str, timeout: int = 30, retries: int = 1):
    """GET a JSON document. Retries once, after RETRY_PAUSE seconds, on HTTP 429,
    a 5xx answer or a timeout."""
    attempt = 0
    while True:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as err:
            if attempt >= retries or not _retryable(err):
                raise
            attempt += 1
            time.sleep(RETRY_PAUSE)


def fetch_greenhouse(board: str) -> list[dict]:
    payload = http_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise BadPayload(f"expected an object with a 'jobs' list, got {type(payload).__name__}")
    jobs = []
    for job in payload["jobs"]:
        jobs.append({
            "key": f"greenhouse:{board}:{job.get('id')}",
            "company_name": job.get("company_name"),
            "title": job.get("title") or "",
            "url": job.get("absolute_url"),
            "location": (job.get("location") or {}).get("name"),
            "posted_at": job.get("first_published") or job.get("updated_at"),
            "text": html_to_text(job.get("content")),
        })
    return jobs


def fetch_lever(site: str) -> list[dict]:
    payload = http_json(f"https://api.lever.co/v0/postings/{site}?mode=json")
    if not isinstance(payload, list):
        raise BadPayload(f"expected a list of postings, got {type(payload).__name__}")
    jobs = []
    for job in payload:
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
            pause: float = REQUEST_PAUSE, rules: str | None = None) -> tuple[dict[str, list[dict]], list[dict]]:
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
        except BadPayload as err:
            entry.update(status="bad_payload", detail=str(err)[:200])
            report.append(entry)
            continue
        except Exception as err:  # network trouble, bad JSON: note it and move on
            entry.update(status="error", detail=f"{type(err).__name__}: {err}"[:200])
            report.append(entry)
            continue
        kept = 0
        has_api_name = any(j.get("company_name") for j in jobs)
        display_name = prepare_board(jobs, company)
        entry["api_name"] = display_name if has_api_name else None
        for job in jobs:
            role_id = classifier.classify(job["title"])
            if role_id is None or not job.get("url"):
                continue
            record = {
                "key": job["key"],
                "company": display_name,
                "title": job["title"].strip(),
                "url": job["url"],
                "location": job.get("location"),
                "level": classifier.level(job["title"]),
                "posted_at": job.get("posted_at"),
                "first_seen": today,
                "last_seen": today,
                # The body only: a title such as "Software Engineer, Data Model"
                # names a team, not a skill the job asks for.
                "skills": matcher.match(job["text"]),
            }
            if rules:
                record["rules"] = rules
            found[role_id].append(record)
            kept += 1
        entry.update(status="ok", jobs=len(jobs), kept=kept)
        report.append(entry)
        if pause:
            time.sleep(pause)
    return found, report


def merge(old: list[dict], new: list[dict], today: str, retention_days: int = RETENTION_DAYS,
          rules: str | None = None) -> list[dict]:
    """Add today's postings to the stored ones. Keeps closed postings for a while
    so the sample grows; drops demo rows as soon as real ones arrive.

    With `rules`, a stored posting that is not open today and was matched under
    other rules (or before rules were recorded) is dropped: we keep no text, so
    its skills cannot be recomputed and would mix two rule sets in one count."""
    cutoff = (datetime.fromisoformat(today) - timedelta(days=retention_days)).date().isoformat()
    by_key = {p["key"]: p for p in old if not p["key"].startswith("demo:")}
    open_today = set()
    for posting in new:
        previous = by_key.get(posting["key"])
        if previous:
            posting["first_seen"] = previous["first_seen"]
        by_key[posting["key"]] = posting
        open_today.add(posting["key"])
    kept = [p for p in by_key.values()
            if p["last_seen"] >= cutoff
            and (rules is None or p["key"] in open_today or p.get("rules") == rules)]
    kept.sort(key=lambda p: (p["company"].lower(), p["title"].lower(), p["key"]))
    return kept


def check_health(previous: dict | None, report: list[dict]) -> tuple[bool, str]:
    """Refuse a run that read far fewer boards than the one before: an outage
    or a blocked network should not shrink the sample."""
    now_ok = {(r["source"], r["board"]) for r in report if r["status"] == "ok"}
    if not now_ok:
        return False, "No job board could be read. Stored data left unchanged."
    before = {(r["source"], r["board"]) for r in (previous or {}).get("boards", []) if r.get("status") == "ok"}
    if not before:
        return True, ""
    still = len(before & now_ok)
    if still < HEALTH_SHARE * len(before):
        return False, (f"Only {still} of the {len(before)} boards that were read last time could be read now "
                       f"(below {int(HEALTH_SHARE * 100)}%). Stored postings and data/run_report.json left "
                       f"unchanged; try again later.")
    return True, ""


# ---------------------------------------------------------------- aggregate

def tier_for(pct: float) -> str:
    for name, floor in TIERS:
        if pct >= floor:
            return name
    return "rare"


def _sort_postings(postings: list[dict]) -> list[dict]:
    return sorted(postings, key=lambda p: (p["company"].lower(), p["title"].lower(), p["key"]))


def reassign(stored: dict[str, list[dict]], classifier: RoleClassifier) -> dict[str, list[dict]]:
    """Apply the current title rules to every stored posting: a posting whose
    title now belongs to another role moves there, one that belongs to no role
    is dropped, and its entry-level flag is recomputed. Demo rows stay put. A
    key stored under two roles is kept once, the copy seen most recently."""
    out: dict[str, list[dict]] = {role["id"]: [] for role in classifier.roles}
    newest: dict[str, dict] = {}
    for role_id, postings in stored.items():
        for p in postings:
            if p["key"].startswith("demo:"):
                out.setdefault(role_id, []).append(p)
                continue
            prev = newest.get(p["key"])
            if prev is None or p.get("last_seen", "") > prev.get("last_seen", ""):
                newest[p["key"]] = p
    for p in newest.values():
        role_id = classifier.classify(p["title"])
        if role_id is None:
            continue
        out[role_id].append(dict(p, level=classifier.level(p["title"])))
    return {role_id: _sort_postings(postings) for role_id, postings in out.items()}


def distinct(postings: list[dict]) -> list[dict]:
    """One posting per company and job. The same job listed in several
    locations is one job, not several: titles are compared after
    normalize_title(). A merged job has every skill any of its listings
    mentions, the newest last_seen, and is entry-level if any listing is."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for p in sorted(postings, key=lambda p: p["key"]):
        groups.setdefault((p["company"], normalize_title(p["title"])), []).append(p)
    merged = []
    for members in groups.values():
        base = dict(members[0])
        if len(members) > 1:
            skills: list[str] = []
            for m in members:
                skills.extend(s for s in m.get("skills", []) if s not in skills)
            base["skills"] = skills
            base["last_seen"] = max(m.get("last_seen") or "" for m in members) or base.get("last_seen")
            if any(m.get("level") == "entry" for m in members):
                base["level"] = "entry"
        merged.append(base)
    return _sort_postings(merged)


def _share(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def aggregate(role: dict, postings: list[dict], skills: list[dict],
              classifier: RoleClassifier | None = None) -> dict:
    classifier = classifier or default_classifier()
    listings = len(postings)
    postings = distinct(postings)
    total = len(postings)
    companies: dict[str, int] = {}
    for p in postings:
        companies[p["company"]] = companies.get(p["company"], 0) + 1
    n_companies = len(companies)
    phd = {p["key"]: classifier.advanced_degree(p["title"]) for p in postings}

    def is_entry(p: dict) -> bool:
        # PhD and Master's internships count in the totals but are not what an
        # undergraduate means by "intern or new grad".
        return p.get("level") == "entry" and not phd[p["key"]]

    entry = [p for p in postings if is_entry(p)]

    rows = []
    for skill in skills:
        hits = [p for p in postings if skill["id"] in p["skills"]]
        if not hits:
            continue
        hit_companies = len({p["company"] for p in hits})
        entry_hits = [p for p in hits if is_entry(p)]
        company_pct = _share(hit_companies, n_companies)
        rows.append({
            "id": skill["id"],
            "name": skill["name"],
            "category": skill["category"],
            "count": len(hits),
            "pct": _share(len(hits), total),
            "company_pct": company_pct,
            "tier": tier_for(company_pct),
            "companies": hit_companies,
            "entry_count": len(entry_hits),
            "entry_companies": len({p["company"] for p in entry_hits}),
        })
    rows.sort(key=lambda r: (-r["companies"], -r["count"], r["name"].lower()))

    company_counts = sorted(([n, c] for n, c in companies.items()), key=lambda x: (-x[1], x[0].lower()))
    seen = [p["last_seen"] for p in postings]
    return {
        "id": role["id"],
        "title": role["title"],
        "blurb": role["blurb"],
        "start_here": role.get("start_here", []),
        "demo": any(p["key"].startswith("demo:") for p in postings),
        "postings": total,
        "listings": listings,
        "companies": n_companies,
        "entry_postings": len(entry),
        "entry_companies": len({p["company"] for p in entry}),
        "top_company": company_counts[0][0] if company_counts else None,
        "top_company_share": _share(company_counts[0][1], total) if company_counts else 0.0,
        "last_seen_from": min(seen) if seen else None,
        "last_seen_to": max(seen) if seen else None,
        "skills": rows,
        "company_counts": company_counts,
        "sample": [
            dict({k: p.get(k) for k in ("company", "title", "url", "location", "level", "last_seen")},
                 phd=phd[p["key"]])
            for p in postings
        ],
    }


def top_skills(rows: list[dict], n: int = 5) -> list[dict]:
    """The headline skills for the job list: most companies first, leaving out
    the loosely matched 'Working with people' skills."""
    picked = sorted((r for r in rows if r["category"] != PEOPLE_CATEGORY),
                    key=lambda r: (-r["company_pct"], -r["pct"], r["name"].lower()))[:n]
    return [{"name": r["name"], "pct": r["pct"], "company_pct": r["company_pct"]} for r in picked]


def build_site_data(generated_at: str | None = None) -> dict:
    """Rebuild everything under docs/data from config/ and data/."""
    roles_config = load_json(CONFIG / "roles.json")
    skills = load_json(CONFIG / "taxonomy.json")["skills"]
    guides = load_json(DATA / "skill_guides.json", {})
    notes = load_json(DATA / "practitioner_notes.json", [])
    generated_at = generated_at or now_iso()

    classifier = RoleClassifier(roles_config)
    stored = {role["id"]: load_json(DATA / "postings" / f"{role['id']}.json", []) for role in roles_config["roles"]}
    by_role = reassign(stored, classifier)
    for role_id, postings in by_role.items():
        if postings != stored.get(role_id):
            dump_json(DATA / "postings" / f"{role_id}.json", postings)

    index_roles = []
    any_demo = False
    for role in roles_config["roles"]:
        agg = aggregate(role, by_role[role["id"]], skills, classifier)
        agg["generated_at"] = generated_at
        any_demo = any_demo or agg["demo"]
        dump_json(SITE_DATA / "roles" / f"{role['id']}.json", agg)
        index_roles.append({
            "id": agg["id"], "title": agg["title"], "blurb": agg["blurb"],
            "postings": agg["postings"], "companies": agg["companies"],
            "entry_postings": agg["entry_postings"], "entry_companies": agg["entry_companies"],
            "top_skills": top_skills(agg["skills"]),
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
        if skill.get("note"):
            skill_meta[skill["id"]]["note"] = skill["note"]

    index = {
        "generated_at": generated_at,
        "demo": any_demo,
        "notice": (load_json(CONFIG / "site.json", {}).get("notice") or None),
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
    rules = rules_version()

    found, report = collect(companies, classifier, matcher, today, rules=rules)
    healthy, message = check_health(load_json(DATA / "run_report.json"), report)
    failed = [f"{r['board']} ({r['status']})" for r in report if r["status"] != "ok"]
    if not healthy:
        print(message, file=sys.stderr)
        if failed:
            print("Boards that could not be read: " + ", ".join(failed), file=sys.stderr)
        return 1
    ok = [r for r in report if r["status"] == "ok"]
    dump_json(DATA / "run_report.json", {"ran_at": now_iso(), "rules": rules, "boards_ok": len(ok),
                                         "boards_failed": len(report) - len(ok), "boards": report})

    role_ids = [role["id"] for role in roles_config["roles"]]
    old = [p for role_id in role_ids for p in load_json(DATA / "postings" / f"{role_id}.json", [])]
    new = [p for role_id in role_ids for p in found[role_id]]
    by_role = reassign({"merged": merge(old, new, today, rules=rules)}, classifier)
    for role_id in role_ids:
        dump_json(DATA / "postings" / f"{role_id}.json", by_role[role_id])
        print(f"{role_id}: {len(found[role_id])} open today, {len(by_role[role_id])} in sample")
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


PRUNE_AFTER_MISSES = 2  # a board must be "not found" in this many runs in a row before it is dropped


def format_companies(config: dict) -> str:
    """companies.json with one company per line, so diffs stay readable."""
    companies = config["companies"]
    lines = ["{", '  "_comment": ' + json.dumps(config["_comment"], ensure_ascii=False) + ","]
    if config.get("pruned_run"):
        lines.append('  "pruned_run": ' + json.dumps(config["pruned_run"]) + ",")
    lines.append('  "companies": [')
    lines += ["    " + json.dumps(c, ensure_ascii=False) + ("," if i < len(companies) - 1 else "")
              for i, c in enumerate(companies)]
    lines += ["  ]", "}"]
    return "\n".join(lines) + "\n"


def cmd_prune_companies(_args) -> int:
    """Stamp the boards the last run could read as checked, and drop a board
    only after it was "not found" in two runs in a row."""
    path = CONFIG / "companies.json"
    config = load_json(path)
    report = load_json(DATA / "run_report.json")
    if not report:
        print("No data/run_report.json yet. Run `collect` first.", file=sys.stderr)
        return 1
    total = len(config["companies"])
    if report.get("boards_ok", 0) < HEALTH_SHARE * total:
        print(f"The last run read only {report.get('boards_ok', 0)} of {total} boards. That looks like an outage, "
              "not missing boards; nothing changed.", file=sys.stderr)
        return 1
    if config.get("pruned_run") == report["ran_at"]:
        print(f"This run report ({report['ran_at']}) was already applied; nothing changed.", file=sys.stderr)
        return 1
    by_board = {(b["source"], b["board"]): b for b in report["boards"]}
    day = report["ran_at"][:10]
    kept, dropped, warned = [], [], []
    for company in config["companies"]:
        seen = by_board.get((company["source"], company["board"]))
        if seen is None:
            kept.append(company)  # not part of the last run: leave as is
            continue
        if seen["status"] == "not_found":
            misses = company.get("misses", 0) + 1
            if misses >= PRUNE_AFTER_MISSES:
                dropped.append(f"{company['board']} (not found {misses} runs in a row)")
                continue
            company["misses"] = misses
            warned.append(company["board"])
        else:
            company.pop("misses", None)
            if seen["status"] == "ok" and seen.get("jobs", 0) > 0:
                company["checked"] = day
                if seen.get("api_name"):
                    company["name"] = seen["api_name"]
        kept.append(company)
    config["companies"] = kept
    config["pruned_run"] = report["ran_at"]
    write_text_atomic(path, format_companies(config))
    print(f"kept {len(kept)} boards; dropped {len(dropped)}: {', '.join(dropped) or '-'}; "
          f"not found once (dropped if it happens again): {', '.join(warned) or '-'}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prune-companies", help="drop boards that were not found in two runs in a row").set_defaults(
        func=cmd_prune_companies)
    sub.add_parser("collect", help="fetch job boards, then rebuild the site data").set_defaults(func=cmd_collect)
    sub.add_parser("build", help="rebuild the site data from stored postings").set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
