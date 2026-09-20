import json

import pytest

from core import evaluation
from core.agent import CareerAgent
from core.config import EVAL_DIR
from core.gap import learning_effort
from core.job_parser import parse_job_text
from core.profile_parser import parse_profile
from core.quiz import generate_quiz, grade_quiz
from core.verify import grade_practical, parse_github_url

TEXT = ("I'm a third-year B.Tech IT student from Hyderabad. I know Java pretty well and I've built two Spring Boot applications where I created "
        "REST APIs and connected them to MySQL. I haven't worked with Docker. I'm interested in backend development.")


def names(e, ids):
    return {e.tax.name(i) for i in ids}


# ---------------------------------------------------------------- taxonomy / normalisation
def test_extraction_guards(engine):
    t = engine.tax
    got = names(engine, [m.skill_id for m in t.extract("I know JS, Java and C++. Experience with Go, REST APIs and RESTful services.")])
    assert {"JavaScript", "Java", "C++", "Go", "REST API"} <= got
    assert "C" not in names(engine, [m.skill_id for m in t.extract("Vitamin C and go to the market")])
    assert "Excel" not in names(engine, [m.skill_id for m in t.extract("I excel at teamwork")])
    assert "JavaScript" not in names(engine, [m.skill_id for m in t.extract("strong Java skills")])


@pytest.mark.parametrize("term,canon", [("RESTful services", "REST API"), ("k8s", "Kubernetes"), ("ECMAScript", "JavaScript"),
                                          ("Kubernets", "Kubernetes"), ("GitHub Actions", "CI/CD"), ("Postgres", "PostgreSQL")])
def test_normalization(engine, term, canon):
    r = engine.tax.normalize(term)
    assert r.ok and engine.tax.name(r.skill_id) == canon


def test_transfer_credit_blocks_lookalikes(engine):
    t = engine.tax
    assert t.transfer_credit("java", "javascript")[0] == 0
    assert t.transfer_credit("postgresql", "mysql")[0] > 0.4


# ---------------------------------------------------------------- profile parsing
def test_profile_evidence_negation_and_levels(engine):
    p, _ = parse_profile(TEXT, engine.tax)
    sk = {engine.tax.name(k): v for k, v in p["skills"].items()}
    assert sk["Docker"]["negated"]
    assert sk["Spring Boot"]["level"] == 2 and sk["Spring Boot"]["evidence"][0]["type"] == "project"
    assert "SQL" in sk and sk["SQL"]["inferred"]                    # implied by MySQL
    assert p["branch"] == "IT" and p["year"] == 3 and p["location"] == "Hyderabad"


def test_self_declared_expert_is_capped(engine):
    p, _ = parse_profile("I am an expert in Python.", engine.tax)
    assert p["skills"]["python"]["level"] <= 2


def test_internship_gives_advanced_evidence(engine):
    p, _ = parse_profile("During my 6 month internship I built REST APIs with Node.js.", engine.tax)
    assert p["skills"]["nodejs"]["level"] == 3 and p["experience_years"] > 0


# ---------------------------------------------------------------- job parsing
def test_job_parser_matches_gold(engine):
    gold = json.loads((EVAL_DIR / "job_gold.json").read_text())
    for j in engine._builtin_jobs:
        g = gold[j["id"]]
        assert {(x["skill"], x["level"]) for x in j["required"]} == {(x["skill"], x["level"]) for x in g["required"]}, j["id"]
        assert {(x["skill"], x["level"]) for x in j["preferred"]} == {(x["skill"], x["level"]) for x in g["preferred"]}, j["id"]


def test_job_parser_free_text(engine):
    r = parse_job_text("Requirements:\n- Strong Python\n- Working knowledge of SQL\nNice to have:\n- Docker\nExperience: 1-3 years. Eligibility: B.Tech / MCA", engine.tax)
    req = {x["skill"]: x["level"] for x in r["required"]}
    assert req == {"python": 3, "sql": 2} and [x["skill"] for x in r["preferred"]] == ["docker"]
    assert r["experience"] == {"min": 1, "max": 3} and set(r["degrees"]) == {"B.Tech", "MCA"}


