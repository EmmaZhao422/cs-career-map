"""Tests for the collector. Run: python -m unittest discover -s collector -v"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROLES = json.loads((ROOT / "config" / "roles.json").read_text())
SKILLS = json.loads((ROOT / "config" / "taxonomy.json").read_text())["skills"]


class TextTests(unittest.TestCase):
    def test_escaped_html_becomes_plain_text(self):
        raw = "&lt;p&gt;Build APIs in &lt;strong&gt;Python&lt;/strong&gt; &amp;amp; Go.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;SQL&lt;/li&gt;&lt;/ul&gt;"
        text = collect.html_to_text(raw)
        self.assertIn("Build APIs in Python & Go.", text)
        self.assertIn("SQL", text)
        self.assertNotIn("<", text)

    def test_empty_input(self):
        self.assertEqual(collect.html_to_text(None), "")


class SkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = collect.SkillMatcher(SKILLS)

    def found(self, text):
        return set(self.matcher.match(text))

    def test_every_pattern_compiles_and_ids_are_unique(self):
        ids = [s["id"] for s in SKILLS]
        self.assertEqual(len(ids), len(set(ids)))
        known = set(ids)
        for skill in SKILLS:
            for prereq in skill.get("prereqs", []):
                self.assertIn(prereq, known, f"{skill['id']} lists unknown prereq {prereq}")

    def test_java_is_not_javascript(self):
        self.assertEqual(self.found("Experience with JavaScript") & {"java", "javascript"}, {"javascript"})
        self.assertEqual(self.found("Experience with Java or Kotlin") & {"java", "javascript"}, {"java"})

    def test_sql_is_not_nosql(self):
        self.assertNotIn("sql", self.found("NoSQL stores such as DynamoDB"))
        self.assertIn("nosql", self.found("NoSQL stores such as DynamoDB"))
        self.assertIn("sql", self.found("Strong SQL skills"))

    def test_c_family(self):
        self.assertIn("cpp", self.found("Proficiency in C++ or Rust"))
        self.assertEqual(self.found("C/C++ experience") & {"c-lang", "cpp"}, {"c-lang", "cpp"})
        self.assertIn("c-sharp", self.found("C# and .NET services"))
        self.assertNotIn("c-lang", self.found("Series C startup with vitamin C"))

    def test_go_the_language_only(self):
        self.assertIn("go", self.found("Python, Go, or Java"))
        self.assertIn("go", self.found("services written in Go."))
        self.assertIn("go", self.found("Experience with Golang"))
        self.assertNotIn("go", self.found("Go to market strategy. Go beyond the brief. We go fast."))

    def test_r_the_language_only(self):
        self.assertIn("r", self.found("Proficiency in SQL, R, or Python"))
        self.assertIn("r", self.found("analysis in R or Python"))
        self.assertNotIn("r", self.found("Our R&D team works on R & D for Toys R Us"))

    def test_words_that_are_also_verbs(self):
        self.assertNotIn("react", self.found("You react quickly to incidents"))
        self.assertIn("react", self.found("Build UIs with React and TypeScript"))
        self.assertNotIn("excel", self.found("You excel at ambiguity. Excel in a fast-paced team."))
        self.assertIn("excel", self.found("Advanced Excel and SQL"))
        self.assertNotIn("rest-apis", self.found("work with the rest of the team"))
        self.assertIn("rest-apis", self.found("design RESTful APIs"))

    def test_ai_terms(self):
        hits = self.found("Ship LLM features: RAG pipelines, evals, prompt engineering, and AI agents in PyTorch")
        self.assertTrue({"llm", "rag", "model-evaluation", "prompt-engineering", "agents", "pytorch"} <= hits)

    def test_statistics_not_regression_testing(self):
        self.assertNotIn("statistics", self.found("own regression testing for releases"))
        self.assertIn("statistics", self.found("logistic regression and hypothesis testing"))


class RoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = collect.RoleClassifier(ROLES)

    def test_titles(self):
        cases = {
            "Software Engineer, New Grad": "software-engineer",
            "Backend Engineer": "software-engineer",
            "Full-Stack Developer": "software-engineer",
            "Software Engineer Intern (Summer 2027)": "software-engineer",
            "Machine Learning Engineer": "ai-engineer",
            "Software Engineer, Machine Learning": "ai-engineer",
            "AI Engineer": "ai-engineer",
            "Research Engineer, Interpretability": "ai-engineer",
            "Data Analyst": "data-analyst",
            "Product Analyst, Growth": "data-analyst",
            "Business Intelligence Analyst": "data-analyst",
            "Senior Software Engineer": None,
            "Staff Machine Learning Engineer": None,
            "Engineering Manager, Payments": None,
            "Software Engineer III": None,
            "Sales Engineer": None,
            "AI Solutions Engineer": None,
            "Account Executive": None,
            "Financial Analyst": None,
        }
        for title, expected in cases.items():
            self.assertEqual(self.classifier.classify(title), expected, title)

    def test_level(self):
        self.assertEqual(self.classifier.level("Software Engineer, New Grad"), "entry")
        self.assertEqual(self.classifier.level("Data Analyst Intern"), "entry")
        self.assertEqual(self.classifier.level("Software Engineer"), "open")


GREENHOUSE_PAYLOAD = {
    "jobs": [
        {"id": 101, "title": "Software Engineer, New Grad", "absolute_url": "https://example.com/jobs/101",
         "location": {"name": "Remote"}, "updated_at": "2026-11-01T10:00:00-04:00",
         "content": "&lt;p&gt;You will write Python and SQL.&lt;/p&gt;"},
        {"id": 102, "title": "Senior Software Engineer", "absolute_url": "https://example.com/jobs/102",
         "location": {"name": "NYC"}, "updated_at": "2026-11-01T10:00:00-04:00",
         "content": "&lt;p&gt;Go and Kubernetes.&lt;/p&gt;"},
        {"id": 103, "title": "Data Analyst", "absolute_url": "https://example.com/jobs/103",
         "location": None, "updated_at": None, "content": "&lt;p&gt;SQL, Tableau and statistics.&lt;/p&gt;"},
    ],
    "meta": {"total": 3},
}

LEVER_PAYLOAD = [
    {"id": "abc", "text": "Machine Learning Engineer", "hostedUrl": "https://example.com/l/abc",
     "categories": {"location": "Paris"}, "createdAt": 1793491200000,
     "descriptionPlain": "Train models in PyTorch.",
     "lists": [{"text": "Requirements", "content": "<li>Python</li><li>LLM evals</li>"}],
     "additionalPlain": "We value clear communication skills."},
]


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.classifier = collect.RoleClassifier(ROLES)
        self.matcher = collect.SkillMatcher(SKILLS)
        self._real = collect.http_json

        def fake(url, timeout=30):
            if "greenhouse" in url and "/goodco/" in url:
                return GREENHOUSE_PAYLOAD
            if "lever" in url and "/leverco" in url:
                return LEVER_PAYLOAD
            raise collect.urllib.error.HTTPError(url, 404, "Not Found", None, None)

        collect.http_json = fake

    def tearDown(self):
        collect.http_json = self._real

    def run_collect(self):
        companies = [
            {"name": "Good Co", "source": "greenhouse", "board": "goodco"},
            {"name": "Lever Co", "source": "lever", "board": "leverco"},
            {"name": "Gone Co", "source": "greenhouse", "board": "gone"},
        ]
        return collect.collect(companies, self.classifier, self.matcher, "2026-11-21", pause=0)

    def test_collect_keeps_matching_roles_and_reports_failures(self):
        found, report = self.run_collect()
        self.assertEqual([p["title"] for p in found["software-engineer"]], ["Software Engineer, New Grad"])
        self.assertEqual(found["software-engineer"][0]["skills"], ["python", "sql"])
        self.assertEqual(found["software-engineer"][0]["level"], "entry")
        self.assertEqual(len(found["data-analyst"]), 1)
        ml = found["ai-engineer"][0]
        self.assertEqual(ml["company"], "Lever Co")
        self.assertTrue({"python", "pytorch", "llm", "model-evaluation", "communication"} <= set(ml["skills"]))
        self.assertEqual({r["board"]: r["status"] for r in report},
                         {"goodco": "ok", "leverco": "ok", "gone": "not_found"})

    def test_no_posting_text_is_stored(self):
        found, _ = self.run_collect()
        for postings in found.values():
            for posting in postings:
                self.assertNotIn("text", posting)

    def test_merge_keeps_first_seen_drops_old_and_demo(self):
        old = [
            {"key": "greenhouse:goodco:101", "company": "Good Co", "title": "Software Engineer, New Grad",
             "first_seen": "2026-10-01", "last_seen": "2026-11-14", "skills": []},
            {"key": "greenhouse:goodco:7", "company": "Good Co", "title": "Old", "first_seen": "2026-01-01",
             "last_seen": "2026-02-01", "skills": []},
            {"key": "greenhouse:goodco:8", "company": "Good Co", "title": "Closed last month",
             "first_seen": "2026-09-01", "last_seen": "2026-10-20", "skills": []},
            {"key": "demo:1", "company": "Demo Company A", "title": "Demo", "first_seen": "2026-11-01",
             "last_seen": "2026-11-01", "skills": []},
        ]
        found, _ = self.run_collect()
        merged = collect.merge(old, found["software-engineer"], "2026-11-21")
        by_key = {p["key"]: p for p in merged}
        self.assertEqual(set(by_key), {"greenhouse:goodco:101", "greenhouse:goodco:8"})
        self.assertEqual(by_key["greenhouse:goodco:101"]["first_seen"], "2026-10-01")
        self.assertEqual(by_key["greenhouse:goodco:101"]["last_seen"], "2026-11-21")


class AggregateTests(unittest.TestCase):
    def test_counts_shares_and_tiers(self):
        def posting(i, company, skills, level="open"):
            return {"key": f"x:{i}", "company": company, "title": "Software Engineer", "url": "https://e.x",
                    "location": None, "level": level, "last_seen": "2026-11-21", "skills": skills}

        postings = [posting(i, "A" if i < 6 else "B", ["python"] + (["sql"] if i < 2 else []),
                            "entry" if i == 0 else "open") for i in range(10)]
        role = {"id": "software-engineer", "title": "Software Engineer", "blurb": "x"}
        agg = collect.aggregate(role, postings, SKILLS)
        self.assertEqual((agg["postings"], agg["companies"], agg["entry_postings"]), (10, 2, 1))
        self.assertFalse(agg["demo"])
        python, sql = agg["skills"][0], agg["skills"][1]
        self.assertEqual((python["id"], python["count"], python["pct"], python["tier"], python["companies"]),
                         ("python", 10, 100.0, "most", 2))
        self.assertEqual((sql["id"], sql["count"], sql["pct"], sql["tier"], sql["companies"], sql["entry_count"]),
                         ("sql", 2, 20.0, "many", 1, 1))

    def test_empty_role(self):
        agg = collect.aggregate({"id": "r", "title": "R", "blurb": "b"}, [], SKILLS)
        self.assertEqual((agg["postings"], agg["skills"]), (0, []))

    def test_tier_edges(self):
        self.assertEqual([collect.tier_for(x) for x in (40, 39.9, 15, 14.9, 5, 4.9)],
                         ["most", "many", "many", "some", "some", "rare"])


if __name__ == "__main__":
    unittest.main()
