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

from report_generator import generate_pdf_report

logger = logging.getLogger(__name__)

@st.cache_resource
def start_backend():
    cmd = [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        return proc
    except Exception as e:
        logger.exception("Failed to start FastAPI backend: %s", e)
        return None

# Trigger FastAPI backend start
start_backend()

API = "http://127.0.0.1:8000"

# ── Session persistence (survives browser reloads) ────────────────────────────
_SESSION_FILE = os.path.join(os.path.dirname(__file__), ".skillecho_session.json")

def _save_session(user_id: int, name: str, role: str) -> None:
    """Write session credentials to a local JSON file."""
    try:
        with open(_SESSION_FILE, "w") as f:
            json.dump({"user_id": user_id, "name": name, "role": role}, f)
    except Exception as e:
        logger.warning("Could not save session: %s", e)

def _load_session() -> dict | None:
    """Read session from file; return None if missing or corrupt."""
    try:
        if os.path.exists(_SESSION_FILE):
            with open(_SESSION_FILE) as f:
                data = json.load(f)
            # Basic validation
            if all(k in data for k in ("user_id", "name", "role")):
                return data
    except Exception as e:
        logger.warning("Could not load session: %s", e)
    return None

def _clear_session() -> None:
    """Delete the session file on logout."""
    try:
        if os.path.exists(_SESSION_FILE):
            os.remove(_SESSION_FILE)
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
    background-image: linear-gradient(135deg, #09090E 0%, #110726 100%) !important;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
}

h1, h2, h3, h4, h5, h6, [data-testid="stHeader"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: #F1F5F9 !important;
    font-weight: 700 !important;
}

/* Text inputs, textareas, and selectboxes styling */
input, textarea, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="select"] div {
    background-color: #16162A !important;
    color: #F1F5F9 !important;
    -webkit-text-fill-color: #F1F5F9 !important;
    border-radius: 8px !important;
}

[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] {
    background-color: #16162A !important;
    border: 1px solid #2D2D4E !important;
    border-radius: 8px !important;
}

input:focus, textarea:focus, [data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within {
    border-color: #7C3AED !important;
    background-color: #1A1A35 !important;
    box-shadow: 0 0 0 1px #7C3AED !important;
}

/* Dropdown list styling */
div[role="listbox"] {
    background-color: #16162A !important;
    color: #F1F5F9 !important;
}

/* Force Streamlit button text to be white and remove black color fallback */
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
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    box-shadow: 0 4px 15px rgba(124, 58, 237, 0.25) !important;
    transition: all 0.2s ease-in-out !important;
    width: 100% !important;
}