# ---------------------------------------------------------------- matching, gaps, ROI
def _analyse(e, text=TEXT):
    e.reset("default")
    return e.run_pipeline(text, k=3)


def test_pipeline_end_to_end(engine):
    st = _analyse(engine)
    assert not st.get("stop") and len(st["trace"]) == 11 and st["roadmap"]
    top = st["matches"][0]
    assert 0 <= top["score"] <= 100 and top["requirements"]
    assert {t["node"] for t in st["trace"]} >= {"profile_parser", "matcher", "roi_engine", "roadmap_generator"}


def test_declared_gap_is_missing_and_more_skills_raise_score(engine):
    _analyse(engine)
    p = engine.get_profile("default")
    job = engine.job("J02")
    before = engine.matcher.match(p, job)
    docker = next((q for q in before["requirements"] if q["skill_id"] == "docker"), None)
    if docker:
        assert docker["status"] == "missing"
    from core.profile import simulate
    after = engine.matcher.match(simulate(p, {q["skill_id"]: 3 for q in before["requirements"] if q["status"] != "matched"}), job)
    assert after["score"] > before["score"] and after["counts"]["required_met"] >= before["counts"]["required_met"]


def test_required_gap_hurts_more_than_preferred(engine):
    from core.profile import simulate
    p = simulate({"skills": {}, "interests": [], "projects": [], "experience_years": 0, "degree": "B.Tech", "branch": "CSE", "location": ""}, {"java": 3, "sql": 2, "git": 2})
    job = {"id": "T1", "title": "T", "company": "C", "domain": "Backend", "experience": {"min": 0, "max": 1}, "degrees": ["B.Tech"],
           "required": [{"skill": "java", "level": 3}, {"skill": "sql", "level": 2}, {"skill": "git", "level": 2}], "preferred": [{"skill": "docker", "level": 1}, {"skill": "aws", "level": 1}]}
    good = engine.matcher.match(p, job)
    job_req_missing = dict(job, required=job["required"] + [{"skill": "docker", "level": 2}], preferred=[{"skill": "aws", "level": 1}])
    worse = engine.matcher.match(p, job_req_missing)
    assert good["score"] > worse["score"] and good["counts"]["required_met"] == 3 and good["tier"] in ("Strong match", "Good match")


def test_gap_effort_includes_prerequisites(engine):
    _analyse(engine)
    p = engine.get_profile("default")
    eff = learning_effort(p, engine.tax, "kubernetes")
    assert "docker" in eff["missing_prereqs"] and eff["total_days"] > engine.tax.effort_days("kubernetes") * 0.9


def test_roi_is_sorted_and_explained(engine):
    st = _analyse(engine)
    rk = st["roi"]["ranking"]
    assert rk == sorted(rk, key=lambda x: -x["roi"]) and rk[0]["explanation"]
    assert all(x["effort_days"] >= 1 for x in rk)
    assert st["roi"]["trajectory"][-1]["suitable"] >= st["roi"]["trajectory"][0]["suitable"]


# ---------------------------------------------------------------- roadmap, quiz, adaptation
def test_roadmap_orders_prerequisites_first(engine):
    e = engine
    _analyse(e)
    days = e.create_roadmap("default", ["kubernetes"], 1.5)
    order = []
    for d in days:
        if d["skill_id"] not in order:
            order.append(d["skill_id"])
    assert order.index("docker") < order.index("kubernetes") and "linux" in order
    assert days[-1]["kind"] == "assessment"
    assert all(days[i]["planned_date"] <= days[i + 1]["planned_date"] for i in range(len(days) - 1))


def test_quiz_structure_and_grading(engine):
    qs = generate_quiz("docker", engine.tax, engine.kb, None, 5, seed=3)
    assert len(qs) == 5
    for q in qs:
        assert len(set(q["options"])) == 4 and 0 <= q["answer"] < 4 and q["topic"]
    perfect = grade_quiz(qs, {q["id"]: q["answer"] for q in qs})
    assert perfect["pct"] == 1.0 and perfect["passed"]
    bad = grade_quiz(qs, {q["id"]: (q["answer"] + 1) % 4 for q in qs})
    assert bad["pct"] == 0 and bad["weak_topics"]


