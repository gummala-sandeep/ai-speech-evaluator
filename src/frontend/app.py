"""app.py — SkillEcho Multi-Page Streamlit Application v2.0"""
from __future__ import annotations
import io, json, logging, os, base64
import subprocess
import sys
import time
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, requests, streamlit as st

st.set_page_config(page_title="SkillEcho Platform", page_icon="🎙️", layout="wide", initial_sidebar_state="expanded")

from src.backend.services.reports import generate_pdf_report

logger = logging.getLogger(__name__)

@st.cache_resource
def start_backend():
    cmd = ["python", "-m", "uvicorn", "src.backend.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    try:
        env = os.environ.copy()
        try:
            if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
                env["DATABASE_URL"] = st.secrets["DATABASE_URL"]
        except Exception:
            pass
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        return proc
    except Exception as e:
        logger.exception("Failed to start FastAPI backend: %s", e)
        return None

# Trigger FastAPI backend start
start_backend()

API = "http://127.0.0.1:8000"

# In-memory sessions cache to prevent multi-device / multi-user session collision on disk
if "_ACTIVE_SESSIONS" not in globals():
    globals()["_ACTIVE_SESSIONS"] = {}

_ACTIVE_SESSIONS = globals()["_ACTIVE_SESSIONS"]

import uuid

def _save_session(user_id: int, name: str, role: str) -> None:
    """Save session to in-memory store and set query parameter to prevent multi-user collisions on disk."""
    try:
        session_id = str(uuid.uuid4())
        _ACTIVE_SESSIONS[session_id] = {"user_id": user_id, "name": name, "role": role}
        st.query_params["session"] = session_id
    except Exception as e:
        logger.warning("Could not save session: %s", e)

def _load_session() -> dict | None:
    """Load session from query parameter and in-memory store."""
    try:
        session_id = st.query_params.get("session")
        if session_id and session_id in _ACTIVE_SESSIONS:
            return _ACTIVE_SESSIONS[session_id]
    except Exception as e:
        logger.warning("Could not load session: %s", e)
    return None

def _clear_session() -> None:
    """Delete session from query parameter and in-memory store on logout."""
    try:
        session_id = st.query_params.get("session")
        if session_id:
            _ACTIVE_SESSIONS.pop(session_id, None)
        st.query_params.clear()
    except Exception as e:
        logger.warning("Could not clear session: %s", e)

# Injecting Custom CSS to enforce the "Premium Obsidian" dark theme
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,400..900;1,400..900&display=swap');

/* Force dark background and core container colors */
html, body, [class*="css"], [data-testid="stAppViewContainer"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    background-color: #09090E !important;
    color: #F1F5F9 !important;
}

.stApp {
    background-color: #09090E !important;
    background-image: radial-gradient(circle at 50% 0%, #1c0e3a 0%, #09090e 70%) !important;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
}

h1, h2, h3, h4, h5, h6, [data-testid="stHeader"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: #F1F5F9 !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px !important;
}

/* Glassmorphic Forms */
.stForm {
    background: rgba(22, 22, 42, 0.55) !important;
    backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 16px !important;
    padding: 2.2rem !important;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.35) !important;
}

/* Text inputs, textareas, and selectboxes styling */
input, textarea, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="select"] div {
    background-color: rgba(22, 22, 42, 0.6) !important;
    color: #F1F5F9 !important;
    -webkit-text-fill-color: #F1F5F9 !important;
    border-radius: 8px !important;
    font-size: 0.92rem !important;
}

[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] {
    background-color: rgba(22, 22, 42, 0.6) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 8px !important;
}

input:focus, textarea:focus, [data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within {
    border-color: #8B5CF6 !important;
    background-color: rgba(26, 26, 53, 0.8) !important;
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.25) !important;
}