.stButton button:hover, .stFormSubmitButton button:hover,
.stButton button:focus, .stFormSubmitButton button:focus,
.stButton button:active, .stFormSubmitButton button:active {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 24px rgba(124, 58, 237, 0.45) !important;
    background: linear-gradient(135deg, #8B5CF6 0%, #5B21B6 100%) !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* Download buttons styling (Glowing Green/Teal) */
.stDownloadButton button {
    background: linear-gradient(135deg, #059669 0%, #0D9488 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    box-shadow: 0 4px 15px rgba(5, 150, 105, 0.2) !important;
    transition: all 0.2s ease-in-out !important;
    width: 100% !important;
}

.stDownloadButton button:hover, .stDownloadButton button:focus, .stDownloadButton button:active {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 24px rgba(5, 150, 105, 0.4) !important;
    background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* Sidebar overrides */
[data-testid="stSidebar"] {
    background-color: #101021 !important;
    border-right: 1px solid #2D2D4E !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p, 
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span {
    color: #F1F5F9 !important;
}

/* Metric layouts */
[data-testid="stMetric"] {
    background-color: #16162A !important;
    border: 1px solid #2D2D4E !important;
    border-radius: 8px !important;
    padding: 1rem !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
}

[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    color: #94A3B8 !important;
    font-weight: 600 !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #F1F5F9 !important;
    font-weight: 700 !important;
}

/* Markdown typography settings */
div[data-testid="stMarkdownContainer"] {
    color: #F1F5F9 !important;
}

div[data-testid="stMarkdownContainer"] p {
    color: #E2E8F0 !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background-color: #16162A !important;
    border: 1px solid #2D2D4E !important;
    border-radius: 8px !important;
    color: #F1F5F9 !important;
}

.streamlit-expanderContent {
    background-color: #101021 !important;
    border: 1px solid #2D2D4E !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    padding: 1rem !important;
}

/* File Uploaders */
[data-testid="stFileUploader"] {
    background-color: #16162A !important;
    border: 1px dashed #475569 !important;
    border-radius: 8px !important;
}

/* Scrollbars */
::-webkit-scrollbar {
    width: 8px;
}
::-webkit-scrollbar-thumb {
    background: #475569;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #64748B;
}

hr {
    border-color: #2D2D4E !important;
}
</style>""", unsafe_allow_html=True)

# ── UI helpers ────────────────────────────────────────────────────────────────
def card(title, body, color="#7C3AED"):
    return (f'<div style="background:#16162A;border:1px solid #2D2D4E;border-left:4px solid {color};'
            f'border-radius:8px;padding:1.2rem 1.4rem;margin-bottom:1rem;box-shadow: 0 2px 8px rgba(0,0,0,0.2);">'
            f'<p style="color:#94A3B8;font-size:.75rem;font-weight:600;letter-spacing:1px;'
            f'text-transform:uppercase;margin:0 0 6px;">{title}</p>'
            f'<div style="color:#F1F5F9;font-size:.92rem;line-height:1.65;">{body}</div></div>')

def score_html(score, level, colour):
    return (f'<div style="background:linear-gradient(135deg,#16162A,#101021);border:2px solid {colour};'
            f'border-radius:8px;padding:2rem;text-align:center;box-shadow:0 4px 20px {colour}22;margin-bottom:1rem;">'
            f'<p style="color:#94A3B8;font-size:.78rem;letter-spacing:1.5px;text-transform:uppercase;margin:0 0 8px;font-weight:600;">FINAL SCORE</p>'
            f'<p style="color:{colour};font-size:4.5rem;font-weight:800;margin:0;line-height:1;">{score}</p>'
            f'<p style="color:#94A3B8;font-size:.85rem;margin:4px 0 0;">out of 100</p>'
            f'<hr style="border-color:#2D2D4E;margin:1rem 0;">'
            f'<p style="color:{colour};font-size:1.15rem;font-weight:700;margin:0;">{level}</p></div>')

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

def api_post(path, payload):
    try:
        r = requests.post(f"{API}{path}", json=payload, timeout=15); r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"❌ {e.response.json().get('detail', str(e)) if e.response else e}"); return None
    except Exception as e:
        st.error(f"❌ {e}"); return None

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
        st.error(f"❌ {e}")
        return None

def api_get(path):
    try:
        r = requests.get(f"{API}{path}", timeout=15); r.raise_for_status(); return r.json()
    except Exception as e:
        st.error(f"❌ {e}"); return None

def call_evaluate(audio_bytes, filename, ref_concept_id, user_id):
    try:
        r = requests.post(f"{API}/evaluate",
            files={"audio_file": (filename, audio_bytes, "audio/wav")},
            data={"ref_concept_id": str(ref_concept_id), "user_id": str(user_id)},
            timeout=180)
        r.raise_for_status(); return r.json()
    except requests.exceptions.Timeout:
        st.error("⏱️ Timed out. Try a shorter clip."); return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Cannot connect to backend."); return None
    except requests.HTTPError as e:
        st.error(f"❌ {e.response.json().get('detail', str(e)) if e.response else e}"); return None
    except Exception as e:
        st.error(f"❌ {e}"); return None

# ── Session state ───────────────────────────────────────────────────────────────
def init_state():
    # Initialise defaults
    for k, v in {"logged_in": False, "user_id": None, "user_name": None, "user_role": None,
                  "page": "login", "result": None, "waveform_png": None,
                  "pdf_bytes": None, "audio_bytes": None, "audio_filename": None, "last_concept_id": None,
                  "admin_concept_title": "", "admin_concept_text": ""}.items():
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
    Render one evaluation record as a styled st.expander with:
    - Colour-coded score progress bar
    - Signal metric tiles (RMS, filler ratio)
    - Read-only transcript text area
    - Stateful PDF generation (no AI re-run; pure report from stored data)
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

    label = f"{ts}  │  {concept}  │  Score: {score}/100  │  {level}"
    if prefix:
        label = f"{prefix}  {label}"

    with st.expander(label, expanded=False):
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
    st.markdown("<p style='color:#94A3B8;margin-bottom:1.5rem;'>Manage the concept library and drill into any student's evaluation.</p>", unsafe_allow_html=True)
    st.markdown("---")

    # ── Section A: Add new concept ───────────────────────────────────────────
    st.markdown("<h3 style='color:#8B5CF6;font-size:1.1rem;font-weight:700;'>➕ Add New Concept</h3>", unsafe_allow_html=True)
    
    with st.form("add_concept_form"):
        c_title = st.text_input("Concept Title", key="admin_concept_title", placeholder="e.g. Transformer Architecture")
        c_text  = st.text_area("Concept Definition", key="admin_concept_text", placeholder="Write the reference explanation here…", height=130)
        c_pdf = st.file_uploader("Upload Reference PDF (Optional)", type=["pdf"])
        sub = st.form_submit_button("Add Concept →", use_container_width=True)
        
    if sub:
        if not c_title.strip() or not c_text.strip():
            st.error("Both title and definition are required.")
        else:
            res = api_post_concept(c_title.strip(), c_text.strip(), c_pdf)
            if res:
                st.success(f"✅ Concept '{res['concept_title']}' added (id={res['ref_concept_id']}).")
                # Reset fields in session state
                st.session_state["admin_concept_title"] = ""
                st.session_state["admin_concept_text"] = ""
                fetch_concepts.clear()
                st.rerun()

    st.markdown("---")

    # ── Section B: All student results with drill-down ───────────────────────
    st.markdown("<h3 style='color:#8B5CF6;font-size:1.1rem;font-weight:700;'>👥 All Student Results — Click to Expand</h3>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", key="admin_refresh"): st.rerun()

    data = api_get("/admin/results")
    if data is None: return
    results = data.get("results", [])
    if not results:
        st.info("No evaluation results yet."); return

    df = pd.DataFrame(results)
    a1, a2, a3 = st.columns(3)
    a1.metric("📊 Total Evaluations",  str(len(df)))
    a2.metric("🎯 Platform Avg Score",  f"{df['overall_score'].mean():.1f}")
    a3.metric("👥 Unique Students",     str(df["student_email"].nunique()))
    st.markdown("<br>", unsafe_allow_html=True)

    for row in results:
        student_label = f"👤 {row.get('student_name','?')} ({row.get('student_email','?')})"
        _result_expander(row, prefix=student_label)

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
