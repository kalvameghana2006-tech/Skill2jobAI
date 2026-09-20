"""Visual identity: 'sketchbook studio' – handwriting type, ink-and-highlighter colours, hand-drawn borders."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

INK, PAPER, TANG, PINK, MINT, LEMON, SKY, GRAPE = "#2B1A4A", "#F4EEFF", "#FF6A2B", "#FF4F9B", "#21D4A0", "#FFE24A", "#52A8FF", "#7A4DFF"
PALETTE = [TANG, GRAPE, MINT, PINK, SKY, LEMON, "#FF9F1C", "#2EC4B6"]
STATUS_COLOR = {"matched": MINT, "partial": LEMON, "missing": PINK, "insufficient": GRAPE}


def inject_css() -> None:
    css = (Path(__file__).parent / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def style_fig(fig, height: int = 340):
    """Apply the sketchbook look to a plotly figure."""
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,253,246,.9)",
        font=dict(family="Patrick Hand, Kalam, cursive", size=16, color=INK), colorway=PALETTE,
        legend=dict(bgcolor="rgba(255,253,246,.9)", bordercolor=INK, borderwidth=2),
        hoverlabel=dict(font=dict(family="Patrick Hand", size=15), bgcolor="#FFFDF6", bordercolor=INK),
    )
    if any(getattr(t, "type", "") == "scatterpolar" for t in fig.data):
        fig.update_layout(margin=dict(l=80, r=80, t=30, b=30))
    fig.update_xaxes(gridcolor="rgba(43,26,74,.12)", linecolor=INK, linewidth=2, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(43,26,74,.12)", linecolor=INK, linewidth=2, zeroline=False)
    return fig