/* Dropdown list styling */
div[role="listbox"] {
    background-color: #101021 !important;
    color: #F1F5F9 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

div[role="option"] {
    color: #E2E8F0 !important;
    transition: all 0.2s ease !important;
}

div[role="option"]:hover {
    background-color: rgba(124, 58, 237, 0.2) !important;
    color: #FFFFFF !important;
}

/* Tab overrides (Glass Pill Segment Control) */
div[role="tablist"] {
    background: rgba(22, 22, 42, 0.45) !important;
    border-radius: 12px !important;
    padding: 6px !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    gap: 8px !important;
    margin-bottom: 1.5rem !important;
}

button[data-baseweb="tab"] {
    background: transparent !important;
    border-bottom: none !important;
    border-radius: 8px !important;
    padding: 8px 18px !important;
    color: #94A3B8 !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3) !important;
}

button[data-baseweb="tab"]:hover {
    color: #FFFFFF !important;
    background: rgba(255, 255, 255, 0.05) !important;
}

/* Buttons styling */
.stButton button, .stDownloadButton button, .stFormSubmitButton button, button[data-testid*="baseButton"] {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

.stButton button p, .stDownloadButton button p, .stFormSubmitButton button p, button[data-testid*="baseButton"] p {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* Primary buttons styling (Glowing Purple) */
.stButton button, .stFormSubmitButton button {
    background: linear-gradient(135deg, #7C3AED 0%, #4F46E5 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.3px !important;
    padding: 0.65rem 1.4rem !important;
    box-shadow: 0 4px 15px rgba(124, 58, 237, 0.25) !important;
    transition: all 0.25s ease-in-out !important;
    width: 100% !important;
}

.stButton button:hover, .stFormSubmitButton button:hover,
.stButton button:focus, .stFormSubmitButton button:focus,
.stButton button:active, .stFormSubmitButton button:active {
    transform: translateY(-1.5px) !important;
    box-shadow: 0 8px 24px rgba(124, 58, 237, 0.45) !important;
    background: linear-gradient(135deg, #8B5CF6 0%, #5B21B6 100%) !important;
}

/* Download buttons styling (Glowing Green/Teal) */
.stDownloadButton button {
    background: linear-gradient(135deg, #059669 0%, #0D9488 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    padding: 0.65rem 1.4rem !important;
    box-shadow: 0 4px 15px rgba(5, 150, 105, 0.2) !important;
    transition: all 0.25s ease-in-out !important;
    width: 100% !important;
}

.stDownloadButton button:hover, .stDownloadButton button:focus, .stDownloadButton button:active {
    transform: translateY(-1.5px) !important;
    box-shadow: 0 8px 24px rgba(5, 150, 105, 0.4) !important;
    background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
}

/* Sidebar overrides */
[data-testid="stSidebar"] {
    background-color: #0B0B14 !important;
    background-image: linear-gradient(180deg, #0B0B14 0%, #150F2E 100%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p, 
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span {
    color: #F1F5F9 !important;
}

[data-testid="stSidebar"] button {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    color: #94A3B8 !important;
    transition: all 0.2s ease !important;
    text-align: left !important;
    justify-content: flex-start !important;
}
[data-testid="stSidebar"] button:hover {
    background: rgba(124, 58, 237, 0.12) !important;
    color: #FFFFFF !important;
    border-color: rgba(124, 58, 237, 0.3) !important;
}

/* Metric layouts (SaaS Dashboard styling) */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(22, 22, 42, 0.65) 0%, rgba(16, 16, 33, 0.3) 100%) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 12px !important;
    padding: 1.2rem !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
    transition: all 0.3s ease !important;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px) !important;
    border-color: rgba(124, 58, 237, 0.25) !important;
    box-shadow: 0 8px 25px rgba(124, 58, 237, 0.1) !important;
}

[data-testid="stMetric"] [data-testid="stMetricLabel"] > div {
    color: #94A3B8 !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] > div {
    color: #F1F5F9 !important;
    font-weight: 800 !important;
    font-size: 1.6rem !important;
    margin-top: 4px !important;
}

/* Expanders (Accordion glassmorphism) */
.streamlit-expanderHeader {
    background: rgba(22, 22, 42, 0.4) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 10px !important;
    padding: 12px 18px !important;
    font-weight: 600 !important;
    color: #F1F5F9 !important;
    transition: all 0.3s ease !important;
}

.streamlit-expanderHeader:hover {
    background: rgba(124, 58, 237, 0.08) !important;
    border-color: rgba(124, 58, 237, 0.25) !important;
}

.streamlit-expanderContent {
    background: rgba(16, 16, 33, 0.15) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    padding: 1.5rem !important;
}

/* File Uploaders */
[data-testid="stFileUploader"] {
    background-color: rgba(22, 22, 42, 0.3) !important;
    border: 1.5px dashed rgba(124, 58, 237, 0.3) !important;
    border-radius: 12px !important;
    padding: 1.5rem !important;
    transition: all 0.3s ease !important;
}

[data-testid="stFileUploader"]:hover {
    border-color: #8B5CF6 !important;
    background-color: rgba(124, 58, 237, 0.05) !important;
}

[data-testid="stFileUploader"] section {
    background-color: transparent !important;
}

/* User Card List and Grid */
.user-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1.2rem;
    margin-top: 1rem;
    margin-bottom: 1rem;
}
.user-item-card {
    background: rgba(22, 22, 42, 0.45);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px;
    padding: 1.2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}
.user-item-card:hover {
    transform: translateY(-3px);
    border-color: rgba(139, 92, 246, 0.4);
    box-shadow: 0 10px 25px rgba(139, 92, 246, 0.15);
}
.user-avatar-circle {
    width: 46px;
    height: 46px;
    border-radius: 50%;
    background: linear-gradient(135deg, #7C3AED, #4F46E5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #FFFFFF;
    font-size: 1.1rem;
    box-shadow: 0 4px 10px rgba(124, 58, 237, 0.3);
    text-transform: uppercase;
}
.user-avatar-circle.admin {
    background: linear-gradient(135deg, #EF4444, #B91C1C);
    box-shadow: 0 4px 10px rgba(239, 68, 68, 0.3);
}
.user-detail-info {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.user-detail-info h4 {
    margin: 0 !important;
    font-size: 0.98rem !important;
    font-weight: 700 !important;
    color: #F1F5F9 !important;
}
.user-detail-info p {
    margin: 0 !important;
    font-size: 0.8rem !important;
    color: #94A3B8 !important;
}
.user-card-badge {
    align-self: center;
    font-size: 0.68rem;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.user-card-badge.student-badge {
    background: rgba(124, 58, 237, 0.12);
    color: #C084FC;
    border: 1px solid rgba(124, 58, 237, 0.25);
}
.user-card-badge.admin-badge {
    background: rgba(239, 68, 68, 0.12);
    color: #FCA5A5;
    border: 1px solid rgba(239, 68, 68, 0.25);
}
.user-card-date {
    font-size: 0.7rem;
    color: #64748B;
    margin-top: 2px;
}

/* Scrollbars */
::-webkit-scrollbar {
    width: 8px;
}
::-webkit-scrollbar-thumb {
    background: #2D2D4E;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #475569;
}

hr {
    border-color: rgba(255, 255, 255, 0.08) !important;
}

/* Concept Cards Styling */
.concept-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1.5rem;
    margin-top: 1rem;
    margin-bottom: 1.5rem;
}
.concept-card {
    background: rgba(22, 22, 42, 0.45);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}
.concept-card:hover {
    transform: translateY(-4px);
    border-color: rgba(124, 58, 237, 0.3);
    box-shadow: 0 12px 30px rgba(124, 58, 237, 0.15);
}
.concept-card-title {
    font-size: 1.15rem !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    margin-bottom: 8px !important;
}
.concept-card-body {
    font-size: 0.88rem;
    color: #E2E8F0;
    line-height: 1.6;
    margin-bottom: 1rem;
    flex-grow: 1;
}
.concept-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 10px;
    margin-top: 10px;
}
.pdf-badge {
    font-size: 0.72rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: inline-block;
}
.pdf-badge.attached {
    background: rgba(5, 150, 105, 0.12);
    color: #34D399;
    border: 1px solid rgba(5, 150, 105, 0.25);
}
.pdf-badge.none {
    background: rgba(100, 116, 139, 0.12);
    color: #94A3B8;
    border: 1px solid rgba(100, 116, 139, 0.25);
}

/* Results (Assessment) Cards Styling */
.results-list {
    display: flex;
    flex-direction: column;
    gap: 1.2rem;
    margin-top: 1rem;
}
.result-card {
    background: rgba(22, 22, 42, 0.45);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 1.5rem;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}
.result-card:hover {
    border-color: rgba(124, 58, 237, 0.25);
    box-shadow: 0 8px 25px rgba(124, 58, 237, 0.1);
}
.result-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    padding-bottom: 10px;
    margin-bottom: 12px;
}
.result-card-student-info {
    display: flex;
    align-items: center;
    gap: 10px;
}
.result-card-score-badge {
    font-size: 1.2rem;
    font-weight: 800;
    padding: 6px 14px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>""", unsafe_allow_html=True)

# ── UI helpers ────────────────────────────────────────────────────────────────
def card(title, body, color="#7C3AED"):
    return (f'<div style="background: rgba(22, 22, 42, 0.5); backdrop-filter: blur(12px);'
            f'border: 1px solid rgba(255, 255, 255, 0.05); border-left: 4px solid {color};'
            f'border-radius: 12px; padding: 1.4rem; margin-bottom: 1.2rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);'
            f'transition: all 0.3s ease;">'
            f'<p style="color: #94A3B8; font-size: .75rem; font-weight: 700; letter-spacing: 1px;'
            f'text-transform: uppercase; margin: 0 0 8px;">{title}</p>'
            f'<div style="color: #F1F5F9; font-size: .95rem; line-height: 1.7;">{body}</div></div>')

def score_html(score, level, colour):
    return (f'<div style="background: radial-gradient(circle at top, rgba(22, 22, 42, 0.8), rgba(10, 10, 21, 0.9));'
            f'backdrop-filter: blur(16px); border: 2px solid {colour};'
            f'border-radius: 16px; padding: 2.2rem 2rem; text-align: center; box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4), 0 0 25px {colour}15; margin-bottom: 1.5rem;">'
            f'<p style="color:#94A3B8;font-size:.8rem;letter-spacing:2px;text-transform:uppercase;margin:0 0 10px;font-weight:700;">FINAL COMPREHENSION SCORE</p>'
            f'<p style="color:{colour};font-size:5rem;font-weight:900;margin:0;line-height:1;text-shadow: 0 0 15px {colour}33;">{score}</p>'
            f'<p style="color:#94A3B8;font-size:.85rem;margin:6px 0 0;font-weight:500;">out of 100</p>'
            f'<div style="height:1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.08), transparent); margin:1.2rem 0;"></div>'
            f'<p style="color:{colour};font-size:1.25rem;font-weight:800;margin:0;letter-spacing:0.5px;text-transform:uppercase;">{level}</p></div>')

def format_definition_text(text: str) -> str:
    """Format definition text into styled HTML paragraphs and lists."""
    if not text:
        return ""
    lines = text.split("\n")
    html_parts = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue
            
        # Check if list item
        if stripped.startswith("-") or stripped.startswith("*") or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] == '.'):
            if not in_list:
                html_parts.append('<ul style="margin: 0.5rem 0 1rem 0; padding-left: 1.5rem; color: #F1F5F9;">')
                in_list = True
            
            # Remove leading marker
            if stripped.startswith("-") or stripped.startswith("*"):
                content = stripped[1:].strip()
            else:
                idx = stripped.find('.')
                content = stripped[idx+1:].strip()
                
            html_parts.append(f'<li style="margin-bottom: 0.4rem; font-size: 0.92rem; line-height: 1.6;">{content}</li>')
        else:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            html_parts.append(f'<p style="color:#F1F5F9; font-size:.92rem; line-height:1.7; margin:0 0 0.8rem 0;">{stripped}</p>')
            
    if in_list:
        html_parts.append('</ul>')
        
    return "".join(html_parts)

def render_waveform(audio_bytes):
    import soundfile as sf
    y, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if y.ndim > 1: y = y.mean(axis=1)
    t = np.linspace(0, len(y)/sr, num=len(y))
    fig, ax = plt.subplots(figsize=(10, 2.8), facecolor="#16162A")
    ax.set_facecolor("#16162A")
    ax.fill_between(t, y, alpha=0.35, color="#7C3AED")
    ax.plot(t, y, color="#8B5CF6", linewidth=0.7)
    ax.set_xlabel("Time (s)", color="#94A3B8", fontsize=9)
    ax.set_ylabel("Amplitude", color="#94A3B8", fontsize=9)
    ax.tick_params(colors="#94A3B8", labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor("#2D2D4E")
    ax.axhline(0, color="#2D2D4E", linewidth=0.6, linestyle="--")
    fig.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#16162A")
    plt.close(fig); buf.seek(0)
    return buf.getvalue()

# ── API helpers ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_concepts():
    try:
        r = requests.get(f"{API}/concepts", timeout=8); r.raise_for_status()
        return r.json().get("concepts", [])
    except Exception as e:
        st.error(f"Backend unreachable: {e}"); return []

def fetch_concept_pdf(concept_id: int) -> bytes | None:
    try:
        r = requests.get(f"{API}/concepts/{concept_id}/pdf", timeout=15)
        if r.status_code == 200:
            return r.content
    except Exception as e:
        logger.warning("Could not fetch concept PDF: %s", e)
    return None

def _get_error_detail(e: Exception) -> str:
    """Extract a friendly error message from a requests exception, checking for JSON detail."""
    if isinstance(e, requests.HTTPError) and e.response is not None:
        try:
            err_json = e.response.json()
            if isinstance(err_json, dict) and "detail" in err_json:
                detail = err_json["detail"]
                if isinstance(detail, list):
                    parts = []
                    for item in detail:
                        if isinstance(item, dict) and "msg" in item:
                            parts.append(str(item["msg"]))
                        else:
                            parts.append(str(item))
                    return ", ".join(parts)
                return str(detail)
        except Exception:
            pass
        try:
            text = e.response.text
            if text and len(text) < 150:
                return text
        except Exception:
            pass
    return str(e)

def api_post(path, payload):
    try:
        r = requests.post(f"{API}{path}", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"❌ {_get_error_detail(e)}")
        return None

def api_post_concept(title: str, definition: str, pdf_file) -> dict | None:
    try:
        files = {}
        if pdf_file is not None:
            files["reference_pdf"] = (pdf_file.name, pdf_file.getvalue(), "application/pdf")
        
        data = {
            "concept_title": title,
            "concept_text": definition
        }
        r = requests.post(f"{API}/admin/concepts", data=data, files=files if files else None, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"❌ {_get_error_detail(e)}")
        return None

def api_delete_concept(concept_id: int) -> bool:
    try:
        r = requests.delete(f"{API}/admin/concepts/{concept_id}", timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        st.error(f"❌ Delete failed: {_get_error_detail(e)}")
        return False

def api_update_concept(concept_id: int, title: str, definition: str, pdf_file, clear_pdf: bool) -> dict | None:
    try:
        files = {}
        if pdf_file is not None:
            files["reference_pdf"] = (pdf_file.name, pdf_file.getvalue(), "application/pdf")
        
        data = {
            "concept_title": title,
            "concept_text": definition,
            "clear_pdf": str(clear_pdf).lower()
        }
        r = requests.put(f"{API}/admin/concepts/{concept_id}", data=data, files=files if files else None, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"❌ Update failed: {_get_error_detail(e)}")
        return None

def api_get_concept_pdf(concept_id: int):
    try:
        r = requests.get(f"{API}/concepts/{concept_id}/pdf", timeout=20)
        if r.status_code == 200:
            return r.content
        return None
    except Exception:
        return None

def api_get(path):
    try:
        r = requests.get(f"{API}{path}", timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"❌ {_get_error_detail(e)}")
        return None

def call_evaluate(audio_bytes, filename, ref_concept_id, user_id):
    try:
        r = requests.post(f"{API}/evaluate",
            files={"audio_file": (filename, audio_bytes, "audio/wav")},
            data={"ref_concept_id": str(ref_concept_id), "user_id": str(user_id)},
            timeout=180)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        st.error("⏱️ Timed out. Try a shorter clip.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Cannot connect to backend.")
        return None
    except Exception as e:
        st.error(f"❌ {_get_error_detail(e)}")
        return None

# ── Session state ───────────────────────────────────────────────────────────────
def init_state():
    # Initialise defaults
    for k, v in {"logged_in": False, "user_id": None, "user_name": None, "user_role": None,
                  "page": "login", "result": None, "waveform_png": None,
                  "pdf_bytes": None, "audio_bytes": None, "audio_filename": None, "last_concept_id": None,
                  "admin_concept_title": "", "admin_concept_text": "", "is_adding": False,
                  "editing_concept_id": None, "confirm_delete_id": None}.items():
        if k not in st.session_state: st.session_state[k] = v

    # Restore saved session from disk (survives page reloads)
    if not st.session_state["logged_in"]:
        saved = _load_session()
        if saved:
            st.session_state.update({
                "logged_in": True,
                "user_id":   saved["user_id"],
                "user_name": saved["name"],
                "user_role": saved["role"],
                "page": "admin" if saved["role"] == "admin" else "practice",
            })

def logout():
    _clear_session()  # Delete the persisted session file
    st.session_state.update({"logged_in": False, "user_id": None, "user_name": None,
        "user_role": None, "page": "login", "result": None, "waveform_png": None,
        "pdf_bytes": None, "audio_bytes": None, "audio_filename": None, "last_concept_id": None})
    st.rerun()

# ── Sidebar ───────────────────────────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown("<h2 style='color:#8B5CF6;font-size:1.5rem;margin:0;font-weight:800;letter-spacing:0.5px;'>🎙️ SkillEcho</h2>"
                    "<p style='color:#A78BFA;font-size:.75rem;margin:4px 0 1.2rem;font-style:italic;line-height:1.3;'>Validating vocal comprehension, echoing conceptual mastery.</p>",
                    unsafe_allow_html=True)
        st.markdown("---")
        if not st.session_state["logged_in"]:
            if st.button("🔑 Login", key="sb_l"): st.session_state["page"] = "login"; st.rerun()
            if st.button("📝 Register", key="sb_r"): st.session_state["page"] = "register"; st.rerun()
        elif st.session_state["user_role"] == "student":
            st.markdown(f"<p style='color:#F1F5F9;font-weight:600;margin:0;'>👤 {st.session_state['user_name']}</p>"
                        "<span style='background:#7C3AED22;color:#8B5CF6;font-size:.72rem;padding:2px 8px;border-radius:6px;font-weight:600;'>Student</span>",
                        unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🎙️ Practice Area", key="sb_p"): st.session_state["page"] = "practice"; st.rerun()
            if st.button("📊 My Dashboard", key="sb_d"): st.session_state["page"] = "dashboard"; st.rerun()
            st.markdown("---")
            if st.button("🚪 Logout", key="sb_lo"): logout()
        elif st.session_state["user_role"] == "admin":
            st.markdown(f"<p style='color:#F1F5F9;font-weight:600;margin:0;'>👤 {st.session_state['user_name']}</p>"
                        "<span style='background:#DC262622;color:#F87171;font-size:.72rem;padding:2px 8px;border-radius:6px;font-weight:600;'>Admin</span>",
                        unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚙️ Admin Panel", key="sb_a"): st.session_state["page"] = "admin"; st.rerun()
            st.markdown("---")
            if st.button("🚪 Logout", key="sb_lo2"): logout()

# ── Page 1: Login ─────────────────────────────────────────────────────────────
def page_login():
    st.markdown("<h1 style='color:#F1F5F9;font-size:2rem;font-weight:800;text-align:center;'>🔑 Welcome Back</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8;text-align:center;margin-bottom:2rem;'>Sign in to your SkillEcho account</p>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            sub = st.form_submit_button("Sign In →", use_container_width=True)
        if sub:
            if not email or not password:
                st.error("Email and password are required.")
            else:
                res = api_post("/auth/login", {"email": email, "password": password})
                if res:
                    _save_session(res["user_id"], res["name"], res["role"])  # Persist to disk
                    st.session_state.update({"logged_in": True, "user_id": res["user_id"],
                        "user_name": res["name"], "user_role": res["role"],
                        "page": "admin" if res["role"] == "admin" else "practice"})
                    st.success(f"✅ Welcome, {res['name']}!"); st.rerun()
        if st.button("Create Account →", key="go_reg"):
            st.session_state["page"] = "register"; st.rerun()

# ── Page 2: Register ──────────────────────────────────────────────────────────
def page_register():
    st.markdown("<h1 style='color:#F1F5F9;font-size:2rem;font-weight:800;text-align:center;'>📝 Create Account</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8;text-align:center;margin-bottom:2rem;'>Join SkillEcho to start practising</p>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("reg_form"):
            name = st.text_input("Full Name", placeholder="Jane Smith")
            email = st.text_input("Email", placeholder="jane@example.com")
            password = st.text_input("Password", type="password", placeholder="Min. 6 characters")
            role = st.selectbox("Account Type", ["student", "admin"])
            sub = st.form_submit_button("Create Account →", use_container_width=True)
        if sub:
            if not name or not email or not password:
                st.error("All fields are required.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                res = api_post("/auth/register", {"name": name, "email": email, "password": password, "role": role})
                if res:
                    st.success("✅ Account created! Please sign in.")
                    st.session_state["page"] = "login"; st.rerun()
        if st.button("← Back to Login", key="go_login"):
            st.session_state["page"] = "login"; st.rerun()

# ── Page 3: Practice Area ─────────────────────────────────────────────────────
def page_practice():
    st.markdown("<h1 style='color:#F1F5F9;font-size:1.9rem;font-weight:800;'>🎙️ Practice Area</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8;margin-bottom:1.5rem;'>Select a concept, upload your WAV explanation, and get instant AI feedback.</p>", unsafe_allow_html=True)
    st.markdown("---")
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("<h3 style='color:#8B5CF6;font-size:1.05rem;font-weight:700;'>📋 Concept & Audio</h3>", unsafe_allow_html=True)
        concepts = fetch_concepts()
        if not concepts:
            st.warning("No concepts found. Ensure the API is running."); return
        cmap = {c["concept_title"]: c for c in concepts}
        sel = cmap[st.selectbox("Select Reference Concept", list(cmap.keys()))]
        
        # Display nicely formatted definition
        formatted_definition = format_definition_text(sel['concept_text'])
        st.markdown(card("Reference Concept", formatted_definition), unsafe_allow_html=True)

        # ── Resource Card (NEW UX) ──
        if sel.get("reference_pdf_path"):
            pdf_bytes = fetch_concept_pdf(sel["ref_concept_id"])
            if pdf_bytes:
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                
                # HTML card with embedded PDF iframe
                pdf_html = (
                    f'<div style="background:#16162A; border:1px solid #2D2D4E; border-left:4px solid #7C3AED; border-radius:8px; padding:1.2rem; margin-bottom:1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">'
                    f'<p style="color:#8B5CF6; font-size:1.05rem; font-weight:700; margin-top:0; margin-bottom:0.75rem;">📚 Reference Resources</p>'
                    f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="400px" style="border:none; border-radius:6px; margin-bottom:1rem;"></iframe>'
                    f'</div>'
                )
                st.markdown(pdf_html, unsafe_allow_html=True)
                st.download_button(
                    label="📥 Download Reference PDF",
                    data=pdf_bytes,
                    file_name=f"{sel['concept_title'].replace(' ', '_')}_reference.pdf",
                    mime="application/pdf",
                    key=f"dl_ref_{sel['ref_concept_id']}"
                )
            else:
                st.markdown(
                    f'<div style="background:#16162A; border:1px solid #2D2D4E; border-left:4px solid #7C3AED; border-radius:8px; padding:1.2rem; margin-bottom:1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">'
                    f'<p style="color:#8B5CF6; font-size:1.05rem; font-weight:700; margin-top:0; margin-bottom:0.75rem;">📚 Reference Resources</p>'
                    f'<p style="color:#94A3B8; font-size:.9rem; margin:0;">PDF is not available on server.</p>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                f'<div style="background:#16162A; border:1px solid #2D2D4E; border-left:4px solid #7C3AED; border-radius:8px; padding:1.2rem; margin-bottom:1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">'
                f'<p style="color:#8B5CF6; font-size:1.05rem; font-weight:700; margin-top:0; margin-bottom:0.75rem;">📚 Reference Resources</p>'
                f'<p style="color:#94A3B8; font-size:.9rem; margin:0;">No reference PDF has been uploaded for this concept.</p>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.markdown("<p style='color:#94A3B8;font-size:.85rem;'>Upload your WAV audio explanation:</p>", unsafe_allow_html=True)
        uploaded = st.file_uploader("Upload WAV", type=["wav"], label_visibility="collapsed")
        if uploaded:
            ab = uploaded.read()
            st.session_state["audio_bytes"] = ab
            st.session_state["audio_filename"] = uploaded.name
            
            # Immediately show audio player so they can listen before analyzing
            st.markdown("<p style='color:#94A3B8;font-size:.85rem;margin-top:0.5rem;margin-bottom:0.5rem;'>🎵 Preview your uploaded recording:</p>", unsafe_allow_html=True)
            st.audio(ab, format='audio/wav')

            with st.spinner("Rendering waveform…"):
                try:
                    st.session_state["waveform_png"] = render_waveform(ab)
                except Exception as e:
                    st.warning(f"Waveform: {e}"); st.session_state["waveform_png"] = None
            if st.session_state["waveform_png"]:
                st.image(st.session_state["waveform_png"], use_column_width=True, caption="Amplitude vs. Time")
        
        st.markdown("<br>", unsafe_allow_html=True)
        go = st.button("🔍 Analyze Concept Understanding", disabled=(uploaded is None))
        if go and st.session_state.get("audio_bytes"):
            if st.session_state["result"] is None or st.session_state["last_concept_id"] != sel["ref_concept_id"]:
                with st.spinner("🤖 Transcribing · Embedding · Scoring…"):
                    res = call_evaluate(st.session_state["audio_bytes"],
                        st.session_state["audio_filename"] or "rec.wav",
                        sel["ref_concept_id"], st.session_state.get("user_id") or 0)
                if res and res.get("status") in ("success", "Topic Mismatch"):
                    st.session_state.update({"result": res, "last_concept_id": sel["ref_concept_id"], "pdf_bytes": None})
                    if res.get("status") == "Topic Mismatch":
                        st.warning("⚠️ Topic Mismatch! The explanation does not match the selected concept.")
                    else:
                        st.success("✅ Analysis complete!")
                elif res:
                    st.error(f"Unexpected: {res}")
            else:
                st.info("ℹ️ Showing cached result. Change concept or re-upload to re-run.")
    with right:
        st.markdown("<h3 style='color:#8B5CF6;font-size:1.05rem;font-weight:700;'>📊 Evaluation Results</h3>", unsafe_allow_html=True)
        res = st.session_state.get("result")
        if res is None:
            st.markdown("<div style='background:#16162A;border:1px dashed #2D2D4E;border-radius:8px;"
                        "padding:3rem 2rem;text-align:center;'>"
                        "<p style='font-size:3rem;margin:0;'>🎤</p>"
                        "<p style='color:#94A3B8;margin:8px 0 0;'>Upload a WAV and click "
                        "<strong style='color:#8B5CF6;'>Analyze Concept Understanding</strong>.</p></div>", unsafe_allow_html=True)
        else:
            ev = res.get("evaluation", {}); sig = res.get("signal_features", {})
            fil = res.get("filler_stats", {}); transcript = res.get("transcript", "")
            
            topic_match_val = res.get("topic_match", True)
            bi_similarity = float(res.get("semantic_similarity", 0.0))
            cross_similarity = float(res.get("cross_encoder_score", 0.0))
            semantic_accuracy = (0.5 * bi_similarity + 0.5 * cross_similarity) * 100 if topic_match_val else 0.0
            
            filler_ratio_val = float(fil.get("filler_ratio", 0.0))
            pause_ratio_val = float(sig.get("pause_ratio", 0.0))
            filler_points = 20 if filler_ratio_val < 0.05 else 10
            pause_points = 15 if pause_ratio_val < 0.25 else 5
            delivery_fluency = ((filler_points + pause_points) / 35.0) * 100

            score = int(ev.get("overall_score", 0))
            level = ev.get("understanding_level", "N/A")
            colour = ev.get("colour_hex", "#94A3B8")
            st.markdown(score_html(score, level, colour), unsafe_allow_html=True)
            
            # Primary Granular Metrics
            g1, g2, g3 = st.columns(3)
            g1.metric("🎯 Topic Guardrail", "MATCH" if topic_match_val else "MISMATCH")
            g2.metric("🧠 Semantic Accuracy", f"{semantic_accuracy:.1f}%")
            g3.metric("🗣️ Delivery Fluency", f"{delivery_fluency:.1f}%")
            
            st.markdown("<h4 style='color:#A78BFA;font-size:0.95rem;margin-top:1rem;margin-bottom:0.5rem;'>Detailed Indicators</h4>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Bi-Encoder", f"{bi_similarity*100:.1f}%")
            c2.metric("Cross-Encoder", f"{cross_similarity*100:.1f}%")
            c3.metric("Filler Ratio", f"{filler_ratio_val*100:.2f}%")
            c4.metric("Pause Ratio", f"{pause_ratio_val*100:.1f}%")
            
            st.markdown(f"<p style='color:#94A3B8;font-size:0.8rem;margin-top:0.25rem;'>🎙️ Vocal Amplitude (RMS Energy): <strong style='color:#F1F5F9;'>{float(sig.get('rms_energy',0.0)):.5f}</strong></p>", unsafe_allow_html=True)
            
            st.markdown(card("Transcribed Explanation",
                f"<p style='color:#F1F5F9;font-size:.9rem;line-height:1.7;margin:0;'>{transcript or '(No speech detected)'}</p>",
                "#D97706"), unsafe_allow_html=True)
            bd = fil.get("filler_breakdown", {})
            if any(v > 0 for v in bd.values()):
                badges = " ".join(f"<span style='background:#2D2D4E;border-radius:6px;padding:2px 9px;"
                    f"color:#8B5CF6;font-size:.82rem;font-weight:600;'>{w}: {n}</span>"
                    for w, n in bd.items() if n > 0)
                st.markdown(card("Filler Breakdown",
                    f"<div style='display:flex;flex-wrap:wrap;gap:6px;'>{badges}</div>", "#D97706"),
                    unsafe_allow_html=True)
            with st.expander("🔬 Full Signal Metrics"):
                st.json({"duration_sec": round(float(sig.get("duration_sec",0)),3),
                    "rms_energy": round(float(sig.get("rms_energy",0)),8),
                    "zero_crossing_rate": round(float(sig.get("zero_crossing_rate",0)),8),
                    "pause_ratio": round(float(sig.get("pause_ratio",0)),6),
                    "filler_word_count": fil.get("filler_word_count",0),
                    "total_words": fil.get("total_words",0)})
            st.markdown("---")
            if st.session_state["pdf_bytes"] is None:
                wf = st.session_state.get("waveform_png")
                try:
                    pdf = generate_pdf_report(
                        metrics={"similarity_score": bi_similarity,
                            "cross_encoder_score": cross_similarity,
                            "topic_match": topic_match_val,
                            "filler_ratio": filler_ratio_val,
                            "pause_ratio": pause_ratio_val,
                            "rms_energy": float(sig.get("rms_energy",0)),
                            "overall_score": score, "understanding_level": level},
                        transcript=transcript,
                        reference_text=res.get("concept",{}).get("concept_text",""),
                        waveform_bytes=io.BytesIO(wf) if wf else io.BytesIO())
                    st.session_state["pdf_bytes"] = pdf.getvalue()
                except Exception as e:
                    st.error(f"PDF error: {e}")
            if st.session_state["pdf_bytes"]:
                st.download_button("📄 Download Evaluation Report (PDF)",
                    data=st.session_state["pdf_bytes"], file_name="skillecho_report.pdf", mime="application/pdf")

# ── Shared expander helper (used by both Dashboard and Admin) ─────────────────
_LEVEL_COLOUR = {
    "Strong Understanding": "#2ecc71",
    "Moderate Understanding": "#f39c12",
    "Poor Understanding": "#e74c3c",
    "Topic Mismatch": "#e74c3c",
}

def _result_expander(row: dict, prefix: str = "") -> None:
    """
    Render one evaluation record as a styled card with student profile info
    and an expandable diagnostics details section.
    """
    score       = int(row.get("overall_score", 0))
    level       = row.get("understanding_level", "N/A")
    concept     = row.get("concept_title", "")
    ts          = row.get("created_at", "")
    transcript  = row.get("transcript_text", "") or "(No transcript recorded)"
    rms         = float(row.get("rms_energy", 0.0))
    filler      = float(row.get("filler_ratio", 0.0))
    result_id   = int(row.get("result_id", 0))
    colour      = _LEVEL_COLOUR.get(level, "#94A3B8")

    topic_match_val = row.get("topic_match", True)
    bi_similarity   = float(row.get("similarity_score", 0.0))
    cross_similarity = float(row.get("cross_encoder_score", 0.0))
    pause_ratio_val = float(row.get("pause_ratio", 0.0))
    
    # Semantic Accuracy (average of bi-encoder and cross-encoder)
    semantic_accuracy = (0.5 * bi_similarity + 0.5 * cross_similarity) * 100 if topic_match_val else 0.0
    
    # Delivery Fluency calculation
    filler_points = 20 if filler < 0.05 else 10
    pause_points = 15 if pause_ratio_val < 0.25 else 5
    delivery_fluency = ((filler_points + pause_points) / 35.0) * 100

    student_name = row.get("student_name") or st.session_state.get("user_name") or "Student"
    student_email = row.get("student_email") or "student@skillecho.com"
    initials = "".join([part[0] for part in student_name.split() if part])[:2].upper() or "?"

    def to_rgb(h):
        h = h.lstrip('#')
        return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"

    # Render card markup
    st.markdown(
        f"<div class='result-card' style='margin-bottom: 1rem;'>"
        f"  <div class='result-card-header'>"
        f"    <div class='result-card-student-info'>"
        f"      <div class='user-avatar-circle student'>{initials}</div>"
        f"      <div>"
        f"        <h4 style='margin:0; font-size:1.05rem; font-weight:700; color:#F1F5F9;'>{student_name}</h4>"
        f"        <p style='margin:0; font-size:0.8rem; color:#94A3B8;'>{student_email} • {ts}</p>"
        f"      </div>"
        f"    </div>"
        f"    <span class='result-card-score-badge' style='background: rgba({to_rgb(colour)}, 0.12); color:{colour}; border:1px solid rgba({to_rgb(colour)}, 0.25);'>{score}/100</span>"
        f"  </div>"
        f"  <div style='margin-bottom: 10px;'>"
        f"    <p style='margin:0; font-size:0.88rem; color:#E2E8F0;'><strong>Concept Evaluated:</strong> {concept}</p>"
        f"    <p style='margin:2px 0 0; font-size:0.85rem; color:#94A3B8;'><strong>Level:</strong> <span style='color:{colour}; font-weight:700;'>{level}</span></p>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True
    )

    with st.expander("🔍 View Detailed Diagnostics & Report", expanded=False):
        # ── Score bar ────────────────────────────────────────────────────
        st.markdown(
            f"<div style='margin:4px 0 10px;'>"
            f"<div style='display:flex;justify-content:space-between;margin-bottom:4px;'>"
            f"<span style='color:#94A3B8;font-size:.78rem;font-weight:600;letter-spacing:.8px;text-transform:uppercase;'>Overall Score</span>"
            f"<span style='color:{colour};font-size:.9rem;font-weight:700;'>{score} / 100</span></div>"
            f"<div style='height:10px;background:#2D2D4E;border-radius:5px;'>"
            f"<div style='height:10px;background:{colour};width:{score}%;border-radius:5px;"
            f"transition:width .4s;'></div></div></div>",
            unsafe_allow_html=True,
        )

        # ── Signal metric tiles ──────────────────────────────────────────
        g1, g2, g3 = st.columns(3)
        g1.metric("🎯 Topic Guardrail", "MATCH" if topic_match_val else "MISMATCH")
        g2.metric("🧠 Semantic Accuracy", f"{semantic_accuracy:.1f}%")
        g3.metric("🗣️ Delivery Fluency", f"{delivery_fluency:.1f}%")

        st.markdown("<h4 style='color:#A78BFA;font-size:0.85rem;margin-top:0.5rem;margin-bottom:0.25rem;'>Detailed Indicators</h4>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Bi-Encoder", f"{bi_similarity * 100:.1f}%")
        m2.metric("Cross-Encoder", f"{cross_similarity * 100:.1f}%")
        m3.metric("Filler Ratio", f"{filler * 100:.2f}%")
        m4.metric("Pause Ratio", f"{pause_ratio_val * 100:.1f}%")

        st.markdown(f"<p style='color:#94A3B8;font-size:0.8rem;margin-top:0.25rem;margin-bottom:1rem;'>🎙️ Vocal Amplitude (RMS Energy): <strong style='color:#F1F5F9;'>{rms:.5f}</strong></p>", unsafe_allow_html=True)

        # ── Transcript ───────────────────────────────────────────────────
        st.markdown(
            "<p style='color:#94A3B8;font-size:.78rem;font-weight:600;letter-spacing:.8px;"
            "text-transform:uppercase;margin-bottom:4px;'>Transcribed Explanation</p>",
            unsafe_allow_html=True,
        )
        st.text_area(
            label="transcript",
            value=transcript,
            height=110,
            disabled=True,
            label_visibility="collapsed",
            key=f"ta_{result_id}",
        )

        # ── PDF generation (stateful, no AI call) ────────────────────────
        pdf_key = f"hist_pdf_{result_id}"
        if pdf_key not in st.session_state:
            st.session_state[pdf_key] = None

        col_btn, col_dl = st.columns([1, 1])
        with col_btn:
            if st.button("📄 Generate PDF Report", key=f"gen_{result_id}"):
                try:
                    pdf_buf = generate_pdf_report(
                        metrics={
                            "similarity_score": bi_similarity,
                            "cross_encoder_score": cross_similarity,
                            "topic_match": topic_match_val,
                            "filler_ratio": filler,
                            "pause_ratio": pause_ratio_val,
                            "rms_energy": rms,
                            "overall_score": score,
                            "understanding_level": level,
                        },
                        transcript=transcript,
                        reference_text=f"Concept: {concept}",
                        waveform_bytes=io.BytesIO(),
                    )
                    st.session_state[pdf_key] = pdf_buf.getvalue()
                    st.success("✅ PDF ready — click Download below.")
                except Exception as e:
                    st.error(f"PDF error: {e}")
        with col_dl:
            if st.session_state.get(pdf_key):
                st.download_button(
                    "⬇️ Download Report",
                    data=st.session_state[pdf_key],
                    file_name=f"skillecho_report_{result_id}.pdf",
                    mime="application/pdf",
                    key=f"dl_{result_id}",
                )

# ── Page 4: Student Dashboard ─────────────────────────────────────────────────
def page_dashboard():
    import pandas as pd
    uid = st.session_state["user_id"]
    st.markdown("<h1 style='color:#F1F5F9;font-size:1.9rem;font-weight:800;'>📊 My Progress Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8;margin-bottom:1.5rem;'>Click any session below to drill into the full transcript and signal details.</p>", unsafe_allow_html=True)
    st.markdown("---")

    data = api_get(f"/users/{uid}/history")
    if data is None: return
    history = data.get("history", [])
    if not history:
        st.info("🎤 No evaluations yet. Head to Practice Area and submit your first audio!"); return

    df = pd.DataFrame(history)

    # ── KPI summary ──────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🎯 Avg Score",      f"{df['overall_score'].mean():.1f}")
    k2.metric("🏆 Best Score",     f"{df['overall_score'].max():.0f}")
    k3.metric("🎙️ Sessions",       str(len(df)))
    k4.metric("💪 Strong Results", str(int((df["understanding_level"] == "Strong Understanding").sum())))
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Score progression chart ──────────────────────────────────────────────
    st.markdown("<h3 style='color:#8B5CF6;font-size:1.05rem;font-weight:700;'>📈 Score Progression</h3>", unsafe_allow_html=True)
    chart_df = df[["created_at", "overall_score"]].rename(columns={"overall_score": "Score"}).set_index("created_at")
    st.line_chart(chart_df, use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Drill-down expanders ─────────────────────────────────────────────────
    st.markdown("<h3 style='color:#8B5CF6;font-size:1.05rem;font-weight:700;'>📋 Session History — Click to Expand</h3>", unsafe_allow_html=True)
    for row in history:
        _result_expander(row)

# ── Page 5: Admin Panel ───────────────────────────────────────────────────────
def page_admin():
    import pandas as pd
    if st.session_state.get("user_role") != "admin":
        st.error("⛔ Access denied. Admins only."); return
    st.markdown("<h1 style='color:#F1F5F9;font-size:1.9rem;font-weight:800;'>⚙️ Admin Panel</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8;margin-bottom:1.5rem;'>Manage the concept library, track student evaluations, and monitor registered users.</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Set up tabs for clean administration UX
    tab_concepts, tab_history, tab_users = st.tabs([
        "➕ Concept Management", 
        "📊 Student Assessment History", 
        "👥 Registered Users"
    ])

    # ── TAB 1: Concept Management ──
    with tab_concepts:
        st.markdown("<h3 style='color:#8B5CF6;font-size:1.1rem;font-weight:700;'>➕ Add New Concept</h3>", unsafe_allow_html=True)
        
        # We bind the inputs to keys in session state so they persist and can be easily cleared
        c_title = st.text_input("Concept Title", key="admin_concept_title", placeholder="e.g. Transformer Architecture", disabled=st.session_state.is_adding)
        c_text  = st.text_area("Concept Definition", key="admin_concept_text", placeholder="Write the reference explanation here…", height=130, disabled=st.session_state.is_adding)
        c_pdf = st.file_uploader("Upload Reference PDF (Optional)", type=["pdf"], key="admin_concept_pdf", disabled=st.session_state.is_adding)
        
        # The submit button is restricted (disabled) during addition
        sub = st.button("Add Concept →", disabled=st.session_state.is_adding, use_container_width=True)
        
        if sub:
            if not c_title.strip() or not c_text.strip():
                st.error("Both title and definition are required.")
            else:
                st.session_state.is_adding = True
                st.rerun()

        # If adding, run the API call inside a loading spinner
        if st.session_state.is_adding:
            with st.spinner("Creating concept and extracting embeddings... Please wait."):
                pdf_file = st.session_state.get("admin_concept_pdf")
                res = api_post_concept(st.session_state.admin_concept_title.strip(), st.session_state.admin_concept_text.strip(), pdf_file)
                if res:
                    st.success(f"✅ Concept '{res['concept_title']}' added successfully (ID: {res['ref_concept_id']}).")
                    st.session_state["admin_concept_title"] = ""
                    st.session_state["admin_concept_text"] = ""
                    st.session_state["admin_concept_pdf"] = None
                    fetch_concepts.clear()
                else:
                    st.error("Failed to add concept. Please check backend connectivity.")
                st.session_state.is_adding = False
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("<h3 style='color:#8B5CF6;font-size:1.1rem;font-weight:700;'>📋 Existing Concepts</h3>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Concepts List", key="admin_refresh_concepts"): 
            fetch_concepts.clear()
            st.rerun()

        concepts = fetch_concepts()
        if not concepts:
            st.info("No reference concepts exist in the library yet.")
        else:
            for c in concepts:
                cid = c.get("ref_concept_id")
                ctitle = c.get("concept_title")
                ctext = c.get("concept_text")
                cpdf = c.get("reference_pdf_path")
                
                # Check if this concept is currently being edited
                if st.session_state.editing_concept_id == cid:
                    st.markdown(f"#### ✏️ Editing Concept #{cid}", unsafe_allow_html=True)
                    with st.form(f"edit_concept_form_{cid}"):
                        edit_title = st.text_input("Concept Title", value=ctitle)
                        edit_text = st.text_area("Concept Definition", value=ctext, height=130)
                        edit_pdf = st.file_uploader("Replace Reference PDF (Optional)", type=["pdf"], key=f"edit_pdf_{cid}")
                        clear_existing_pdf = st.checkbox("Remove existing PDF reference", value=False)
                        
                        e_col1, e_col2 = st.columns(2)
                        with e_col1:
                            save_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)
                        with e_col2:
                            cancel_btn = st.form_submit_button("❌ Cancel", use_container_width=True)
                            
                    if save_btn:
                        if not edit_title.strip() or not edit_text.strip():
                            st.error("Title and definition are required.")
                        else:
                            with st.spinner("Updating concept..."):
                                res = api_update_concept(cid, edit_title.strip(), edit_text.strip(), edit_pdf, clear_existing_pdf)
                                if res:
                                    st.success("✅ Concept updated successfully!")
                                    st.session_state.editing_concept_id = None
                                    fetch_concepts.clear()
                                    st.rerun()
                                else:
                                    st.error("Failed to update concept.")
                                    
                    if cancel_btn:
                        st.session_state.editing_concept_id = None
                        st.rerun()
                        
                elif st.session_state.confirm_delete_id == cid:
                    st.warning(f"⚠️ Are you sure you want to delete concept '{ctitle}'? This will delete all evaluation results associated with it!")
                    del_col1, del_col2 = st.columns(2)
                    with del_col1:
                        if st.button("🗑️ Yes, Delete", key=f"confirm_del_btn_{cid}", use_container_width=True):
                            with st.spinner("Deleting..."):
                                if api_delete_concept(cid):
                                    st.success("✅ Concept deleted successfully!")
                                    st.session_state.confirm_delete_id = None
                                    fetch_concepts.clear()
                                    st.rerun()
                    with del_col2:
                        if st.button("❌ Cancel", key=f"cancel_del_btn_{cid}", use_container_width=True):
                            st.session_state.confirm_delete_id = None
                            st.rerun()
                else:
                    # Render concept in a card layout
                    pdf_badge = (
                        f"<span class='pdf-badge attached'>📄 PDF Attached</span>"
                        if cpdf else
                        f"<span class='pdf-badge none'>❌ No PDF</span>"
                    )
                    
                    card_html = (
                        f"<div class='concept-card' style='margin-bottom:1.5rem;'>"
                        f"  <div>"
                        f"    <div style='display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;'>"
                        f"      <h4 class='concept-card-title'>#{cid}: {ctitle}</h4>"
                        f"      {pdf_badge}"
                        f"    </div>"
                        f"    <div class='concept-card-body'>"
                        f"      {format_definition_text(ctext)}"
                        f"    </div>"
                        f"  </div>"
                        f"</div>"
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    # Render action controls for this card
                    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
                    with btn_col1:
                        if st.button("✏️ Edit Concept", key=f"edit_btn_{cid}", use_container_width=True):
                            st.session_state.editing_concept_id = cid
                            st.rerun()
                    with btn_col2:
                        if st.button("🗑️ Delete", key=f"del_btn_{cid}", use_container_width=True):
                            st.session_state.confirm_delete_id = cid
                            st.rerun()
                    with btn_col3:
                        if cpdf:
                            # Direct download button for PDF
                            pdf_bytes = api_get_concept_pdf(cid)
                            if pdf_bytes:
                                st.download_button(
                                    "⬇️ Download PDF",
                                    data=pdf_bytes,
                                    file_name=f"reference_concept_{cid}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_pdf_btn_{cid}",
                                    use_container_width=True
                                )
                            else:
                                st.button("❌ PDF Offline", key=f"dl_offline_{cid}", disabled=True, use_container_width=True)
                        else:
                            st.button("🚫 No PDF", key=f"dl_none_{cid}", disabled=True, use_container_width=True)
                            
                    st.markdown("<hr style='border-color: rgba(255,255,255,0.04); margin:1.5rem 0;'>", unsafe_allow_html=True)

    # ── TAB 2: Assessment History ──
    with tab_history:
        st.markdown("<h3 style='color:#8B5CF6;font-size:1.1rem;font-weight:700;'>👥 Student Results</h3>", unsafe_allow_html=True)
        if st.button("🔄 Refresh History Log", key="admin_refresh_hist"): st.rerun()

        data = api_get("/admin/results")
        if data is None:
            st.error("Failed to retrieve result logs from backend.")
        else:
            results = data.get("results", [])
            if not results:
                st.info("No evaluation results yet.")
            else:
                df = pd.DataFrame(results)
                a1, a2, a3 = st.columns(3)
                a1.metric("📊 Total Evaluations",  str(len(df)))
                a2.metric("🎯 Platform Avg Score",  f"{df['overall_score'].mean():.1f}")
                a3.metric("👥 Unique Students",     str(df["student_email"].nunique()))
                st.markdown("<br>", unsafe_allow_html=True)

                for row in results:
                    _result_expander(row)

    # ── TAB 3: Registered Users ──
    with tab_users:
        st.markdown("<h3 style='color:#8B5CF6;font-size:1.1rem;font-weight:700;'>👥 Registered Users</h3>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Registered Users", key="admin_refresh_users"): st.rerun()

        userdata = api_get("/admin/users")
        if userdata is None:
            st.error("Failed to retrieve user list from backend.")
        else:
            users = userdata.get("users", [])
            if not users:
                st.info("No registered users found.")
            else:
                udf = pd.DataFrame(users)
                u1, u2 = st.columns(2)
                u1.metric("Total Users", str(len(udf)))
                u2.metric("Admins", str(len(udf[udf['role'] == 'admin'])))
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Render clean user profile cards grid instead of basic dataframe
                users_html = "<div class='user-list'>"
                for u in users:
                    name = u.get("name", "Unknown")
                    email = u.get("email", "No Email")
                    role = u.get("role", "student")
                    created_at = u.get("created_at", "N/A")
                    
                    # Compute initials
                    initials = "".join([part[0] for part in name.split() if part])[:2].upper() or "?"
                    
                    role_class = "admin-badge" if role == "admin" else "student-badge"
                    avatar_class = "admin" if role == "admin" else "student"
                    
                    users_html += (
                        f"<div class='user-item-card'>"
                        f"  <div class='user-avatar-circle {avatar_class}'>{initials}</div>"
                        f"  <div class='user-detail-info'>"
                        f"    <h4>{name}</h4>"
                        f"    <p>{email}</p>"
                        f"    <div class='user-card-date'>Joined: {created_at}</div>"
                        f"  </div>"
                        f"  <span class='user-card-badge {role_class}'>{role}</span>"
                        f"</div>"
                    )
                users_html += "</div>"
                st.markdown(users_html, unsafe_allow_html=True)

# ── Main router ───────────────────────────────────────────────────────────────
def main():
    init_state()
    sidebar()
    page = st.session_state["page"]

    if page == "login":
        page_login()
    elif page == "register":
        page_register()
    elif page == "practice":
        if not st.session_state["logged_in"]:
            st.session_state["page"] = "login"; st.rerun()
        page_practice()
    elif page == "dashboard":
        if not st.session_state["logged_in"]:
            st.session_state["page"] = "login"; st.rerun()
        page_dashboard()
    elif page == "admin":
        if st.session_state.get("user_role") != "admin":
            st.session_state["page"] = "login"; st.rerun()
        page_admin()
    else:
        st.session_state["page"] = "login"; st.rerun()

    st.markdown("---")
    st.markdown("<p style='text-align:center;color:#94A3B8;font-size:.75rem;'>"
                "SkillEcho v2.0 · Whisper · MiniLM · librosa · FastAPI · Streamlit</p>",
                unsafe_allow_html=True)

if __name__ == "__main__":
    main()
else:
    main()
