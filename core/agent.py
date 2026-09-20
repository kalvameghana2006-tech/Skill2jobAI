"""Career Copilot: a tool-calling agent over the real Python tools in core/tools.py.

* With a Gemini key: Gemini plans and calls the tools (automatic function calling); every call is logged.
* Without a key: a deterministic planner detects the intents in the message and runs the same tools in the
  right ORDER (retrieve -> analyse -> rank -> recommend), so multi-step questions still work offline.
Both paths return a visible tool trace so the reasoning is inspectable.
"""
from __future__ import annotations

import functools
import json
import re

from . import tools as T

SYSTEM = ("You are Skill2Job, a careful career coach for students. ALWAYS call tools to get facts about the user's jobs, gaps, ROI, "
          "resources and roadmap – never guess numbers. Call several tools in sequence for multi-part questions "
          "(e.g. match_jobs -> analyze_skill_gap -> rank_skills_by_roi -> search_learning_resources). "
          "Explain briefly why, be encouraging, and never promise employment.")


def _short(obj, n: int = 260) -> str:
    s = json.dumps(obj, default=str, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


class CareerAgent:
    def __init__(self, engine, uid: str = "default"):
        self.engine, self.uid = engine, uid

    # ---------------------------------------------------------------- entry
    def ask(self, message: str, history: list[dict] | None = None) -> dict:
        T.bind(self.engine, self.uid)
        trace: list[dict] = []
        if self.engine.llm.available:
            try:
                ans = self._ask_gemini(message, history or [], trace)
                if ans:
                    return {"answer": ans, "trace": trace, "mode": "Gemini tool-calling"}
            except Exception as exc:
                trace.append({"tool": "⚠ gemini", "args": {}, "result": f"{type(exc).__name__}: {exc}"[:200]})
        ans = self._plan_and_answer(message, trace)
        return {"answer": ans, "trace": trace, "mode": "Offline planner (rule-based tool orchestration)"}

    # ---------------------------------------------------------------- Gemini path
    def _ask_gemini(self, message: str, history: list[dict], trace: list[dict]) -> str | None:
        from google.genai import types

        def wrap(tool):
            fn = tool.func

            @functools.wraps(fn)
            def logged(*a, **kw):
                try:
                    out = fn(*a, **kw)
                except Exception as exc:
                    out = {"error": str(exc)}
                trace.append({"tool": tool.name, "args": kw or list(a), "result": _short(out)})
                return out
            return logged

        contents = [types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part(text=m["content"])]) for m in history[-6:]]
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
        cfg = types.GenerateContentConfig(system_instruction=SYSTEM, tools=[wrap(t) for t in T.ALL_TOOLS], temperature=0.3)
        resp = self.engine.llm.client.models.generate_content(model=self.engine.llm.model, contents=contents, config=cfg)
        return (resp.text or "").strip() or None

    # ---------------------------------------------------------------- offline planner
    INTENTS = [
        ("today", r"\b(today|todays|today's|what should i do now|next task)\b"),
        ("quiz", r"\b(quiz|test me|question me)\b"),
        ("roadmap", r"\b(roadmap|study plan|day[- ]by[- ]day|schedule|plan for)\b"),
        ("roi", r"\b(first|priorit\w*|roi|worth|most valuable|which skill|what should i learn|what to learn|learn next)\b"),
        ("gap", r"\b(missing|gap|lack|need to learn|what am i missing|weak)\b"),
        ("why", r"\b(why|explain).*(match|job|role|fit)|\bwhy (is|am)\b"),
        ("resources", r"\b(resource|course|video|tutorial|youtube|coursera|nptel|skill india|learn|how (do|to|can))\b"),
        ("concept", r"\b(what is|what are|explain|difference between|how does|define)\b"),
        ("rematch", r"\b(unlock|new jobs|updated|after (learning|completing)|progress)\b"),
        ("jobs", r"\b(job|jobs|role|roles|match|matches|apply|hiring|opportunit\w*)\b"),
    ]

    def _plan_and_answer(self, message: str, trace: list[dict]) -> str:
        e = self.engine
        low = message.lower()

        def call(name: str, **kw):
            try:
                out = T.TOOLS_BY_NAME[name].func(**kw)
            except Exception as exc:
                out = {"error": str(exc)}
            trace.append({"tool": name, "args": kw, "result": _short(out)})
            return out

        intents = [n for n, rx in self.INTENTS if re.search(rx, low)]
        mentions = [m.skill_id for m in e.tax.extract(message)]
        skill_name = e.tax.name(mentions[0]) if mentions else ""
        domain = next((d for d in ("Backend", "Frontend", "Full Stack", "Data Analytics", "Data Science", "Data Engineering", "Cloud", "DevOps", "QA", "Testing", "Mobile", "Security")
                       if d.lower() in low), "")
        parts: list[str] = []
        prof = e.get_profile(self.uid)
        if not prof or not prof["skills"]:
            if len(message.split()) > 8 and mentions:
                out = call("extract_skills", text=message)
                names = ", ".join(f"{s['skill']} (L{s['level']})" for s in out["skills"] if not s["negated"])
                return (f"I read this as: **{names}**. Save it on the **Profile** page to unlock job matching, ROI and a roadmap. "
                        "Meanwhile, ask me any concept question (for example *what is a Dockerfile?*).")
            if not ({"concept", "resources", "quiz"} & set(intents)):
                return "I need a profile first – open **Profile Intake** and tell me what you know, then I can match jobs, find gaps and plan your learning."
        if "today" in intents:
            out = call("get_todays_task")
            parts.append(out.get("message") or f"**Day {out['day']} – {out['title']}** (~{out['minutes']} min)\n" + "\n".join(f"- {c}" for c in out["checklist"]))
        if "rematch" in intents:
            out = call("rematch_jobs")
            parts.append(f"You now match **{out['suitable_now']}** roles (started at {out['suitable_at_start']}). Best: {out['best']['title']} at {out['best']['score']:.0f}%.")
        if "why" in intents or ("jobs" in intents and re.search(r"\bwhy\b", low)):
            out = call("explain_job_match", job=next((j["title"] for j in e.jobs if j["title"].lower() in low), ""))
            if "error" not in out:
                parts.append(f"**{out['job']}** – {out['score']}% ({out['tier']}). {out['headline']} {out['verdict']}\n" +
                             "\n".join(f"✓ {s}" for s in out["strengths"][:4]) + "\n" + "\n".join(f"⚠ {g}" for g in out["gaps"][:4]))
        elif "jobs" in intents and not ({"roi", "roadmap"} & set(intents)) or ("jobs" in intents and "gap" not in intents and "roi" not in intents):
            out = call("match_jobs", top_k=5, domain=domain)
            parts.append(f"You currently meet the criteria for **{out['total_suitable']}** role{'s' if out['total_suitable'] != 1 else ''}. Top matches:\n" +
                         "\n".join(f"- **{j['title']}** ({j['company']}) – {j['score']}% · core skills {j['required']} · {j['tier']}" for j in out["jobs"]))
        if "gap" in intents or ("why" in intents and not parts):
            jobname = next((j["title"] for j in e.jobs if j["title"].lower() in low), "")
            out = call("analyze_skill_gap", job=jobname)
            if "gaps" in out:
                parts.append(f"For **{out['job']}** the gaps are:\n" + "\n".join(
                    f"- **{g['skill']}** ({g['importance']}, {g['status']}): needs {g['needs']}, you have {g['now']}; ~{g['days']} days; relevant to {g['jobs_relevant']} jobs" for g in out["gaps"][:6]))
        top_skill = None
        if {"roi", "roadmap"} & set(intents) or ("jobs" in intents and "resources" in intents):
            out = call("rank_skills_by_roi", top_k=5)
            if "ranking" in out and out["ranking"]:
                top_skill = out["ranking"][0]["skill"]
                parts.append("Learn in this order (highest ROI first):\n" + "\n".join(
                    f"{i}. **{r['skill']}** – {r['priority']} priority · {r['jobs_unlocked']} jobs unlocked · ~{r['effort_days']:g} days\n   {r['why']}" for i, r in enumerate(out["ranking"][:4], 1)))
                if out.get("trajectory"):
                    tr = out["trajectory"]
                    parts.append(f"Following this plan takes you from **{tr[0]['suitable']}** suitable roles to about **{tr[min(3, len(tr) - 1)]['suitable']}**.")
        if "roadmap" in intents:
            skills = [skill_name] if skill_name else ([r["skill"] for r in out["ranking"][:3]] if top_skill else [])
            if skills:
                out2 = call("build_learning_roadmap", skills=skills)
                if "days" in out2:
                    parts.append(f"I built and saved a **{out2['days']}-day roadmap** (see the Roadmap page). It starts with:\n" + "\n".join(f"- {d}" for d in out2["first_days"][:4]))
        if ("resources" in intents or top_skill) and "concept" not in intents or (skill_name and "resources" in intents):
            target = skill_name or top_skill
            if target:
                out = call("search_learning_resources", skill=target)
                if "resources" in out:
                    parts.append(f"Best resources for **{out['skill']}** at your level:\n" + "\n".join(
                        f"- [{r['title']}]({r['url']}) – {r['source']}, {r['difficulty']}, ~{r['minutes']} min" for r in out["resources"][:4]))
        if "concept" in intents or (not parts and not intents):
            out = call("retrieve_study_notes", question=message)
            parts.append(out["answer"] + ("\n\n_Sources: " + "; ".join(out["sources"][:3]) + "_" if out.get("sources") else ""))
        if "quiz" in intents and skill_name:
            out = call("make_quiz", skill=skill_name, n=3)
            if "questions" in out:
                parts.append(f"Warm-up on **{out['skill']}**:\n" + "\n".join(f"{i}. {q['q']}" for i, q in enumerate(out["questions"], 1)) + "\n\nTake the graded version on the Daily Task page.")
        return "\n\n".join(parts) or "I can match jobs, analyse gaps, rank skills by ROI, find resources, build a roadmap, explain concepts from study notes and quiz you. What would you like?"
