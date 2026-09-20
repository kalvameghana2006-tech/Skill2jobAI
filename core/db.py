"""SQLite persistence: profile, skills, roadmap, progress, verification, notifications, match history."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id TEXT PRIMARY KEY, name TEXT, degree TEXT, branch TEXT, year INTEGER, location TEXT,
  interests TEXT, experience_years REAL, hours_per_day REAL, target_role TEXT, projects TEXT,
  certifications TEXT, raw_text TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS skills(skill_id TEXT PRIMARY KEY, skill_name TEXT, category TEXT, parent_skill TEXT);
CREATE TABLE IF NOT EXISTS candidate_skills(
  user_id TEXT, skill_id TEXT, proficiency INTEGER, evidence TEXT, evidence_type TEXT, confidence REAL,
  verified INTEGER DEFAULT 0, negated INTEGER DEFAULT 0, inferred INTEGER DEFAULT 0, source TEXT,
  PRIMARY KEY(user_id, skill_id));
CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT, experience TEXT);
CREATE TABLE IF NOT EXISTS job_skills(job_id TEXT, skill_id TEXT, importance TEXT, required_level INTEGER,
  PRIMARY KEY(job_id, skill_id));
CREATE TABLE IF NOT EXISTS custom_jobs(job_id TEXT PRIMARY KEY, payload TEXT);
CREATE TABLE IF NOT EXISTS roadmap(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, seq INTEGER, planned_date TEXT, skill_id TEXT,
  title TEXT, kind TEXT, plan TEXT, status TEXT DEFAULT 'pending', inserted INTEGER DEFAULT 0,
  quiz_score REAL, task_state TEXT DEFAULT '{}', updated_at TEXT);
CREATE TABLE IF NOT EXISTS progress(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, day_id INTEGER, event TEXT, score REAL, total REAL,
  detail TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS verification(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, skill_id TEXT, level TEXT, score REAL, passed INTEGER,
  detail TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, kind TEXT, title TEXT, body TEXT, dedupe_key TEXT,
  created_at TEXT, read INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS match_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, created_at TEXT, label TEXT, top_job_id TEXT,
  top_score REAL, suitable_count INTEGER, avg_top5 REAL, detail TEXT);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str | None = None):
        self.path = str(path or DB_PATH)
        self._lock = threading.RLock()
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        with self._lock:
            c = sqlite3.connect(self.path, check_same_thread=False)
            c.row_factory = sqlite3.Row
            try:
                yield c
                c.commit()
            finally:
                c.close()

    # ---------------------------------------------------------------- static seed (skills / jobs)
    def seed_static(self, taxonomy, jobs: list[dict]) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM skills")
            c.executemany("INSERT INTO skills VALUES(?,?,?,?)", [
                (sid, s["name"], s["category"], (s.get("prereqs") or [None])[0]) for sid, s in taxonomy.skills.items()])
            c.execute("DELETE FROM jobs")
            c.execute("DELETE FROM job_skills")
            for j in jobs:
                c.execute("INSERT INTO jobs VALUES(?,?,?,?,?)",
                          (j["id"], j["title"], j["company"], j.get("city", ""), f"{j['experience']['min']}-{j['experience']['max']}"))
                for imp, key in (("required", "required"), ("preferred", "preferred")):
                    for r in j[key]:
                        c.execute("INSERT OR REPLACE INTO job_skills VALUES(?,?,?,?)", (j["id"], r["skill"], imp, r["level"]))

    # ---------------------------------------------------------------- profile
    def save_profile(self, p: dict) -> None:
        uid = p["user_id"]
        with self.conn() as c:
            exists = c.execute("SELECT created_at FROM users WHERE user_id=?", (uid,)).fetchone()
            c.execute("""INSERT OR REPLACE INTO users VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                uid, p.get("name", ""), p.get("degree", ""), p.get("branch", ""), p.get("year") or 0, p.get("location", ""),
                json.dumps(p.get("interests", [])), p.get("experience_years", 0.0), p.get("hours_per_day", 1.5),
                p.get("target_role", ""), json.dumps(p.get("projects", [])), json.dumps(p.get("certifications", [])),
                p.get("raw_text", ""), exists["created_at"] if exists else now(), now()))
            c.execute("DELETE FROM candidate_skills WHERE user_id=?", (uid,))
            for sid, s in p.get("skills", {}).items():
                ev = s.get("evidence", [])
                c.execute("INSERT INTO candidate_skills VALUES(?,?,?,?,?,?,?,?,?,?)", (
                    uid, sid, s.get("level", 1), json.dumps(ev), ev[0]["type"] if ev else "self_declared",
                    s.get("confidence", 0.5), s.get("verified", 0), int(s.get("negated", False)),
                    int(s.get("inferred", False)), s.get("source", "")))

    def load_profile(self, uid: str) -> dict | None:
        with self.conn() as c:
            u = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
            if not u:
                return None
            p = {"user_id": uid, "name": u["name"], "degree": u["degree"], "branch": u["branch"], "year": u["year"],
                 "location": u["location"], "interests": json.loads(u["interests"] or "[]"),
                 "experience_years": u["experience_years"], "hours_per_day": u["hours_per_day"],
                 "target_role": u["target_role"], "projects": json.loads(u["projects"] or "[]"),
                 "certifications": json.loads(u["certifications"] or "[]"), "raw_text": u["raw_text"], "skills": {}}
            for r in c.execute("SELECT * FROM candidate_skills WHERE user_id=?", (uid,)):
                p["skills"][r["skill_id"]] = {
                    "skill_id": r["skill_id"], "level": r["proficiency"], "evidence": json.loads(r["evidence"] or "[]"),
                    "confidence": r["confidence"], "verified": r["verified"], "negated": bool(r["negated"]),
                    "inferred": bool(r["inferred"]), "source": r["source"]}
            return p

    def reset_user(self, uid: str) -> None:
        with self.conn() as c:
            for t in ("users", "candidate_skills", "roadmap", "progress", "verification", "notifications", "match_history"):
                c.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))

    # ---------------------------------------------------------------- roadmap
    def replace_roadmap(self, uid: str, days: list[dict]) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM roadmap WHERE user_id=?", (uid,))
            for i, d in enumerate(days, 1):
                c.execute("""INSERT INTO roadmap(user_id,seq,planned_date,skill_id,title,kind,plan,status,inserted,updated_at)
                             VALUES(?,?,?,?,?,?,?,?,?,?)""",
                          (uid, i, d["planned_date"], d["skill_id"], d["title"], d["kind"], json.dumps(d), "pending", 0, now()))

    def get_roadmap(self, uid: str) -> list[dict]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM roadmap WHERE user_id=? ORDER BY seq", (uid,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["plan"] = json.loads(d["plan"])
            d["task_state"] = json.loads(d.get("task_state") or "{}")
            out.append(d)
        return out

    def update_day(self, day_id: int, **fields) -> None:
        if not fields:
            return
        if "plan" in fields:
            fields["plan"] = json.dumps(fields["plan"])
        if "task_state" in fields:
            fields["task_state"] = json.dumps(fields["task_state"])
        fields["updated_at"] = now()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.conn() as c:
            c.execute(f"UPDATE roadmap SET {cols} WHERE id=?", (*fields.values(), day_id))

    def insert_days_after(self, uid: str, after_seq: int, days: list[dict]) -> None:
        """Insert extra days (revision / practice / reassessment) and renumber the rest."""
        with self.conn() as c:
            c.execute("UPDATE roadmap SET seq = seq + ? WHERE user_id=? AND seq > ?", (len(days), uid, after_seq))
            for i, d in enumerate(days, 1):
                c.execute("""INSERT INTO roadmap(user_id,seq,planned_date,skill_id,title,kind,plan,status,inserted,updated_at)
                             VALUES(?,?,?,?,?,?,?,?,?,?)""",
                          (uid, after_seq + i, d["planned_date"], d["skill_id"], d["title"], d["kind"], json.dumps(d), "pending", 1, now()))

    def set_dates(self, uid: str, dates: dict[int, str]) -> None:
        with self.conn() as c:
            for day_id, dt in dates.items():
                c.execute("UPDATE roadmap SET planned_date=? WHERE id=? AND user_id=?", (dt, day_id, uid))

    # ---------------------------------------------------------------- progress / verification
    def add_progress(self, uid: str, day_id: int | None, event: str, score: float | None = None, total: float | None = None,
                     detail: dict | None = None) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO progress(user_id,day_id,event,score,total,detail,created_at) VALUES(?,?,?,?,?,?,?)",
                      (uid, day_id, event, score, total, json.dumps(detail or {}), now()))

    def list_progress(self, uid: str, event: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM progress WHERE user_id=?", [uid]
        if event:
            q += " AND event=?"
            args.append(event)
        with self.conn() as c:
            return [dict(r) | {"detail": json.loads(r["detail"] or "{}")} for r in c.execute(q + " ORDER BY id", args)]

    def add_verification(self, uid: str, skill_id: str, level: str, score: float, passed: bool, detail: dict | None = None) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO verification(user_id,skill_id,level,score,passed,detail,created_at) VALUES(?,?,?,?,?,?,?)",
                      (uid, skill_id, level, score, int(passed), json.dumps(detail or {}), now()))

    def list_verifications(self, uid: str, skill_id: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM verification WHERE user_id=?", [uid]
        if skill_id:
            q += " AND skill_id=?"
            args.append(skill_id)
        with self.conn() as c:
            return [dict(r) | {"detail": json.loads(r["detail"] or "{}")} for r in c.execute(q + " ORDER BY id", args)]

    # ---------------------------------------------------------------- notifications
    def add_notification(self, uid: str, kind: str, title: str, body: str, dedupe_key: str | None = None) -> bool:
        with self.conn() as c:
            if dedupe_key and c.execute("SELECT 1 FROM notifications WHERE user_id=? AND dedupe_key=?", (uid, dedupe_key)).fetchone():
                return False
            c.execute("INSERT INTO notifications(user_id,kind,title,body,dedupe_key,created_at) VALUES(?,?,?,?,?,?)",
                      (uid, kind, title, body, dedupe_key, now()))
            return True

    def list_notifications(self, uid: str, limit: int = 50) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit))]

    def unread_count(self, uid: str) -> int:
        with self.conn() as c:
            return c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (uid,)).fetchone()[0]

    def mark_all_read(self, uid: str) -> None:
        with self.conn() as c:
            c.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))

    # ---------------------------------------------------------------- match history
    def add_snapshot(self, uid: str, label: str, top_job_id: str, top_score: float, suitable: int, avg_top5: float, detail: dict) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO match_history(user_id,created_at,label,top_job_id,top_score,suitable_count,avg_top5,detail) VALUES(?,?,?,?,?,?,?,?)",
                      (uid, now(), label, top_job_id, top_score, suitable, avg_top5, json.dumps(detail)))

    def list_snapshots(self, uid: str) -> list[dict]:
        with self.conn() as c:
            return [dict(r) | {"detail": json.loads(r["detail"] or "{}")} for r in c.execute("SELECT * FROM match_history WHERE user_id=? ORDER BY id", (uid,))]

    # ---------------------------------------------------------------- custom jobs
    def add_custom_job(self, job: dict) -> None:
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO custom_jobs VALUES(?,?)", (job["id"], json.dumps(job)))

    def list_custom_jobs(self) -> list[dict]:
        with self.conn() as c:
            return [json.loads(r["payload"]) for r in c.execute("SELECT payload FROM custom_jobs ORDER BY rowid")]

    def delete_custom_job(self, job_id: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM custom_jobs WHERE job_id=?", (job_id,))
