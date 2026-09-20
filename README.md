# Skill2Job AI ✎ — evidence-backed, semantic, adaptive career agent

> Don't just tell a student which jobs they can apply for. Tell them **exactly what to learn, why it matters, what to do today**, verify it, and **re-match their jobs** as their skills grow.

```
text / resume / voice → profile parsing → skill normalisation → job matching (explainable)
   → gap analysis → ROI ranking → day-by-day roadmap → resources → quiz + practical verification
   → progress + notifications → updated profile → re-match → newly unlocked jobs
```

## 1. Run it (3 minutes)

```bash
unzip skill2job-ai.zip && cd skill2job-ai
./run.sh            # macOS/Linux   (Windows: run.bat)
# or manually:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Python 3.10+. `data/` is pre-built; rebuild anytime with `python scripts/build_data.py`.
**No API key is required** – the whole app runs in an offline "smart mode". Keys only make it smarter (below).
First launch with `sentence-transformers` downloads a ~90 MB model once. To skip that: `EMBEDDING_BACKEND=hash`.

## 2. WHERE YOU ADD YOUR API KEYS  🔑

| What | Where | Needed for | Required? |
|---|---|---|---|
| **`GEMINI_API_KEY`** (Google AI Studio → https://aistudio.google.com/apikey) | open the **`.env`** file in the project root and paste it after `GEMINI_API_KEY=` (restart the app). Users are never asked for a key. (On Streamlit Cloud, put it in *Secrets* instead.) | Gemini structured resume/text parsing, messy-JD parsing, friendly match narratives, scenario quizzes grounded in notes, practical-task grading, **voice transcription**, and the **tool-calling Career Copilot** | optional |
| `GEMINI_MODEL` | `.env` (default `gemini-2.5-flash`) | change model | optional |
| `YOUTUBE_API_KEY` | `.env` | swaps YouTube *search links* for real top videos on every roadmap day | optional |
| `GITHUB_TOKEN` | `.env` | higher GitHub API rate limit for the practical repo check | optional |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `.env` | mirror morning / evening / completion notifications to your phone | optional |

Code locations: `core/llm.py` (Gemini wrapper – all calls fail soft), `core/agent.py` (tool calling), `core/config.py` (env loading).

## 3. Mapping to the scoring rubric

**Creativity (100)** – "sketchbook studio" identity: handwriting type (Caveat / Patrick Hand / Permanent Marker), ink-and-highlighter palette on dotted paper, hand-drawn borders, sticky notes, hatched progress bars, score rings.
Beyond chat: 3-way intake (type / resume PDF-DOCX / **voice**), sliders (study hours, plan size, score filters), forms, radar + ROI + trajectory charts, interactive quizzes, practical-submission form, timeline roadmap. Polish: loading spinners with personality, empty states on every page, friendly error card (no stack traces), toasts, balloons, offline/online mode badge.

**Problem relevance (100)** – targets the real gap of job portals (resume → list of jobs): *specific gaps, ROI-ranked, taught, verified, re-matched*. Original: counterfactual ROI, adaptive roadmap, evidence-strength scoring, "insufficient evidence" state, prerequisites graph.

**Technical (100)**
* *Core pipeline (RAG)* – `core/rag/`: **loaders** (markdown / json / pdf / txt) → **splitters** (heading-aware + sentence windows) → **embeddings** (Sentence-Transformers, offline hashing fallback) → **vector store** (persistent NumPy cosine, metadata filters) → **hybrid retriever** (dense + BM25 + Reciprocal-Rank-Fusion). 1,100+ chunks: 79 study notes, 670 resources, 43 job postings; users can upload their own notes.
* *RAG quality* – grounded answers only from retrieved chunks with numbered citations; unrelated questions return "not found" instead of hallucinating; lessons and quizzes trace to module titles.
* *Tools* – `core/tools.py`: 13 `@tool` functions with docstrings/typed args; all numbers come from Python (matcher, ROI counterfactuals, GitHub API repo checks, quiz grading), never from the LLM.
* *Orchestration* – `core/graph.py`: **LangGraph** workflows (11-node analysis graph with a conditional early exit; 4-node learning-loop graph) + visible **agent trace** in the UI; Career Copilot chains tools (match → gap → ROI → resources).
* *Live correctness* – 30 automated tests (`pytest`), UI smoke tests of every page, graceful fallbacks (no key, no internet, no GitHub, no sentence-transformers).

## 4. How accuracy is protected (not keyword matching)

1. **Profile Parsing Agent** → skill + level + *evidence + evidence type* (internship, project, certification, coursework, self-declared…). Negations ("I haven't used Docker") become **declared gaps**. A self-claimed "expert" without evidence is capped at Intermediate.
2. **Normalisation** – 79-skill taxonomy with aliases (`RESTful services → REST API`, `k8s → Kubernetes`), fuzzy + embedding fallback.
3. **Job Parsing Agent** – free-text JDs → required vs preferred, level (basic/intermediate/strong), experience, degrees.
4. **Matching** – per requirement: presence (direct / inferred / **transferable from a related skill family**, with a "never related" block-list so *Java ≠ JavaScript*), level fit, evidence strength. Seven weighted signals (`core/config.py::MATCH_WEIGHTS`): required 0.40 · preferred 0.10 · semantic 0.10 · proficiency 0.15 · evidence 0.10 · experience 0.08 · education 0.07. Explanations cite the evidence.
5. **Gap states**: 🟢 matched · 🟡 partial · 🔴 missing · ⚠️ insufficient evidence (listed but unproven).
6. **ROI** = (4×jobs newly suitable + 0.12×score gain + demand) ÷ effort days, computed by *actually adding the skill (and missing prerequisites) to the profile and re-running the matcher*; ordering is greedy with re-ranking.
7. **Verification ladder**: self-completion → AI quiz (≥70%) → practical (GitHub repo files/README keywords + rubric-graded write-up). Verified skills re-enter matching as high-strength evidence.

### Measured results (`python -m core.evaluation` – hashing embedder, no LLM)
20 hand-labelled candidates × 43 postings (3,977 required-skill judgements), 119 synonym pairs, 43 job descriptions with gold structure:

| Metric | Result |
|---|---|
| Skill extraction P / R / F1 | 98.9% / 100% / 99.4% |
| "I haven't used X" (negation) F1 | 100% |
| Proficiency exact / within ±1 level | 85.4% / 100% |
| Skill normalisation accuracy | 100% (n=119) |
| Job parsing required / preferred F1, level accuracy | 100% / 100% / 100% |
| Requirement status accuracy (has / partial / missing) | 97.3% |
| Gap detection P / R | 99.2% / 98.9% |
| Suitable-role F1 (only 12 positive pairs – small!) | 68.7% (recall 91.7%, precision 55%) |
| Top-3 contains the candidate's target role family | 100% |

**Read honestly:** the job descriptions come from a few templates and the candidate set is small, so treat these as regression numbers (the *Trust & Accuracy* page re-computes them live and lists failures). The weakest metric is deciding "qualifies now" – it is deliberately strict (level-adequate coverage ≥ 70%). Real-world messy text is where Gemini + Sentence-Transformers should help; I could not test the Gemini and Sentence-Transformers paths against live services in my build sandbox – they are written to fail soft to the tested offline paths.

## 5. Testing procedure for the judge (5 minutes)

1. **Home → "Java backend fresher"** (one click) – watch the LangGraph trace: parsing → normalisation → RAG retrieval → matching → gaps → ROI → roadmap → resources.
2. **Profile Intake** → type: *"I'm a Java developer. I've built two Spring Boot projects and know SQL. I haven't worked with Docker. I'm interested in backend development."* → Docker appears as a **declared gap**; SQL/Java show project evidence.
3. **Job Matches → Why this score?** – requirement table, evidence quotes, score anatomy radar.
4. **Skill Gaps** – level needed vs current, jobs affected (x/43), effort with prerequisites, path, project.
5. **ROI Analysis** – ranked bars + "if you learn them in this order" trajectory + written reasoning.
6. **Roadmap → Daily Task** – lesson brief with RAG citations, level-matched resources with "why for you", checklist, quiz. **Answer badly** (<50%) → revision + practice + reassessment days are inserted; answer well → plan continues.
7. Jump to the **assessment day** → pass quiz + submit practical (a public GitHub URL or write-up) → **Progress** shows the verified skill, and the "roles you qualify for" count rises; notifications announce it.
8. **Career Copilot** – *"I want backend jobs – what should I learn first and where?"* → see the tool-call trace. **Resources → Ask the study notes** shows cited answers.
9. **Notifications** → simulate morning / evening. **Trust & Accuracy** → run the evaluation.

## 6. Project layout

```
app.py                     Streamlit entry (sidebar, nav, error handling)
ui/                        theme (style.css), components, pages/ (14 screens)
core/
  taxonomy.py              skill graph, aliases, extraction, normalisation, prerequisites, transfer credit
  profile_parser.py        Profile Parsing Agent (rules + Gemini)      profile.py  evidence→level, implied skills
  job_parser.py            Job Parsing Agent                            matcher.py  hybrid explainable scoring
  gap.py  roi.py           gap analysis, counterfactual ROI             roadmap.py  day-by-day + adaptive revision days
  resources.py  quiz.py  verify.py  notifications.py
  rag/                     loaders, splitters, vectorstore, hybrid retriever, KnowledgeBase
  tools.py  agent.py       13 LangChain tools, Copilot (Gemini tool calling / offline planner)
  graph.py                 LangGraph workflows           engine.py  orchestration + learning loop
  db.py                    SQLite (users, skills, candidate_skills, jobs, job_skills, roadmap, progress, verification, notifications, match_history)
  evaluation.py            gold-label evaluation + weight tuning
