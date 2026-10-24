"""Single source of truth for the design system (palette + CSS). Pages never define their own CSS."""
from __future__ import annotations

import streamlit as st

C = dict(
    bg="#F5F7FB", card="#FFFFFF", navy="#172554", accent="#4F46E5", violet="#7C3AED", teal="#0D9488",
    text="#1E293B", muted="#64748B", border="#E2E8F0", success="#15803D", warn="#D97706", error="#DC2626",
    # derived tints (backgrounds for states / hover)
    elevated="#EEF2FF", success_bg="#F0FDF4", warn_bg="#FFFBEB", error_bg="#FEF2F2", info_bg="#EEF2FF",
    track="#E2E8F0", neutral="#CBD5E1", sidebar="#172554",
)

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root { --bg:%(bg)s; --card:%(card)s; --navy:%(navy)s; --accent:%(accent)s; --violet:%(violet)s; --teal:%(teal)s;
  --text:%(text)s; --muted:%(muted)s; --border:%(border)s; --ok:%(success)s; --warn:%(warn)s; --err:%(error)s;
  --radius:14px; --shadow:0 1px 2px rgba(23,37,84,.06), 0 4px 14px rgba(23,37,84,.06); }
html, body, [class*="css"], .stApp, button, input, textarea { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }
.stApp { background:var(--bg); color:var(--text); }
header[data-testid="stHeader"] { background:transparent; }
#MainMenu, footer { visibility:hidden; }
.block-container { padding-top:2rem; padding-bottom:4rem; max-width:1100px; }
h1,h2,h3,h4 { color:var(--navy); letter-spacing:-0.02em; font-weight:700; }
p, li, label, span, .stMarkdown, div[data-testid="stCaptionContainer"] { color:var(--text); }
div[data-testid="stCaptionContainer"], .mt-muted { color:var(--muted); }
a { color:var(--accent); }

