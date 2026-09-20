from __future__ import annotations

import streamlit as st

from core.config import env
from ui import state
from ui.components import chip, empty_state, esc, section, show

ICON = {"morning": "🌅", "evening": "🌙", "completion": "🎉", "verified": "🏅", "unlock": "🔓"}
COLOR = {"morning": "lemon", "evening": "grape", "completion": "mint", "verified": "mint", "unlock": "pink"}


def _sim(kind: str) -> None:
    made = state.eng().notify_tick(state.UID, force=kind)
    st.session_state["notif_msg"] = f"Simulated {kind}: " + (", ".join(made) if made else "nothing new (already sent today, or no pending day)")


def render() -> None:
    e = state.eng()
    section("Notifications", "Personal nudges tied to your roadmap – morning plan, evening reminder, completions and unlocks.", "🔔")
    c1, c2, c3 = st.columns(3)
    c1.button("🌅 Simulate morning", on_click=_sim, args=("morning",), key="n_m")
    c2.button("🌙 Simulate evening (task incomplete)", on_click=_sim, args=("evening",), key="n_e")
    c3.button("✓ Mark all read", on_click=lambda: e.db.mark_all_read(state.UID), key="n_r")
    if st.session_state.get("notif_msg"):
        st.info(st.session_state.pop("notif_msg"))
    items = e.db.list_notifications(state.UID)
    if not items:
        empty_state("🔕", "All quiet", "Create a roadmap and complete a day – notifications appear here (use the simulate buttons to preview them).")
    for n in items:
        show(f'<div class="card tight {"lemon" if not n["read"] else ""}"><div class="row top"><div style="font-size:2rem">{ICON.get(n["kind"], "🔔")}</div><div class="grow"><b style="font-size:1.25rem">{esc(n["title"])}</b> '
             f'<span class="mono muted">{esc(n["created_at"][:16].replace("T", " "))}</span><div style="white-space:pre-wrap">{esc(n["body"]).replace(chr(10), "<br>")}</div></div>{chip(n["kind"], COLOR.get(n["kind"], ""))}</div></div>')
    tg = bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"))
    show(f'<div class="card tight">📨 <b>Push channel:</b> {"Telegram connected ✔" if tg else "in-app only. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env to mirror every message to your phone."}</div>')
