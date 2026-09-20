"""Quiz generation and grading.

Questions are generated from the curated learning modules (term <-> definition pairs), so every question is
traceable to a module title. When Gemini is available it additionally writes scenario questions grounded in
retrieved study-note chunks; the result is schema-validated before use. Grading is plain Python.
"""
from __future__ import annotations

import random

from .config import QUIZ_PASS
from .curriculum import path_for


def _items(skill_id: str) -> list[dict]:
    out = []
    for m in path_for(skill_id)["modules"]:
        for t in m["terms"]:
            out.append({"term": t["term"], "definition": t["definition"], "module": m["title"]})
    return out


def _distractor_terms(skill_id: str, item: dict, taxonomy, rng: random.Random, k: int = 3) -> list[dict]:
    pool = [i for i in _items(skill_id) if i["term"] != item["term"]]
    rng.shuffle(pool)
    out = pool[:k]
    if len(out) < k:  # borrow from sibling skills in the same category
        cat = taxonomy.get(skill_id)["category"]
        for sid in taxonomy.by_category().get(cat, []):
            if sid == skill_id or len(out) >= k:
                continue
            extra = _items(sid)
            rng.shuffle(extra)
            out += [e for e in extra if e["term"] != item["term"]][: k - len(out)]
    return out[:k]


def _build_mc(skill_id: str, item: dict, taxonomy, rng: random.Random, kind: str, qid: str) -> dict:
    d = _distractor_terms(skill_id, item, taxonomy, rng)
    if kind == "term":
        opts = [item["term"]] + [x["term"] for x in d]
        q = f"Which term is described by: “{item['definition']}”?"
    else:
        opts = [item["definition"]] + [x["definition"] for x in d]
        q = f"In {taxonomy.name(skill_id)}, what does “{item['term']}” mean?"
    order = list(range(len(opts)))
    rng.shuffle(order)
    options = [opts[i] for i in order]
    return {"id": qid, "q": q, "options": options, "answer": options.index(opts[0]),
            "explanation": f"{item['term']}: {item['definition']}.", "topic": item["module"], "source": "learning path"}


def bank_quiz(skill_id: str, taxonomy, n: int = 5, focus_topics: list[str] | None = None, seed: int | None = None) -> list[dict]:
    rng = random.Random(seed if seed is not None else random.randrange(10 ** 9))
    items = _items(skill_id)
    if not items:
        return []
    rng.shuffle(items)
    focus = [i for i in items if focus_topics and i["module"] in focus_topics]
    rest = [i for i in items if i not in focus]
    # cover as many modules as possible: sort rest so distinct modules come first
    seen, ordered = set(), []
    for i in rest:
        if i["module"] not in seen:
            ordered.append(i)
            seen.add(i["module"])
    ordered += [i for i in rest if i not in ordered]
    chosen = (focus[: max(1, int(n * 0.6))] if focus else []) + ordered
    chosen = chosen[:n]
    return [_build_mc(skill_id, it, taxonomy, rng, "term" if k % 2 == 0 else "definition", f"q{k + 1}") for k, it in enumerate(chosen)]


def _validate(q) -> bool:
    return (isinstance(q, dict) and isinstance(q.get("q"), str) and isinstance(q.get("options"), list) and len(q["options"]) == 4
            and len(set(map(str, q["options"]))) == 4 and isinstance(q.get("answer"), int) and 0 <= q["answer"] < 4)


def llm_quiz(skill_id: str, taxonomy, kb, llm, n: int, focus_topics: list[str] | None) -> list[dict]:
    name = taxonomy.name(skill_id)
    hits = kb.notes(f"{name} {' '.join(focus_topics or [])}", skill_id=skill_id, k=4)
    if not hits:
        return []
    ctx = "\n\n".join(h.doc.text for h in hits)
    prompt = (f"Write {n} multiple-choice questions (4 options each) that test practical understanding of {name}, using ONLY facts in the notes below. "
              f"Prefer short scenarios over pure definitions. Return JSON list: "
              f'[{{"q": str, "options": [4 strings], "answer": index 0-3, "explanation": str, "topic": short module name}}]\n\nNOTES:\n{ctx}')
    data = llm.generate_json(prompt, system="You are a careful technical examiner. Never use facts that are not in the notes.")
    if not isinstance(data, list):
        return []
    qs = []
    for i, q in enumerate(data):
        if _validate(q):
            qs.append({"id": f"g{i + 1}", "q": q["q"], "options": [str(o) for o in q["options"]], "answer": q["answer"],
                       "explanation": str(q.get("explanation", "")), "topic": str(q.get("topic") or hits[0].doc.metadata.get("heading", "")),
                       "source": "Gemini, grounded in study notes"})
    return qs


def generate_quiz(skill_id: str, taxonomy, kb=None, llm=None, n: int = 5, focus_topics: list[str] | None = None, seed: int | None = None) -> list[dict]:
    qs: list[dict] = []
    if llm and llm.available and kb is not None:
        qs = llm_quiz(skill_id, taxonomy, kb, llm, max(2, n // 2 + 1), focus_topics)
    bank = bank_quiz(skill_id, taxonomy, n=n, focus_topics=focus_topics, seed=seed)
    qs = (qs + bank)[:n]
    for i, q in enumerate(qs, 1):
        q["id"] = f"q{i}"
    return qs


def grade_quiz(quiz: list[dict], answers: dict[str, int]) -> dict:
    per, correct, weak = [], 0, []
    for q in quiz:
        chosen = answers.get(q["id"])
        ok = chosen == q["answer"]
        correct += ok
        if not ok and q["topic"] not in weak:
            weak.append(q["topic"])
        per.append({"id": q["id"], "correct": ok, "chosen": chosen, "answer": q["answer"], "topic": q["topic"], "explanation": q["explanation"]})
    total = len(quiz)
    pct = correct / total if total else 0.0
    return {"score": correct, "total": total, "pct": round(pct, 3), "per_question": per, "weak_topics": weak, "passed": pct >= QUIZ_PASS}