/* Sidebar: navy, white text */
section[data-testid="stSidebar"] { background:var(--navy); border-right:0; }
section[data-testid="stSidebar"] * { color:#E0E7FF; }
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] { border-radius:10px; padding:.45rem .7rem; }
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover { background:rgba(255,255,255,.08); }
section[data-testid="stSidebar"] a[aria-current="page"] { background:rgba(255,255,255,.16); }
section[data-testid="stSidebar"] a[aria-current="page"] span { color:#fff; font-weight:600; }
.mt-brand { font-weight:800; font-size:1.3rem; letter-spacing:-0.02em; color:#fff !important; }
.mt-brand span { color:#A5B4FC !important; }
.mt-tag { color:#A5B4FC !important; font-size:.8rem; margin-top:-2px; line-height:1.35; }
.mt-side-card { background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.14); border-radius:12px; padding:.7rem .9rem; margin-top:1rem; }
.mt-side-card p { margin:.35rem 0 0; font-size:.8rem; color:#C7D2FE !important; }

/* Hero */
.mt-hero { background:linear-gradient(135deg, var(--navy) 0%%, #3730A3 55%%, var(--violet) 100%%); border-radius:20px;
  padding:2.4rem 2.2rem; box-shadow:var(--shadow); margin-bottom:1.2rem; }
.mt-hero * { color:#fff !important; }
.mt-hero h1 { font-size:2.5rem; line-height:1.12; margin:.2rem 0 .7rem; font-weight:800; }
.mt-hero p { font-size:1.05rem; max-width:680px; color:#E0E7FF !important; }
.mt-eyebrow { color:var(--accent); font-weight:700; font-size:.76rem; letter-spacing:.12em; text-transform:uppercase; }
.mt-hero .mt-eyebrow { color:#C4B5FD !important; }

/* Cards */
.mt-card { background:var(--card); border:1px solid var(--border); border-radius:var(--radius); padding:1.1rem 1.25rem; margin-bottom:.9rem; box-shadow:var(--shadow); }
.mt-card h4 { margin:0 0 .35rem; font-size:1rem; color:var(--navy); }
.mt-card p { margin:.25rem 0; color:var(--muted); line-height:1.6; }
.mt-card.accent { border-left:4px solid var(--accent); }
.mt-card.ok { border-left:4px solid var(--ok); background:%(success_bg)s; }
.mt-card.warn { border-left:4px solid var(--warn); background:%(warn_bg)s; }
.mt-card.err { border-left:4px solid var(--err); background:%(error_bg)s; }
.mt-card.info { border-left:4px solid var(--teal); background:#F0FDFA; }
.mt-card.ok h4 { color:var(--ok); } .mt-card.warn h4 { color:#B45309; } .mt-card.err h4 { color:var(--err); }
.mt-card.ok p, .mt-card.warn p, .mt-card.err p { color:var(--text); }
.mt-metric { background:var(--card); border:1px solid var(--border); border-radius:var(--radius); padding:1rem 1.2rem; box-shadow:var(--shadow); }
.mt-metric .v { font-size:2rem; font-weight:800; letter-spacing:-0.02em; color:var(--navy); }
.mt-metric .l { color:var(--muted); font-size:.74rem; text-transform:uppercase; letter-spacing:.08em; font-weight:600; }
.mt-metric .h { color:var(--muted); font-size:.8rem; margin-top:2px; }
.mt-chip { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.74rem; font-weight:600; border:1px solid var(--border); background:#fff; color:var(--muted); margin:0 6px 4px 0; }
.mt-chip.ok { color:var(--ok); background:%(success_bg)s; border-color:#BBF7D0; }
.mt-chip.warn { color:#B45309; background:%(warn_bg)s; border-color:#FDE68A; }
.mt-chip.err { color:var(--err); background:%(error_bg)s; border-color:#FECACA; }
.mt-chip.accent { color:var(--accent); background:%(elevated)s; border-color:#C7D2FE; }
.mt-side-card .mt-chip { background:rgba(255,255,255,.14); border-color:rgba(255,255,255,.25); color:#fff !important; }
.mt-bar { background:var(--track); border-radius:999px; height:9px; overflow:hidden; }
.mt-bar > div { height:100%%; border-radius:999px; }
.mt-row { display:flex; justify-content:space-between; align-items:baseline; font-size:.92rem; margin:12px 0 5px; }
.mt-quote, .mt-step { font-family:ui-monospace, 'Cascadia Code', Consolas, monospace; background:#F8FAFC; border:1px solid var(--border); color:var(--text); border-radius:8px; }
.mt-quote { padding:3px 10px; display:inline-block; }
.mt-step { padding:7px 12px; margin:5px 0; }
.mt-step.bad { background:%(error_bg)s; border-color:#FECACA; }
.mt-step.good { background:%(success_bg)s; border-color:#BBF7D0; }

/* Controls */
.stButton > button, .stFormSubmitButton > button { border-radius:10px; border:1px solid var(--border); background:#fff; color:var(--navy); font-weight:600; padding:.5rem 1.15rem; box-shadow:0 1px 2px rgba(23,37,84,.06); transition:all .15s ease; }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color:var(--accent); color:var(--accent); }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] { background:var(--accent); border-color:var(--accent); color:#fff; }
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover { background:#4338CA; border-color:#4338CA; color:#fff; }
.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible, a:focus-visible, button:focus-visible { outline:3px solid #A5B4FC !important; outline-offset:2px; }
textarea, input { background:#fff !important; color:var(--text) !important; border-radius:10px !important; }
div[data-baseweb="textarea"], div[data-baseweb="input"], div[data-baseweb="select"] > div { background:#fff !important; border-color:var(--border) !important; border-radius:10px !important; }
div[data-baseweb="textarea"]:focus-within, div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within { border-color:var(--accent) !important; box-shadow:0 0 0 3px #C7D2FE; }
div[data-baseweb="popover"] li, div[data-baseweb="menu"] li { color:var(--text); }
div[data-testid="stForm"] { background:var(--card); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); padding:1.2rem; }
div[data-testid="stExpander"] { border:1px solid var(--border); border-radius:var(--radius); background:var(--card); }
button[data-baseweb="tab"] { color:var(--muted); font-weight:600; }
button[data-baseweb="tab"][aria-selected="true"] { color:var(--accent); }
div[data-baseweb="tab-highlight"] { background:var(--accent); }
div[data-testid="stProgress"] div[role="progressbar"] > div > div { background:var(--accent); }
div[data-testid="stAlert"] { border-radius:12px; }
@media (max-width: 720px) { .mt-hero h1 { font-size:1.75rem; } .mt-hero { padding:1.5rem 1.2rem; } .block-container { padding-left:1rem; padding-right:1rem; } .mt-metric .v { font-size:1.6rem; } }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS % C, unsafe_allow_html=True)


def stretch() -> dict:
    """Width kwargs that avoid the deprecated use_container_width on current Streamlit."""
    try:
        major, minor = (int(x) for x in st.__version__.split(".")[:2])
    except ValueError:
        major, minor = 1, 50
    return {"width": "stretch"} if (major, minor) >= (1, 50) else {"use_container_width": True}