def test_adaptive_roadmap(engine):
    e = engine
    _analyse(e)
    e.create_roadmap("default", ["docker"], 1.5)
    day = e.current_day("default")
    n0 = len(e.roadmap("default"))
    quiz = e.day_quiz(day, seed=1)
    good = e.submit_quiz("default", day, quiz, {q["id"]: q["answer"] for q in quiz})
    assert good["decision"] == "continue" and len(e.roadmap("default")) == n0
    day2 = e.current_day("default")
    quiz2 = e.day_quiz(day2, seed=2)
    bad = e.submit_quiz("default", day2, quiz2, {q["id"]: (q["answer"] + 1) % 4 for q in quiz2})
    assert bad["decision"] in ("retake", "revise") and bad["inserted"] >= 1
    rm = e.roadmap("default")
    assert len(rm) == n0 + bad["inserted"] and any(d["inserted"] for d in rm)
    assert [d["seq"] for d in rm] == list(range(1, len(rm) + 1))


def test_verification_updates_profile_and_rematches(engine):
    e = engine
    _analyse(e)
    e.create_roadmap("default", ["git"], 1.5)
    before = len(e.db.list_snapshots("default"))
    a = next(d for d in e.roadmap("default") if d["kind"] == "assessment")
    quiz = e.day_quiz(a, seed=5)
    r = e.submit_quiz("default", a, quiz, {q["id"]: q["answer"] for q in quiz})
    assert r["final"] and "passed" in r["message"]
    assert e.get_profile("default")["skills"]["git"]["verified"] >= 1
    assert len(e.db.list_snapshots("default")) == before + 1
    prac = e.submit_practical("default", a, "", "I built a project using git with branches, commits, merge and a pull request; I resolved a conflict and documented the workflow in the readme. " * 2)
    assert prac["parts"]["keywords"] > 0.3


def test_practical_grading_offline_and_url_parsing(engine):
    assert parse_github_url("https://github.com/octocat/Hello-World.git") == ("octocat", "Hello-World")
    assert parse_github_url("https://example.com/x") is None
    weak = grade_practical("docker", engine.tax, engine.embedder, None, "", "I did docker.")
    strong = grade_practical("docker", engine.tax, engine.embedder, None, "", "I wrote a Dockerfile and a docker-compose.yml with a container image, volume and network for my Flask service, documented in the README. " * 2)
    assert strong["score"] > weak["score"] and not weak["passed"]


# ---------------------------------------------------------------- RAG + agent
def test_rag_retrieval_is_grounded(engine):
    hits = engine.kb.notes("dockerfile layer caching", skill_id="docker", k=3)
    assert hits and "docker" in hits[0].doc.metadata["skill_id"]
    ans = engine.kb.answer("what is layer caching in docker?")
    assert ans["grounded"] and ans["sources"]
    assert not engine.kb.answer("qzxv plmk wqrt")["grounded"]


def test_agent_multistep_offline(engine):
    _analyse(engine)
    out = CareerAgent(engine).ask("I want backend jobs - what should I learn first and where do I learn it?")
    tools = [t["tool"] for t in out["trace"]]
    assert tools.index("rank_skills_by_roi") < tools.index("search_learning_resources") and out["answer"]


def test_notifications_dedupe(engine):
    _analyse(engine)
    engine.create_roadmap("default", ["git"], 1.5)
    assert engine.notify_tick("default", force="morning") == ["morning"]
    assert engine.notify_tick("default", force="morning") == []


# ---------------------------------------------------------------- accuracy regression
def test_accuracy_regression(engine):
    rep = evaluation.run_all(engine)
    assert rep["extraction"]["skills"]["f1"] >= 0.9
    assert rep["extraction"]["negation"]["f1"] >= 0.9
    assert rep["normalization"]["accuracy"] >= 0.95
    assert rep["job_parsing"]["required"]["f1"] >= 0.98
    assert rep["matching"]["status_accuracy"] >= 0.93
    assert rep["matching"]["top3_relevance"] >= 0.9