data_src/*.txt             EDITABLE sources (taxonomy, learning paths, 43 jobs)  →  scripts/build_data.py  →  data/*.json + data/knowledge/*.md
data/eval/                 gold candidates, normalisation pairs, job gold, last report.json
tests/                     30 tests (core + UI)
```

## 7. Customising

* **Jobs / skills / lessons**: edit `data_src/jobs.txt`, `taxonomy.txt`, `paths.txt`, then `python scripts/build_data.py`. Or paste any JD in *Job Matches → Add your own job description*.
* **Resource links**: entries marked *search link* open a YouTube / Coursera / GitHub search for the named creator or topic; *course catalogue* opens NPTEL / Skill India portals. For exact URLs edit `scripts/build_data.py` (`DOCS`, `CREATORS`) or set `YOUTUBE_API_KEY`.
* **Weights**: `core/config.py`; tune with `python -m core.evaluation --tune`.
* **Companies in the job set are fictional** – replace with real postings for production use.
* Run tests: `pytest -q`.

## 8. Known limits
* Skill levels are estimated from text evidence – always editable on the *Skill Profile* page.
* "Unlocked roles" means *meets our matching criteria*, never a hiring guarantee.
* Voice needs a browser mic permission; transcription uses Gemini if a key is present, otherwise free Google Web Speech (internet needed).
* Browser push notifications are not used; in-app + optional Telegram instead.
