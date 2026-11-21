#!/usr/bin/env python3
"""Write DEMO postings so the website can be developed before the first real
collection run.

Every row is invented: the companies are called "Demo Company N", the links go
nowhere, and the skill frequencies are placeholders. The site shows a banner
while demo rows are present, and the first successful `collect` run deletes
them.

    python collector/demo_data.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402

# Placeholder chance that a demo posting mentions each skill. Not real data.
DEMO_RATES = {
    "software-engineer": {
        "python": .55, "java": .42, "javascript": .38, "typescript": .36, "cpp": .22, "go": .24, "sql": .34,
        "data-structures-algorithms": .52, "system-design": .30, "distributed-systems": .27, "testing": .33,
        "git": .28, "linux": .18, "docker": .21, "kubernetes": .19, "ci-cd": .22, "aws": .31, "gcp": .12,
        "react": .29, "nodejs": .14, "rest-apis": .44, "microservices": .13, "nosql": .11, "oop": .16,
        "communication": .37, "cross-functional": .41, "llm": .09, "machine-learning": .12, "rust": .07,
        "graphql": .06, "kafka": .06, "concurrency": .08, "html-css": .10, "kotlin": .05, "swift": .05,
    },
    "ai-engineer": {
        "python": .93, "machine-learning": .88, "deep-learning": .61, "pytorch": .58, "llm": .64,
        "model-evaluation": .41, "rag": .29, "agents": .26, "prompt-engineering": .22, "fine-tuning": .31,
        "mlops": .36, "tensorflow": .27, "nlp": .33, "computer-vision": .17, "sql": .24, "cpp": .19,
        "docker": .22, "kubernetes": .18, "aws": .28, "gcp": .15, "distributed-systems": .23,
        "data-structures-algorithms": .30, "statistics": .21, "spark": .12, "scikit-learn": .14,
        "pandas": .13, "communication": .34, "cross-functional": .38, "rest-apis": .20, "git": .12,
        "data-pipelines": .16, "java": .10, "go": .08, "rust": .06,
    },
    "data-analyst": {
        "sql": .91, "python": .58, "excel": .47, "tableau": .44, "dashboards": .56, "statistics": .52,
        "ab-testing": .31, "data-visualization": .43, "looker": .23, "power-bi": .21, "r": .26,
        "communication": .62, "cross-functional": .71, "data-modeling": .19, "data-warehouse": .28,
        "dbt": .14, "pandas": .12, "data-pipelines": .17, "machine-learning": .11, "git": .07,
    },
}

POSTINGS_PER_ROLE = 60
COMPANIES = [f"Demo Company {chr(65 + i)}" for i in range(18)]
TITLES = {
    "software-engineer": ["Software Engineer", "Software Engineer, New Grad", "Backend Engineer",
                          "Frontend Engineer", "Software Engineer Intern", "Full-Stack Engineer"],
    "ai-engineer": ["Machine Learning Engineer", "AI Engineer", "Applied AI Engineer",
                    "Machine Learning Engineer, New Grad", "Research Engineer"],
    "data-analyst": ["Data Analyst", "Product Analyst", "Business Intelligence Analyst",
                     "Data Analyst Intern", "Analytics Analyst"],
}


def main() -> int:
    roles_config = collect.load_json(collect.CONFIG / "roles.json")
    known = {s["id"] for s in collect.load_json(collect.CONFIG / "taxonomy.json")["skills"]}
    classifier = collect.RoleClassifier(roles_config)
    rng = random.Random(20261121)
    today = "2026-11-21"
    for role in roles_config["roles"]:
        rates = DEMO_RATES[role["id"]]
        unknown = set(rates) - known
        if unknown:
            raise SystemExit(f"demo rates name skills that are not in the taxonomy: {sorted(unknown)}")
        postings = []
        for i in range(POSTINGS_PER_ROLE):
            title = rng.choice(TITLES[role["id"]])
            postings.append({
                "key": f"demo:{role['id']}:{i}",
                "company": rng.choice(COMPANIES),
                "title": title,
                "url": None,
                "location": None,
                "level": classifier.level(title),
                "posted_at": None,
                "first_seen": today,
                "last_seen": today,
                "skills": sorted(s for s, rate in rates.items() if rng.random() < rate),
            })
        collect.dump_json(collect.DATA / "postings" / f"{role['id']}.json", postings)
    index = collect.build_site_data(generated_at="2026-11-21T07:00:00+00:00")
    print("wrote demo data:", ", ".join(f"{r['id']}={r['postings']}" for r in index["roles"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
