"""Personalised notification layer: morning plan, evening nudge, completion, unlock alerts.

Notifications are stored in SQLite and shown in the app (bell + toasts). If TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID are set, the same messages are also pushed to Telegram.
"""
from __future__ import annotations

from datetime import date, datetime

from .config import env


def send_telegram(text: str) -> bool:
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    try:
        import requests

        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": text}, timeout=8)
        return r.ok
    except Exception:
        return False


def _push(db, uid: str, kind: str, title: str, body: str, key: str | None = None) -> bool:
    created = db.add_notification(uid, kind, title, body, key)
    if created:
        send_telegram(f"{title}\n{body}")
    return created


def morning(db, uid: str, day: dict) -> bool:
    p = day["plan"]
    lines = [f"Today's focus: {p['title']}", f"Estimated time: {p.get('est_minutes', 90)} minutes."]
    if p.get("watch"):
        lines.append("🎥 Watch  📚 Learn  💻 Practice  🧪 Check-in" if p["kind"] in ("learn", "practice", "revision") else "🧪 Assessment day")
    return _push(db, uid, "morning", f"🌅 Day {day['seq']} is ready", "\n".join(lines), f"morning:{day['planned_date']}:{day['id']}")


def evening(db, uid: str, day: dict) -> bool:
    return _push(db, uid, "evening", "🔔 Today's roadmap task is incomplete",
                 f"{day['plan']['title']} is still open. Continue now, or reschedule from the Daily Task page.",
                 f"evening:{day['planned_date']}:{day['id']}")


def completed(db, uid: str, day: dict, next_day: dict | None, note: str = "") -> bool:
    body = note or f"{day['plan']['title']} is done."
    if next_day:
        body += f"\nTomorrow: {next_day['plan']['title']}."
    return _push(db, uid, "completion", f"🎉 Day {day['seq']} completed!", body, f"done:{day['id']}:{day['status']}")


def verified(db, uid: str, skill_name: str, level: str) -> bool:
    return _push(db, uid, "verified", f"✅ {skill_name} verified", f"{skill_name} is now {level}-verified and counts as strong evidence when we re-match your jobs.")


def unlocked(db, uid: str, before: int, after: int, skill_name: str) -> bool:
    if after <= before:
        return False
    return _push(db, uid, "unlock", "🔓 New roles unlocked",
                 f"Your updated skills unlocked {after - before} additional role(s) in the curated job set ({before} → {after}). "
                 "That means they meet our matching criteria – not a guarantee of hiring.", f"unlock:{skill_name}:{after}")


def tick(db, uid: str, roadmap: list[dict], now: datetime | None = None, force: str | None = None) -> list[str]:
    """Generate any notifications that are due. `force` in {'morning','evening'} simulates the time of day (demo)."""
    now = now or datetime.now()
    today = (now.date() if not isinstance(now, date) or isinstance(now, datetime) else now).isoformat()
    todays = [d for d in roadmap if d["planned_date"] <= today and d["status"] == "pending"]
    if not todays:
        return []
    day = todays[0]
    made = []
    if force == "morning" or (force is None and now.hour >= 6):
        if morning(db, uid, day):
            made.append("morning")
    if force == "evening" or (force is None and now.hour >= 18):
        if evening(db, uid, day):
            made.append("evening")
    return made
