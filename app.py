import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

import sys
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        def _silent_call_connection_lost(self, exc):
            try:
                self._sock.shutdown(1)
            except Exception:
                pass
        _ProactorBasePipeTransport._call_connection_lost = _silent_call_connection_lost
    except Exception:
        pass

import importlib
import db
importlib.reload(db)
import resume_parser
import job_scraper
importlib.reload(job_scraper)
import matcher
importlib.reload(matcher)
import copilot
importlib.reload(copilot)
import auto_applicant
importlib.reload(auto_applicant)

st.set_page_config(
    page_title="AI Job Application Co-Pilot",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# PWA Mobile App Support
st.markdown("""
<link rel="manifest" href="/app/static/manifest.json">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="JobAgent">
<meta name="theme-color" content="#1E3A8A">
""", unsafe_allow_html=True)

# Custom Styling
st.markdown("""
<style>
    /* Main Layout Polish */
    .main-header {
        font-size: 2.1rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .skill-chip {
        display: inline-block;
        background-color: #EFF6FF;
        color: #1D4ED8;
        padding: 0.25rem 0.65rem;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 0.15rem;
        border: 1px solid #BFDBFE;
    }
    .missing-chip {
        display: inline-block;
        background-color: #FEF2F2;
        color: #B91C1C;
        padding: 0.25rem 0.65rem;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 0.15rem;
        border: 1px solid #FECACA;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }

    /* ================= MODERN SAAS SIDEBAR ================= */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0B0F19 0%, #111827 100%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    /* Hide the default widget label "Navigation" */
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-testid="stWidgetLabel"] {
        display: none !important;
    }

    /* Transform radio options into modern sleek navigation pills */
    [data-testid="stSidebar"] div[data-testid="stRadioGroup"],
    [data-testid="stSidebar"] div[role="radiogroup"] {
        display: flex !important;
        flex-direction: column !important;
        gap: 8px !important;
        width: 100% !important;
    }
    
    [data-testid="stSidebar"] label[data-testid="stRadioOption"],
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 0.65rem 0.95rem !important;
        margin-bottom: 0px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }

    /* Completely hide the radio button circle/dot */
    [data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:not([data-testid="stMarkdownContainer"]),
    [data-testid="stSidebar"] label[data-testid="stRadioOption"] span:first-child,
    [data-testid="stSidebar"] label[data-testid="stRadioOption"] input[type="radio"],
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
        visibility: hidden !important;
        width: 0px !important;
        height: 0px !important;
        opacity: 0 !important;
        position: absolute !important;
        pointer-events: none !important;
    }

    /* Ensure text container spans full width with modern typography */
    [data-testid="stSidebar"] label[data-testid="stRadioOption"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] div[role="radiogroup"] label p {
        width: 100% !important;
    }

    [data-testid="stSidebar"] label[data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] div[role="radiogroup"] label p {
        font-size: 0.92rem !important;
        font-weight: 500 !important;
        color: #94A3B8 !important;
        margin: 0 !important;
        letter-spacing: 0.2px !important;
        transition: color 0.15s ease !important;
    }

    /* Hover effect */
    [data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover,
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: rgba(255, 255, 255, 0.08) !important;
        border-color: rgba(99, 102, 241, 0.4) !important;
        transform: translateX(4px) !important;
    }

    [data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover p {
        color: #F8FAFC !important;
    }

    /* Active / Selected Tab State */
    [data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"],
    [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked),
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(90deg, rgba(59, 130, 246, 0.22) 0%, rgba(99, 102, 241, 0.18) 100%) !important;
        border: 1px solid #3B82F6 !important;
        border-left: 4px solid #60A5FA !important;
        box-shadow: 0 4px 14px rgba(59, 130, 246, 0.25) !important;
    }

    [data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* ================= GOOGLE PIXEL 9A & MOBILE UI ================= */
    @media (max-width: 768px) {
        /* Optimize screen padding for 412px Pixel 9a width */
        .block-container {
            padding-top: 1.0rem !important;
            padding-bottom: 5.5rem !important;
            padding-left: 0.80rem !important;
            padding-right: 0.80rem !important;
            max-width: 100vw !important;
        }

        /* Material You responsive typography */
        .main-header {
            font-size: 1.45rem !important;
            line-height: 1.25 !important;
            letter-spacing: -0.3px !important;
            margin-bottom: 0.35rem !important;
        }
        .sub-header {
            font-size: 0.88rem !important;
            line-height: 1.4 !important;
            margin-bottom: 1.0rem !important;
        }

        /* Material You Card Surface */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 18px !important;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04) !important;
            padding: 0.95rem 0.85rem !important;
            margin-bottom: 0.85rem !important;
        }

        /* Metrics: 2x2 grid on Pixel 9a / mobile */
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 10px !important;
        }
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] {
            width: 100% !important;
            min-width: 0 !important;
            background: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 14px !important;
            padding: 10px 12px !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
        }

        /* Job card action buttons: 2x2 touch grid */
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"]:last-child {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 8px !important;
            margin-top: 10px !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"]:last-child > [data-testid="column"] {
            width: 100% !important;
            min-width: 0 !important;
        }

        /* Tactile touch buttons: 44px min height with active haptic press */
        .stButton > button, 
        .stLinkButton > a {
            min-height: 44px !important;
            font-size: 0.90rem !important;
            font-weight: 600 !important;
            border-radius: 12px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            touch-action: manipulation !important;
            -webkit-tap-highlight-color: transparent !important;
        }
        .stButton > button:active,
        .stLinkButton > a:active {
            transform: scale(0.96) !important;
        }

        /* Preset location buttons wrap gracefully */
        [data-testid="stHorizontalBlock"]:has(button[key^="btn_loc_"]) {
            display: flex !important;
            flex-wrap: wrap !important;
            gap: 6px !important;
        }
        [data-testid="stHorizontalBlock"]:has(button[key^="btn_loc_"]) > [data-testid="column"] {
            flex: 1 1 28% !important;
            min-width: 85px !important;
        }

        /* Skill chips comfortable on touchscreen */
        .skill-chip, .missing-chip {
            padding: 0.3rem 0.6rem !important;
            font-size: 0.8rem !important;
            border-radius: 8px !important;
            margin: 0.15rem !important;
        }

        /* Mobile Hamburger Drawer Control */
        [data-testid="stSidebarCollapsedControl"] {
            background: #1E3A8A !important;
            color: #FFFFFF !important;
            border-radius: 12px !important;
            padding: 6px !important;
            box-shadow: 0 4px 14px rgba(30, 58, 138, 0.35) !important;
            top: 0.65rem !important;
            left: 0.65rem !important;
            z-index: 9999 !important;
        }
        [data-testid="stSidebarCollapsedControl"] svg {
            fill: #FFFFFF !important;
            stroke: #FFFFFF !important;
        }

        /* Drawer navigation items */
        [data-testid="stSidebar"] label[data-testid="stRadioOption"],
        [data-testid="stSidebar"] div[role="radiogroup"] > label {
            min-height: 48px !important;
            padding: 0.8rem 1rem !important;
            border-radius: 14px !important;
            font-size: 1rem !important;
        }

        /* Tab strip scrolling */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            white-space: nowrap !important;
            -webkit-overflow-scrolling: touch !important;
            gap: 6px !important;
            padding-bottom: 4px !important;
        }
        [data-testid="stTabs"] button[role="tab"] {
            padding: 8px 14px !important;
            font-size: 0.88rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

def format_source_badge(source: str) -> str:
    s = str(source).lower()
    if "linkedin" in s:
        return '<span style="background-color: #0A66C2; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">LinkedIn</span>'
    elif "wellfound" in s:
        return '<span style="background-color: #141413; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">Wellfound</span>'
    elif "remoteok" in s:
        return '<span style="background-color: #EA4335; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">RemoteOK</span>'
    elif "arbeitnow" in s:
        return '<span style="background-color: #4F46E5; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">Arbeitnow</span>'
    elif "jobicy" in s:
        return '<span style="background-color: #0284C7; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">Jobicy</span>'
    elif "remotive" in s:
        return '<span style="background-color: #059669; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">Remotive</span>'
    elif "wework" in s:
        return '<span style="background-color: #D97706; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">WeWorkRemotely</span>'
    return f'<span style="background-color: #6B7280; color: white; padding: 3px 9px; border-radius: 6px; font-weight: 600; font-size: 0.78rem;">{source}</span>'

def format_score_badge(score: float) -> str:
    if score >= 75:
        return f'<span style="background-color: #DCFCE7; color: #166534; border: 1px solid #86EFAC; padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.85rem;">🔥 {score}% Match</span>'
    elif score >= 50:
        return f'<span style="background-color: #DBEAFE; color: #1E40AF; border: 1px solid #93C5FD; padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.85rem;">🎯 {score}% Match</span>'
    elif score >= 30:
        return f'<span style="background-color: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.85rem;">⚡ {score}% Match</span>'
    return f'<span style="background-color: #F3F4F6; color: #4B5563; border: 1px solid #E5E7EB; padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.85rem;">📋 {score}% Match</span>'

def get_local_ip() -> str:
    """Returns local LAN IP address for phone/mobile access."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.17"

def get_gemini_api_key() -> str:
    """Retrieves Gemini API key from local DB, Streamlit Cloud secrets, or environment."""
    key = db.get_setting("gemini_api_key", "")
    if key:
        return key
    try:
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")

def matches_place_filter(job: dict, place_query: str) -> bool:
    """Smart place and location matcher supporting Remote, regions, and custom cities/countries."""
    if not place_query or not place_query.strip():
        return True
    
    pq = place_query.strip().lower()
    job_loc = str(job.get('location', '')).strip().lower()
    job_title = str(job.get('title', '')).strip().lower()
    job_desc = str(job.get('description', ''))[:400].lower()
    
    # 1. Remote presets
    if pq in ["remote", "remote only", "anywhere", "worldwide"]:
        if "remote" in job_loc or "anywhere" in job_loc or "worldwide" in job_loc or "remote" in job_title:
            return True
        if not job_loc and job.get("source") in ["RemoteOK", "WeWorkRemotely", "Remotive"]:
            return True
        return False
        
    # 2. US / United States synonyms
    if pq in ["us", "usa", "united states", "america", "americas"]:
        us_indicators = ["united states", "usa", "us,", "us ", "(us)", "u.s.", "america", "new york", "san francisco", "los angeles", "california", "texas", "austin", "seattle", "boston", "chicago", "utah", "colorado", "florida", "ohio", "michigan"]
        if any(ind in job_loc for ind in us_indicators) or any(ind in job_title for ind in ["(us)", "us only", "usa only", "us/"]):
            return True
        return False

    # 3. Europe / UK synonyms
    if pq in ["europe", "uk", "united kingdom", "eu", "emea"]:
        eu_indicators = ["united kingdom", "uk", "england", "london", "bristol", "manchester", "germany", "berlin", "france", "paris", "spain", "netherlands", "amsterdam", "ireland", "dublin", "europe", "emea"]
        if any(ind in job_loc for ind in eu_indicators) or any(ind in job_title for ind in ["(uk)", "(eu)", "(emea)"]):
            return True
        return False
        
    # 4. Asia / APAC synonyms
    if pq in ["asia", "apac", "asia-pacific"]:
        asia_indicators = ["singapore", "india", "tokyo", "japan", "korea", "seoul", "indonesia", "jakarta", "philippines", "davao", "manila", "malaysia", "china", "hong kong", "taiwan", "bangalore", "chennai", "pune", "delhi", "mumbai", "apac", "asia"]
        if any(ind in job_loc for ind in asia_indicators) or any(ind in job_title for ind in ["(apac)", "(asia)"]):
            return True
        return False

    # 5. General substring match in location, title, or description prefix
    if pq in job_loc or pq in job_title or pq in job_desc:
        return True
        
    return False

# Initialize Session State
if "selected_job" not in st.session_state:
    st.session_state.selected_job = None
if "cached_jobs" not in st.session_state:
    st.session_state.cached_jobs = db.get_all_jobs()
if "current_page" not in st.session_state:
    st.session_state.current_page = "📄 Resume Profile"

# Handle pending navigation redirect before the radio widget is instantiated
if "nav_redirect" in st.session_state:
    st.session_state.current_page = st.session_state.pop("nav_redirect")

# Sidebar Navigation
with st.sidebar:
    # Brand Header
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding: 4px 2px;">
        <div style="width: 44px; height: 44px; border-radius: 12px; background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%); display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4); font-size: 22px;">
            💼
        </div>
        <div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.3px; line-height: 1.2;">
                Job Co-Pilot
            </div>
            <div style="display: flex; align-items: center; gap: 6px; margin-top: 3px;">
                <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background-color: #10B981; box-shadow: 0 0 8px #10B981;"></span>
                <span style="font-size: 0.72rem; color: #94A3B8; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;">Autonomous Agent</span>
            </div>
        </div>
    </div>
    <div style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; color: #64748B; margin: 12px 0 8px 4px; display: flex; align-items: center; justify-content: space-between;">
        <span>Workspace</span>
        <span style="background: rgba(255, 255, 255, 0.06); padding: 1px 7px; border-radius: 4px; font-size: 0.65rem; color: #94A3B8;">5 Modules</span>
    </div>
    """, unsafe_allow_html=True)
    
    NAV_OPTIONS = ["📄 Resume Profile", "🔍 Job Discovery", "🎯 Match & Co-Pilot", "📊 Application Tracker", "⚙️ Settings"]
    curr_idx = NAV_OPTIONS.index(st.session_state.current_page) if st.session_state.current_page in NAV_OPTIONS else 0
    page = st.radio(
        "Navigation",
        NAV_OPTIONS,
        index=curr_idx,
        label_visibility="collapsed"
    )
    st.session_state.current_page = page
    
    # Active Profile Card in sidebar
    active_resume = db.get_active_resume()
    if active_resume:
        cand_name = active_resume.get("name", "Candidate")
        cand_email = active_resume.get("email", "N/A")
        cand_skills = active_resume.get("skills", [])
        
        # Initials generator
        name_parts = cand_name.strip().split()
        if len(name_parts) >= 2:
            initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
        elif len(name_parts) == 1 and name_parts[0]:
            initials = name_parts[0][:2].upper()
        else:
            initials = "CV"
            
        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 14px; margin-top: 24px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                <span style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #64748B;">Candidate Profile</span>
                <span style="background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.65rem; font-weight: 700; padding: 2px 7px; border-radius: 9999px; display: flex; align-items: center; gap: 4px;">
                    <span style="width: 5px; height: 5px; border-radius: 50%; background: #10B981; display: inline-block;"></span> Active
                </span>
            </div>
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                <div style="width: 38px; height: 38px; border-radius: 50%; background: linear-gradient(135deg, #6366F1 0%, #EC4899 100%); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem; color: #FFFFFF; box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3); flex-shrink: 0;">
                    {initials}
                </div>
                <div style="min-width: 0; flex: 1;">
                    <div style="font-size: 0.92rem; font-weight: 700; color: #F1F5F9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 4px;">
                        <span>{cand_name}</span>
                        <span style="color: #38BDF8; font-size: 0.82rem;" title="Verified Profile">✓</span>
                    </div>
                    <div style="font-size: 0.74rem; color: #94A3B8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        {cand_email}
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px;">
                <span style="background: rgba(59, 130, 246, 0.12); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.25); font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 6px;">
                    🛠️ {len(cand_skills)} Skills
                </span>
                <span style="background: rgba(168, 85, 247, 0.12); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.25); font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 6px;">
                    ⚡ Auto-Fill Ready
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: 12px; padding: 14px; margin-top: 24px; text-align: center;">
            <div style="font-size: 0.88rem; font-weight: 700; color: #FBBF24;">⚠️ No Resume Loaded</div>
            <div style="font-size: 0.74rem; color: #94A3B8; margin-top: 4px; line-height: 1.4;">Head to <b>Resume Profile</b> tab to upload your CV and enable auto-pilot.</div>
        </div>
        """, unsafe_allow_html=True)
        
    # System Status Card
    cached_count = len(st.session_state.cached_jobs) if "cached_jobs" in st.session_state and st.session_state.cached_jobs else 0
    st.markdown(f"""
    <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 12px; padding: 12px; margin-top: 14px;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <span style="font-size: 0.72rem; color: #94A3B8; font-weight: 500;">AI Engine</span>
            <span style="font-size: 0.72rem; color: #34D399; font-weight: 600; display: flex; align-items: center; gap: 4px;">
                <span style="width: 6px; height: 6px; border-radius: 50%; background: #10B981; box-shadow: 0 0 6px #10B981; display: inline-block;"></span> Gemini Cascade (3.5 / 3.6 Flash)
            </span>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255, 255, 255, 0.04);">
            <span style="font-size: 0.72rem; color: #94A3B8; font-weight: 500;">Job Database</span>
            <span style="font-size: 0.72rem; color: #60A5FA; font-weight: 600;">{cached_count} Indexed</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Pixel 9a / Mobile Access Card
    local_ip = get_local_ip()
    mobile_url = f"http://{local_ip}:8501"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={mobile_url}"
    
    with st.expander("📱 Pixel 9a / Mobile Sync", expanded=False):
        st.markdown(f"""
        <div style="text-align: center; padding: 4px 0;">
            <div style="font-size: 0.78rem; font-weight: 700; color: #60A5FA; margin-bottom: 6px;">Scan with Pixel 9a Camera</div>
            <img src="{qr_url}" style="width: 130px; height: 130px; border-radius: 10px; background: white; padding: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);" />
            <div style="font-size: 0.72rem; color: #94A3B8; margin-top: 8px;">Or open on mobile:</div>
            <div style="font-size: 0.76rem; font-weight: 600; color: #38BDF8; word-break: break-all; margin-top: 2px;"><code>{mobile_url}</code></div>
            <div style="font-size: 0.68rem; color: #64748B; margin-top: 6px; line-height: 1.3;">Connect phone to same Wi-Fi. In Chrome, tap ⋮ ➡️ <i>Install app</i> for full-screen PWA!</div>
        </div>
        """, unsafe_allow_html=True)

# ================= PAGE 1: RESUME PROFILE =================
if page == "📄 Resume Profile":
    st.markdown('<div class="main-header">📄 Resume Hub & Profile</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upload your resume to automatically extract your skills, experience, and contact details.</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        st.subheader("Upload Resume File")
        uploaded_file = st.file_uploader(
            "Upload your PDF, DOCX, or TXT resume",
            type=["pdf", "docx", "txt"],
            help="Your resume will be parsed locally. Contact info and skills are indexed for matching."
        )
        
        col_load_demo, col_or = st.columns([1, 1])
        with col_load_demo:
            if st.button("🚀 Load Sample Developer Resume", use_container_width=True):
                sample_path = Path(__file__).parent / "sample_resume.txt"
                if sample_path.exists():
                    with open(sample_path, "r", encoding="utf-8") as f:
                        parsed = resume_parser.parse_resume(f, "sample_resume.txt")
                        db.save_resume(
                            name=parsed["name"],
                            email=parsed["email"],
                            phone=parsed["phone"],
                            skills=parsed["skills"],
                            experience=parsed["experience"],
                            education=parsed["education"],
                            raw_text=parsed["raw_text"]
                        )
                        st.success("Loaded sample profile successfully!")
                        st.rerun()

        if uploaded_file is not None:
            if st.button("⚡ Parse & Save Resume", type="primary", use_container_width=True):
                with st.spinner("Extracting candidate profile and skills..."):
                    parsed = resume_parser.parse_resume(uploaded_file, uploaded_file.name)
                    res_id = db.save_resume(
                        name=parsed["name"],
                        email=parsed["email"],
                        phone=parsed["phone"],
                        skills=parsed["skills"],
                        experience=parsed["experience"],
                        education=parsed["education"],
                        raw_text=parsed["raw_text"]
                    )
                    st.success(f"Resume saved! Extracted {len(parsed['skills'])} skills.")
                    st.rerun()

    with col2:
        st.subheader("Current Candidate Profile")
        active = db.get_active_resume()
        if active:
            with st.container(border=True):
                name_input = st.text_input("Candidate Name", value=active.get("name", ""))
                c_email, c_phone = st.columns(2)
                with c_email:
                    email_input = st.text_input("Email", value=active.get("email", ""))
                with c_phone:
                    phone_input = st.text_input("Phone", value=active.get("phone", ""))
                
                skills_list = active.get("skills", [])
                st.write("**Extracted Skills:**")
                skills_chips = " ".join([f'<span class="skill-chip">{s}</span>' for s in skills_list])
                st.markdown(skills_chips, unsafe_allow_html=True)
                
                skills_edit = st.text_area(
                    "Edit Skills (comma separated)", 
                    value=", ".join(skills_list),
                    help="Add or remove specific skills to calibrate matching"
                )
                
                if st.button("Save Profile Changes"):
                    new_skills = [s.strip() for s in skills_edit.split(",") if s.strip()]
                    db.update_resume_profile(active["id"], name_input, email_input, phone_input, new_skills)
                    st.success("Profile updated!")
                    st.rerun()
        else:
            st.info("No active resume. Please upload one or load the sample resume.")

    st.divider()
    st.subheader("⚙️ Default Application Answers")
    st.caption("These default values are used by the Co-Pilot to pre-fill common job application fields.")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        years_exp = st.text_input("Years of Experience", value=db.get_setting("years_exp", "4+ years"))
    with col_p2:
        expected_salary = st.text_input("Expected Salary / Rate", value=db.get_setting("expected_salary", "$110,000 - $140,000 / yr"))
    with col_p3:
        notice_period = st.text_input("Notice Period / Availability", value=db.get_setting("notice_period", "Immediate (2 weeks)"))
        
    col_p4, col_p5 = st.columns(2)
    with col_p4:
        work_auth = st.selectbox(
            "Work Authorization", 
            ["Authorized to work without sponsorship", "Requires visa sponsorship", "US Citizen / Permanent Resident", "EU Citizen", "Other"],
            index=0
        )
    with col_p5:
        portfolio_url = st.text_input("Portfolio / GitHub URL", value=db.get_setting("portfolio_url", "https://github.com/"))
        
    if st.button("Save Application Preferences"):
        db.set_setting("years_exp", years_exp)
        db.set_setting("expected_salary", expected_salary)
        db.set_setting("notice_period", notice_period)
        db.set_setting("work_auth", work_auth)
        db.set_setting("portfolio_url", portfolio_url)
        st.success("Preferences saved successfully!")

# ================= PAGE 2: JOB DISCOVERY =================
elif page == "🔍 Job Discovery":
    st.markdown('<div class="main-header">🔍 Live Remote Job Discovery</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Fetch real-time openings from RemoteOK and We Work Remotely, scored against your resume.</div>', unsafe_allow_html=True)
    
    active_resume = db.get_active_resume()
    
    # Section 1: Collapsible Live Job Fetcher
    with st.expander("📥 Fetch New Live Jobs (LinkedIn, Wellfound, RemoteOK, etc.)", expanded=False):
        st.caption("Download fresh postings from live APIs directly into your local database.")
        col_s1, col_s2, col_s3 = st.columns([1.5, 1.2, 1.3])
        with col_s1:
            search_query = st.text_input("Role / Keyword to Fetch", placeholder="e.g. Python, Full Stack, React, Java, DevOps...", key="fetch_kw_input")
        with col_s2:
            fetch_location = st.text_input("Target Location", value="Remote", placeholder="e.g. Remote, United States, Singapore, India...", key="fetch_loc_input")
        with col_s3:
            category_choice = st.selectbox(
                "Category (WeWorkRemotely)",
                [c[0] for c in job_scraper.WWR_CATEGORIES]
            )
            cat_slug = next(c[1] for c in job_scraper.WWR_CATEGORIES if c[0] == category_choice)
        sources_selected = st.multiselect(
            "Select Platforms to Query:", 
            ["LinkedIn", "Wellfound", "RemoteOK", "Arbeitnow", "Jobicy", "Remotive", "WeWorkRemotely"], 
            default=["LinkedIn", "Wellfound", "RemoteOK", "Arbeitnow", "Jobicy", "Remotive"]
        )
        if st.button("🔄 Download Fresh Jobs Now", type="primary", use_container_width=True):
            with st.spinner("Connecting to job feeds..."):
                fetched = job_scraper.fetch_all_jobs(
                    sources=sources_selected,
                    search_query=search_query,
                    location=fetch_location,
                    category=cat_slug,
                    limit_per_source=30
                )
                saved_count = db.save_jobs(fetched)
                st.session_state.cached_jobs = db.get_all_jobs()
                st.success(f"Fetched and added {len(fetched)} live jobs! ({saved_count} new/updated)")
                st.rerun()

    all_jobs = db.get_all_jobs()
    st.session_state.cached_jobs = all_jobs

    if not all_jobs:
        st.info("No jobs stored yet. Expand 'Fetch New Live Jobs' above and click Download!")
    else:
        st.markdown("### 🎯 Explore & Apply to Matched Positions")
        
        # Load tracked jobs from Application Tracker
        tracked_ids, tracked_keys = db.get_tracked_job_identifiers()
        
        # Real-time search inside current list
        col_f1, col_f2, col_f3, col_f4 = st.columns([1.7, 1.3, 1.0, 1.0])
        with col_f1:
            filter_text = st.text_input("🔍 Keyword Search", placeholder="Role, company, or tech skill...", key="filter_text_input")
        with col_f2:
            place_filter = st.text_input("📍 Place / Location", placeholder="e.g. Remote, US, Singapore, UK, India...", key="place_filter_input")
        with col_f3:
            sort_by = st.selectbox("Sort Order", ["Highest Match Score", "Most Recent"])
        with col_f4:
            st.write("")
            st.write("")
            hide_applied = st.checkbox(
                "🚫 Hide Applied", 
                value=True, 
                help="Automatically hides any jobs that are already in your Application Tracker."
            )

        # Quick Location Presets with on_click callback (prevents instantiation error)
        def set_place_preset(preset_val: str):
            st.session_state["place_filter_input"] = preset_val

        col_p_label, col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns([0.8, 0.8, 0.9, 1.2, 1.1, 1.0])
        with col_p_label:
            st.markdown('<div style="padding-top: 6px; font-size: 0.82rem; font-weight: 700; color: #64748B;">Quick Places:</div>', unsafe_allow_html=True)
        with col_p1:
            st.button("🌐 All", on_click=set_place_preset, args=("",), use_container_width=True, key="btn_loc_all")
        with col_p2:
            st.button("🏠 Remote", on_click=set_place_preset, args=("Remote",), use_container_width=True, key="btn_loc_remote")
        with col_p3:
            st.button("🏢 US / Americas", on_click=set_place_preset, args=("United States",), use_container_width=True, key="btn_loc_us")
        with col_p4:
            st.button("🏰 Europe & UK", on_click=set_place_preset, args=("Europe",), use_container_width=True, key="btn_loc_eu")
        with col_p5:
            st.button("🌏 Asia & SG", on_click=set_place_preset, args=("Singapore",), use_container_width=True, key="btn_loc_asia")

        # Platform selector
        source_filter = st.radio(
            "Filter by Platform:",
            ["All", "LinkedIn", "Wellfound", "RemoteOK", "Arbeitnow", "Jobicy", "Remotive", "WeWorkRemotely"],
            horizontal=True,
            key="filter_source_radio"
        )

        min_score = st.slider("Filter by Minimum Match Score (%)", min_value=0, max_value=90, value=0, step=5)

        # Compute matches for jobs against active resume
        scored_jobs = []
        hidden_applied_count = 0
        for j in all_jobs:
            j_id = str(j.get("id", ""))
            j_key = (str(j.get("title", "")).strip().lower(), str(j.get("company", "")).strip().lower())
            is_in_tracker = (j_id in tracked_ids) or (j_key in tracked_keys)
            
            # Remove from discovery if already applied / in tracker
            if is_in_tracker:
                hidden_applied_count += 1
                if hide_applied:
                    continue

            # Source check
            if source_filter != "All" and j.get("source", "").strip().lower() != source_filter.strip().lower():
                continue

            # Place / Location check
            if place_filter and not matches_place_filter(j, place_filter):
                continue
                
            # Quick text search filter
            if filter_text:
                q = filter_text.lower().strip()
                clean_tags_str = ' '.join(matcher.extract_clean_tags(j.get('tags', [])))
                combined = f"{j.get('title','')} {j.get('company','')} {clean_tags_str} {j.get('description','')}".lower()
                if q not in combined:
                    continue

            if active_resume:
                match_info = matcher.compute_local_match(active_resume, j)
                score = match_info["score"]
                matched_skills = match_info["matched_skills"]
                missing_skills = match_info["missing_skills"]
            else:
                score = 50.0
                matched_skills = []
                missing_skills = []
                
            if score >= min_score:
                scored_jobs.append({
                    **j,
                    "match_score": score,
                    "matched_skills": matched_skills,
                    "missing_skills": missing_skills,
                    "is_in_tracker": is_in_tracker
                })

        if sort_by == "Highest Match Score":
            scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)

        caption_items = [f"Showing **{len(scored_jobs)}** open positions"]
        if place_filter:
            caption_items.append(f"📍 filtered by **'{place_filter}'**")
        if hide_applied and hidden_applied_count > 0:
            caption_items.append(f"**{hidden_applied_count}** in Tracker hidden")
        caption_items.append(f"**{len(all_jobs)}** total in database")
        st.caption(" • ".join(caption_items))

        if not scored_jobs:
            st.warning(f"⚠️ No jobs found matching your filters. Try clearing the search box or lowering the Minimum Score slider!")

        for job in scored_jobs[:45]:
            score = job.get("match_score", 50)
            
            with st.container(border=True):
                c_top1, c_top2 = st.columns([3.3, 1.2])
                with c_top1:
                    st.markdown(f"#### {job['title']}")
                    src_badge = format_source_badge(job.get('source', 'Remote'))
                    tracker_badge = ' &nbsp;•&nbsp; <span style="background-color: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">📌 In Tracker</span>' if job.get('is_in_tracker') else ""
                    st.markdown(f"🏢 **{job['company']}** &nbsp;•&nbsp; 📍 {job.get('location', 'Remote')} &nbsp;•&nbsp; {src_badge}{tracker_badge}", unsafe_allow_html=True)
                    if job.get('salary'):
                        st.markdown(f"💰 **Comp:** `{job['salary']}`")
                with c_top2:
                    score_badge_html = format_score_badge(score)
                    st.markdown(f'<div style="text-align: right;">{score_badge_html}</div>', unsafe_allow_html=True)
                    if job.get('published_date'):
                        st.caption(f"📅 {job['published_date'][:16]}")
                
                # Tags & Matched Skills
                matched_kws = job.get('matched_skills', [])
                clean_job_tags = matcher.extract_clean_tags(job.get('tags', []))
                if matched_kws:
                    chips = " ".join([f'<span class="skill-chip">✓ {s}</span>' for s in matched_kws[:7]])
                    st.markdown(f"**Matched Skills:** {chips}", unsafe_allow_html=True)
                elif clean_job_tags:
                    chips = " ".join([f'<span class="skill-chip">{t}</span>' for t in clean_job_tags[:6]])
                    st.markdown(f"**Tags:** {chips}", unsafe_allow_html=True)
                    
                # Short Description Preview
                desc_preview = job.get('description', '')[:200]
                if desc_preview:
                    st.caption(f"{desc_preview}...")
                    
                # Action Buttons
                btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([1.3, 1.1, 0.8, 1])
                with btn_col1:
                    if st.button(f"🤖 Auto-Apply", key=f"auto_{job['id']}", type="primary", use_container_width=True, help="Auto-tailors materials and pops open browser window!"):
                        st.session_state.selected_job = job
                        st.session_state.nav_redirect = "🎯 Match & Co-Pilot"
                        st.session_state.trigger_auto_apply = True
                        st.rerun()
                with btn_col2:
                    if st.button(f"🎯 Co-Pilot", key=f"copilot_{job['id']}", use_container_width=True, help="Review match breakdown and tailor cover letters"):
                        st.session_state.selected_job = job
                        st.session_state.nav_redirect = "🎯 Match & Co-Pilot"
                        st.rerun()
                with btn_col3:
                    if st.button(f"💾 Save", key=f"save_{job['id']}", use_container_width=True):
                        db.save_or_update_application(
                            job_id=job['id'],
                            job_title=job['title'],
                            company=job['company'],
                            apply_url=job.get('apply_url', job.get('url', '')),
                            match_score=score,
                            status='Saved'
                        )
                        st.toast(f"Saved {job['title']} to your Application Tracker!")
                        st.rerun()
                with btn_col4:
                    apply_link = job.get('apply_url') or job.get('url')
                    if apply_link:
                        st.link_button("🔗 Job Link", apply_link, use_container_width=True)

# ================= PAGE 3: MATCH & CO-PILOT =================
elif page == "🎯 Match & Co-Pilot":
    st.markdown('<div class="main-header">🎯 Application Match & Co-Pilot</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Deep ATS alignment, custom cover letters, tailored bullet points, and 1-click application prep.</div>', unsafe_allow_html=True)
    
    active_resume = db.get_active_resume()
    target_job = st.session_state.selected_job
    
    # Allow choosing job from cached list if none selected
    all_jobs = db.get_all_jobs()
    if not target_job and all_jobs:
        job_options = {f"{j['title']} @ {j['company']} ({j['source']})": j for j in all_jobs}
        selected_key = st.selectbox("Choose a job to analyze:", list(job_options.keys()))
        target_job = job_options[selected_key]
        st.session_state.selected_job = target_job
        
    if not active_resume:
        st.warning("⚠️ Please upload or load a resume in the 'Resume Profile' tab first!")
    elif not target_job:
        st.info("ℹ️ Please select a job from the 'Job Discovery' tab or fetch jobs first!")
    else:
        # Job Overview Header
        with st.container(border=True):
            j_col1, j_col2 = st.columns([2.6, 1.4])
            with j_col1:
                st.markdown(f"## {target_job['title']} @ **{target_job['company']}**")
                st.write(f"📍 {target_job.get('location', 'Remote')} &nbsp;|&nbsp; 🏷️ {target_job.get('source')} &nbsp;|&nbsp; 💰 {target_job.get('salary', 'Salary Not Disclosed')}")
                prof_stat = auto_applicant.get_profile_status()
                cookie_cnt = prof_stat.get("total_cookies", 0)
                st.markdown(f'<div style="font-size: 0.8rem; color: #16A34A; font-weight: 600;">🍪 Persistent Cache Active &nbsp;•&nbsp; {cookie_cnt} saved session cookies &nbsp;•&nbsp; Auto-login enabled</div>', unsafe_allow_html=True)
            with j_col2:
                auto_pilot_clicked = st.button("🤖 Auto-Pilot Apply (Pops Browser)", type="primary", use_container_width=True, help="Auto-tailors your materials, opens a real browser, pre-fills your data, and waits for your final review!")
                apply_url = target_job.get('apply_url') or target_job.get('url')
                if apply_url:
                    st.link_button("🌐 Open Job Link", apply_url, use_container_width=True)

        if st.session_state.get("trigger_auto_apply"):
            auto_pilot_clicked = True
            st.session_state.trigger_auto_apply = False

        if auto_pilot_clicked:
            gemini_key = get_gemini_api_key()
            with st.status("🤖 Running Auto-Pilot Job Application...", expanded=True) as status:
                st.write("1. ✍️ Tailoring cover letter specifically for this job...")
                st.write("2. 🍪 Loading persistent browser profile & cache memory (saved logins active)...")
                st.write("3. 🖥️ Launching visible Chrome browser on your screen...")
                st.write("4. 📝 Detecting form inputs, pre-filling answers & attaching resume...")
                st.write("5. 👀 Screen is popped open! Please review fields, answer custom questions, and click Submit when ready.")
                result = auto_applicant.auto_apply_to_job(
                    job_data=target_job,
                    resume_data=active_resume,
                    api_key=gemini_key,
                    keep_open_seconds=90
                )
                status.update(label="✅ Auto-Pilot session finished!", state="complete", expanded=False)
            
            with st.expander("📋 View Auto-Pilot Session Activity Logs", expanded=True):
                for l in result.get("logs", []):
                    st.write(f"- {l}")
            st.success("Application marked as 'In Progress' / 'Applied' in your Application Tracker!")
        
        # Deep Match Analysis
        st.subheader("📊 Match Diagnostic & Skill Gap Analysis")
        
        # Check settings for Gemini API
        gemini_key = get_gemini_api_key()
        use_ai = bool(gemini_key)
        
        # Rate-Limit Shield: Cache analysis in session state per job & candidate to prevent burning API calls
        match_cache_key = f"match_ai_{target_job.get('id', '')}_{active_resume.get('name', '')}"
        if match_cache_key in st.session_state:
            match_results = st.session_state[match_cache_key]
        else:
            with st.spinner("Analyzing candidate match and ATS keywords..."):
                if use_ai:
                    match_results = matcher.analyze_match_with_gemini(active_resume, target_job, gemini_key)
                else:
                    match_results = matcher.compute_local_match(active_resume, target_job)
                st.session_state[match_cache_key] = match_results
                
        score = match_results.get("score", 0.0)
        is_ai_mode = match_results.get("analysis_mode") == "gemini_ai"
        quota_exhausted = match_results.get("quota_exhausted", False)
        
        if quota_exhausted:
            st.info("ℹ️ **Gemini Free-Tier daily limit reached for today:** Automatically running in **Smart Local Heuristic Mode** — your match score, skill breakdown, cover letters, and outreach tools remain 100% functional and offline-ready.")
        
        col_m1, col_m2, col_m3 = st.columns([1, 1.5, 1.5])
        with col_m1:
            st.metric(label="Overall Match Score", value=f"{score}%")
            if is_ai_mode:
                st.caption("✨ Evaluated with Google Gemini AI")
            else:
                st.caption("⚡ Calculated via local TF-IDF & Skill Taxonomy")
                
        with col_m2:
            st.write("**✅ Matched Skills:**")
            matched = match_results.get("matched_skills", [])
            if matched:
                st.markdown(" ".join([f'<span class="skill-chip">{s}</span>' for s in matched]), unsafe_allow_html=True)
            else:
                st.write("No exact skill overlap detected.")
                
        with col_m3:
            st.write("**⚠️ Missing / Gap Skills:**")
            missing = match_results.get("missing_skills", [])
            if missing:
                st.markdown(" ".join([f'<span class="missing-chip">{s}</span>' for s in missing[:12]]), unsafe_allow_html=True)
            else:
                st.write("No major skill gaps identified!")

        if use_ai and "summary" in match_results:
            st.info(f"**Recruiter Assessment:** {match_results['summary']}")
            if match_results.get("ats_recommendations"):
                st.write("**ATS Keyword Tips:**")
                for tip in match_results["ats_recommendations"]:
                    st.markdown(f"- {tip}")

        st.divider()

        # ⚡ 1-Click Application Quick-Fill Kit
        with st.expander("⚡ 1-Click Application Quick-Fill Kit (Tap any box to copy)", expanded=False):
            st.caption("Essential candidate fields for application portals (Workday, Greenhouse, Lever, Ashby). Tap the copy button on any box to copy instantly!")
            
            c_kit1, c_kit2, c_kit3 = st.columns(3)
            with c_kit1:
                st.caption("👤 Full Name")
                st.code(active_resume.get('name', 'Candidate'), language=None)
                st.caption("📧 Email")
                st.code(active_resume.get('email', 'applicant@email.com'), language=None)
                st.caption("📱 Phone")
                st.code(active_resume.get('phone', '+1 555-0199'), language=None)
                st.caption("📍 Location")
                st.code(db.get_setting("user_location", active_resume.get('location', 'Remote / Worldwide')), language=None)
                
            with c_kit2:
                st.caption("🔗 LinkedIn URL")
                li_url = db.get_setting("linkedin_url", active_resume.get('links', {}).get('linkedin', 'https://linkedin.com/in/'))
                st.code(li_url, language=None)
                st.caption("💻 GitHub URL")
                gh_url = db.get_setting("github_url", active_resume.get('links', {}).get('github', 'https://github.com/'))
                st.code(gh_url, language=None)
                st.caption("🌐 Portfolio / Website")
                pf_url = db.get_setting("portfolio_url", active_resume.get('links', {}).get('portfolio', 'https://portfolio.dev'))
                st.code(pf_url, language=None)
                st.caption("⏳ Notice Period")
                st.code(db.get_setting("notice_period", "Immediate (2 weeks)"), language=None)

            with c_kit3:
                st.caption("💼 Years of Experience")
                st.code(db.get_setting("years_exp", "4+ years"), language=None)
                st.caption("💰 Desired Compensation")
                st.code(db.get_setting("expected_salary", "$130,000 / yr (Flexible)"), language=None)
                st.caption("🛂 Work Authorization")
                st.code(db.get_setting("work_auth", "Authorized to work without sponsorship"), language=None)
                st.caption("🏷️ Top Skills")
                st.code(", ".join(active_resume.get('skills', [])[:6]), language=None)

        # Co-Pilot Tools Tabs
        tool_tab1, tool_tab2, tool_tab3, tool_tab4, tool_tab5, tool_tab6 = st.tabs([
            "✍️ Tailored Cover Letter", 
            "📝 Optimized Bullet Points", 
            "💬 Recruiter Outreach (LinkedIn/Email)", 
            "📋 Quick-Fill Form Answers",
            "🎯 Interview Prep Cheat Sheet",
            "💰 Salary Intelligence Advisor"
        ])
        
        with tool_tab1:
            col_t1, col_t2 = st.columns([1, 2])
            with col_t1:
                tone = st.selectbox("Tone", ["Confident & Professional", "Technical & Concise", "Enthusiastic & Creative"])
                gen_letter_btn = st.button("Generate Cover Letter", type="primary", use_container_width=True)
            
            # Fetch existing saved application for this job if any
            existing_app = db.get_application_by_job_id(target_job['id'])
            initial_letter = existing_app.get('cover_letter', '') if existing_app else ""
            
            if gen_letter_btn or not initial_letter:
                with st.spinner("Drafting tailored cover letter..."):
                    generated_letter = copilot.generate_cover_letter(active_resume, target_job, api_key=gemini_key, tone=tone)
            else:
                generated_letter = initial_letter

            with col_t2:
                letter_text = st.text_area("Cover Letter Editor", value=generated_letter, height=350)
                
                c_sv1, c_sv2 = st.columns(2)
                with c_sv1:
                    if st.button("💾 Save Cover Letter to Application"):
                        db.save_or_update_application(
                            job_id=target_job['id'],
                            job_title=target_job['title'],
                            company=target_job['company'],
                            apply_url=target_job.get('apply_url', target_job.get('url', '')),
                            match_score=score,
                            cover_letter=letter_text
                        )
                        st.success("Cover letter saved to tracker!")
                with c_sv2:
                    st.download_button(
                        label="📥 Download as .txt",
                        data=letter_text,
                        file_name=f"Cover_Letter_{target_job['company']}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

        with tool_tab2:
            st.write("Customize your resume achievements specifically targeting this position:")
            if st.button("⚡ Generate Tailored Resume Bullets"):
                with st.spinner("Generating impact bullets..."):
                    bullets = copilot.generate_tailored_bullets(active_resume, target_job, api_key=gemini_key)
                    for b in bullets:
                        st.markdown(f"- {b}")
            else:
                st.caption("Click the button above to generate 3 tailored accomplishment statements.")

        with tool_tab3:
            st.markdown("#### 👥 Find & Message Decision Makers on LinkedIn")
            st.caption(f"Connect directly with the hiring team at **{target_job['company']}** to fast-track your application past automated resume filters.")
            
            # 1. Target Hiring Personas & Direct LinkedIn Search Links
            st.markdown("##### 1️⃣ Select Decision Maker Persona to Target:")
            recruiter_targets = copilot.get_recruiter_targets(target_job['company'], target_job['title'])
            
            cols_r1, cols_r2 = st.columns(2)
            for idx, target in enumerate(recruiter_targets):
                col = cols_r1 if idx % 2 == 0 else cols_r2
                with col:
                    with st.container(border=True):
                        st.markdown(f"**{target['persona']}**")
                        st.caption(target['description'])
                        st.info(f"💡 **Tip:** {target['tip']}", icon="💡")
                        
                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            st.link_button("🔗 Open on LinkedIn", target['linkedin_url'], use_container_width=True)
                        with btn_c2:
                            st.link_button("🔎 Google X-Ray Search", target['xray_url'], use_container_width=True)

            # Optional AI Intel from Gemini
            if use_ai and gemini_key:
                with st.expander("⚡ Analyze Hiring Structure with Gemini AI", expanded=False):
                    if st.button("Generate Decision Maker Strategy with AI", key="btn_ai_recruiter_intel"):
                        with st.spinner("Analyzing company structure and outreach strategy..."):
                            intel = copilot.find_company_decision_makers_ai(target_job['company'], target_job['title'], gemini_key)
                            st.markdown(intel)

            st.divider()

            # 2. Tailored Message Generator
            st.markdown("##### 2️⃣ Customize & Copy Your Direct Outreach Message:")
            
            col_m_opt1, col_m_opt2, col_m_opt3 = st.columns([1.5, 1.5, 1.2])
            with col_m_opt1:
                selected_persona_name = st.selectbox(
                    "Target Persona",
                    [t["persona"] for t in recruiter_targets],
                    index=0
                )
                selected_persona_id = next(t["id"] for t in recruiter_targets if t["persona"] == selected_persona_name)
                
            with col_m_opt2:
                msg_format = st.radio(
                    "Format",
                    ["LinkedIn Connection Note (≤ 300 chars)", "LinkedIn InMail / Longer DM", "Recruiter Cold Email"],
                    index=0
                )
                format_key = "linkedin_note" if "300" in msg_format else ("linkedin_inmail" if "InMail" in msg_format else "email")

            with col_m_opt3:
                contact_name = st.text_input("Contact's First Name (Optional)", placeholder="e.g. Sarah, Alex")

            # Generate tailored note
            outreach_text = copilot.generate_persona_outreach(
                resume_data=active_resume,
                job_data=target_job,
                persona_id=selected_persona_id,
                contact_name=contact_name,
                msg_type=format_key
            )

            # Live Character Counter for LinkedIn Notes
            char_count = len(outreach_text)
            if format_key == "linkedin_note":
                if char_count <= 300:
                    st.markdown(f'<div style="font-size: 0.82rem; font-weight: 700; color: #16A34A; margin-bottom: 6px;">📏 {char_count} / 300 characters ✅ Fits LinkedIn Connection Note limit</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="font-size: 0.82rem; font-weight: 700; color: #DC2626; margin-bottom: 6px;">⚠️ {char_count} / 300 characters — Exceeds LinkedIn 300 char note limit</div>', unsafe_allow_html=True)

            st.text_area("Outreach Message Preview (Editable)", value=outreach_text, height=160 if format_key == "linkedin_note" else 260)
            
            with st.expander("📋 Click here for 1-Click Copy Code Block", expanded=True):
                st.code(outreach_text, language=None)

        with tool_tab4:
            st.write("Copy-paste ready answers for typical company application portals (Workday, Greenhouse, Lever):")
            user_prefs = {
                "years_exp": db.get_setting("years_exp", "4+ years"),
                "expected_salary": db.get_setting("expected_salary", "$120,000 / yr"),
                "work_auth": db.get_setting("work_auth", "Authorized to work"),
                "notice_period": db.get_setting("notice_period", "Immediate (2 weeks)")
            }
            form_answers = copilot.generate_application_answers(active_resume, target_job, user_prefs)
            for q, a in form_answers.items():
                with st.expander(f"**{q}**", expanded=True):
                    st.code(a, language=None)

        with tool_tab5:
            st.markdown("#### 🎯 Role-Specific Interview Preparation Cheat Sheet")
            st.caption(f"Targeted technical and behavioral talking points for your upcoming interviews with **{target_job['company']}** for the **{target_job['title']}** role.")
            
            c_int1, c_int2 = st.columns([2.5, 1])
            with c_int2:
                regen_interview = st.button("🔄 Refresh Cheat Sheet", use_container_width=True)
                
            interview_cache_key = f"interview_prep_{target_job['id']}_{active_resume.get('name', '')}"
            if regen_interview or interview_cache_key not in st.session_state:
                with st.spinner("Analyzing job requirements and drafting tailored STAR talking points..."):
                    cheat_sheet_data = copilot.generate_interview_cheat_sheet(active_resume, target_job, api_key=gemini_key)
                    st.session_state[interview_cache_key] = cheat_sheet_data
            else:
                cheat_sheet_data = st.session_state[interview_cache_key]
                
            st.info(f"💡 **Interviewer Focus:** {cheat_sheet_data.get('role_summary', '')}")
            
            st.markdown("##### 1️⃣ High-Probability Interview Questions & Structured STAR Answers:")
            for idx, q_item in enumerate(cheat_sheet_data.get("questions", []), 1):
                with st.container(border=True):
                    st.markdown(f"**Q{idx}: {q_item.get('question', '')}**")
                    st.caption(f"📌 Focus: {q_item.get('category', 'Technical Competency')}")
                    
                    with st.expander("🗣️ View Recommended STAR Talking Points (Situation, Task, Action, Result)", expanded=True):
                        star = q_item.get("star_framework", {})
                        if isinstance(star, dict):
                            st.markdown(f"**• Situation:** {star.get('Situation', '')}")
                            st.markdown(f"**• Task:** {star.get('Task', '')}")
                            st.markdown(f"**• Action:** {star.get('Action', '')}")
                            st.markdown(f"**• Result:** {star.get('Result', '')}")
                        else:
                            st.markdown(str(star))
                            
                    st.markdown(f'<div style="font-size: 0.82rem; color: #D97706; font-weight: 600;">💡 Pro-Tip: {q_item.get("pro_tip", "")}</div>', unsafe_allow_html=True)
                    
            st.markdown("##### 2️⃣ Impressive Questions to Ask the Interviewer:")
            st.caption("Ask these at the end of your call to demonstrate technical depth, ownership, and seniority:")
            for r_q in cheat_sheet_data.get("reverse_questions", []):
                st.code(r_q, language=None)

        with tool_tab6:
            st.markdown("#### 💰 Salary Intelligence & Compensation Advisor")
            st.caption(f"Real-time compensation benchmark and application negotiation guidance for **{target_job['title']}** at **{target_job['company']}**.")
            
            user_prefs_dict = {
                "years_exp": db.get_setting("years_exp", "4+ years"),
                "expected_salary": db.get_setting("expected_salary", "$120,000 / yr"),
                "work_auth": db.get_setting("work_auth", "Authorized to work"),
                "notice_period": db.get_setting("notice_period", "Immediate (2 weeks)")
            }
            salary_data = copilot.estimate_salary_benchmark(target_job, user_prefs_dict)
            
            if salary_data.get("has_posted_salary"):
                st.success(f"💵 **Employer Stated Compensation:** {salary_data['posted_salary']}")
            else:
                st.info(f"ℹ️ Employer did not list a salary in the posting. Showing market intelligence based on **{salary_data['level']}** in **{salary_data['domain']}**.")
                
            st.markdown(f"📍 Market Scope: **{salary_data['location_context']}** &nbsp;•&nbsp; Level: **{salary_data['level']}**")
            
            p_cols = st.columns(4)
            pcts = salary_data.get("percentiles", {})
            with p_cols[0]:
                st.metric("25th Percentile", pcts.get("p25", "N/A"), help="Entry / Conservative market base")
            with p_cols[1]:
                st.metric("Median (Market Rate)", pcts.get("p50_median", "N/A"), help="Typical market compensation")
            with p_cols[2]:
                st.metric("75th Percentile", pcts.get("p75", "N/A"), help="Competitive tier for strong candidates")
            with p_cols[3]:
                st.metric("90th Percentile", pcts.get("p90_top", "N/A"), help="Top-of-market / Staff / Tech Lead")
                
            st.divider()
            st.markdown("##### 📝 How to Answer Compensation Fields on Application Forms:")
            guidance = salary_data.get("form_guidance", {})
            
            g_col1, g_col2 = st.columns(2)
            with g_col1:
                st.caption("If the form has a text box (Preferred):")
                st.code(guidance.get("text_input", "Competitive / Open to discussion"), language=None)
            with g_col2:
                st.caption("If the form requires a strictly numeric field:")
                st.code(guidance.get("number_input", "125000"), language=None)
                
            st.markdown(f'<div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 0.88rem; color: #166534;"><strong>🤝 Recruiter Screening Phone Script:</strong><br>{guidance.get("negotiation_tip", "")}</div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("🚀 Mark Application Status")
        col_st1, col_st2, col_st3 = st.columns([1.5, 1.5, 2])
        with col_st1:
            new_status = st.selectbox("Update Status", ["Saved", "Applied", "Interviewing", "Offer", "Rejected"])
        with col_st2:
            st.write("")
            st.write("")
            if st.button("Update Tracker"):
                applied_date_val = datetime.now().strftime("%Y-%m-%d") if new_status == "Applied" else ""
                db.save_or_update_application(
                    job_id=target_job['id'],
                    job_title=target_job['title'],
                    company=target_job['company'],
                    apply_url=target_job.get('apply_url', target_job.get('url', '')),
                    match_score=score,
                    status=new_status,
                    applied_date=applied_date_val
                )
                st.success(f"Status updated to '{new_status}'!")

# ================= PAGE 4: APPLICATION TRACKER =================
elif page == "📊 Application Tracker":
    st.markdown('<div class="main-header">📊 Application Pipeline & Tracker</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Monitor your active job submissions, interview stages, and follow-ups.</div>', unsafe_allow_html=True)
    
    apps = db.get_applications()
    
    # Metrics
    saved_count = sum(1 for a in apps if a['status'] == 'Saved')
    applied_count = sum(1 for a in apps if a['status'] == 'Applied')
    interview_count = sum(1 for a in apps if a['status'] == 'Interviewing')
    offer_count = sum(1 for a in apps if a['status'] == 'Offer')
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💾 Saved Jobs", saved_count)
    m2.metric("📨 Applied", applied_count)
    m3.metric("🤝 Interviews", interview_count)
    m4.metric("🎉 Offers", offer_count)
    
    col_t_met, col_t_exp = st.columns([2.5, 1.5])
    with col_t_exp:
        if apps:
            export_rows = []
            for a in apps:
                export_rows.append({
                    "Company": a.get("company", ""),
                    "Job Title": a.get("job_title", ""),
                    "Status": a.get("status", "Saved"),
                    "Match Score": f"{a.get('match_score', 0)}%",
                    "Date Applied": a.get("applied_date", ""),
                    "Application Link": a.get("apply_url", ""),
                    "Notes": a.get("notes", ""),
                    "Last Updated": str(a.get("updated_at", ""))[:19]
                })
            apps_df = pd.DataFrame(export_rows)
            csv_data = apps_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export Applications to CSV",
                data=csv_data,
                file_name=f"job_applications_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                help="Export all tracked jobs and application stages to a clean CSV."
            )

    st.divider()
    
    if not apps:
        st.info("You haven't tracked any applications yet. Browse jobs in 'Job Discovery' and click 'Save' or 'Co-Pilot'!")
    else:
        status_tabs = st.tabs(["All", "Saved", "Applied", "Interviewing", "Offer", "Rejected"])
        tab_names = ["All", "Saved", "Applied", "Interviewing", "Offer", "Rejected"]
        
        for tab, t_name in zip(status_tabs, tab_names):
            with tab:
                filtered_apps = apps if t_name == "All" else [a for a in apps if a['status'] == t_name]
                if not filtered_apps:
                    st.caption(f"No applications currently in '{t_name}'.")
                else:
                    for app in filtered_apps:
                        with st.container(border=True):
                            c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
                            with c1:
                                st.markdown(f"### {app['job_title']} @ **{app['company']}**")
                                if app.get('applied_date'):
                                    st.caption(f"📅 Applied on: {app['applied_date']}")
                            with c2:
                                st.write(f"Match: **{app.get('match_score', 0)}%**")
                                st.write(f"Status: `{app['status']}`")
                            with c3:
                                if app.get('apply_url'):
                                    st.link_button("🔗 Job Link", app['apply_url'], use_container_width=True)
                            with c4:
                                if st.button("🗑️", key=f"del_{app['id']}", help="Delete application"):
                                    db.delete_application(app['id'])
                                    st.rerun()
                                    
                            if app.get('cover_letter'):
                                with st.expander("📄 View Saved Cover Letter"):
                                    st.text(app['cover_letter'])

# ================= PAGE 5: SETTINGS =================
elif page == "⚙️ Settings":
    st.markdown('<div class="main-header">⚙️ Settings & AI Configuration</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Configure Google Gemini API keys, local matching heuristics, and defaults.</div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.subheader("🤖 Google Gemini AI Key")
        st.write("Using a Gemini API Key enables deeper qualitative ATS recruiter analysis, personalized cover letters, and bullet point rewrites.")
        
        current_key = get_gemini_api_key()
        if current_key:
            st.success("🟢 Connected to Google Gemini AI (**Smart Cascade: Gemini 3.5 & 3.6 Flash / Lite with Auto-Fallback**) — Active & Ready!")
        else:
            st.info("⚪ Local Heuristic Mode (Free offline TF-IDF matching active)")

        new_key = st.text_input("Gemini API Key", value=current_key, type="password", placeholder="AIzaSy...")
        
        if st.button("Save API Key", type="primary"):
            db.set_setting("gemini_api_key", new_key)
            st.success("API key saved securely in local database!")
            
        st.caption("Don't have a Gemini key? Get a free key at [Google AI Studio](https://aistudio.google.com/). The Co-Pilot also functions 100% offline using built-in TF-IDF and skill taxonomy!")

    with st.container(border=True):
        st.subheader("👤 Candidate Profile & Quick-Apply Defaults")
        st.write("Customize your default links, contact details, and job preferences. These are instantly pre-filled into your **1-Click Application Kit** across all job portals:")
        
        c_set1, c_set2 = st.columns(2)
        with c_set1:
            cfg_li = st.text_input("LinkedIn Profile URL", value=db.get_setting("linkedin_url", "https://linkedin.com/in/"), key="cfg_li")
            cfg_gh = st.text_input("GitHub Profile URL", value=db.get_setting("github_url", "https://github.com/"), key="cfg_gh")
            cfg_pf = st.text_input("Portfolio / Website URL", value=db.get_setting("portfolio_url", "https://"), key="cfg_pf")
            cfg_loc = st.text_input("Current Location", value=db.get_setting("user_location", "Remote / Worldwide"), key="cfg_loc")
            
        with c_set2:
            cfg_exp = st.text_input("Years of Experience", value=db.get_setting("years_exp", "4+ years"), key="cfg_exp")
            cfg_sal = st.text_input("Expected Salary / Rate", value=db.get_setting("expected_salary", "$130,000 / yr (Flexible)"), key="cfg_sal")
            cfg_auth = st.text_input("Work Authorization", value=db.get_setting("work_auth", "Authorized to work without sponsorship"), key="cfg_auth")
            cfg_not = st.text_input("Notice Period / Availability", value=db.get_setting("notice_period", "Immediate (2 weeks)"), key="cfg_not")
            
        if st.button("Save Profile Defaults", type="primary", key="btn_save_defaults"):
            db.set_setting("linkedin_url", cfg_li.strip())
            db.set_setting("github_url", cfg_gh.strip())
            db.set_setting("portfolio_url", cfg_pf.strip())
            db.set_setting("user_location", cfg_loc.strip())
            db.set_setting("years_exp", cfg_exp.strip())
            db.set_setting("expected_salary", cfg_sal.strip())
            db.set_setting("work_auth", cfg_auth.strip())
            db.set_setting("notice_period", cfg_not.strip())
            st.success("Candidate application defaults saved successfully!")
            st.rerun()

    with st.container(border=True):
        st.subheader("🍪 Browser Sessions & Cache Memory Manager")
        st.write("Never sign in repeatedly across platforms. The agent maintains a persistent Chrome browser profile that securely keeps your session tokens, cookies, and cache memory preserved across all auto-applications.")
        
        prof_status = auto_applicant.get_profile_status()
        
        b_col1, b_col2, b_col3, b_col4 = st.columns(4)
        with b_col1:
            st.metric("Profile Status", "🟢 Active" if prof_status["exists"] else "⚪ Not Initialized")
        with b_col2:
            st.metric("Saved Cookies", f"{prof_status['total_cookies']} items")
        with b_col3:
            st.metric("Google Account", "🟢 Synced" if prof_status['google_cookies'] > 0 else "⚪ Not Detected")
        with b_col4:
            st.metric("Cache Size", f"{prof_status['size_mb']} MB")

        st.caption(f"📁 Local Profile Path: `{prof_status['path']}`")

        st.divider()
        st.markdown("#### 🔑 1-Click Browser Launcher & One-Time Sign In")
        st.write("Need to sign in to LinkedIn, Google, Wellfound, or Indeed? Launch the browser window, log in once, and your sessions will remain permanently saved on this machine!")
        
        col_login_target, col_login_btn = st.columns([2.5, 1.5])
        with col_login_target:
            target_site = st.selectbox(
                "Select Destination to Open:",
                [
                    "LinkedIn (https://www.linkedin.com/login)",
                    "Google Account (https://accounts.google.com)",
                    "Wellfound / AngelList (https://wellfound.com/login)",
                    "Indeed (https://secure.indeed.com)",
                    "Custom URL..."
                ],
                key="sel_login_platform"
            )
            custom_url = ""
            if "Custom URL" in target_site:
                custom_url = st.text_input("Enter Portal URL:", placeholder="https://boards.greenhouse.io/...", key="custom_portal_url")
        
        with col_login_btn:
            st.write("")
            st.write("")
            if st.button("🚀 Open Browser Window", type="primary", use_container_width=True, help="Opens the persistent browser so you can log in once. Your session will be remembered forever!"):
                url_to_open = custom_url if ("Custom URL" in target_site and custom_url) else target_site.split("(")[-1].rstrip(")")
                with st.spinner("Opening browser window on your screen... Feel free to log in!"):
                    res = auto_applicant.open_persistent_browser_manager(target_url=url_to_open, wait_seconds=180)
                    st.success(f"Browser closed and session saved! {res['status']['total_cookies']} cookies active.")
                    st.rerun()

        st.divider()
        st.markdown("#### 🔄 Import Cache & Cookies from Installed Chrome")
        st.write("Seed or refresh your login sessions and cache memory directly from your existing Google Chrome browser:")
        col_sync1, col_sync2 = st.columns([2.5, 1.5])
        with col_sync1:
            st.caption("Pulls `Local State`, `Cookies`, `Local Storage` and `IndexedDB` from `C:\\Users\\hp\\AppData\\Local\\Google\\Chrome\\User Data\\Default`.")
        with col_sync2:
            if st.button("🔄 Import from Chrome", use_container_width=True, help="Import your existing Chrome cookies and logins into the agent's browser profile."):
                with st.spinner("Importing Chrome cache and cookies..."):
                    sync_res = auto_applicant.sync_chrome_cache(force=True)
                    if sync_res.get("success"):
                        st.success(sync_res.get("message"))
                        st.rerun()
                    else:
                        st.error(sync_res.get("message"))

    with st.container(border=True):
        st.subheader("📱 Google Pixel 9a & Mobile Experience")
        st.write("Use this Co-Pilot on your smartphone (Google Pixel 9a, Android, or iOS) with a tailored Material You touch interface.")
        
        local_ip = get_local_ip()
        mobile_url = f"http://{local_ip}:8501"
        qr_img_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={mobile_url}"
        
        m_col1, m_col2 = st.columns([1.2, 2.8])
        with m_col1:
            st.markdown(f'<div style="text-align: center; background: white; padding: 12px; border-radius: 16px; border: 1px solid #E2E8F0; display: inline-block;"><img src="{qr_img_url}" width="160" height="160" alt="Pixel 9a QR Code" /><div style="font-size: 0.75rem; color: #64748B; margin-top: 6px; font-weight: 600;">Scan with Pixel 9a Camera</div></div>', unsafe_allow_html=True)
        with m_col2:
            st.markdown(f"#### 🌐 Mobile Web URL: `{mobile_url}`")
            st.write("1. **Connect:** Ensure your Google Pixel 9a is connected to the same Wi-Fi network.")
            st.write("2. **Open:** Scan the QR code with your camera or type the URL above into Google Chrome on your phone.")
            st.write("3. **Install as App (PWA):** In Chrome on your Pixel 9a, tap the 3 dots **(⋮)** ➡️ **'Install app'** (or **'Add to Home screen'**) for a native full-screen app experience!")
            st.write("4. **Pixel 9a Features Active:**")
            st.markdown("""
            - 🎯 **412px Viewport Optimization**: Card margins and typography scale to fit your 6.3\" Actua OLED screen without horizontal overflow.
            - 👆 **Tactile 44px+ Touch Targets**: Buttons and chips formatted as 2×2 mobile grids with instant haptic press visual response.
            - 📋 **1-Tap Mobile Clipboard**: Easily copy tailored cover letters and LinkedIn outreach notes directly to paste into the mobile LinkedIn or email apps.
            - ⚡ **Real-Time Remote Control**: Trigger desktop auto-pilot applications and monitor pipeline status directly from your phone.
            """)

    with st.container(border=True):
        st.subheader("🧹 Maintenance")
        if st.button("Clear Cached Jobs"):
            conn = db.get_db_connection()
            conn.cursor().execute("DELETE FROM jobs")
            conn.commit()
            conn.close()
            st.session_state.cached_jobs = []
            st.success("Job cache cleared!")
            st.rerun()
