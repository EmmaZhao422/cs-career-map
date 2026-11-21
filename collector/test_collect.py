"""Tests for the collector. Run: python -m unittest discover -s collector -v"""
import io
import json
import os
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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


class ContentTests(unittest.TestCase):
    """The hand-written files the site and the skill depend on."""

    def test_every_skill_has_a_complete_guide(self):
        guides = json.loads((ROOT / "data" / "skill_guides.json").read_text())
        ids = {s["id"] for s in SKILLS}
        self.assertEqual(set(guides), ids)
        for skill_id, guide in guides.items():
            self.assertTrue(guide["level"] and guide["project"], skill_id)
            # A guide may ship without resources until someone opens and checks a link.
            self.assertTrue(0 <= len(guide["resources"]) <= 2, skill_id)
            for res in guide["resources"]:
                self.assertTrue(res["url"].startswith("https://"), res["url"])
                self.assertRegex(res["checked"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(res["title"] and res["by"])

    def test_start_here_lists_are_real_skills_with_guides(self):
        guides = json.loads((ROOT / "data" / "skill_guides.json").read_text())
        for role in ROLES["roles"]:
            self.assertTrue(3 <= len(role["start_here"]) <= 6, role["id"])
            for skill_id in role["start_here"]:
                self.assertIn(skill_id, guides)
                self.assertTrue(guides[skill_id]["resources"], skill_id)

    def test_hiring_notes_point_at_real_skills_and_carry_sources(self):
        notes = json.loads((ROOT / "data" / "practitioner_notes.json").read_text())
        skill_ids = {s["id"] for s in SKILLS}
        role_ids = {r["id"] for r in ROLES["roles"]}
        for note in notes:
            self.assertIn(note["skill"], skill_ids)
            self.assertTrue(note.get("role") is None or note["role"] in role_ids)
            self.assertTrue(note["note"] and note["who"])
            if note.get("kind") == "published":
                self.assertTrue(note["source"].startswith("https://"))

    def test_hiring_notes_sit_on_the_skill_they_are_about(self):
        notes = {n["who"]: n for n in json.loads((ROOT / "data" / "practitioner_notes.json").read_text())}
        expected = {
            "GitLab handbook, AI-Native Hiring Working Group": "communication",
            "Anthropic research, How employment is changing at Anthropic": "llm",
            "Anthropic, Guidance on Candidates' AI Usage": "prompt-engineering",
            "Stripe careers, Software Engineer, New Grad": "data-structures-algorithms",
        }
        for who, skill in expected.items():
            self.assertEqual(notes[who]["skill"], skill, who)


class CleaningTests(unittest.TestCase):
    def test_lines_shared_by_most_postings_are_dropped(self):
        intro = "We build autonomy, AI and computer vision products for a safer world."
        jobs = [{"text": intro + "\nPython and SQL.\nRequirement number %d for this particular job only." % i}
                for i in range(8)]
        jobs.append({"text": "A different posting that mentions computer vision in its own requirements section."})
        collect.strip_boilerplate(jobs)
        self.assertNotIn("autonomy", jobs[0]["text"])
        self.assertIn("Python and SQL.", jobs[0]["text"])              # lines under 20 characters always stay
        self.assertIn("Requirement number 0", jobs[0]["text"])
        self.assertIn("computer vision", jobs[8]["text"])              # said once, so it stays

    def test_small_boards_are_left_alone(self):
        jobs = [{"text": "The same long introduction line appears in every posting here."} for _ in range(3)]
        collect.strip_boilerplate(jobs)
        self.assertTrue(all(j["text"] for j in jobs))

    def test_one_job_in_many_cities_keeps_its_requirements(self):
        # The reviewer's case: six listings of one job plus four other jobs.
        intro = "Acme builds payment software used by millions of businesses around the world."
        req = "Experience with Kafka and distributed systems in production environments."
        jobs = [{"title": f"Software Engineer, Payments - {city}", "text": intro + "\n" + req}
                for city in ("London", "Dublin", "Toronto", "Remote", "Austin, TX", "NYC")]
        jobs += [{"title": f"Software Engineer, Team {t}", "text": intro + f"\nYou will own the {t} service end to end, from design to on-call."}
                 for t in ("Search", "Ledger", "Billing", "Identity")]
        collect.strip_boilerplate(jobs)
        self.assertIn(req, jobs[0]["text"])            # one job, so not boilerplate
        self.assertNotIn(intro, jobs[0]["text"])       # shared by all five jobs
        self.assertNotIn(intro, jobs[-1]["text"])

    def test_boilerplate_lines_compare_without_punctuation(self):
        jobs = [{"title": f"Job {i}", "text": ("We are an equal opportunity employer, and we value diversity!" if i % 2
                                                else "We are an equal-opportunity employer and we value diversity.")
                 + f"\nThe thing only job {i} needs, described at some length here."} for i in range(8)]
        collect.strip_boilerplate(jobs)
        self.assertTrue(all("equal" not in j["text"] for j in jobs))
        self.assertIn("only job 3", jobs[3]["text"])

    def test_short_lines_need_a_stricter_share(self):
        short = "Benefits and perks for you"         # 26 characters
        many = [{"title": f"Job {i}", "text": short + f"\nRequirement {i}"} for i in range(10)]
        collect.strip_boilerplate(many)                # 10 of 10 titles: boilerplate
        self.assertNotIn(short, many[0]["text"])
        few = [{"title": f"Job {i}", "text": (short if i < 7 else "") + f"\nRequirement {i}"} for i in range(10)]
        collect.strip_boilerplate(few)                 # 7 titles: under the minimum of 8
        self.assertIn(short, few[0]["text"])

    def test_company_name_is_not_a_skill(self):
        matcher = collect.SkillMatcher(SKILLS)
        text = collect.strip_names("Join MongoDB. You will use Redis and MongoDB Atlas.", "MongoDB")
        self.assertIn("nosql", matcher.match(text))        # Redis still counts
        only = collect.strip_names("MongoDB is hiring. MongoDB values ownership.", "MongoDB")
        self.assertNotIn("nosql", matcher.match(only))

    def test_only_the_display_name_is_stripped_case_sensitively(self):
        self.assertEqual(collect.strip_names("Notion uses notion of state.", "Notion").split(), ["uses", "notion", "of", "state."])
        self.assertIn("Figma", collect.strip_names("Build plugins for Figma.", "Acme"))
        self.assertNotIn("Figma", collect.strip_names("Figma is hiring.", "Figma"))

    def test_common_word_names_are_left_alone(self):
        for name in ("Block", "Box", "Toast", "Medium", "Lattice", "Render", "Unity"):
            text = f"Ship code in a {name} of work; {name} is hiring."
            self.assertEqual(collect.strip_names(text, name), text, name)

    def test_prepare_board_strips_display_name_not_token_or_label(self):
        jobs = [{"title": "Software Engineer", "company_name": "Acme Robotics", "text": "acmebot and Acme Robotics use Go, Python."}]
        name = collect.prepare_board(jobs, {"name": "Acme", "board": "acmebot"})
        self.assertEqual(name, "Acme Robotics")
        self.assertIn("acmebot", jobs[0]["text"])
        self.assertNotIn("Acme Robotics", jobs[0]["text"])


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

    def test_patterns_tightened_after_the_first_audit(self):
        self.assertNotIn("ruby", self.found("integrating with local payment rails"))
        self.assertIn("ruby", self.found("a large Ruby on Rails monolith"))
        self.assertNotIn("data-structures-algorithms", self.found("infrastructure, algorithms, and integrations"))
        self.assertIn("data-structures-algorithms", self.found("solid grasp of algorithms and data structures"))
        self.assertNotIn("operating-systems", self.found("Lattice OS, an AI-powered operating system that turns data"))
        self.assertIn("operating-systems", self.found("coursework in operating systems and networking"))
        self.assertNotIn("concurrency", self.found("supports concurrent streams of data; ship features concurrently"))
        self.assertIn("concurrency", self.found("multithreading, concurrency and locking"))
        self.assertNotIn("ab-testing", self.found("field exercises, test events, experimentation campaigns"))
        self.assertIn("ab-testing", self.found("design A/B tests and read the results"))
        self.assertNotIn("git", self.found("GitLab is an open core software company"))
        self.assertIn("git", self.found("comfortable with Git and code review"))

    def test_model_evaluation_not_business_benchmarking(self):
        self.assertNotIn("model-evaluation", self.found("benchmark our pricing against competitors"))
        self.assertIn("model-evaluation", self.found("build evals and benchmarks for models"))

    def test_statistics_not_regression_testing(self):
        self.assertNotIn("statistics", self.found("own regression testing for releases"))
        self.assertIn("statistics", self.found("logistic regression and hypothesis testing"))

    def test_false_positives_from_the_independent_review(self):
        negatives = {
            "rag": ["We track risks with a red/amber/green rag status.", "a rag-tag group of builders"],
            "git": ["You will use GitHub Copilot daily."],
            "go": ["Go to market with us. Go-to-market strategy. Strategy, Go to market."],
            "r": ["Intel(R) Xeon processors"],
            "spark": ["Spark joy in every customer.", "Our mission: Spark curiosity."],
            "swift": ["Swift decisions matter here."],
            "tensorflow": ["jax is a word in nothing we know", "Ajax requests"],
            "deep-learning": ["We build power transformers for the grid."],
            "agents": ["Tool use and safety training for warehouse staff."],
            "docker": ["Track shipping containers across ports."],
            "linux": ["Timestamps are stored as UNIX time."],
            "rest-apis": ["Integrate with partner APIs and the rest of the team.", "Our API is public."],
            "dashboards": ["Build Grafana dashboards and monitoring dashboards for on-call."],
        }
        for skill, texts in negatives.items():
            for text in texts:
                self.assertNotIn(skill, self.found(text), f"{skill}: {text}")

    def test_true_positives_from_the_independent_review(self):
        positives = {
            "rag": ["Build RAG pipelines.", "retrieval-augmented generation"],
            "git": ["Git and GitHub workflows"],
            "go": ["We use Go for services.", "Go-based microservices", "languages such as Go and Rust",
                   "services written in Go", "Python, Go, or Java"],
            "c-lang": ["C, Java or Python", "Embedded C on microcontrollers", "Our runtime is written in C.",
                       "C/C++ experience"],
            "machine-learning": ["machine-learning models"],
            "deep-learning": ["deep-learning research", "transformer models", "Hugging Face Transformers"],
            "terraform": ["infrastructure-as-code"],
            "nlp": ["natural-language processing"],
            "mlops": ["ML Ops", "MLOps", "LLMOps tooling"],
            "agents": ["function calling", "tool-use", "tool calling", "LLM tool use"],
            "ab-testing": ["run A/B-tests"],
            "sql": ["Postgres"],
            "tensorflow": ["JAX and Flax"],
            "spark": ["Apache Spark", "PySpark", "experience with Spark and Kafka", "Spark, Kafka"],
            "swift": ["iOS in Swift and SwiftUI", "Swift, Kotlin"],
            "docker": ["Docker", "containerization", "containers on Kubernetes"],
            "rest-apis": ["REST APIs", "API design", "building APIs", "web APIs", "RESTful services"],
            "dashboards": ["Build dashboards in Tableau for leadership", "business intelligence"],
            "looker": ["Looker Studio reports"],
            "r": ["(R, Python)"],
        }
        for skill, texts in positives.items():
            for text in texts:
                self.assertIn(skill, self.found(text), f"{skill}: {text}")

    def test_fourth_audit_false_positives_and_kept_matches(self):
        positives = {
            "gpu-cuda": ["We write Triton kernels.", "Optimizing GPU kernels for attention."],
            "sas-spss": ["Experience with SAS, R or Stata for analysis.", "Comfortable with SQL, SAS."],
            "rag": ["Work with embedding models and vector stores.", "Learned embeddings power ranking."],
            "system-design": ["We design scalable systems for payments.", "Good grounding in system design."],
            "git": ["Daily use of Git and GitHub review."],
            "agile": ["We are an Agile team using sprints."],
            "fine-tuning": ["You will be fine-tuning LLMs for customers."],
            "excel": ["Strong spreadsheet skills.", "Advanced Excel."],
            "operating-systems": ["Study of algorithms, operating systems and networks."],
            "dashboards": ["Build dashboards for the sales team.", "Experience with BI tools."],
            "angular-vue": ["Front end in Vue or Angular."],
        }
        negatives = {
            "gpu-cuda": ["We run a large GPU fleet for model training.", "Scaling jobs to thousands of GPUs.", "Serve inference on CPU and GPU."],
            "sas-spss": ["Storage uses PCIe, SAS, and I2C links.", "SATA, SAS and NVMe drives."],
            "rag": ["Our goal is embedding them into daily practice."],
            "system-design": ["Building high-quality, scalable systems that matter."],
            "git": ["CI/CD runs on GitHub Actions."],
            "agile": ["Parts lists live in tools such as Agile, with revisions."],
            "fine-tuning": ["Fine-tuning performance for low latency."],
            "excel": ["Charts, spreadsheets and other surfaces in our product."],
            "operating-systems": ["Experience with UNIX-like operating systems and Terraform."],
            "dashboards": ["As a Business Intelligence Analyst you will help.", "The observability stack \u2014 dashboards and metrics."],
            "angular-vue": ["Vue d'ensemble du projet."],
        }
        for skill, texts in positives.items():
            for text in texts:
                self.assertIn(skill, self.found(text), f"{skill}: {text}")
        for skill, texts in negatives.items():
            for text in texts:
                self.assertNotIn(skill, self.found(text), f"{skill}: {text}")

    def test_new_skills(self):
        positives = {
            "django-flask": ["Django or Flask", "APIs in FastAPI"],
            "spring": ["Spring Boot", "Java and Spring"],
            "angular-vue": ["Angular", "Vue.js"],
            "observability": ["observability", "Prometheus and Grafana", "monitoring and alerting", "tools like Datadog"],
            "grpc": ["gRPC services", "Protocol Buffers"],
            "elasticsearch-search": ["Elasticsearch", "OpenSearch clusters"],
            "reinforcement-learning": ["reinforcement learning", "RLHF"],
            "gpu-cuda": ["CUDA kernels", "GPU programming"],
            "analytics-tools": ["Google Analytics", "Amplitude or Mixpanel"],
            "sas-spss": ["SAS, SPSS or Stata"],
            "jupyter": ["Jupyter", "Databricks notebooks"],
            "agile": ["Agile", "Scrum ceremonies"],
        }
        negatives = {
            "spring": ["Spring 2027 internship with Java"],
            "angular-vue": ["angular momentum", "Angular velocity sensors"],
            "analytics-tools": ["signal amplitude"],
            "sas-spss": ["Azure SAS tokens", "our SaaS product"],
            "jupyter": ["a notebook and a pen"],
            "agile": ["an agile team that moves fast"],
            "gpu-cuda": ["GPUs are expensive."],
        }
        for skill, texts in positives.items():
            for text in texts:
                self.assertIn(skill, self.found(text), f"{skill}: {text}")
        for skill, texts in negatives.items():
            for text in texts:
                self.assertNotIn(skill, self.found(text), f"{skill}: {text}")


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
            "Software Engineer II, Frontend": "software-engineer",
            "Software Engineer, Applied AI Infrastructure": "ai-engineer",
            "AI Software Engineer II": "ai-engineer",
            "AI/ML Engineer": "ai-engineer",
            "Site Reliability Engineer, AI Infrastructure (Starshield)": None,
            "GNC Engineer - Embedded Controls, AI Satellites (Starmind)": None,
            "AI Marketing Engineer": None,
            "Threat Research Engineer, Security Factory": None,
            "IT Systems Engineer": None,
            "People Systems Engineer": None,
            "Platform Engineer - Commercial Services Tools": "software-engineer",
            "Technical Operations & Insights Analyst": None,  # operations analysts are a different job (fourth audit)
            "Software Engineer 3": None,
            "Software Engineer 3, Identity and Access Management": None,
            "Forward Deployed Software Engineer - US Government": None,
            "AI Forward Deployed Engineer - Germany": None,
            "Billing Operations Analyst 1": None,
            "Procurement Operations Analyst": None,
            "Software Engineer II, Data Analytics & Engineering": "software-engineer",
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

    def test_titles_from_the_independent_review(self):
        cases = {
            # newly matched
            "Software Engineering Intern": "software-engineer",
            "Software Engineering Internship, Summer 2027": "software-engineer",
            "Software Development Engineer": "software-engineer",
            "Data Analytics Intern": "data-analyst",
            "Engineer, Backend": "software-engineer",
            "Engineer, Frontend Platform": "software-engineer",
            # team names are not seniority
            "Software Engineer, Staff Tools": "software-engineer",
            "Software Engineer, Lead Generation": "software-engineer",
            "Software Engineer, Head Unit": "software-engineer",
            "Member of Technical Staff": "software-engineer",
            # seniority before the role noun, or right after it
            "Staff Software Engineer": None,
            "Lead Engineer": None,
            "Head of Engineering": None,
            "Software Engineering Manager": None,
            "Manager, Software Engineering": None,
            "Software Engineer Lead": None,
            "Senior Member of Technical Staff": None,
            # contract work is a different arrangement
            "Contract Student Worker - Software Engineer (40hrs/wk)": None,
            "Software Engineer, Gameplay - Unpublished R&D Product (Contract)": None,
            "Contract  Student Worker - Data Analyst (Part-time)": None,
            "Contract Student Worker \u2013 AI Validation and Benchmarking Engineer (40hrs / week Full-Time)": None,
            # different jobs from general software engineering
            "Embedded Software Engineer (Starlink)": None,
            "Embedded Software Engineer (Firmware) - DoorDash Air": None,
            "Flight Software Engineer": None,
            "Software Engineer, Flight Software (Starlink)": None,
            "Full Stack Software Engineer, Flight Software": "software-engineer",
            "RF Software Engineer (Starlink)": None,
            "Salesforce Software Engineer": None,
            "Demo Software Engineer (f/m/d)": None,
            "Front End Engineer, Marketing": None,
            "Intern, Software Engineer, SDET, Summer 2027": None,
            "Software Engineer in Test": None,
            # AI engineer: research titles need an AI/ML term
            "Research Engineer": None,
            "Research Engineer, Discovery": None,
            "Research Engineer, Pretraining Scaling": "ai-engineer",
            "Research Engineer, Code RL (Reinforcement Learning)": "ai-engineer",
            "Applied Scientist": None,
            "Applied Scientist II - Advertiser Optimization": None,
            "AI Applied Scientist": "ai-engineer",
            "Applied AI, Research Engineer": "ai-engineer",
            "AI Security Research & Red Team Engineer": None,
            "AI Growth Engineer": None,
            "People Analytics AI Engineer": None,
            "AI Engineer, Customer Success": None,
            "Systems Research Engineer, GPU Programming": None,
            "Machine Learning Engineer II - Growth & Personalisation": "ai-engineer",
            "Research Engineer, Cybersecurity RL": "ai-engineer",
        }
        for title, expected in cases.items():
            self.assertEqual(self.classifier.classify(title), expected, title)

    def test_titles_from_the_fourth_audit(self):
        cases = {
            # data analyst: operations, master data, customer success, finance and mid-level are other jobs
            "Business Analyst, Operations": None,
            "Master Data Analyst": None,
            "Business Analyst (Customer Success)": None,
            "Finance Data Analyst Intern": None,
            "Business Analyst (Mid-level)": None,
            "Product Data Analyst": "data-analyst",
            "Business Analyst (Growth)": "data-analyst",
            # AI engineer: consulting and internal enablement are not building models
            "Applied AI Engineer - Technology Consultant": None,
            "AI Enablement Engineer": None,
            "Applied AI Engineer": "ai-engineer",
            # level 3 and above in parentheses
            "Machine Learning Engineer (L3)": None,
            "Machine Learning Engineer (L2)": "ai-engineer",
            # ambiguous AI systems titles need a software or ML word
            "AI Systems Engineer (f/m/d)": None,
            "AI Infrastructure System Engineer": None,
            "AI Infrastructure Systems Engineer": None,
            "AI Infrastructure Software Engineer": "ai-engineer",
            "Machine Learning Infrastructure Engineer": "ai-engineer",
            "ML Systems Engineer": "ai-engineer",
            "AI Systems Software Engineer": "ai-engineer",
        }
        for title, expected in cases.items():
            self.assertEqual(self.classifier.classify(title), expected, title)

    def test_level(self):
        self.assertEqual(self.classifier.level("Software Engineer, New Grad"), "entry")
        self.assertEqual(self.classifier.level("Data Analyst Intern"), "entry")
        self.assertEqual(self.classifier.level("Software Engineer"), "open")

    def test_level_one_titles_are_entry_and_level_two_is_not(self):
        entry = ["Software Engineer I", "Software Engineer I, Payments", "Software Engineer 1 - Cloud Infrastructure",
                 "Software Engineer-1, Money Movement", "Machine Learning Engineer 1", "Software Engineer Grad 2027",
                 "University Grad Software Engineer 2027 (USA)", "[2027] Software Engineer, Early Career",
                 "Software Engineer \u2160"]
        not_entry = ["Software Engineer II", "Software Engineer 2", "Software Engineer II, Backend",
                     "Software Engineer in Test", "Machine Learning Engineer 2", "Software Engineer, Infrastructure",
                     "Software Engineer 10x"]
        for title in entry:
            self.assertEqual(self.classifier.level(title), "entry", title)
        for title in not_entry:
            self.assertEqual(self.classifier.level(title), "open", title)

    def test_advanced_degree(self):
        for title in ("PhD Intern, Software Engineer - Graphics (2027)", "2027 Summer Intern, MS/PhD, Software Engineer",
                      "Master's Machine Learning Engineer, Intern", "Systems PhD - Software Engineer"):
            self.assertTrue(self.classifier.advanced_degree(title), title)
        for title in ("Software Engineer Intern", "2027 Summer Intern, BS/MS/PhD, Software Engineer, Eval Data Infra",
                      "Production Master Data Analyst"):
            self.assertFalse(self.classifier.advanced_degree(title), title)


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

    def test_board_company_name_wins_over_our_label(self):
        payload = {"jobs": [dict(GREENHOUSE_PAYLOAD["jobs"][0], company_name="Good Company, Inc.")]}
        collect.http_json = lambda url, timeout=30: payload
        found, report = collect.collect([{"name": "goodco", "source": "greenhouse", "board": "goodco"}],
                                        self.classifier, self.matcher, "2026-11-21", pause=0)
        self.assertEqual(found["software-engineer"][0]["company"], "Good Company, Inc.")
        self.assertEqual(report[0]["api_name"], "Good Company, Inc.")

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


def posting(key, company, title, skills, level="open", last_seen="2026-11-21", **extra):
    return dict({"key": key, "company": company, "title": title, "url": "https://e.x", "location": None,
                 "level": level, "first_seen": "2026-11-01", "last_seen": last_seen, "skills": skills}, **extra)


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self._real = collect.http_json
        self._pause = collect.RETRY_PAUSE
        collect.RETRY_PAUSE = 0

    def tearDown(self):
        collect.http_json = self._real
        collect.RETRY_PAUSE = self._pause

    def test_wrong_payload_shape_is_reported_not_counted_as_ok(self):
        classifier, matcher = collect.RoleClassifier(ROLES), collect.SkillMatcher(SKILLS)
        collect.http_json = lambda url, timeout=30: {"error": "rate limited"} if "greenhouse" in url else {"ok": True}
        companies = [{"name": "G", "source": "greenhouse", "board": "g"}, {"name": "L", "source": "lever", "board": "l"}]
        _, report = collect.collect(companies, classifier, matcher, "2026-11-21", pause=0)
        self.assertEqual([r["status"] for r in report], ["bad_payload", "bad_payload"])
        with self.assertRaises(collect.BadPayload):
            collect.http_json = lambda url, timeout=30: []
            collect.fetch_greenhouse("x")

    def test_http_json_retries_once_on_429_5xx_and_timeouts(self):
        real_open = collect.urllib.request.urlopen
        calls = []

        def run(errors):
            calls.clear()

            def fake_open(request, timeout=30):
                calls.append(request.full_url)
                if len(calls) <= len(errors):
                    raise errors[len(calls) - 1]
                return io.BytesIO(b'{"jobs": []}')
            collect.urllib.request.urlopen = fake_open
            return collect.http_json("https://example.com/x")

        def http(code):
            return collect.urllib.error.HTTPError("https://example.com/x", code, "x", None, None)

        try:
            self.assertEqual(run([http(429)]), {"jobs": []})
            self.assertEqual(len(calls), 2)
            self.assertEqual(run([http(503)]), {"jobs": []})
            self.assertEqual(run([socket.timeout("slow")]), {"jobs": []})
            self.assertEqual(run([collect.urllib.error.URLError(TimeoutError("slow"))]), {"jobs": []})
            with self.assertRaises(collect.urllib.error.HTTPError):
                run([http(404)])                     # not retried
            self.assertEqual(len(calls), 1)
            with self.assertRaises(collect.urllib.error.HTTPError):
                run([http(500), http(500)])          # only one retry
            self.assertEqual(len(calls), 2)
        finally:
            collect.urllib.request.urlopen = real_open

    def test_health_check_refuses_a_run_that_read_far_fewer_boards(self):
        before = {"boards": [{"source": "greenhouse", "board": f"b{i}", "status": "ok"} for i in range(10)]}
        now = [{"source": "greenhouse", "board": f"b{i}", "status": "ok" if i < 5 else "error"} for i in range(10)]
        healthy, message = collect.check_health(before, now)
        self.assertFalse(healthy)
        self.assertIn("5 of the 10", message)
        now = [{"source": "greenhouse", "board": f"b{i}", "status": "ok" if i < 6 else "error"} for i in range(10)]
        self.assertTrue(collect.check_health(before, now)[0])
        self.assertTrue(collect.check_health(None, now)[0])
        self.assertFalse(collect.check_health(None, [{"source": "lever", "board": "x", "status": "error"}])[0])

    def test_dump_json_replaces_the_file_in_one_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            collect.dump_json(path, {"a": 1})
            collect.dump_json(path, {"a": 2})
            self.assertEqual(json.loads(path.read_text()), {"a": 2})
            self.assertEqual(os.listdir(tmp), ["a.json"])  # no temporary file left behind


class PruneCompaniesTests(unittest.TestCase):
    def run_prune(self, companies, boards, ran_at="2026-11-28T09:00:00+00:00", pruned_run=None):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir, data_dir = Path(tmp) / "config", Path(tmp) / "data"
            config = {"_comment": "c", "companies": companies}
            if pruned_run:
                config["pruned_run"] = pruned_run
            collect.dump_json(config_dir / "companies.json", config)
            ok = sum(1 for b in boards if b["status"] == "ok")
            collect.dump_json(data_dir / "run_report.json", {"ran_at": ran_at, "boards_ok": ok, "boards": boards})
            real = collect.CONFIG, collect.DATA
            collect.CONFIG, collect.DATA = config_dir, data_dir
            try:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = collect.cmd_prune_companies(None)
            finally:
                collect.CONFIG, collect.DATA = real
            return code, json.loads((config_dir / "companies.json").read_text())

    @staticmethod
    def boards(statuses):
        return [{"source": "greenhouse", "board": f"b{i}", "status": s, "jobs": 3 if s == "ok" else 0}
                for i, s in enumerate(statuses)]

    def test_a_board_is_dropped_only_after_two_misses_in_a_row(self):
        companies = [{"name": f"B{i}", "source": "greenhouse", "board": f"b{i}", "checked": None} for i in range(8)]
        companies[1]["misses"] = 1
        code, config = self.run_prune(companies, self.boards(["ok", "not_found", "not_found", "error"] + ["ok"] * 4))
        self.assertEqual(code, 0)
        by_board = {c["board"]: c for c in config["companies"]}
        self.assertNotIn("b1", by_board)                 # second miss in a row
        self.assertEqual(by_board["b2"]["misses"], 1)    # first miss: kept
        self.assertIn("b3", by_board)                    # an error is not a miss
        self.assertEqual(by_board["b0"]["checked"], "2026-11-28")
        self.assertEqual(config["pruned_run"], "2026-11-28T09:00:00+00:00")

    def test_refuses_after_an_outage_or_a_second_time(self):
        companies = [{"name": f"B{i}", "source": "greenhouse", "board": f"b{i}"} for i in range(5)]
        code, config = self.run_prune(companies, self.boards(["ok", "ok", "error", "error", "not_found"]))
        self.assertEqual(code, 1)
        self.assertEqual(len(config["companies"]), 5)
        code, _ = self.run_prune(companies, self.boards(["ok"] * 5), pruned_run="2026-11-28T09:00:00+00:00")
        self.assertEqual(code, 1)


class RulesVersionTests(unittest.TestCase):
    def test_rules_version_changes_with_the_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "roles.json").write_text("{}")
            (d / "taxonomy.json").write_text("{}")
            first = collect.rules_version(d)
            self.assertEqual(first, collect.rules_version(d))
            (d / "taxonomy.json").write_text('{"skills": []}')
            self.assertNotEqual(first, collect.rules_version(d))
        self.assertRegex(collect.rules_version(), r"^[0-9a-f]{12}$")

    def test_merge_drops_closed_postings_made_under_other_rules(self):
        old = [
            posting("k:1", "A", "Software Engineer", ["python"], last_seen="2026-11-14", rules="old"),
            posting("k:2", "A", "Backend Engineer", ["go"], last_seen="2026-11-14", rules="new"),
            posting("k:3", "A", "Frontend Engineer", ["react"], last_seen="2026-11-14"),   # no rules field
            posting("k:4", "A", "Platform Engineer", ["go"], last_seen="2026-11-14"),
        ]
        new = [posting("k:4", "A", "Platform Engineer", ["go", "kubernetes"], rules="new")]
        merged = collect.merge(old, new, "2026-11-21", rules="new")
        self.assertEqual([p["key"] for p in merged], ["k:2", "k:4"])
        self.assertEqual(merged[1]["first_seen"], "2026-11-01")
        # Without a rules version (as build does), nothing is dropped for it.
        self.assertEqual(len(collect.merge(old, [], "2026-11-21")), 4)

    def test_collect_records_rules_and_matches_the_body_only(self):
        classifier, matcher = collect.RoleClassifier(ROLES), collect.SkillMatcher(SKILLS)
        real = collect.http_json
        collect.http_json = lambda url, timeout=30: {"jobs": [
            {"id": 1, "title": "Software Engineer, Data Model", "absolute_url": "https://e.x/1",
             "content": "&lt;p&gt;You will write Python.&lt;/p&gt;"}]}
        try:
            found, _ = collect.collect([{"name": "A", "source": "greenhouse", "board": "a"}], classifier, matcher,
                                       "2026-11-21", pause=0, rules="abc")
        finally:
            collect.http_json = real
        self.assertEqual(found["software-engineer"][0]["skills"], ["python"])   # not data-modeling
        self.assertEqual(found["software-engineer"][0]["rules"], "abc")


class AggregateTests(unittest.TestCase):
    def test_counts_shares_and_tiers(self):
        postings = [posting(f"x:{i}", "A" if i < 6 else "B", f"Software Engineer, Team {chr(65 + i)}",
                            ["python"] + (["sql"] if i < 2 else []) + (["go"] if i in (0, 6) else []),
                            "entry" if i in (0, 6) else "open") for i in range(10)]
        postings += [posting(f"y:{i}", c, "Software Engineer", ["java"]) for i, c in enumerate("CDEFGHIJ")]
        role = {"id": "software-engineer", "title": "Software Engineer", "blurb": "x"}
        agg = collect.aggregate(role, postings, SKILLS)
        self.assertEqual((agg["postings"], agg["companies"], agg["entry_postings"], agg["entry_companies"]),
                         (18, 10, 2, 2))
        self.assertEqual((agg["top_company"], agg["top_company_share"]), ("A", 33.3))
        self.assertFalse(agg["demo"])
        rows = {r["id"]: r for r in agg["skills"]}
        self.assertEqual([r["id"] for r in agg["skills"]][:2], ["java", "python"])   # most companies first
        java, python, sql, go = rows["java"], rows["python"], rows["sql"], rows["go"]
        self.assertEqual((java["count"], java["pct"], java["companies"], java["company_pct"], java["tier"]),
                         (8, 44.4, 8, 80.0, "most"))
        self.assertEqual((python["count"], python["pct"], python["companies"], python["company_pct"], python["tier"]),
                         (10, 55.6, 2, 20.0, "some"))
        # tier follows the company share: 1 of 10 companies is "some", though 2 of 18 postings
        self.assertEqual((sql["count"], sql["companies"], sql["company_pct"], sql["tier"], sql["entry_count"],
                          sql["entry_companies"]), (2, 1, 10.0, "some", 1, 1))
        self.assertEqual((go["entry_count"], go["entry_companies"]), (2, 2))

    def test_phd_postings_count_in_totals_not_in_entry(self):
        postings = [
            posting("x:1", "A", "Software Engineer Intern", ["python"], "entry"),
            posting("x:2", "B", "PhD Intern, Software Engineer - Graphics (2027)", ["python", "cpp"], "entry"),
            posting("x:3", "C", "2027 Summer Intern, MS/PhD, Software Engineer", ["cpp"], "entry"),
        ]
        agg = collect.aggregate({"id": "software-engineer", "title": "T", "blurb": "b"}, postings, SKILLS)
        self.assertEqual((agg["postings"], agg["entry_postings"], agg["entry_companies"]), (3, 1, 1))
        rows = {r["id"]: r for r in agg["skills"]}
        self.assertEqual((rows["cpp"]["count"], rows["cpp"]["entry_count"], rows["cpp"]["entry_companies"]), (2, 0, 0))
        self.assertEqual(rows["python"]["entry_count"], 1)
        self.assertEqual([s["phd"] for s in agg["sample"]], [False, True, True])

    def test_same_title_at_same_company_counts_once(self):
        postings = [
            posting("x:1", "A", "Software Engineer", ["python"]),
            posting("x:2", "A", "Software  engineer", ["python"]),   # same job, second location
            posting("x:3", "A", "Backend Engineer", ["go"]),
            posting("x:4", "B", "Software Engineer", ["java"]),
        ]
        agg = collect.aggregate({"id": "software-engineer", "title": "T", "blurb": "b"}, postings, SKILLS)
        self.assertEqual((agg["listings"], agg["postings"], agg["companies"]), (4, 3, 2))
        self.assertEqual({s["id"]: s["count"] for s in agg["skills"]}, {"python": 1, "go": 1, "java": 1})

    def test_titles_normalised_before_deduplication(self):
        same = [
            ("Software Engineer Intern, Backend (Summer 2027 - Mexico)", "Software Engineer Intern, Backend (Summer 2027 - Toronto)"),
            ("Software Engineer Intern, Backend (Summer 2027 - Mexico/Montreal/SF/Toronto)", "Software Engineer Intern, Backend (Summer 2027)"),
            ("Software Engineer Intern (2027) - Austin, TX", "Software Engineer Intern (2027) - London, UK"),
            ("Software Engineer - New Grad (2027 Start) - Aarhus", "Software Engineer - New Grad (2027 Start) - London"),
            ("Software Engineer (London)", "Software Engineer (Remote)"),
            ("Software Engineer  (Remote Eligible in Bulgaria)", "Software Engineer"),
            ("Demo Software Engineer (f/m/d)", "Demo Software Engineer (M/F/X)"),
            ("Research Engineer, Pretraining Scaling - London", "Research Engineer, Pretraining Scaling"),
            ("Software Engineer – Remote", "Software Engineer — NYC"),
            ("Software Engineer - Figma Weave (Tel Aviv, Israel)", "Software Engineer - Figma Weave"),
        ]
        different = [
            ("Software Engineer, Payments", "Software Engineer, Search"),
            ("Software Engineer - Backend", "Software Engineer - Frontend"),
            ("Software Engineer (Starlink)", "Software Engineer (Starshield)"),
            ("Software Engineer Intern (Summer 2027)", "Software Engineer Intern (Winter 2027)"),
            ("Software Engineer - Edge", "Software Engineer"),
        ]
        for a, b in same:
            self.assertEqual(collect.normalize_title(a), collect.normalize_title(b), (a, b))
        for a, b in different:
            self.assertNotEqual(collect.normalize_title(a), collect.normalize_title(b), (a, b))

    def test_collapsed_listings_merge_skills_dates_and_level(self):
        postings = [
            posting("x:1", "A", "Software Engineer Intern, Backend (Summer 2027 - Mexico)", ["python"], "open", "2026-11-01"),
            posting("x:2", "A", "Software Engineer Intern, Backend (Summer 2027 - Toronto)", ["go"], "entry", "2026-11-21"),
            posting("x:3", "A", "Software Engineer, Payments", ["java"]),
            posting("x:4", "A", "Software Engineer, Search", ["java"]),
        ]
        merged = collect.distinct(postings)
        self.assertEqual(len(merged), 3)
        intern = next(p for p in merged if "Intern" in p["title"])
        self.assertEqual((intern["skills"], intern["last_seen"], intern["level"]), (["python", "go"], "2026-11-21", "entry"))

    def test_stored_postings_move_to_the_role_their_title_now_belongs_to(self):
        classifier = collect.RoleClassifier(ROLES)
        stored = {
            "data-analyst": [posting("x:1", "A", "Data Analyst", ["sql"]),
                             posting("x:2", "A", "Procurement Operations Analyst", ["excel"]),
                             posting("demo:1", "Demo Company A", "Anything", [])],
            "software-engineer": [posting("x:3", "A", "Software Engineer, Machine Learning", ["python"]),
                                  posting("x:4", "A", "Software Engineer I", ["go"]),
                                  posting("x:1", "A", "Data Analyst", ["sql"], last_seen="2026-10-01")],
            "ai-engineer": [posting("x:5", "A", "Research Engineer", ["python"])],
        }
        out = collect.reassign(stored, classifier)
        self.assertEqual([p["key"] for p in out["data-analyst"]], ["x:1", "demo:1"])
        self.assertEqual(out["data-analyst"][0]["last_seen"], "2026-11-21")    # newest copy of a duplicate key
        self.assertEqual([p["key"] for p in out["ai-engineer"]], ["x:3"])     # moved, not deleted
        self.assertEqual([p["key"] for p in out["software-engineer"]], ["x:4"])
        self.assertEqual(out["software-engineer"][0]["level"], "entry")        # level recomputed

    def test_build_writes_the_output_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = collect.CONFIG, collect.DATA, collect.SITE_DATA, collect.SKILL_DATA
            for name in ("roles.json", "taxonomy.json"):
                (root / "config").mkdir(exist_ok=True)
                (root / "config" / name).write_text((ROOT / "config" / name).read_text())
            collect.dump_json(root / "data" / "postings" / "software-engineer.json", [
                posting("x:1", "A", "Software Engineer", ["python", "communication", "cross-functional"]),
                posting("x:2", "B", "Software Engineer Intern", ["python", "go"], "entry"),
                posting("x:3", "B", "Software Engineer, Machine Learning", ["pytorch"]),
            ])
            collect.CONFIG, collect.DATA = root / "config", root / "data"
            collect.SITE_DATA, collect.SKILL_DATA = root / "docs", root / "skill"
            try:
                index = collect.build_site_data("2026-11-21T00:00:00+00:00")
                role = json.loads((root / "docs" / "roles" / "software-engineer.json").read_text())
                moved = json.loads((root / "data" / "postings" / "ai-engineer.json").read_text())
            finally:
                collect.CONFIG, collect.DATA, collect.SITE_DATA, collect.SKILL_DATA = real
        se = next(r for r in index["roles"] if r["id"] == "software-engineer")
        self.assertEqual((se["postings"], se["companies"], se["entry_postings"], se["entry_companies"]), (2, 2, 1, 1))
        self.assertEqual(se["top_skills"][0], {"name": "Python", "pct": 100.0, "company_pct": 100.0})
        self.assertNotIn("Written & verbal communication", [s["name"] for s in se["top_skills"]])
        self.assertEqual((role["top_company"], role["top_company_share"]), ("A", 50.0))
        for key in ("count", "pct", "company_pct", "tier", "companies", "entry_count", "entry_companies"):
            self.assertIn(key, role["skills"][0])
        self.assertEqual([p["key"] for p in moved], ["x:3"])

    def test_empty_role(self):
        agg = collect.aggregate({"id": "r", "title": "R", "blurb": "b"}, [], SKILLS)
        self.assertEqual((agg["postings"], agg["skills"], agg["top_company"], agg["entry_companies"]), (0, [], None, 0))

    def test_tier_edges(self):
        self.assertEqual([collect.tier_for(x) for x in (60, 59.9, 30, 29.9, 10, 9.9)],
                         ["most", "many", "many", "some", "some", "rare"])


if __name__ == "__main__":
    unittest.main()
