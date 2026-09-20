"""Build the JSON data files used by the app from the editable text sources in data_src/.

    python scripts/build_data.py

Outputs (all in data/):
  taxonomy.json       skills, aliases, prerequisites, implies, families, not-related pairs
  paths.json          per-skill learning modules (terms/definitions, practice, project, repo rubric)
  knowledge/*.md      one markdown study note per skill (loaded by the RAG pipeline)
  resources.json      learning resources (YouTube / Coursera / NPTEL / Skill India / docs / practice)
  jobs.json           curated job postings as FREE TEXT (parsed later by the Job Parsing Agent)
  eval/job_gold.json  the structured truth behind every posting (used to evaluate the job parser)
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SRC = ROOT / "data_src"
DATA = ROOT / "data"

from core.models import slugify  # noqa: E402

# --------------------------------------------------------------------------------------------
# 1. taxonomy
# --------------------------------------------------------------------------------------------

def build_taxonomy() -> dict:
    rows, families, not_related = [], [], []
    section = "skills"
    for raw in (SRC / "taxonomy.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            section = line[1:].strip()
            continue
        if section == "skills":
            f = [x.strip() for x in line.split("|")]
            if len(f) < 7:
                raise ValueError(f"bad taxonomy row: {line}")
            rows.append(f)
        elif section == "families":
            name, credit, members = [x.strip() for x in line.split(":", 2)]
            families.append({"name": name, "credit": float(credit), "members": [m.strip() for m in members.split(",")]})
        elif section == "not_related":
            a, b = [x.strip() for x in line.split(":")]
            not_related.append([a, b])
    name_to_id = {r[0]: slugify(r[0]) for r in rows}
    skills = {}
    for name, cat, aliases, prereqs, effort, implies, desc in rows:
        ext, norm = [], []
        for a in [x.strip() for x in aliases.split(",") if x.strip()]:
            (norm if a.startswith("~") else ext).append(a.lstrip("~").strip())
            if a.startswith("~"):
                pass
        sid = name_to_id[name]
        skills[sid] = {
            "id": sid, "name": name, "category": cat,
            "aliases": sorted(set(ext)), "norm_aliases": sorted(set(norm)),
            "prereqs": [name_to_id[p.strip()] for p in prereqs.split(",") if p.strip()],
            "effort_days": float(effort),
            "implies": [name_to_id[p.strip()] for p in implies.split(",") if p.strip()],
            "description": desc,
        }
    for fam in families:
        fam["members"] = [name_to_id[m] for m in fam["members"]]
    nr = [[name_to_id[a], name_to_id[b]] for a, b in not_related]
    out = {"skills": skills, "families": families, "not_related": nr}
    (DATA / "taxonomy.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"taxonomy: {len(skills)} skills, {len(families)} families")
    return out


# --------------------------------------------------------------------------------------------
# 2. learning paths + knowledge notes
# --------------------------------------------------------------------------------------------

def parse_paths(tax: dict) -> dict:
    name_to_id = {s["name"]: sid for sid, s in tax["skills"].items()}
    paths: dict[str, dict] = {}
    cur = None
    for fname in ("paths.txt", "paths_extra.txt"):
        for raw in (SRC / fname).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                nm = line[1:].strip()
                if nm not in name_to_id:
                    raise ValueError(f"unknown skill in paths: {nm}")
                cur = paths.setdefault(name_to_id[nm], {"modules": [], "project": "", "check_files": [], "check_keywords": []})
            elif line.startswith("project:"):
                cur["project"] = line.split(":", 1)[1].strip()
            elif line.startswith("check_files:"):
                cur["check_files"] = [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
            elif line.startswith("check_keywords:"):
                cur["check_keywords"] = [x.strip().lower() for x in line.split(":", 1)[1].split(",") if x.strip()]
            elif line.startswith("M:"):
                title, terms, practice = [x.strip() for x in line[2:].split("||")]
                tlist = []
                for chunk in terms.split(";"):
                    if ": " not in chunk:
                        raise ValueError(f"term without definition in '{title}': {chunk}")
                    t, d = chunk.split(": ", 1)
                    tlist.append({"term": t.strip(), "definition": d.strip()})
                cur["modules"].append({"title": title, "terms": tlist, "practice": practice})
    missing = [s for s in tax["skills"] if s not in paths]
    print(f"paths: {len(paths)} skills, {sum(len(p['modules']) for p in paths.values())} modules; missing: {missing}")
    (DATA / "paths.json").write_text(json.dumps(paths, indent=1, ensure_ascii=False), encoding="utf-8")
    return paths


def write_knowledge(tax: dict, paths: dict) -> None:
    kdir = DATA / "knowledge"
    kdir.mkdir(exist_ok=True)
    for f in kdir.glob("*.md"):
        f.unlink()
    for sid, p in paths.items():
        s = tax["skills"][sid]
        lines = [f"# {s['name']}", "", f"> {s['description']}.", f"> Category: {s['category']}. Typical effort: about {int(s['effort_days'])} study days.", ""]
        for m in p["modules"]:
            lines.append(f"## {m['title']}")
            lines.append("")
            for t in m["terms"]:
                lines.append(f"- **{t['term']}** — {t['definition']}.")
            lines.append("")
            lines.append(f"Practice: {m['practice']}.")
            lines.append("")
        lines += ["## Mini project", "", f"{p['project']}.", ""]
        (kdir / f"{sid}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"knowledge: {len(paths)} markdown notes")


# --------------------------------------------------------------------------------------------
# 3. resources
# --------------------------------------------------------------------------------------------

DOCS = {
    "docker": "https://docs.docker.com/get-started/", "kubernetes": "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
    "git": "https://git-scm.com/book/en/v2", "linux": "https://linuxjourney.com/", "react": "https://react.dev/learn",
    "angular": "https://angular.dev/tutorials", "nodejs": "https://nodejs.org/en/learn/getting-started/introduction-to-nodejs",
    "expressjs": "https://expressjs.com/en/starter/installing.html", "django": "https://docs.djangoproject.com/en/stable/intro/tutorial01/",
    "flask": "https://flask.palletsprojects.com/en/stable/quickstart/", "fastapi": "https://fastapi.tiangolo.com/tutorial/",
    "spring_boot": "https://spring.io/guides/gs/rest-service/", "rest_api": "https://developer.mozilla.org/en-US/docs/Web/HTTP",
    "html_css": "https://developer.mozilla.org/en-US/docs/Learn_web_development", "python": "https://docs.python.org/3/tutorial/",
    "java": "https://dev.java/learn/", "javascript": "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting",
    "typescript": "https://www.typescriptlang.org/docs/handbook/intro.html", "go": "https://go.dev/doc/tutorial/",
    "sql": "https://www.postgresql.org/docs/current/tutorial-sql.html", "postgresql": "https://www.postgresql.org/docs/current/tutorial.html",
    "mysql": "https://dev.mysql.com/doc/refman/8.0/en/tutorial.html", "mongodb": "https://www.mongodb.com/docs/manual/tutorial/getting-started/",
    "redis": "https://redis.io/docs/latest/", "aws": "https://aws.amazon.com/getting-started/",
    "azure": "https://learn.microsoft.com/en-us/training/azure/", "gcp": "https://cloud.google.com/docs/get-started",
    "terraform": "https://developer.hashicorp.com/terraform/tutorials", "ci_cd": "https://docs.github.com/en/actions/quickstart",
    "pandas": "https://pandas.pydata.org/docs/user_guide/10min.html", "numpy": "https://numpy.org/doc/stable/user/absolute_beginners.html",
    "machine_learning": "https://scikit-learn.org/stable/getting_started.html", "tensorflow_pytorch": "https://pytorch.org/tutorials/beginner/basics/intro.html",
    "power_bi": "https://learn.microsoft.com/en-us/power-bi/fundamentals/", "tableau": "https://www.tableau.com/learn/training",
    "selenium": "https://www.selenium.dev/documentation/webdriver/getting_started/", "api_testing": "https://learning.postman.com/docs/getting-started/overview/",
    "llms_genai": "https://ai.google.dev/gemini-api/docs", "nlp": "https://huggingface.co/learn/nlp-course", "mlops": "https://mlflow.org/docs/latest/",
    "graphql": "https://graphql.org/learn/", "bash": "https://www.gnu.org/software/bash/manual/bash.html",
    "design_patterns": "https://refactoring.guru/design-patterns", "system_design": "https://github.com/donnemartin/system-design-primer",
    "agile": "https://scrumguides.org/", "bootstrap_tailwind": "https://tailwindcss.com/docs/installation",
    "vuejs": "https://vuejs.org/guide/introduction.html", "nextjs": "https://nextjs.org/learn", "kotlin": "https://kotlinlang.org/docs/getting-started.html",
    "flutter": "https://docs.flutter.dev/get-started", "android_development": "https://developer.android.com/courses",
    "cpp": "https://en.cppreference.com/w/", "c": "https://en.cppreference.com/w/c", "excel": "https://support.microsoft.com/en-us/excel",
    "statistics": "https://www.khanacademy.org/math/statistics-probability", "aspnet": "https://learn.microsoft.com/en-us/aspnet/core/tutorials/",
    "csharp": "https://learn.microsoft.com/en-us/dotnet/csharp/tour-of-csharp/", "monitoring": "https://prometheus.io/docs/introduction/overview/",
    "unit_testing": "https://junit.org/junit5/docs/current/user-guide/", "cybersecurity": "https://owasp.org/www-project-top-ten/",
    "computer_vision": "https://docs.opencv.org/4.x/d9/df8/tutorial_root.html", "big_data": "https://spark.apache.org/docs/latest/quick-start.html",
    "message_queues": "https://kafka.apache.org/documentation/#gettingStarted", "hibernate_jpa": "https://spring.io/guides/gs/accessing-data-jpa/",
    "redux": "https://redux-toolkit.js.org/tutorials/quick-start", "etl": "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/index.html",
    "r": "https://cran.r-project.org/manuals.html",
}
CREATORS = {
    "python": ("Corey Schafer", "freeCodeCamp.org"), "java": ("Telusko", "Apna College"), "javascript": ("Traversy Media", "Hitesh Choudhary"),
    "typescript": ("Programming with Mosh", "Fireship"), "c": ("Neso Academy", "Jenny's Lectures"), "cpp": ("Apna College", "Abdul Bari"),
    "csharp": ("freeCodeCamp.org", "Tim Corey"), "go": ("freeCodeCamp.org", "TechWorld with Nana"), "kotlin": ("Philipp Lackner", "freeCodeCamp.org"),
    "sql": ("Alex The Analyst", "freeCodeCamp.org"), "bash": ("freeCodeCamp.org", "NetworkChuck"), "dsa": ("Abdul Bari", "take U forward"),
    "oop": ("Kunal Kushwaha", "Telusko"), "operating_systems": ("Gate Smashers", "Jenny's Lectures"), "computer_networks": ("Gate Smashers", "Neso Academy"),
    "dbms": ("Gate Smashers", "Knowledge Gate"), "system_design": ("Gaurav Sen", "ByteByteGo"), "design_patterns": ("Christopher Okhravi", "Derek Banas"),
    "git": ("Kunal Kushwaha", "freeCodeCamp.org"), "linux": ("NetworkChuck", "freeCodeCamp.org"), "agile": ("Simplilearn", "Atlassian"),
    "spring_boot": ("Amigoscode", "Telusko"), "rest_api": ("freeCodeCamp.org", "Postman"), "nodejs": ("Traversy Media", "Programming with Mosh"),
    "expressjs": ("Web Dev Simplified", "Traversy Media"), "django": ("Corey Schafer", "freeCodeCamp.org"), "flask": ("Corey Schafer", "Tech With Tim"),
    "fastapi": ("freeCodeCamp.org", "Bitfumes"), "hibernate_jpa": ("Amigoscode", "Telusko"), "microservices": ("Amigoscode", "TechWorld with Nana"),
    "graphql": ("The Net Ninja", "freeCodeCamp.org"), "authentication": ("Web Dev Simplified", "Traversy Media"),
    "message_queues": ("Hussein Nasser", "freeCodeCamp.org"), "aspnet": ("Tim Corey", "freeCodeCamp.org"), "html_css": ("Kevin Powell", "SuperSimpleDev"),
    "react": ("The Net Ninja", "Codevolution"), "angular": ("The Net Ninja", "Academind"), "vuejs": ("The Net Ninja", "Traversy Media"),
    "bootstrap_tailwind": ("Traversy Media", "The Net Ninja"), "redux": ("Codevolution", "Dave Gray"), "nextjs": ("freeCodeCamp.org", "Fireship"),
    "mysql": ("Programming with Mosh", "Bro Code"), "postgresql": ("freeCodeCamp.org", "Amigoscode"), "mongodb": ("Traversy Media", "freeCodeCamp.org"),
    "redis": ("freeCodeCamp.org", "Fireship"), "docker": ("TechWorld with Nana", "freeCodeCamp.org"), "kubernetes": ("TechWorld with Nana", "KodeKloud"),
    "ci_cd": ("TechWorld with Nana", "freeCodeCamp.org"), "aws": ("freeCodeCamp.org", "Be A Better Dev"), "azure": ("freeCodeCamp.org", "John Savill"),
    "gcp": ("freeCodeCamp.org", "Google Cloud Tech"), "terraform": ("freeCodeCamp.org", "TechWorld with Nana"), "monitoring": ("TechWorld with Nana", "freeCodeCamp.org"),
    "pandas": ("Corey Schafer", "Keith Galli"), "numpy": ("freeCodeCamp.org", "Keith Galli"), "data_visualization": ("Alex The Analyst", "freeCodeCamp.org"),
    "excel": ("Kevin Stratvert", "ExcelIsFun"), "power_bi": ("Guy in a Cube", "Alex The Analyst"), "tableau": ("Alex The Analyst", "Tableau"),
    "statistics": ("StatQuest with Josh Starmer", "Khan Academy"), "machine_learning": ("Krish Naik", "StatQuest with Josh Starmer"),
    "deep_learning": ("3Blue1Brown", "Andrej Karpathy"), "tensorflow_pytorch": ("freeCodeCamp.org", "Python Engineer"), "nlp": ("freeCodeCamp.org", "StatQuest with Josh Starmer"),
    "llms_genai": ("Andrej Karpathy", "freeCodeCamp.org"), "mlops": ("DataTalksClub", "Krish Naik"), "computer_vision": ("freeCodeCamp.org", "Murtaza's Workshop"),
    "etl": ("Seattle Data Guy", "freeCodeCamp.org"), "big_data": ("freeCodeCamp.org", "Edureka"), "data_warehousing": ("Seattle Data Guy", "Alex The Analyst"),
    "manual_testing": ("Software Testing Mentor", "Edureka"), "selenium": ("Raghav Pal", "Edureka"), "test_automation": ("Raghav Pal", "Execute Automation"),
    "api_testing": ("Postman", "Raghav Pal"), "unit_testing": ("Amigoscode", "Corey Schafer"), "cybersecurity": ("NetworkChuck", "freeCodeCamp.org"),
    "android_development": ("Philipp Lackner", "freeCodeCamp.org"), "flutter": ("freeCodeCamp.org", "The Net Ninja"), "r": ("freeCodeCamp.org", "Simplilearn"),
}
NPTEL = {"python", "java", "dsa", "oop", "operating_systems", "computer_networks", "dbms", "machine_learning", "deep_learning", "statistics", "c", "cpp",
         "nlp", "cybersecurity", "computer_vision", "big_data", "data_warehousing", "system_design", "sql", "design_patterns"}
SKILL_INDIA = {"python", "java", "javascript", "html_css", "sql", "excel", "power_bi", "tableau", "aws", "azure", "gcp", "cybersecurity",
               "data_visualization", "machine_learning", "git", "linux", "manual_testing", "android_development"}
PRACTICE = {"sql": "https://www.hackerrank.com/domains/sql", "python": "https://www.hackerrank.com/domains/python", "java": "https://www.hackerrank.com/domains/java",
            "c": "https://www.hackerrank.com/domains/c", "cpp": "https://www.hackerrank.com/domains/cpp", "bash": "https://www.hackerrank.com/domains/shell",
            "dsa": "https://leetcode.com/problemset/", "oop": "https://www.hackerrank.com/domains/java"}


def yt(q: str) -> str:
    return "https://www.youtube.com/results?search_query=" + quote_plus(q)


def build_resources(tax: dict, paths: dict) -> None:
    out = []
    for sid, s in tax["skills"].items():
        nm = s["name"]
        c1, c2 = CREATORS.get(sid, ("freeCodeCamp.org", "Traversy Media"))
        proj = paths.get(sid, {}).get("project", f"Build a small {nm} project")
        n = 0

        def add(**kw):
            nonlocal n
            n += 1
            kw.update({"id": f"{sid}-{n}", "skill": sid})
            out.append(kw)

        add(title=f"{nm} for beginners — {c1}", type="video", difficulty="beginner", duration_min=120, source="YouTube",
            url=yt(f"{c1} {nm} tutorial for beginners"), link_kind="search", creator=c1,
            why=f"A structured start on {nm} from a creator students trust; best when you are new to it or refreshing basics.")
        add(title=f"Build a {nm} project — {c2}", type="video", difficulty="intermediate", duration_min=90, source="YouTube",
            url=yt(f"{c2} {nm} project tutorial"), link_kind="search", creator=c2,
            why=f"Build-along video: you write a working {nm} project instead of only watching, which is what interviewers probe.")
        add(title=f"{nm} — official / reference documentation", type="docs", difficulty="intermediate", duration_min=60, source="Official documentation",
            url=DOCS.get(sid) or ("https://www.google.com/search?q=" + quote_plus(f"{nm} official documentation getting started")),
            link_kind="direct" if sid in DOCS else "search",
            why=f"Authoritative reference for exact behaviour; reading it builds the vocabulary used in {nm} job descriptions.")
        add(title=f"{nm} courses on Coursera", type="course", difficulty="beginner", duration_min=600, source="Coursera",
            url="https://www.coursera.org/search?query=" + quote_plus(nm), link_kind="search",
            why=f"Structured multi-week {nm} course with graded exercises and an optional certificate.")
        if sid in NPTEL:
            add(title=f"NPTEL / SWAYAM lectures relevant to {nm}", type="course", difficulty="intermediate", duration_min=900, source="NPTEL",
                url="https://nptel.ac.in/courses", link_kind="catalog",
                why=f"Free IIT/IISc lecture series; strong on the theory behind {nm} that campus and technical interviews test.")
        if sid in SKILL_INDIA:
            add(title=f"Skill India Digital Hub — {nm} related courses", type="course", difficulty="beginner", duration_min=480, source="Skill India",
                url="https://www.skillindiadigital.gov.in/", link_kind="catalog",
                why=f"Free government-backed digital skilling content with a completion certificate for {nm}.")
        add(title=f"{nm} practice exercises", type="practice", difficulty="beginner", duration_min=90,
            source="HackerRank / LeetCode" if sid in PRACTICE else "GitHub",
            url=PRACTICE.get(sid) or ("https://github.com/search?type=repositories&q=" + quote_plus(f"{nm} exercises beginner")),
            link_kind="direct" if sid in PRACTICE else "search",
            why=f"Small graded problems that turn {nm} concepts into muscle memory.")
        add(title=f"Mini project: {proj[:110]}", type="project", difficulty="intermediate", duration_min=180, source="GitHub",
            url="https://github.com/search?type=repositories&q=" + quote_plus(f"{nm} mini project"), link_kind="search",
            why="Portfolio-ready project that doubles as the practical verification task for this skill.")
        add(title=f"{nm} explained — freeCodeCamp articles", type="article", difficulty="beginner", duration_min=30, source="Technical blogs",
            url="https://www.freecodecamp.org/news/search/?query=" + quote_plus(nm), link_kind="search",
            why=f"Short read to consolidate {nm} between videos and to see the same idea explained differently.")
        add(title=f"{nm} in production — engineering talks", type="talk", difficulty="advanced", duration_min=45, source="YouTube",
            url=yt(f"{nm} conference talk best practices production"), link_kind="search",
            why=f"Advanced talk on real-world trade-offs with {nm}; watch after you can build the basics.")
    (DATA / "resources.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"resources: {len(out)}")


# --------------------------------------------------------------------------------------------
# 4. jobs (free text) + gold structure
# --------------------------------------------------------------------------------------------

LEVEL_PHRASES = {
    "s": ["strong proficiency in {x}", "deep hands-on expertise in {x}", "strong command of {x}", "advanced skills in {x}"],
    "m": ["working knowledge of {x}", "hands-on experience with {x}", "practical experience with {x}", "comfort building with {x}"],
    "b": ["basic understanding of {x}", "familiarity with {x}", "exposure to {x}", "basic awareness of {x}"],
}
PREF_HEADS = ["Nice to have:", "Good to have:", "Bonus points:", "Preferred:"]
REQ_HEADS = ["Must have:", "Requirements:", "What you'll need:", "Required skills:"]
BAD_VARIANTS = {"py", "ts", "jdk", "sh scripting", "c plus plus", "c plus-plus", "shell", "sh", "go lang", "rstudio", "kotlin android",
                "leetcode", "coding interview", "competitive programming", "acid transactions", "er diagrams", "normalization",
                "process scheduling", "osi model", "sdlc", "jira", "caching", "logging", "alerting", "elk", "state management",
                "context api", "server side rendering", "ssr", "pub/sub", "event driven", "nosql", "rest endpoints", "probability",
                "regression analysis", "a/b testing", "helm", "eks", "aks", "gke", "iam", "rds", "s3", "ec2", "bert", "yolo", "cnn", "rnn", "lstm",
                "kubectl", "scipy", "xgboost", "jsx", "drf", "vuex", "nuxt", "rxjs", "sso", "uat", "tdd", "stlc", "siem", "dax", "mocha", "jest"}


def cap(x: str) -> str:
    return x[:1].upper() + x[1:]


def join_and(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def surface(sid: str, tax, rng: random.Random) -> str:
    s = tax.get(sid)
    nm = s["name"]
    if rng.random() > 0.4:
        return nm
    cands = [a for a in s.get("aliases", []) if len(a) >= 4 and a.lower() not in BAD_VARIANTS and "/" not in a and "&" not in a and " and " not in a]
    rng.shuffle(cands)
    for a in cands:
        ms = tax.extract(a)
        if len(ms) == 1 and ms[0].skill_id == sid and ms[0].start == 0 and ms[0].end == len(a):
            return a
    return nm


def group_by_level(items: list[tuple[str, str]]) -> list[tuple[str, list[str]]]:
    order = ["s", "m", "b"]
    groups = []
    for lv in order:
        ids = [sid for sid, l in items if l == lv]
        if ids:
            groups.append((lv, ids))
    return groups


def render_job(row: dict, idx: int, tax) -> str:
    rng = random.Random(1000 + idx)
    template = idx % 3
    req_groups = group_by_level(row["required"])
    pref_groups = group_by_level(row["preferred"])

    def phrase(lv: str, ids: list[str]) -> str:
        names = [surface(i, tax, rng) for i in ids]
        return rng.choice(LEVEL_PHRASES[lv]).format(x=join_and(names))

    exp_min, exp_max = row["exp"]
    exp_txt = "Freshers and final-year students are welcome" if (exp_min, exp_max) == (0, 1) and idx % 2 == 0 else f"Experience: {exp_min}-{exp_max} years"
    if exp_txt.startswith("Fresh"):
        exp_txt += " (0-1 years)"
    edu_txt = "Eligibility: " + " / ".join(row["degrees"])
    head = f"{row['company']} is hiring a {row['title']} for our {row['city']} team ({row['mode']})."

    if template == 0:  # bullet lists with headings
        lines = [head, row["summary"], "", f"{exp_txt}. {edu_txt}.", "", rng.choice(REQ_HEADS)]
        for lv, ids in req_groups:
            lines.append("- " + cap(phrase(lv, ids)))
        lines += ["", rng.choice(PREF_HEADS)]
        for lv, ids in pref_groups:
            lines.append("- " + cap(phrase(lv, ids)))
        return "\n".join(lines)
    if template == 1:  # flowing prose
        req_sent = "You should have " + join_and([phrase(lv, ids) for lv, ids in req_groups]) + "."
        pref_sent = "It is a plus if you also bring " + join_and([phrase(lv, ids) for lv, ids in pref_groups]) + "."
        return "\n".join([head, "", f"About the role. {row['summary']}", "", f"What you bring: {req_sent}", pref_sent, "", f"{exp_txt}. {edu_txt}."])
    # template 2: 'Requirements' and 'Good to have' with sentence-style bullets
    lines = [head, "", "About the role:", row["summary"], "", "Requirements:"]
    for lv, ids in req_groups:
        lines.append("* " + cap(phrase(lv, ids)) + ".")
    lines += ["", "Good to have:"]
    for lv, ids in pref_groups:
        lines.append("* " + cap(phrase(lv, ids)) + ".")
    lines += ["", f"{exp_txt}. {edu_txt}."]
    return "\n".join(lines)


def build_jobs(tax_dict: dict) -> None:
    from core.taxonomy import Taxonomy

    class _T(Taxonomy):
        def get(self, sid):  # type: ignore[override]
            return self.skills[sid]

    tax = _T()
    name_to_id = {s["name"]: sid for sid, s in tax_dict["skills"].items()}
    jobs, gold = [], {}
    idx = 0
    for raw in (SRC / "jobs.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = [x.strip() for x in line.split("|")]
        if len(f) != 11:
            raise ValueError(f"bad job row ({len(f)} fields): {line}")
        title, company, city, mode, exp, degrees, domain, salary, req, pref, summary = f

        def split_skills(txt: str) -> list[tuple[str, str]]:
            out = []
            for part in txt.split(";"):
                part = part.strip()
                if not part:
                    continue
                nm, lv = part.rsplit(":", 1)
                out.append((name_to_id[nm.strip()], lv.strip()))
            return out

        emin, emax = [int(x) for x in exp.split("-")]
        row = {"title": title, "company": company, "city": city, "mode": mode, "exp": (emin, emax),
               "degrees": [d.strip() for d in degrees.split(",")], "required": split_skills(req),
               "preferred": split_skills(pref), "summary": summary}
        jid = f"J{idx + 1:02d}"
        text = render_job(row, idx, tax)
        jobs.append({"id": jid, "title": title, "company": company, "city": city, "mode": mode, "domain": domain,
                     "salary_lpa": float(salary), "description": text})
        gold[jid] = {"required": [{"skill": s, "level": {"b": 1, "m": 2, "s": 3}[l]} for s, l in row["required"]],
                     "preferred": [{"skill": s, "level": {"b": 1, "m": 2, "s": 3}[l]} for s, l in row["preferred"]],
                     "experience": [emin, emax], "degrees": row["degrees"]}
        idx += 1
    (DATA / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
    (DATA / "eval").mkdir(exist_ok=True)
    (DATA / "eval" / "job_gold.json").write_text(json.dumps(gold, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"jobs: {len(jobs)}")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    taxonomy = build_taxonomy()
    paths_ = parse_paths(taxonomy)
    write_knowledge(taxonomy, paths_)
    build_resources(taxonomy, paths_)
    build_jobs(taxonomy)
    print("done")
