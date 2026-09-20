"""Small HTML building blocks (cards, chips, rings, bars) rendered with st.markdown."""
from __future__ import annotations

import html
import re

import streamlit as st

from core.models import EVIDENCE_LABEL, LEVEL_NAMES

EVIDENCE_ICON = {"production": "🏢", "internship": "🎒", "verified_practical": "🏅", "major_project": "🏗️", "project": "🛠️", "github": "🐙",
                 "verified_quiz": "✅", "certification": "📜", "coursework": "📚", "practice": "🧩", "inferred": "🧭", "self_declared": "💬"}
STATUS_ICON = {"matched": "✓", "partial": "◐", "missing": "✗", "insufficient": "?"}
TIER_COLOR = {"Strong match": "mint", "Good match": "mint", "Close match": "lemon", "Stretch": "grape", "Not yet": "pink"}
PRIORITY_COLOR = {"Very High": "pink", "High": "tang", "Medium": "lemon", "Low": "grape"}


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def H(s: str) -> str:
    """Collapse indentation/newlines so Streamlit's markdown never treats HTML as a code block."""
    return re.sub(r"\s*\n\s*", " ", s.strip())


def show(s: str) -> None:
    st.markdown(H(s), unsafe_allow_html=True)


def section(title: str, sub: str = "", emoji: str = "") -> None:
    show(f'<div class="section">{emoji} {esc(title)}</div>' + (f'<div class="sub">{sub}</div>' if sub else ""))


def chip(text: str, color: str = "") -> str:
    return f'<span class="chip {color}">{esc(text)}</span>'


def status_chip(status: str) -> str:
    color = {"matched": "mint", "partial": "lemon", "missing": "pink", "insufficient": "grape"}[status]
    label = {"matched": "Matched", "partial": "Partial", "missing": "Missing", "insufficient": "Needs evidence"}[status]
    return f'<span class="chip {color}">{STATUS_ICON[status]} {label}</span>'


def pips(level: int, n: int = 4, cls: str = "") -> str:
    return f'<span class="pips {cls}" title="{esc(LEVEL_NAMES.get(level, ""))}">' + "".join(f'<i class="pip {"on" if i < level else ""}"></i>' for i in range(n)) + "</span>"


def ring(pct: float, size: str = "", color: str | None = None) -> str:
    color = color or ("var(--mint)" if pct >= 75 else "var(--lemon)" if pct >= 60 else "var(--tang)" if pct >= 45 else "var(--pink)")
    return f'<div class="ring {size}" style="--p:{max(0, min(100, pct)):.0f};--c:{color}"><span>{pct:.0f}%</span></div>'


def bar(pct: float, cls: str = "") -> str:
    return f'<div class="bar {cls}"><i style="width:{max(2, min(100, pct)):.0f}%"></i></div>'


def tile(n, label: str) -> str:
    return f'<div class="tile"><div class="n">{esc(n)}</div><div class="l">{esc(label)}</div></div>'


def evidence_chip(etype: str) -> str:
    return f'<span class="chip">{EVIDENCE_ICON.get(etype, "•")} {esc(EVIDENCE_LABEL.get(etype, etype))}</span>'


def empty_state(emoji: str, title: str, text: str) -> None:
    show(f'<div class="card empty"><div class="doodle">{emoji}</div><div class="big">{esc(title)}</div><p class="muted">{text}</p></div>')


def skeleton(n: int = 3) -> str:
    return "".join('<div class="shimmer"></div>' for _ in range(n))


def goto(page: str) -> None:
    """on_click callback: switch the sidebar page."""
    st.session_state["nav"] = page


def jump(page: str) -> None:
    """Navigate from inside page code (after widgets exist): queue the page and rerun."""
    st.session_state["_goto"] = page
    st.rerun()


def plot(fig) -> None:
    """st.plotly_chart across Streamlit versions (width='stretch' in new releases, use_container_width in older)."""
    cfg = {"displayModeBar": False}
    try:
        st.plotly_chart(fig, width="stretch", config=cfg)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, config=cfg)
