"""HTML/CSS komponenty pro hezčí UI (Streamlit sám o sobě umí jen základní prvky)."""
from __future__ import annotations

from html import escape

import streamlit as st

CSS = """
<style>
:root { --ink:#1c1f2e; --muted:#6b7085; --line:#e6e8f0; --brand:#4f46e5; }
.block-container { padding-top: 2rem; max-width: 1180px; }
h1, h2, h3 { letter-spacing: -0.01em; }

.hero { padding: 1.4rem 1.6rem; border-radius: 18px; margin-bottom: 1.2rem;
        background: linear-gradient(135deg,#4f46e5 0%,#7c3aed 55%,#db2777 100%); color:#fff; }
.hero h1 { color:#fff; margin:0; font-size:2rem; }
.hero p  { margin:.35rem 0 0; opacity:.92; font-size:1.02rem; }

.step { font-weight:700; color:var(--brand); font-size:.8rem; text-transform:uppercase;
        letter-spacing:.06em; margin-bottom:.2rem; }

.card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:1rem 1.2rem;
        margin-bottom:.75rem; box-shadow:0 1px 2px rgba(20,20,50,.04); }
.card h4 { margin:0 0 .4rem; font-size:1rem; }
.muted { color:var(--muted); font-size:.88rem; }

.ring { width:170px; height:170px; border-radius:50%; margin:.4rem auto .6rem;
        display:flex; align-items:center; justify-content:center; }
.ring-inner { width:130px; height:130px; border-radius:50%; background:#fff;
        display:flex; flex-direction:column; align-items:center; justify-content:center; }
.ring-num { font-size:2.6rem; font-weight:800; line-height:1; color:var(--ink); }
.ring-lbl { font-size:.8rem; color:var(--muted); }
.verdict-label { text-align:center; font-weight:700; font-size:1.1rem; }

.chip { display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.78rem;
        font-weight:600; margin:0 .3rem .3rem 0; border:1px solid transparent; }
.chip.met { background:#e6f6ef; color:#137a52; border-color:#bfe8d4; }
.chip.partial { background:#fff6db; color:#8a6400; border-color:#f3e0a3; }
.chip.missing { background:#fde8eb; color:#a3243a; border-color:#f5c2cb; }
.chip.must { background:#eef0ff; color:#3730a3; }
.chip.nice { background:#f2f3f7; color:#555b70; }
.chip.skill { background:#f2f3f7; color:#2d3142; font-weight:500; }

.req { display:flex; gap:.8rem; align-items:flex-start; padding:.7rem .9rem; border-radius:12px;
       border:1px solid var(--line); background:#fff; margin-bottom:.5rem; }
.req .dot { width:10px; height:10px; border-radius:50%; margin-top:.45rem; flex:none; }
.req .t { font-weight:600; }

.bar { height:9px; background:#eef0f6; border-radius:99px; overflow:hidden; margin:.2rem 0 .6rem; }
.bar > div { height:100%; border-radius:99px; }

.old { background:#f6f6f9; color:#7a7f93; text-decoration:line-through; padding:.5rem .7rem;
       border-radius:10px; font-size:.9rem; }
.new { background:#ecfdf5; border:1px solid #c7eedc; padding:.6rem .8rem; border-radius:10px; margin-top:.4rem; }

.timeline { border-left:2px solid var(--line); margin-left:.4rem; padding-left:1rem; }
.timeline .item { position:relative; margin-bottom:.8rem; }
.timeline .item:before { content:""; position:absolute; left:-1.42rem; top:.35rem; width:10px; height:10px;
        border-radius:50%; background:var(--brand); }
</style>
"""

STATUS_CZ = {"met": "Splněno", "partial": "Částečně", "missing": "Chybí"}
STATUS_COLOR = {"met": "#1f9d6b", "partial": "#e0a100", "missing": "#d1495b"}
IMPORTANCE_CZ = {"must": "povinné", "nice": "výhodou"}
CATEGORY_CZ = {
    "hard_skill": "Technické dovednosti", "soft_skill": "Měkké dovednosti",
    "experience": "Praxe", "education": "Vzdělání", "language": "Jazyky", "other": "Ostatní",
}


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def inject_css() -> None:
    html(CSS)


def hero(title: str, subtitle: str) -> None:
    html(f'<div class="hero"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>')


def score_ring(score: int, label: str, color: str) -> None:
    html(
        f'<div class="ring" style="background:conic-gradient({color} {score * 3.6}deg,#eef0f6 0deg)">'
        f'<div class="ring-inner"><div class="ring-num">{score}</div><div class="ring-lbl">ze 100</div></div></div>'
        f'<div class="verdict-label" style="color:{color}">{escape(label)}</div>'
    )


def chips(items: list[str], kind: str = "skill") -> str:
    return "".join(f'<span class="chip {kind}">{escape(str(i))}</span>' for i in items)


def bar(label: str, value: int) -> str:
    color = "#1f9d6b" if value >= 75 else "#e0a100" if value >= 50 else "#d1495b"
    return (f'<div class="muted" style="display:flex;justify-content:space-between">'
            f'<span>{escape(label)}</span><span>{value} %</span></div>'
            f'<div class="bar"><div style="width:{value}%;background:{color}"></div></div>')


def requirement_row(text: str, importance: str, status: str, evidence: str) -> str:
    return (
        f'<div class="req"><div class="dot" style="background:{STATUS_COLOR[status]}"></div><div>'
        f'<div class="t">{escape(text)}</div>'
        f'<div style="margin:.25rem 0">'
        f'<span class="chip {status}">{STATUS_CZ[status]}</span>'
        f'<span class="chip {importance}">{IMPORTANCE_CZ[importance]}</span></div>'
        f'<div class="muted">{escape(evidence)}</div></div></div>'
    )


def card(title: str, body_html: str) -> None:
    html(f'<div class="card"><h4>{escape(title)}</h4>{body_html}</div>')


def bullet_list(items: list[str]) -> str:
    if not items:
        return '<div class="muted">—</div>'
    return "<ul style='margin:.2rem 0 0 1.1rem;padding:0'>" + "".join(
        f"<li style='margin-bottom:.25rem'>{escape(i)}</li>" for i in items) + "</ul>"
