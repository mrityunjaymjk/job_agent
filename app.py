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
importlib.reload(resume_parser)
import job_scraper
importlib.reload(job_scraper)
import matcher
importlib.reload(matcher)
import copilot
importlib.reload(copilot)
import auto_applicant
importlib.reload(auto_applicant)
import auto_hunter
importlib.reload(auto_hunter)

st.set_page_config(
    page_title="AI Job Application Co-Pilot",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Start background Auto-Hunter scheduler daemon if enabled
auto_hunter.ensure_hunter_daemon_running()

# PWA & iOS Safari Mobile Support (iPhone 13-18, Android & Modern WebKit)
st.markdown("""
<link rel="manifest" href="/app/static/manifest.json">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="JobAgent">
<meta name="format-detection" content="telephone=no">
<meta name="theme-color" content="#1E3A8A">
<link rel="apple-touch-icon" href="https://api.iconify.design/lucide:briefcase.svg?color=%231E3A8A">
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
    [data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child,
    [data-testid="stSidebar"] label[data-testid="stRadioOption"] div:has(+ [data-testid="stMarkdownContainer"]),
    [data-testid="stSidebar"] [class*="e1dm8mpf4"],
    [data-testid="stSidebar"] [class*="e1dm8mpf5"],
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

    /* ================= IPHONE (13-18 / PRO / MAX), GALAXY S24 & MOBILE UI ================= */
    html {
        scroll-behavior: smooth !important;
        -webkit-tap-highlight-color: transparent !important;
    }

    body, button, input, select, textarea {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased !important;
    }

    @media (max-width: 768px) {
        /* iOS Safe Area Insets for iPhone 13-18 (Notch & Dynamic Island) and Android */
        .block-container {
            padding-top: max(1.0rem, calc(env(safe-area-inset-top) + 0.35rem)) !important;
            padding-bottom: max(5.5rem, calc(env(safe-area-inset-bottom) + 4.5rem)) !important;
            padding-left: max(0.70rem, env(safe-area-inset-left)) !important;
            padding-right: max(0.70rem, env(safe-area-inset-right)) !important;
            max-width: 100vw !important;
        }

        /* Apple SF Pro & Modern responsive typography */
        .main-header {
            font-size: 1.40rem !important;
            line-height: 1.25 !important;
            letter-spacing: -0.35px !important;
            margin-bottom: 0.30rem !important;
            font-weight: 800 !important;
        }
        .sub-header {
            font-size: 0.85rem !important;
            line-height: 1.38 !important;
            margin-bottom: 0.85rem !important;
            color: #64748B !important;
        }

        /* Prevent auto-zooming on focus in iOS Safari & Mobile Chrome (requires >= 16px) */
        input, select, textarea, [data-baseweb="input"] input, [data-baseweb="select"] input {
            font-size: 16px !important;
            -webkit-appearance: none !important;
        }

        /* iOS Widget / Squircle Card Surfaces */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 20px !important;
            border: 1px solid #E2E8F0 !important;
            box-shadow: 0 3px 14px rgba(15, 23, 42, 0.04) !important;
            padding: 0.95rem 0.80rem !important;
            margin-bottom: 0.80rem !important;
            background: #FFFFFF !important;
        }

        /* Metrics: 2x2 grid on iPhone 13-18 & Galaxy S24 */
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 8px !important;
        }
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] {
            width: 100% !important;
            min-width: 0 !important;
            background: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 16px !important;
            padding: 8px 10px !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.30rem !important;
            font-weight: 800 !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.78rem !important;
        }

        /* Job card action buttons: 2x2 touch grid */
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"]:last-child {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 8px !important;
            margin-top: 10px !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"]:last-child > [data-testid="column"] {
            width: 100% !important;
            min-width: 0 !important;
        }

        /* Tactile touch buttons: 46px min height with iOS haptic active press */
        .stButton > button, 
        .stLinkButton > a {
            min-height: 46px !important;
            font-size: 0.90rem !important;
            font-weight: 600 !important;
            border-radius: 14px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            touch-action: manipulation !important;
            -webkit-tap-highlight-color: transparent !important;
            -webkit-touch-callout: none !important;
            user-select: none !important;
            transition: transform 0.12s cubic-bezier(0.2, 0, 0, 1), background-color 0.15s ease !important;
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
            min-width: 80px !important;
        }

        /* Quick-fill kit code blocks & chips: compact spacing */
        .stCodeBlock {
            border-radius: 14px !important;
            margin-bottom: 6px !important;
        }

        /* Skill chips comfortable on touchscreen */
        .skill-chip, .missing-chip {
            padding: 0.28rem 0.58rem !important;
            font-size: 0.78rem !important;
            border-radius: 8px !important;
            margin: 0.12rem !important;
        }

        /* Mobile: Sidebar Toggle Control hidden since bottom dock handles navigation */
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        button[aria-label="Expand sidebar"],
        button[aria-label="Collapse sidebar"],
        button[aria-controls="stSidebar"] {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }

        /* Drawer navigation items */
        [data-testid="stSidebar"] label[data-testid="stRadioOption"],
        [data-testid="stSidebar"] div[role="radiogroup"] > label {
            min-height: 48px !important;
            padding: 0.75rem 0.95rem !important;
            border-radius: 14px !important;
            font-size: 0.96rem !important;
        }

        /* Tab strip scrolling: native iOS momentum with hidden scrollbars */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            white-space: nowrap !important;
            -webkit-overflow-scrolling: touch !important;
            gap: 6px !important;
            padding-bottom: 4px !important;
            scrollbar-width: none !important;
            -ms-overflow-style: none !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {
            display: none !important;
        }
        [data-testid="stTabs"] button[role="tab"] {
            padding: 8px 14px !important;
            font-size: 0.85rem !important;
            border-radius: 12px 12px 0 0 !important;
        }
    }

    /* iPhone 13 mini / Small Screens (375px) */
    @media (max-width: 380px) {
        .block-container {
            padding-left: 0.50rem !important;
            padding-right: 0.50rem !important;
        }
        .main-header {
            font-size: 1.25rem !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.15rem !important;
        }
        .stButton > button, 
        .stLinkButton > a {
            font-size: 0.82rem !important;
            min-height: 42px !important;
            padding: 0 4px !important;
        }
    }

    /* iPhone 13, 14, 15, 16, 17, 18 Standard / Pro & Galaxy S24 (381px - 410px) */
    @media (min-width: 381px) and (max-width: 410px) {
        .main-header {
            font-size: 1.38rem !important;
        }
        .stButton > button, 
        .stLinkButton > a {
            min-height: 44px !important;
            font-size: 0.88rem !important;
        }
    }

    /* iPhone Plus & Pro Max / Galaxy S24+ & Ultra (411px - 440px) */
    @media (min-width: 411px) and (max-width: 768px) {
        .main-header {
            font-size: 1.48rem !important;
        }
    }

    /* Desktop: Hide Mobile Bottom Navigation Dock */
    @media (min-width: 769px) {
        .st-key-mobile_bottom_dock,
        .st-key-mob_nav_radio,
        div:has(> div > [data-testid="stHorizontalBlock"] button[key^="mob_btn_"]) {
            display: none !important;
        }
    }

    /* Mobile: Native Fixed Bottom Navigation Bar (Dock) */
    @media (max-width: 768px) {
        .block-container {
            padding-bottom: calc(96px + env(safe-area-inset-bottom, 0px)) !important;
        }

        .st-key-mobile_bottom_dock,
        .st-key-mob_nav_radio,
        div[class*="st-key-mobile_bottom_dock"] {
            display: block !important;
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100vw !important;
            max-width: 100vw !important;
            background: rgba(15, 23, 42, 0.96) !important;
            backdrop-filter: blur(24px) saturate(180%) !important;
            -webkit-backdrop-filter: blur(24px) saturate(180%) !important;
            border-top: 1px solid rgba(255, 255, 255, 0.14) !important;
            padding: 8px 10px calc(8px + env(safe-area-inset-bottom, 0px)) 10px !important;
            margin: 0 !important;
            z-index: 999999 !important;
            box-shadow: 0 -8px 28px rgba(0, 0, 0, 0.5) !important;
        }

        /* Strict single horizontal row flexbox for 5 tabs */
        .st-key-mob_nav_radio div[role="radiogroup"],
        .st-key-mobile_bottom_dock div[role="radiogroup"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            justify-content: space-around !important;
            width: 100% !important;
            max-width: 100% !important;
            gap: 6px !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* Each segment: 1/5th equal width, touch-friendly icon tab */
        .st-key-mob_nav_radio div[role="radiogroup"] > label,
        .st-key-mobile_bottom_dock div[role="radiogroup"] > label {
            flex: 1 1 0px !important;
            min-width: 0 !important;
            height: 48px !important;
            min-height: 48px !important;
            max-height: 48px !important;
            border-radius: 14px !important;
            background: rgba(30, 41, 59, 0.70) !important;
            border: 1px solid rgba(255, 255, 255, 0.10) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 !important;
            margin: 0 !important;
            cursor: pointer !important;
            transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1) !important;
            -webkit-tap-highlight-color: transparent !important;
        }

        /* Completely HIDE all radio circles, dots, toggle controls, and inputs inside dock */
        .st-key-mob_nav_radio [data-testid="stRadioOption"] > div > div:first-child,
        .st-key-mob_nav_radio [data-testid="stRadioOption"] > div > *:not([data-testid="stMarkdownContainer"]),
        .st-key-mob_nav_radio [data-testid="stRadioOption"] div:has(+ [data-testid="stMarkdownContainer"]),
        .st-key-mob_nav_radio [class*="e1dm8mpf4"],
        .st-key-mob_nav_radio [class*="e1dm8mpf5"],
        .st-key-mob_nav_radio label > div:not(:has([data-testid="stMarkdownContainer"])),
        .st-key-mob_nav_radio label > div:first-child:not(:has([data-testid="stMarkdownContainer"])),
        .st-key-mob_nav_radio label > div:not(:last-child),
        .st-key-mob_nav_radio label > span,
        .st-key-mob_nav_radio input,
        .st-key-mob_nav_radio input[type="radio"],
        .st-key-mob_nav_radio div[role="radiogroup"] input,
        .st-key-mob_nav_radio [data-baseweb="radio"] > div:first-child,
        .st-key-mob_nav_radio [data-baseweb="radio"] > div:first-of-type,
        .st-key-mob_nav_radio div[role="radiogroup"] > label > div:first-child,
        .st-key-mob_nav_radio div[role="radiogroup"] > label > div:first-of-type,
        .st-key-mob_nav_radio [data-testid="stRadioButtonCustom"],
        .st-key-mob_nav_radio svg,
        .st-key-mobile_bottom_dock [data-testid="stRadioOption"] > div > div:first-child,
        .st-key-mobile_bottom_dock [data-testid="stRadioOption"] > div > *:not([data-testid="stMarkdownContainer"]),
        .st-key-mobile_bottom_dock [class*="e1dm8mpf4"],
        .st-key-mobile_bottom_dock [class*="e1dm8mpf5"],
        .st-key-mobile_bottom_dock svg,
        .st-key-mobile_bottom_dock label > div:not(:has([data-testid="stMarkdownContainer"])),
        .st-key-mobile_bottom_dock input {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            opacity: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            pointer-events: none !important;
            position: absolute !important;
        }

        /* Ensure ONLY the markdown container holding the icon is visible and centered */
        .st-key-mob_nav_radio label [data-testid="stMarkdownContainer"],
        .st-key-mob_nav_radio [data-testid="stRadioOption"] > div,
        .st-key-mobile_bottom_dock label [data-testid="stMarkdownContainer"],
        .st-key-mobile_bottom_dock [data-testid="stRadioOption"] > div {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            text-align: center !important;
        }

        /* Hide top sidebar toggle controls on mobile */
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        button[aria-label="Expand sidebar"],
        button[aria-label="Collapse sidebar"],
        button[aria-controls="stSidebar"] {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }

        /* Clean font styling for the emoji icons */
        .st-key-mob_nav_radio div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p,
        .st-key-mobile_bottom_dock div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p {
            font-size: 1.50rem !important;
            line-height: 1 !important;
            margin: 0 !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        /* Active Selected Tab: Glowing Electric Blue pill */
        .st-key-mob_nav_radio div[role="radiogroup"] > label:has(input:checked),
        .st-key-mobile_bottom_dock div[role="radiogroup"] > label:has(input:checked) {
            background: linear-gradient(135deg, #1D4ED8 0%, #3B82F6 100%) !important;
            background-color: #2563EB !important;
            border: 1px solid #93C5FD !important;
            box-shadow: 0 0 16px rgba(59, 130, 246, 0.6), 0 2px 10px rgba(99, 102, 241, 0.4) !important;
            transform: translateY(-2px) !important;
        }

        .st-key-mob_nav_radio div[role="radiogroup"] > label:active,
        .st-key-mobile_bottom_dock div[role="radiogroup"] > label:active {
            transform: scale(0.92) !important;
        }

        /* Completely HIDE and REMOVE Streamlit Cloud Manage App button and viewer badge */
        [data-testid="manage-app-button"],
        div:has(> [data-testid="manage-app-button"]),
        div[class*="viewerBadge_container"],
        .viewerBadge_container,
        footer,
        header [data-testid="stToolbar"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
            height: 0 !important;
            width: 0 !important;
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
        
    # India / Pune / Local synonyms
    if pq in ["india", "in", "bharat"]:
        india_indicators = ["india", "pune", "bangalore", "bengaluru", "mumbai", "delhi", "new delhi", "noida", "gurgaon", "gurugram", "hyderabad", "chennai", "kolkata", "ahmedabad", "mh, india", "mh"]
        if any(ind in job_loc for ind in india_indicators):
            return True
        return False

    if pq in ["pune", "pun"]:
        if "pune" in job_loc or "pune" in job_title or "mh, india" in job_loc or "maharashtra" in job_loc:
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
NAV_OPTIONS = ["📄 Resume Profile", "🔍 Job Discovery", "⏰ Auto-Hunter", "🎯 Match & Co-Pilot", "📊 Application Tracker", "⚙️ Settings"]
NAV_ICONS = ["📄", "🔍", "⏰", "🎯", "📊", "⚙️"]

if "current_page" not in st.session_state or st.session_state.current_page not in NAV_OPTIONS:
    st.session_state.current_page = "📄 Resume Profile"

# Handle pending navigation redirect before the radio widget is instantiated
if "nav_redirect" in st.session_state:
    st.session_state.current_page = st.session_state.pop("nav_redirect")

# Synchronize session state keys with current_page before widgets render
curr_page = st.session_state.current_page
curr_icon = NAV_ICONS[NAV_OPTIONS.index(curr_page)]

if "sidebar_nav" not in st.session_state or st.session_state.sidebar_nav != curr_page:
    st.session_state.sidebar_nav = curr_page

if "mob_nav_radio" not in st.session_state or st.session_state.mob_nav_radio != curr_icon:
    st.session_state.mob_nav_radio = curr_icon

def _on_sidebar_nav_change():
    new_page = st.session_state.sidebar_nav
    st.session_state.current_page = new_page
    st.session_state.mob_nav_radio = NAV_ICONS[NAV_OPTIONS.index(new_page)]

def _on_mob_nav_change():
    icon = st.session_state.mob_nav_radio
    if icon in NAV_ICONS:
        new_page = NAV_OPTIONS[NAV_ICONS.index(icon)]
        st.session_state.current_page = new_page
        st.session_state.sidebar_nav = new_page

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
        <span style="background: rgba(255, 255, 255, 0.06); padding: 1px 7px; border-radius: 4px; font-size: 0.65rem; color: #94A3B8;">6 Modules</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.radio(
        "Navigation",
        NAV_OPTIONS,
        key="sidebar_nav",
        on_change=_on_sidebar_nav_change,
        label_visibility="collapsed"
    )
    
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
            
        loc_chip = f'<span style="background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.25); font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 6px;">📍 {active_resume.get("location")}</span>' if active_resume.get("location") else ''
        card_html = f"""<div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 14px; margin-top: 24px;">
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
<span style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #64748B;">Candidate Profile</span>
<span style="background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.65rem; font-weight: 700; padding: 2px 7px; border-radius: 9999px; display: flex; align-items: center; gap: 4px;">
<span style="width: 5px; height: 5px; border-radius: 50%; background: #10B981; display: inline-block;"></span> Active
</span>
</div>
<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
<div style="width: 38px; height: 38px; border-radius: 50%; background: linear-gradient(135deg, #6366F1 0%, #EC4899 100%); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem; color: #FFFFFF; box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3); flex-shrink: 0;">{initials}</div>
<div style="min-width: 0; flex: 1;">
<div style="font-size: 0.92rem; font-weight: 700; color: #F1F5F9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 4px;">
<span>{cand_name}</span>
<span style="color: #38BDF8; font-size: 0.82rem;" title="Verified Profile">✓</span>
</div>
<div style="font-size: 0.74rem; color: #94A3B8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{cand_email}</div>
</div>
</div>
<div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px;">
<span style="background: rgba(59, 130, 246, 0.12); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.25); font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 6px;">🛠️ {len(cand_skills)} Skills</span>
{loc_chip}
<span style="background: rgba(168, 85, 247, 0.12); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.25); font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 6px;">⚡ Auto-Fill Ready</span>
</div>
</div>"""
        st.markdown(card_html, unsafe_allow_html=True)
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

    # Mobile Sync Card
    local_ip = get_local_ip()
    mobile_url = f"http://{local_ip}:8501"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={mobile_url}"
    
    with st.expander("📱 Mobile Sync", expanded=False):
        st.markdown(f"""
        <div style="text-align: center; padding: 4px 0;">
            <div style="font-size: 0.78rem; font-weight: 700; color: #60A5FA; margin-bottom: 6px;">Scan with Phone Camera</div>
            <img src="{qr_url}" style="width: 130px; height: 130px; border-radius: 12px; background: white; padding: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);" />
            <div style="font-size: 0.72rem; color: #94A3B8; margin-top: 8px;">Or open on mobile:</div>
            <div style="font-size: 0.76rem; font-weight: 600; color: #38BDF8; word-break: break-all; margin-top: 2px;"><code>{mobile_url}</code></div>
            <div style="font-size: 0.68rem; color: #64748B; margin-top: 6px; line-height: 1.3;">In Chrome or Safari, tap ⋮ / Share ➡️ <i>Install app</i> (or <i>Add to Home</i>) for full-screen PWA!</div>
        </div>
        """, unsafe_allow_html=True)

# ================= MOBILE BOTTOM NAVIGATION DOCK =================
with st.container(key="mobile_bottom_dock"):
    st.radio(
        "Mobile Navigation",
        NAV_ICONS,
        key="mob_nav_radio",
        on_change=_on_mob_nav_change,
        horizontal=True,
        label_visibility="collapsed"
    )

page = st.session_state.current_page

# Clean Mobile UI & Hide Streamlit Cloud parent Manage app button via script
clean_ui_script = """
<script>
function cleanMobileUI() {
    try {
        var doc = window.parent.document;
        if (!doc) return;

        // 1. Hide Streamlit Cloud badges & manage button
        var btn = doc.querySelector('[data-testid="manage-app-button"]');
        if (btn) btn.style.display = 'none';
        var badge = doc.querySelector('[class*="viewerBadge_container"]');
        if (badge) badge.style.display = 'none';

        // 2. Hide Mobile Sidebar Expand/Collapse Toggle Controls
        var selectorsToHide = [
            '[data-testid="stExpandSidebarButton"]',
            '[data-testid="stSidebarCollapseButton"]',
            '[data-testid="stSidebarCollapsedControl"]',
            '[data-testid="collapsedControl"]',
            'button[aria-label="Expand sidebar"]',
            'button[aria-label="Collapse sidebar"]'
        ];
        selectorsToHide.forEach(function(sel) {
            doc.querySelectorAll(sel).forEach(function(el) {
                el.style.setProperty('display', 'none', 'important');
                el.style.setProperty('visibility', 'hidden', 'important');
            });
        });

        // 3. Remove/Hide all radio toggle circles beside dock menu icons
        var dockOptions = doc.querySelectorAll('.st-key-mob_nav_radio [data-testid="stRadioOption"], .st-key-mobile_bottom_dock [data-testid="stRadioOption"]');
        dockOptions.forEach(function(opt) {
            var allDivs = opt.querySelectorAll('div');
            allDivs.forEach(function(d) {
                var testId = d.getAttribute('data-testid');
                if (testId === 'stMarkdownContainer' || d.querySelector('[data-testid="stMarkdownContainer"]')) {
                    d.style.setProperty('display', 'flex', 'important');
                    d.style.setProperty('align-items', 'center', 'important');
                    d.style.setProperty('justify-content', 'center', 'important');
                } else if (d.children.length <= 1) {
                    d.style.setProperty('display', 'none', 'important');
                    d.style.setProperty('visibility', 'hidden', 'important');
                    d.style.setProperty('width', '0px', 'important');
                    d.style.setProperty('height', '0px', 'important');
                }
            });
        });

        // 4. Inject global stylesheet into parent document head
        var styleId = 'job-copilot-clean-dock-css';
        if (!doc.getElementById(styleId)) {
            var styleEl = doc.createElement('style');
            styleEl.id = styleId;
            styleEl.innerHTML = `
                [data-testid="stExpandSidebarButton"],
                [data-testid="stSidebarCollapseButton"],
                [data-testid="stSidebarCollapsedControl"],
                [data-testid="collapsedControl"],
                button[aria-label="Expand sidebar"],
                button[aria-label="Collapse sidebar"] {
                    display: none !important;
                    visibility: hidden !important;
                    width: 0 !important;
                    height: 0 !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                }
                .st-key-mob_nav_radio [data-testid="stRadioOption"] > div > div:first-child,
                .st-key-mob_nav_radio [data-testid="stRadioOption"] > div > *:not([data-testid="stMarkdownContainer"]),
                .st-key-mob_nav_radio [data-testid="stRadioOption"] div:has(+ [data-testid="stMarkdownContainer"]),
                .st-key-mob_nav_radio [class*="e1dm8mpf4"],
                .st-key-mob_nav_radio [class*="e1dm8mpf5"],
                .st-key-mobile_bottom_dock [data-testid="stRadioOption"] > div > div:first-child,
                .st-key-mobile_bottom_dock [data-testid="stRadioOption"] > div > *:not([data-testid="stMarkdownContainer"]),
                .st-key-mobile_bottom_dock [class*="e1dm8mpf4"],
                .st-key-mobile_bottom_dock [class*="e1dm8mpf5"] {
                    display: none !important;
                    visibility: hidden !important;
                    width: 0 !important;
                    height: 0 !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                    position: absolute !important;
                }
                .st-key-mob_nav_radio [data-testid="stMarkdownContainer"],
                .st-key-mobile_bottom_dock [data-testid="stMarkdownContainer"] {
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    width: 100% !important;
                    text-align: center !important;
                }
            `;
            doc.head.appendChild(styleEl);
        }
    } catch(e) {}
}

cleanMobileUI();
setTimeout(cleanMobileUI, 200);
setTimeout(cleanMobileUI, 600);
setTimeout(cleanMobileUI, 1200);
setTimeout(cleanMobileUI, 2500);

try {
    var targetNode = window.parent.document.body;
    var observer = new MutationObserver(function() {
        cleanMobileUI();
    });
    observer.observe(targetNode, { childList: true, subtree: true });
} catch(e) {}
</script>
"""
if hasattr(st, "iframe"):
    st.iframe(clean_ui_script, height=1, width=1)
else:
    import streamlit.components.v1 as components
    components.html(clean_ui_script, height=0, width=0)

# ================= PAGE 1: RESUME PROFILE =================
if page == "📄 Resume Profile":
    st.markdown('<div class="main-header">📄 Resume Hub & Profile</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upload your resume to automatically extract your skills, experience, and contact details.</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1.2, 1])
    
    with col1:
        st.subheader("Add or Update Resume")
        tab_upload, tab_paste = st.tabs(["📁 Upload Resume File", "📝 Paste Resume Text"])
        
        with tab_upload:
            uploaded_file = st.file_uploader(
                "Upload your PDF, DOCX, or TXT resume",
                type=["pdf", "docx", "txt"],
                help="Your resume will be parsed locally. Skills tables, contact info, and experience are extracted."
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
                                raw_text=parsed["raw_text"],
                                location=parsed.get("location", "")
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
                            raw_text=parsed["raw_text"],
                            location=parsed.get("location", "")
                        )
                        loc_msg = f" | 📍 {parsed['location']}" if parsed.get("location") else ""
                        st.success(f"Resume saved! Extracted {len(parsed['skills'])} skills{loc_msg}.")
                        st.rerun()

        with tab_paste:
            st.caption("Don't have the file handy? Simply paste your resume text below:")
            pasted_text = st.text_area(
                "Paste Resume Content",
                height=220,
                placeholder="Paste the full text of your resume here (including contact info, experience, skills list/table, and education)..."
            )
            if st.button("⚡ Parse & Save Pasted Resume", type="primary", use_container_width=True):
                if pasted_text.strip():
                    with st.spinner("Parsing resume details, skills, and sections..."):
                        if hasattr(resume_parser, "parse_resume_text"):
                            parsed = resume_parser.parse_resume_text(pasted_text.strip(), "Pasted Resume")
                        else:
                            import io
                            importlib.reload(resume_parser)
                            if hasattr(resume_parser, "parse_resume_text"):
                                parsed = resume_parser.parse_resume_text(pasted_text.strip(), "Pasted Resume")
                            else:
                                parsed = resume_parser.parse_resume(io.StringIO(pasted_text.strip()), "pasted_resume.txt")
                        res_id = db.save_resume(
                            name=parsed["name"],
                            email=parsed["email"],
                            phone=parsed["phone"],
                            skills=parsed["skills"],
                            experience=parsed["experience"],
                            education=parsed["education"],
                            raw_text=parsed["raw_text"],
                            location=parsed.get("location", "")
                        )
                        loc_msg = f" | 📍 {parsed['location']}" if parsed.get("location") else ""
                        st.success(f"Resume saved! Extracted {len(parsed['skills'])} skills{loc_msg}.")
                        st.rerun()
                else:
                    st.warning("Please paste your resume text before clicking parse.")

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
                
                loc_val = active.get("location", "") or db.get_setting("user_location", "")
                location_input = st.text_input("Location / City & Country", value=loc_val, help="Used for matching regional jobs and auto-filling application forms")
                
                skills_list = active.get("skills", [])
                st.write(f"**Extracted Skills ({len(skills_list)}):**")
                skills_chips = " ".join([f'<span class="skill-chip">{s}</span>' for s in skills_list])
                st.markdown(skills_chips, unsafe_allow_html=True)
                
                skills_edit = st.text_area(
                    "Edit Skills (comma separated)", 
                    value=", ".join(skills_list),
                    help="Add or remove specific skills to calibrate matching"
                )
                
                if st.button("Save Profile Changes"):
                    new_skills = [s.strip() for s in skills_edit.split(",") if s.strip()]
                    db.update_resume_profile(active["id"], name_input, email_input, phone_input, new_skills, location_input)
                    st.success("Profile updated!")
                    st.rerun()
        else:
            st.info("No active resume. Please upload one, paste text, or load the sample resume.")

    st.divider()
    st.subheader("⚙️ Default Application Answers")
    st.caption("These default values are used by the Co-Pilot to pre-fill common job application fields.")
    
    NOTICE_OPTIONS = [
        "Immediate (2 weeks)",
        "Immediate (Available Now)",
        "1 Month (30 days)",
        "2 Months (60 days)",
        "3 Months (90 days)",
        "Serving Notice Period",
        "Casual / Exploring"
    ]
    curr_notice = db.get_setting("notice_period", "Immediate (2 weeks)")
    if curr_notice not in NOTICE_OPTIONS:
        NOTICE_OPTIONS.insert(0, curr_notice)
    notice_idx = NOTICE_OPTIONS.index(curr_notice)

    WORK_AUTH_OPTIONS = [
        "Authorized to work without sponsorship",
        "Requires visa sponsorship",
        "US Citizen / Permanent Resident",
        "EU Citizen",
        "Other"
    ]
    curr_auth = db.get_setting("work_auth", WORK_AUTH_OPTIONS[0])
    if curr_auth not in WORK_AUTH_OPTIONS:
        WORK_AUTH_OPTIONS.append(curr_auth)
    auth_idx = WORK_AUTH_OPTIONS.index(curr_auth)

    links_pref = db.get_candidate_links(active_resume)
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        years_exp = st.text_input("Years of Experience", value=db.get_setting("years_exp", "4+ years"), key="ans_years_exp")
    with col_p2:
        expected_salary = st.text_input("Expected Salary / Rate", value=db.get_setting("expected_salary", "$110,000 - $140,000 / yr"), key="ans_expected_salary")
    with col_p3:
        notice_period = st.selectbox("Notice Period / Availability", NOTICE_OPTIONS, index=notice_idx, key="ans_notice_period")
        
    col_p4, col_p5, col_p6 = st.columns(3)
    with col_p4:
        work_auth = st.selectbox("Work Authorization", WORK_AUTH_OPTIONS, index=auth_idx, key="ans_work_auth")
    with col_p5:
        linkedin_url = st.text_input("LinkedIn Profile URL", value=links_pref.get("linkedin") or "https://linkedin.com/in/", key="ans_linkedin_url")
    with col_p6:
        github_url = st.text_input("GitHub Profile URL", value=links_pref.get("github") or "https://github.com/", key="ans_github_url")
        
    col_p7, col_p8 = st.columns([1.5, 1.5])
    with col_p7:
        portfolio_url = st.text_input("Portfolio / Website URL", value=links_pref.get("portfolio") or "", key="ans_portfolio_url", placeholder="https://myportfolio.dev")
    with col_p8:
        user_loc = st.text_input("Current Location", value=db.get_setting("user_location", active_resume.get("location", "Pune, India") if active_resume else "Pune, India"), key="ans_user_location")

    if st.button("Save Application Preferences", type="primary", key="btn_save_app_prefs"):
        db.set_setting("years_exp", years_exp.strip())
        db.set_setting("expected_salary", expected_salary.strip())
        db.set_setting("notice_period", notice_period)
        db.set_setting("work_auth", work_auth)
        db.set_setting("linkedin_url", linkedin_url.strip())
        db.set_setting("github_url", github_url.strip())
        db.set_setting("portfolio_url", portfolio_url.strip())
        db.set_setting("user_location", user_loc.strip())
        st.success("Application preferences & profile links saved successfully!")
        st.rerun()

# ================= PAGE 2: JOB DISCOVERY =================
elif page == "🔍 Job Discovery":
    st.markdown('<div class="main-header">🔍 Multi-Portal Job Discovery</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Fetch live on-site, hybrid, and remote openings from Naukri, Indeed, LinkedIn, Wellfound, and global feeds, scored against your ATS resume.</div>', unsafe_allow_html=True)
    
    active_resume = db.get_active_resume()
    all_stored_jobs = db.get_all_jobs()
    
    # Section 1: Collapsible Live Job Fetcher
    with st.expander("📥 Fetch New Live Jobs (Naukri, Indeed, LinkedIn, Wellfound, etc.)", expanded=True if not all_stored_jobs else False):
        st.caption("Download fresh openings across local on-site, hybrid, and remote positions directly into your local database.")
        
        cand_default_loc = db.get_setting("user_location", active_resume.get("location", "Pune, India") if active_resume else "Pune, India")
        
        col_s1, col_s2, col_s3 = st.columns([1.5, 1.2, 1.3])
        with col_s1:
            search_query = st.text_input("Role / Tech Stack Keyword", placeholder="e.g. Java, Python, Full Stack, React, DevOps, Spring Boot...", key="fetch_kw_input")
        with col_s2:
            fetch_location = st.text_input("Target Location (City / Country)", value=cand_default_loc, placeholder="e.g. Pune, Bangalore, Mumbai, Delhi, Remote, India, US...", key="fetch_loc_input")
        with col_s3:
            work_mode_choice = st.selectbox(
                "Work Arrangement",
                ["🌐 All Work Types (On-Site, Hybrid & Remote)", "🏢 On-Site (Office)", "🔀 Hybrid", "🏠 Remote Only"],
                key="fetch_work_mode"
            )
            mode_param = "All"
            if "Remote" in work_mode_choice:
                mode_param = "Remote"
            elif "Hybrid" in work_mode_choice:
                mode_param = "Hybrid"
            elif "On-Site" in work_mode_choice:
                mode_param = "On-Site"

        ALL_AVAILABLE_SOURCES = ["Naukri", "Indeed", "LinkedIn", "Wellfound", "Jobicy", "RemoteOK", "Remotive", "Arbeitnow", "WeWorkRemotely"]
        DEFAULT_ACTIVE_SOURCES = ["Naukri", "Indeed", "LinkedIn", "Wellfound", "Jobicy"]
        sources_selected = st.multiselect(
            "Select Platforms to Query:", 
            ALL_AVAILABLE_SOURCES, 
            default=DEFAULT_ACTIVE_SOURCES
        )
        if st.button("🚀 Download Fresh Jobs Now", type="primary", use_container_width=True):
            with st.spinner(f"Querying {len(sources_selected)} platforms for '{search_query or 'Tech'}' in {fetch_location}..."):
                fetched = job_scraper.fetch_all_jobs(
                    sources=sources_selected,
                    search_query=search_query,
                    location=fetch_location,
                    work_mode=mode_param,
                    limit_per_source=25
                )
                saved_count = db.save_jobs(fetched)
                st.session_state.cached_jobs = db.get_all_jobs()
                st.success(f"Fetched and added {len(fetched)} live jobs! ({saved_count} new/updated)")
                st.rerun()

    all_jobs = db.get_all_jobs()
    st.session_state.cached_jobs = all_jobs

    # Morning Auto-Hunter Digest Quick Banner
    h_quick_stats = db.get_hunter_stats()
    if h_quick_stats.get("queued_count", 0) > 0:
        with st.container(border=True):
            col_bn1, col_bn2 = st.columns([3.2, 1.2])
            with col_bn1:
                st.markdown(f'''
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem;">🌅</div>
                    <div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #38BDF8;">Morning Auto-Hunter Digest: {h_quick_stats['queued_count']} High-Match Positions Ready!</div>
                        <div style="font-size: 0.8rem; color: #94A3B8;">Top candidate positions matching up to <strong>{h_quick_stats['top_score']}% ATS score</strong> scouted across Naukri, LinkedIn, Indeed & Wellfound.</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            with col_bn2:
                if st.button("⏰ Open Morning Digest ➔", key="btn_goto_hunter_from_discovery", type="primary", use_container_width=True):
                    st.session_state.current_page = "⏰ Auto-Hunter"
                    st.rerun()

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

        col_p_label, col_p1, col_p2, col_p3, col_p4, col_p5, col_p6 = st.columns([0.8, 0.7, 1.1, 0.9, 1.2, 1.1, 1.0])
        with col_p_label:
            st.markdown('<div style="padding-top: 6px; font-size: 0.82rem; font-weight: 700; color: #64748B;">Quick Places:</div>', unsafe_allow_html=True)
        with col_p1:
            st.button("🌐 All", on_click=set_place_preset, args=("",), use_container_width=True, key="btn_loc_all")
        with col_p2:
            st.button("🇮🇳 India / Pune", on_click=set_place_preset, args=("Pune",), use_container_width=True, key="btn_loc_pune")
        with col_p3:
            st.button("🏠 Remote", on_click=set_place_preset, args=("Remote",), use_container_width=True, key="btn_loc_remote")
        with col_p4:
            st.button("🏢 US / Americas", on_click=set_place_preset, args=("United States",), use_container_width=True, key="btn_loc_us")
        with col_p5:
            st.button("🏰 Europe & UK", on_click=set_place_preset, args=("Europe",), use_container_width=True, key="btn_loc_eu")
        with col_p6:
            st.button("🌏 Asia & SG", on_click=set_place_preset, args=("Singapore",), use_container_width=True, key="btn_loc_asia")

        # Platform Multiselect Filter
        platform_options = ["Naukri", "Indeed", "LinkedIn", "Wellfound", "Jobicy", "RemoteOK", "Remotive", "Arbeitnow", "WeWorkRemotely"]
        existing_sources = sorted(list(set(j.get("source", "").strip() for j in all_jobs if j.get("source", "").strip())))
        combined_platforms = list(platform_options)
        for s in existing_sources:
            if s and s not in combined_platforms:
                combined_platforms.append(s)

        selected_platforms = st.multiselect(
            "🏷️ Filter by Platform (Select one or multiple):",
            options=combined_platforms,
            default=[],
            placeholder="Showing all platforms (Select one or multiple: Naukri, Indeed, LinkedIn...)",
            help="Filter jobs across multiple platforms simultaneously. Leave empty to view all platforms.",
            key="filter_source_multiselect"
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

            # Source / Platform check
            if selected_platforms:
                selected_sources_lower = [s.strip().lower() for s in selected_platforms]
                job_source_lower = str(j.get("source", "")).strip().lower()
                if job_source_lower not in selected_sources_lower:
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
                    if st.button(f"🚀 Auto-Apply", key=f"auto_{job['id']}", type="primary", use_container_width=True, help="Autonomous engine: auto-fills all steps and submits this application!"):
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

# ================= PAGE: AUTO-HUNTER & MORNING DIGEST =================
elif page == "⏰ Auto-Hunter":
    st.markdown('<div class="main-header">⏰ Daily Auto-Hunter & Morning Digest</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Hands-free scout that monitors Naukri, Indeed, LinkedIn, and Wellfound, pre-scores ATS compatibility (>80%), and queues positions for 1-click batch application.</div>', unsafe_allow_html=True)
    
    active_resume = db.get_active_resume()
    gemini_key = get_gemini_api_key()
    
    hunter_settings = auto_hunter.get_hunter_settings()
    hunter_stats = db.get_hunter_stats()
    daemon_status = auto_hunter.get_daemon_status()
    
    # Top Metrics Bar
    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🎯 High-Match Queue", f"{hunter_stats['queued_count']} Jobs", help="Positions discovered matching >= threshold ATS compatibility score")
        m2.metric("🚀 Auto-Applied", f"{hunter_stats['applied_count']} Jobs", help="Positions applied via autonomous batch engine")
        m3.metric("🌟 Top ATS Match", f"{hunter_stats['top_score']:.1f}%" if hunter_stats['top_score'] > 0 else "N/A", help="Highest ATS keyword alignment score in current queue")
        
        status_text = "🟢 Active" if daemon_status["scheduler_enabled"] else "⚪ Manual"
        sched_sub = f"Daily at {daemon_status['scheduled_time']}" if daemon_status["scheduler_enabled"] else "Trigger On-Demand"
        m4.metric("🤖 Background Scout", status_text, sched_sub)

    # Action Toolbar
    act_col1, act_col2, act_col3, act_col4 = st.columns([1.5, 1.8, 1.3, 1.0])
    
    with act_col1:
        run_now_clicked = st.button("⚡ Run Auto-Hunter Now", type="primary", use_container_width=True, help="Immediately crawls Naukri, Indeed, LinkedIn, and Wellfound for fresh matching jobs!")
    with act_col2:
        batch_apply_clicked = st.button("🚀 1-Click Auto-Apply (Top 3)", type="secondary", use_container_width=True, help="Autonomous engine applies to the top 3 high-match positions in queue using your tailored 1-page resume!")
    with act_col3:
        save_all_clicked = st.button("📥 Save All to Tracker", use_container_width=True, help="Imports all current high-matching queue items into Application Tracker under 'Saved'")
    with act_col4:
        clear_queue_clicked = st.button("🧹 Clear Queue", use_container_width=True, help="Removes all queued positions from Morning Digest")

    if run_now_clicked:
        with st.status("🔍 Auto-Hunter scouting platforms for fresh positions...", expanded=True) as status_box:
            st.write(f"1. 👤 Loading candidate profile and skills for **{active_resume.get('name', 'Candidate') if active_resume else 'Candidate'}**...")
            st.write(f"2. 🌐 Querying {len(hunter_settings['sources'])} job boards for '{hunter_settings['keywords']}' in '{hunter_settings['location']}'...")
            
            def _live_log(msg):
                st.write(f"• {msg}")

            hunt_res = auto_hunter.run_auto_hunt(
                search_query=hunter_settings["keywords"],
                location=hunter_settings["location"],
                sources=hunter_settings["sources"],
                work_mode=hunter_settings["work_mode"],
                min_match_score=hunter_settings["min_score"],
                progress_callback=_live_log
            )
            
            if hunt_res.get("success"):
                status_box.update(label=f"🎉 Auto-Hunt Complete: {hunt_res['new_found']} new jobs added, {hunt_res['high_matches']} high matches queued!", state="complete", expanded=False)
                st.balloons()
                st.rerun()
            else:
                status_box.update(label=f"⚠️ {hunt_res.get('error', 'Auto-hunt failed')}", state="error")

    if batch_apply_clicked:
        queued_items = db.get_hunter_queue(status="Queued")
        if not queued_items:
            st.warning("No jobs currently in queue! Click '⚡ Run Auto-Hunter Now' to discover high-matching positions first.")
        elif not active_resume:
            st.warning("Please upload a resume in the 'Resume Profile' tab first!")
        else:
            with st.status("🤖 Running Autonomous Batch Auto-Apply for Top Matches...", expanded=True) as batch_status:
                st.write(f"🚀 Initializing Playwright browser context & persistent cookie sessions...")
                
                def _batch_prog(curr, tot, msg):
                    st.write(f"[{curr}/{tot}] {msg}")
                    
                batch_res = auto_hunter.batch_auto_apply_queue(limit=3, api_key=gemini_key, progress_callback=_batch_prog)
                submitted_cnt = sum(1 for r in batch_res if r.get("submitted"))
                batch_status.update(label=f"✅ Batch application completed! {submitted_cnt}/{len(batch_res)} submitted successfully.", state="complete", expanded=False)
                st.balloons()
                st.rerun()

    if save_all_clicked:
        saved_c = auto_hunter.save_queue_jobs_to_tracker()
        st.success(f"📥 Saved {saved_c} positions into your Application Tracker under 'Saved'!")
        st.rerun()

    if clear_queue_clicked:
        db.clear_hunter_queue()
        st.toast("Auto-Hunter queue cleared.")
        st.rerun()

    # Main Tabs
    h_tab1, h_tab2, h_tab3 = st.tabs([
        f"🌅 Morning Digest Queue ({hunter_stats['queued_count']})",
        "⚙️ Hunter Config & Scheduling",
        "📜 Hunt Activity & Logs"
    ])

    with h_tab1:
        queued_jobs = db.get_hunter_queue(status="Queued")
        
        if not queued_jobs:
            st.markdown("""
            <div style="background: rgba(30, 41, 59, 0.5); border: 2px dashed rgba(148, 163, 184, 0.2); border-radius: 16px; padding: 40px 20px; text-align: center; margin: 20px 0;">
                <div style="font-size: 3rem; margin-bottom: 10px;">🌅</div>
                <div style="font-size: 1.2rem; font-weight: 700; color: #F8FAFC;">Morning Digest Queue is Empty</div>
                <div style="font-size: 0.88rem; color: #94A3B8; max-width: 500px; margin: 8px auto 20px; line-height: 1.5;">
                    The Auto-Hunter hasn't found new positions matching your criteria yet. Click below to trigger a live crawl across Naukri, LinkedIn, Indeed, and Wellfound right now!
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("⚡ Scan & Populate Morning Digest Now", type="primary", key="btn_scan_empty_digest"):
                with st.spinner("Scouting platforms for top matching jobs..."):
                    auto_hunter.run_auto_hunt(
                        search_query=hunter_settings["keywords"],
                        location=hunter_settings["location"],
                        sources=hunter_settings["sources"],
                        min_match_score=hunter_settings["min_score"]
                    )
                    st.rerun()
        else:
            c_filter1, c_filter2 = st.columns([2, 1])
            with c_filter1:
                st.caption(f"Showing **{len(queued_jobs)}** verified high-match positions sorted by ATS compatibility score.")
            with c_filter2:
                q_sort = st.selectbox("Sort By", ["Highest Match Score", "Most Recent"], key="hunter_q_sort")
            
            if q_sort == "Most Recent":
                queued_jobs = sorted(queued_jobs, key=lambda x: x.get("discovered_at", ""), reverse=True)
            else:
                queued_jobs = sorted(queued_jobs, key=lambda x: x.get("match_score", 0.0), reverse=True)

            for q_idx, q in enumerate(queued_jobs):
                q_id = q.get("job_id")
                score = q.get("match_score", 0.0)
                score_color = "#16A34A" if score >= 85 else ("#2563EB" if score >= 75 else "#D97706")
                score_bg = "rgba(22, 163, 74, 0.12)" if score >= 85 else ("rgba(37, 99, 235, 0.12)" if score >= 75 else "rgba(217, 119, 6, 0.12)")
                
                with st.container(border=True):
                    row1_left, row1_right = st.columns([2.5, 1.5])
                    with row1_left:
                        st.markdown(f"### {q.get('job_title')} @ **{q.get('company')}**")
                        st.markdown(f"📍 {q.get('location', 'Remote')} &nbsp;|&nbsp; 🏷️ **{q.get('source')}** &nbsp;|&nbsp; 🕒 Discovered: `{q.get('discovered_at', '')}`")
                    
                    with row1_right:
                        st.markdown(f"""
                        <div style="background: {score_bg}; border: 1px solid {score_color}; border-radius: 10px; padding: 8px 14px; text-align: center;">
                            <div style="font-size: 0.72rem; font-weight: 700; color: #94A3B8; text-transform: uppercase;">ATS Match Score</div>
                            <div style="font-size: 1.4rem; font-weight: 900; color: {score_color}; line-height: 1.1;">{score:.1f}%</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Skills breakdown
                    m_skills = q.get("matched_skills", [])
                    miss_skills = q.get("missing_skills", [])
                    if m_skills:
                        st.markdown("**✅ Matched ATS Skills:** " + " ".join([f'<span class="skill-chip">{s}</span>' for s in m_skills[:8]]), unsafe_allow_html=True)
                    if miss_skills:
                        st.caption("⚠️ Missing / Gap Skills: " + ", ".join(miss_skills[:5]))

                    st.divider()

                    # Action Buttons
                    btn1, btn2, btn3, btn4 = st.columns([1.5, 1.5, 1.5, 0.8])
                    with btn1:
                        if st.button("🚀 1-Click Auto-Apply", key=f"btn_apply_{q_id}", type="primary", use_container_width=True):
                            job_obj = db.get_job_by_id(q_id) or {
                                "id": q_id,
                                "title": q.get("job_title"),
                                "company": q.get("company"),
                                "location": q.get("location"),
                                "source": q.get("source"),
                                "apply_url": q.get("apply_url") or q.get("url", ""),
                                "description": f"{q.get('job_title')} at {q.get('company')}"
                            }
                            with st.status(f"🤖 Autonomous applying to {q.get('company')}...", expanded=True) as apply_stat:
                                res = auto_applicant.auto_apply_to_job(job_obj, active_resume, api_key=gemini_key, auto_submit=True, keep_open_seconds=60)
                                if res.get("submitted"):
                                    apply_stat.update(label="🎉 Application Verified & Submitted!", state="complete")
                                    db.update_hunter_queue_status(q_id, "Applied")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    apply_stat.update(label="⚠️ Application needs manual review on portal", state="complete")
                    
                    with btn2:
                        if st.button("🎯 Tailor Resume & Materials", key=f"btn_tailor_{q_id}", use_container_width=True):
                            job_obj = db.get_job_by_id(q_id) or {
                                "id": q_id,
                                "title": q.get("job_title"),
                                "company": q.get("company"),
                                "location": q.get("location"),
                                "source": q.get("source"),
                                "apply_url": q.get("apply_url") or q.get("url", ""),
                                "description": f"{q.get('job_title')} at {q.get('company')}"
                            }
                            st.session_state.selected_job = job_obj
                            st.session_state.nav_redirect = "🎯 Match & Co-Pilot"
                            st.rerun()

                    with btn3:
                        apply_url_val = q.get("apply_url") or q.get("url")
                        if apply_url_val:
                            st.link_button("🌐 Open Job Portal", apply_url_val, use_container_width=True)
                        else:
                            st.button("Saved", disabled=True, use_container_width=True)
                    
                    with btn4:
                        if st.button("❌", key=f"btn_dismiss_{q_id}", help="Dismiss from Morning Digest", use_container_width=True):
                            db.dismiss_hunter_queue_item(q_id)
                            st.toast(f"Dismissed {q.get('job_title')}")
                            st.rerun()

    with h_tab2:
        st.markdown("#### ⚙️ Configure Auto-Hunter Routine & Criteria")
        st.caption("Customize what positions the Morning Scout searches for and when it executes.")

        with st.form("hunter_config_form"):
            col_cfg1, col_cfg2 = st.columns(2)
            with col_cfg1:
                cfg_enabled = st.toggle("🤖 Enable Daily Automatic Morning Scouting", value=hunter_settings.get("enabled", False), help="When ON, the background daemon automatically checks job boards every morning at your specified time.")
                cfg_time = st.text_input("Daily Morning Scout Time (24h format HH:MM)", value=hunter_settings.get("schedule_time", "09:00"), help="e.g. 09:00 for 9 AM, 08:30 for 8:30 AM")
                cfg_query = st.text_input("Target Role / Tech Stack Keywords", value=hunter_settings.get("keywords", ""), help="e.g. Java Developer, Spring Boot, Microservices, Python, React...")
                cfg_loc = st.text_input("Target Location", value=hunter_settings.get("location", "Pune, India"), help="City, State, Country, or 'Remote'")
            
            with col_cfg2:
                work_mode_opts = ["All", "Remote", "Hybrid", "On-Site"]
                cur_wm = hunter_settings.get("work_mode", "All")
                wm_idx = work_mode_opts.index(cur_wm) if cur_wm in work_mode_opts else 0
                cfg_work_mode = st.selectbox("Work Mode Filter", work_mode_opts, index=wm_idx)
                cfg_min_score = st.slider("Minimum ATS Compatibility Score (%)", min_value=60, max_value=95, value=int(hunter_settings.get("min_score", 80)), step=5, help="Only jobs matching at or above this score are queued into your Morning Digest.")
                cfg_auto_apply = st.toggle("🚀 Auto-Apply Top Matches Automatically", value=hunter_settings.get("auto_apply", False), help="When enabled, the scout automatically submits applications to the top 3 high matches each morning without waiting for manual confirmation!")

            st.markdown("##### Platforms to Search:")
            ALL_HUNTER_SOURCES = ["Naukri", "Indeed", "LinkedIn", "Wellfound", "Jobicy", "RemoteOK", "Remotive", "Arbeitnow"]
            cfg_sources = st.multiselect(
                "Select Search Platforms",
                options=ALL_HUNTER_SOURCES,
                default=[s for s in hunter_settings.get("sources", auto_hunter.DEFAULT_SOURCES) if s in ALL_HUNTER_SOURCES],
                label_visibility="collapsed"
            )

            save_cfg_btn = st.form_submit_button("💾 Save Auto-Hunter Settings", type="primary", use_container_width=True)
            if save_cfg_btn:
                auto_hunter.save_hunter_settings({
                    "enabled": cfg_enabled,
                    "schedule_time": cfg_time.strip() or "09:00",
                    "keywords": cfg_query.strip(),
                    "location": cfg_loc.strip(),
                    "work_mode": cfg_work_mode,
                    "min_score": float(cfg_min_score),
                    "sources": cfg_sources if cfg_sources else ALL_HUNTER_SOURCES,
                    "auto_apply": cfg_auto_apply
                })
                auto_hunter.ensure_hunter_daemon_running()
                st.success("✅ Auto-Hunter settings saved and background daemon updated!")
                st.rerun()

    with h_tab3:
        st.markdown("#### 📜 Auto-Hunter Execution History")
        st.caption("Logs of recent background and manual hunting runs.")
        
        runs = db.get_hunter_runs(limit=15)
        if not runs:
            st.info("No hunter runs recorded yet. Click '⚡ Run Auto-Hunter Now' above to perform your first hunt!")
        else:
            df_runs = pd.DataFrame(runs)
            cols_needed = ["run_time", "query", "location", "total_scanned", "new_found", "high_matches_found", "status"]
            for col in cols_needed:
                if col not in df_runs.columns:
                    df_runs[col] = ""
            df_display = df_runs[cols_needed].copy()
            df_display.columns = ["Timestamp", "Keywords", "Location", "Scanned", "New Added", "High Matches", "Status"]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            with st.expander("🔍 View Detailed Notes for Recent Runs"):
                for r in runs[:5]:
                    st.markdown(f"**Run #{r['id']} ({r['run_time']})** — `{r.get('sources', '')}`")
                    st.write(f"• Query: `{r['query']}` | Location: `{r['location']}`")
                    st.write(f"• Summary: {r.get('summary_notes', 'Completed')}")
                    st.divider()


# ================= PAGE 3: MATCH & CO-PILOT =================
elif page == "🎯 Match & Co-Pilot":
    st.markdown('<div class="main-header">🎯 Application Match & Co-Pilot</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Deep ATS alignment, custom cover letters, tailored bullet points, and 1-click application prep.</div>', unsafe_allow_html=True)
    
    active_resume = db.get_active_resume()
    all_jobs = db.get_all_jobs()
    applications = db.get_applications()

    # Build Applied / In-Tracker job options
    applied_job_options = {}
    for a in applications:
        jid = a.get("job_id")
        job = db.get_job_by_id(jid) if jid else None
        if not job:
            job = {
                "id": jid or f"app_{a['id']}",
                "title": a.get("job_title", "Software Engineer"),
                "company": a.get("company", "Company"),
                "location": "Remote / On-site",
                "source": "Application Tracker",
                "url": a.get("apply_url", ""),
                "apply_url": a.get("apply_url", ""),
                "description": a.get("notes", "") or f"{a.get('job_title')} at {a.get('company')}",
                "salary": "Salary Not Disclosed",
                "tags": []
            }
        else:
            job = dict(job)
        job["application_status"] = a.get("status", "Applied")
        job["applied_date"] = a.get("applied_date", "")
        job["app_id"] = a.get("id")

        stat = a.get("status", "Applied")
        dt = f" • {a.get('applied_date')}" if a.get("applied_date") else ""
        lbl = f"🏢 {a.get('company')} — {a.get('job_title')}  [{stat}{dt}]"
        if lbl in applied_job_options:
            lbl = f"{lbl} (#{a['id']})"
        applied_job_options[lbl] = job

    # Build All Discovered Jobs options
    discovered_job_options = {}
    for j in all_jobs:
        j_copy = dict(j)
        lbl = f"🏢 {j.get('company')} — {j.get('title')}  ({j.get('source', 'Web')})"
        if lbl in discovered_job_options:
            lbl = f"{lbl} (#{j['id']})"
        discovered_job_options[lbl] = j_copy

    current_job = st.session_state.get("selected_job")

    # Match current_job in applied jobs
    is_current_in_applied = False
    applied_match_idx = 0
    if current_job and applied_job_options:
        cur_id = str(current_job.get("id", ""))
        cur_key = (str(current_job.get("title", "")).strip().lower(), str(current_job.get("company", "")).strip().lower())
        for idx, (lbl, j) in enumerate(applied_job_options.items()):
            if (cur_id and str(j.get("id")) == cur_id) or (cur_key[0] and cur_key[1] and (str(j.get("title")).strip().lower(), str(j.get("company")).strip().lower()) == cur_key):
                is_current_in_applied = True
                applied_match_idx = idx
                break

    # Match current_job in discovered jobs
    discovered_match_idx = 0
    if current_job and discovered_job_options:
        cur_id = str(current_job.get("id", ""))
        cur_key = (str(current_job.get("title", "")).strip().lower(), str(current_job.get("company", "")).strip().lower())
        for idx, (lbl, j) in enumerate(discovered_job_options.items()):
            if (cur_id and str(j.get("id")) == cur_id) or (cur_key[0] and cur_key[1] and (str(j.get("title")).strip().lower(), str(j.get("company")).strip().lower()) == cur_key):
                discovered_match_idx = idx
                break

    # Build source options
    source_options = []
    if applied_job_options:
        source_options.append(f"📋 Jobs Applied / In Tracker ({len(applied_job_options)})")
    if discovered_job_options:
        source_options.append(f"🔍 All Discovered Jobs ({len(discovered_job_options)})")
    if not source_options:
        source_options = ["🔍 No Jobs Available"]

    # Synchronize external navigation / initial selection
    cur_job_id_str = str(current_job.get("id", "")) if current_job else ""
    if st.session_state.get("last_synced_copilot_job_id") != cur_job_id_str:
        st.session_state["last_synced_copilot_job_id"] = cur_job_id_str
        if is_current_in_applied and source_options:
            st.session_state["copilot_source_choice"] = source_options[0]
        elif not is_current_in_applied and len(source_options) > 1:
            st.session_state["copilot_source_choice"] = source_options[1]

    # Render Prominent Job Selector Dropdown Card
    with st.container(border=True):
        c_mode, c_dropdown = st.columns([1.1, 2.9])
        with c_mode:
            st.markdown("<div style='font-size: 0.82rem; font-weight: 700; color: #38BDF8; margin-bottom: 2px;'>📂 SELECT FROM:</div>", unsafe_allow_html=True)
            chosen_source = st.radio(
                "Filter Source",
                options=source_options,
                key="copilot_source_choice",
                label_visibility="collapsed"
            )
        
        with c_dropdown:
            if "Applied" in chosen_source and applied_job_options:
                st.markdown("<div style='font-size: 0.82rem; font-weight: 700; color: #38BDF8; margin-bottom: 2px;'>🎯 CHOOSE APPLIED JOB TO TAILOR ATS RESUME & OUTREACH:</div>", unsafe_allow_html=True)
                sel_lbl = st.selectbox(
                    "Select Applied Job",
                    options=list(applied_job_options.keys()),
                    index=applied_match_idx if applied_match_idx < len(applied_job_options) else 0,
                    key="copilot_applied_job_select",
                    label_visibility="collapsed"
                )
                target_job = applied_job_options[sel_lbl]
                st.session_state.selected_job = target_job
            elif "Discovered" in chosen_source and discovered_job_options:
                st.markdown("<div style='font-size: 0.82rem; font-weight: 700; color: #38BDF8; margin-bottom: 2px;'>🎯 CHOOSE DISCOVERED JOB TO TAILOR & APPLY:</div>", unsafe_allow_html=True)
                sel_lbl = st.selectbox(
                    "Select Discovered Job",
                    options=list(discovered_job_options.keys()),
                    index=discovered_match_idx if discovered_match_idx < len(discovered_job_options) else 0,
                    key="copilot_discovered_job_select",
                    label_visibility="collapsed"
                )
                target_job = discovered_job_options[sel_lbl]
                st.session_state.selected_job = target_job
            elif current_job:
                target_job = current_job
            else:
                target_job = None

    # Reset any job-specific input widgets when switching to a different job
    cur_selected_id = str(target_job.get("id", "")) if target_job else ""
    if st.session_state.get("active_copilot_job_id") != cur_selected_id:
        for k in ["cold_mail_recipient", "cold_mail_subj", "cold_mail_body", "cold_mail_contact_name"]:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state.active_copilot_job_id = cur_selected_id

    if not active_resume:
        st.warning("⚠️ Please upload or load a resume in the 'Resume Profile' tab first!")
    elif not target_job:
        st.info("ℹ️ Please select a job from the dropdown above or from 'Job Discovery' to begin tailoring!")
    else:
        # Job Overview Header
        with st.container(border=True):
            j_col1, j_col2 = st.columns([2.3, 1.7])
            with j_col1:
                st.markdown(f"## {target_job['title']} @ **{target_job['company']}**")
                st.write(f"📍 {target_job.get('location', 'Remote')} &nbsp;|&nbsp; 🏷️ {target_job.get('source')} &nbsp;|&nbsp; 💰 {target_job.get('salary', 'Salary Not Disclosed')}")
                
                existing_app = db.get_application_by_job_id(target_job.get('id', ''))
                if existing_app:
                    app_status = existing_app.get('status', 'Applied')
                    app_date = existing_app.get('applied_date', '')
                    date_str = f" • Applied on: {app_date}" if app_date else ""
                    status_bg = "#DCFCE7" if app_status == "Applied" else ("#FEF3C7" if app_status == "Needs Review" else "#DBEAFE")
                    status_color = "#166534" if app_status == "Applied" else ("#92400E" if app_status == "Needs Review" else "#1E40AF")
                    st.markdown(
                        f'<div style="background:{status_bg}; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; padding: 3px 8px; display: inline-block; font-size: 0.82rem; font-weight: 600; color:{status_color}; margin-top: 3px; margin-bottom: 6px;">'
                        f'📋 Application Tracker: <strong>{app_status}</strong>{date_str}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                prof_stat = auto_applicant.get_profile_status()
                cookie_cnt = prof_stat.get("total_cookies", 0)
                st.markdown(f'<div style="font-size: 0.8rem; color: #16A34A; font-weight: 600;">🍪 Persistent Cache Active &nbsp;•&nbsp; {cookie_cnt} saved session cookies &nbsp;•&nbsp; Auto-login enabled</div>', unsafe_allow_html=True)
            with j_col2:
                auto_mode = st.toggle("🚀 Autonomous Mode (Auto-Submits)", value=True, help="When ON, the bot fills all steps, answers screening questions, checks terms, and clicks Submit Application for you automatically!")
                if auto_mode:
                    auto_pilot_clicked = st.button("🚀 Run Autonomous Auto-Apply", type="primary", use_container_width=True, help="Autonomous engine: opens portal, fills all wizard steps, and clicks Submit Application automatically!")
                else:
                    auto_pilot_clicked = st.button("👀 Co-Pilot Assist (Pre-fill & Review)", type="secondary", use_container_width=True, help="Pre-fills your information and leaves browser open for manual review and submission.")
                
                apply_url = target_job.get('apply_url') or target_job.get('url')
                if apply_url:
                    st.link_button("🌐 Open Job Link", apply_url, use_container_width=True)

        if st.session_state.get("trigger_auto_apply"):
            auto_pilot_clicked = True
            st.session_state.trigger_auto_apply = False

        if auto_pilot_clicked:
            gemini_key = get_gemini_api_key()
            mode_label = "Autonomous Auto-Apply (Auto-Submit Enabled)" if auto_mode else "Co-Pilot Assist (Pre-Fill & Review)"
            with st.status(f"🤖 Running {mode_label}...", expanded=True) as status:
                st.write("1. ✍️ Tailoring cover letter specifically for this job...")
                st.write("2. 🍪 Loading persistent browser profile & cache memory (saved logins active)...")
                st.write("3. 🖥️ Launching browser context...")
                st.write("4. 📝 Auto-filling multi-step form, answering screening questions & attaching resume...")
                if auto_mode:
                    st.write("5. 🚀 Executing 'Submit Application' and verifying submission confirmation...")
                else:
                    st.write("5. 👀 Form pre-filled! Browser opened for your manual review.")

                result = auto_applicant.auto_apply_to_job(
                    job_data=target_job,
                    resume_data=active_resume,
                    api_key=gemini_key,
                    auto_submit=auto_mode,
                    keep_open_seconds=90
                )
                if result.get("submitted"):
                    status.update(label="🎉 Application Verified & Submitted!", state="complete", expanded=False)
                else:
                    status.update(label="⚠️ Application Needs Review (Confirmation Not Detected)", state="complete", expanded=False)
            
            with st.expander("📋 View Auto-Apply Session Activity Logs", expanded=True):
                for l in result.get("logs", []):
                    st.write(f"- {l}")

            cand_email = active_resume.get("email") or "mrityunjayk456@gmail.com"
            if result.get("submitted"):
                st.balloons()
                st.success(f"🎉 Application Submitted & Confirmed! The platform will send an automated revert/confirmation email to **{cand_email}**.")
                if result.get("screenshot") and os.path.exists(result["screenshot"]):
                    st.image(result["screenshot"], caption="📸 Submission Confirmation Proof", use_container_width=True)
            else:
                st.warning(f"⚠️ Application form was opened, but final platform confirmation receipt was not detected. Status is marked as **Needs Review** in your Application Tracker to prevent false applications. Revert emails are only sent by platforms once submission is confirmed.")
        
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
                links_kit = db.get_candidate_links(active_resume)
                st.caption("🔗 LinkedIn URL")
                st.code(links_kit.get("linkedin") or "https://linkedin.com/in/", language=None)
                st.caption("💻 GitHub URL")
                st.code(links_kit.get("github") or "https://github.com/", language=None)
                st.caption("🌐 Portfolio / Website")
                pf_display = links_kit.get("portfolio")
                if not pf_display or pf_display == links_kit.get("github"):
                    pf_display = links_kit.get("github") or "https://portfolio.dev"
                st.code(pf_display, language=None)
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
        tool_tab0, tool_tab1, tool_tab2, tool_tab3, tool_tab4, tool_tab5, tool_tab6, tool_tab7 = st.tabs([
            "📄 Tailored ATS Resume (1-Page)",
            "📧 Cold Mail HRs & Recruiters",
            "✍️ Tailored Cover Letter", 
            "📝 Optimized Bullet Points", 
            "💬 LinkedIn Direct Messages",
            "📋 Quick-Fill Form Answers",
            "🎯 Interview Prep Cheat Sheet",
            "💰 Salary Intelligence Advisor"
        ])

        with tool_tab0:
            st.markdown(f"#### 📄 Executive 1-Page ATS Resume for **{target_job['title']}** at **{target_job['company']}**")
            st.caption("Custom-engineered single-page resume with categorized skills, role-targeted summary, and clean alignment. Automatically attached during Auto-Apply on Indeed, LinkedIn, Greenhouse, and Lever!")

            tailored_res_files = auto_applicant.generate_tailored_resume_files(active_resume, target_job, api_key=gemini_key)
            
            c_res_info, c_res_dl = st.columns([2.5, 1.5])
            with c_res_info:
                st.markdown(f"**🎯 Target Role Headline:** `{tailored_res_files.get('headline', '')}`")
                st.markdown("**📝 Tailored Professional Summary:**")
                st.info(tailored_res_files.get("summary", ""))
                
                match_skills = tailored_res_files.get("matching_skills", [])
                if match_skills:
                    st.write("**✅ Highlighted ATS Keywords:**")
                    st.markdown(" ".join([f'<span class="skill-chip">{s}</span>' for s in match_skills]), unsafe_allow_html=True)
                    
            with c_res_dl:
                st.write("")
                st.markdown('<div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 0.85rem; color: #166534;">⚡ <strong>Auto-Attach Active:</strong><br>Guaranteed 1-Page Format. Automatically attached when you auto-apply.</div>', unsafe_allow_html=True)
                
                pdf_p = Path(tailored_res_files.get("pdf", ""))
                if pdf_p.exists():
                    with open(pdf_p, "rb") as f_pdf:
                        st.download_button(
                            label="📥 Download Executive Resume (.PDF)",
                            data=f_pdf.read(),
                            file_name=pdf_p.name,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
                        
                docx_p = Path(tailored_res_files.get("docx", ""))
                if docx_p.exists():
                    with open(docx_p, "rb") as f_docx:
                        st.download_button(
                            label="📥 Download Editable Resume (.DOCX)",
                            data=f_docx.read(),
                            file_name=docx_p.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )

            with st.expander("👀 View Full Tailored Plaintext Resume", expanded=False):
                txt_p = Path(tailored_res_files.get("txt", ""))
                if txt_p.exists():
                    with open(txt_p, "r", encoding="utf-8") as f_txt:
                        st.code(f_txt.read(), language=None)

        with tool_tab1:
            st.markdown(f"#### 📧 Cold Email HRs & Decision Makers at **{target_job['company']}**")
            st.caption(f"Directly pitch the Hiring Team, Technical Recruiters, or Engineering Managers at **{target_job['company']}** to bypass automated application portals.")

            c_find1, c_find2 = st.columns([1.5, 2.5])
            with c_find1:
                st.markdown("##### 1️⃣ Target Decision Maker")
                recruiter_targets = copilot.get_recruiter_targets(target_job['company'], target_job['title'])
                target_persona = st.selectbox(
                    "Select Target Persona",
                    [t["persona"] for t in recruiter_targets],
                    index=0,
                    key="cold_mail_persona"
                )
                contact_name = st.text_input("HR / Recruiter Name (Optional)", placeholder="e.g. Sarah or Alex", key="cold_mail_contact_name")
                
                email_style_label = st.selectbox(
                    "Email Pitch Framework",
                    [
                        "🎯 High-Impact 3-Paragraph Pitch (Proven 45%+ Response Rate)",
                        "💻 Technical Deep-Dive & Projects Alignment (Java / Spring Boot)",
                        "☕ Short & Sweet 3-Sentence Coffee Chat",
                        "🔄 Day 4 Polite Follow-Up Bump"
                    ],
                    index=0,
                    key="cold_mail_style"
                )
                style_key = "high_impact"
                if "Technical" in email_style_label: style_key = "technical"
                elif "Short" in email_style_label: style_key = "short"
                elif "Follow-Up" in email_style_label: style_key = "followup"

            with c_find2:
                st.markdown("##### 2️⃣ Recruiter Search Links & Email Prediction")
                curr_target = next(t for t in recruiter_targets if t["persona"] == target_persona)
                st.info(f"💡 **Strategy:** {curr_target['tip']}", icon="💡")
                
                c_lk1, c_lk2 = st.columns(2)
                with c_lk1:
                    st.link_button("🔎 Search HRs on LinkedIn", curr_target['linkedin_url'], use_container_width=True)
                with c_lk2:
                    st.link_button("🌐 Google X-Ray Search", curr_target['xray_url'], use_container_width=True)

                cold_data = copilot.generate_cold_email(
                    resume_data=active_resume,
                    job_data=target_job,
                    contact_name=contact_name,
                    email_style=style_key,
                    api_key=gemini_key
                )
                
                hr_email_input = st.text_input(
                    "Recipient HR / Recruiter Email Address:",
                    value=cold_data["primary_email"],
                    help="Predicted corporate email address. You can edit this with the recruiter's exact email.",
                    key="cold_mail_recipient"
                )
                st.caption(f"Predicted patterns: `{', '.join(cold_data['suggested_emails'][:3])}`")

            st.divider()

            st.markdown("##### 3️⃣ Composed Cold Email Pitch")
            email_subject = st.text_input("Subject Line:", value=cold_data["subject"], key="cold_mail_subj")
            email_body = st.text_area("Email Body (Editable):", value=cold_data["body"], height=280, key="cold_mail_body")

            import urllib.parse
            encoded_to = urllib.parse.quote(hr_email_input.strip())
            encoded_su = urllib.parse.quote(email_subject.strip())
            encoded_body = urllib.parse.quote(email_body.strip())

            gmail_web_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={encoded_to}&su={encoded_su}&body={encoded_body}"
            mailto_desktop_url = f"mailto:{encoded_to}?subject={encoded_su}&body={encoded_body}"

            col_send1, col_send2, col_send3 = st.columns([1.5, 1.5, 1.2])
            with col_send1:
                st.link_button("🚀 Open in Gmail (Auto-Composed)", gmail_web_url, type="primary", use_container_width=True, help="Opens Gmail in browser with recipient, subject, and tailored body pre-filled!")
            with col_send2:
                st.link_button("📧 Open in Outlook / Mail Client", mailto_desktop_url, use_container_width=True, help="Opens default mail client with pre-filled content.")
            with col_send3:
                st.download_button(
                    "📥 Copy / Download Pitch (.txt)",
                    data=f"To: {hr_email_input}\nSubject: {email_subject}\n\n{email_body}",
                    file_name=f"Cold_Email_{target_job['company']}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
        
        with tool_tab2:
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

        with tool_tab3:
            st.write("Customize your resume achievements specifically targeting this position:")
            if st.button("⚡ Generate Tailored Resume Bullets"):
                with st.spinner("Generating impact bullets..."):
                    bullets = copilot.generate_tailored_bullets(active_resume, target_job, api_key=gemini_key)
                    for b in bullets:
                        st.markdown(f"- {b}")
            else:
                st.caption("Click the button above to generate 3 tailored accomplishment statements.")

        with tool_tab4:
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

        with tool_tab5:
            st.write("Copy-paste ready answers for typical company application portals (Workday, Greenhouse, Lever):")
            links_ans = db.get_candidate_links(active_resume)
            user_prefs = {
                "years_exp": db.get_setting("years_exp", "4+ years"),
                "expected_salary": db.get_setting("expected_salary", "$120,000 / yr"),
                "work_auth": db.get_setting("work_auth", "Authorized to work without sponsorship"),
                "notice_period": db.get_setting("notice_period", "Immediate (2 weeks)"),
                "linkedin_url": links_ans.get("linkedin", ""),
                "github_url": links_ans.get("github", ""),
                "portfolio_url": links_ans.get("portfolio", "") or links_ans.get("github", "")
            }
            form_answers = copilot.generate_application_answers(active_resume, target_job, user_prefs)
            for q, a in form_answers.items():
                with st.expander(f"**{q}**", expanded=True):
                    st.code(a, language=None)

        with tool_tab6:
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

        with tool_tab7:
            st.markdown("#### 💰 Salary Intelligence & Compensation Advisor")
            st.caption(f"Real-time compensation benchmark and application negotiation guidance for **{target_job['title']}** at **{target_job['company']}**.")
            
            links_sal = db.get_candidate_links(active_resume)
            user_prefs_dict = {
                "years_exp": db.get_setting("years_exp", "4+ years"),
                "expected_salary": db.get_setting("expected_salary", "$120,000 / yr"),
                "work_auth": db.get_setting("work_auth", "Authorized to work without sponsorship"),
                "notice_period": db.get_setting("notice_period", "Immediate (2 weeks)"),
                "linkedin_url": links_sal.get("linkedin", ""),
                "github_url": links_sal.get("github", ""),
                "portfolio_url": links_sal.get("portfolio", "") or links_sal.get("github", "")
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
        status_tabs = st.tabs(["All", "Saved", "Applied", "Needs Review", "Interviewing", "Offer", "Rejected"])
        tab_names = ["All", "Saved", "Applied", "Needs Review", "Interviewing", "Offer", "Rejected"]
        
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
        
        links_cfg = db.get_candidate_links()
        c_set1, c_set2 = st.columns(2)
        with c_set1:
            cfg_li = st.text_input("LinkedIn Profile URL", value=links_cfg.get("linkedin") or "https://linkedin.com/in/", key="cfg_li")
            cfg_gh = st.text_input("GitHub Profile URL", value=links_cfg.get("github") or "https://github.com/", key="cfg_gh")
            cfg_pf = st.text_input("Portfolio / Website URL", value=links_cfg.get("portfolio") or "", key="cfg_pf")
            cfg_loc = st.text_input("Current Location", value=db.get_setting("user_location", "Remote / Worldwide"), key="cfg_loc")
            
        with c_set2:
            cfg_exp = st.text_input("Years of Experience", value=db.get_setting("years_exp", "4+ years"), key="cfg_exp")
            cfg_sal = st.text_input("Expected Salary / Rate", value=db.get_setting("expected_salary", "$130,000 / yr (Flexible)"), key="cfg_sal")
            cfg_auth = st.text_input("Work Authorization", value=db.get_setting("work_auth", "Authorized to work without sponsorship"), key="cfg_auth")
            notice_set_opts = ["Immediate (2 weeks)", "Immediate (Available Now)", "1 Month (30 days)", "2 Months (60 days)", "3 Months (90 days)", "Serving Notice Period", "Casual / Exploring"]
            curr_set_not = db.get_setting("notice_period", "Immediate (2 weeks)")
            if curr_set_not not in notice_set_opts:
                notice_set_opts.insert(0, curr_set_not)
            cfg_not = st.selectbox("Notice Period / Availability", notice_set_opts, index=notice_set_opts.index(curr_set_not), key="cfg_not")
            
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
                    "Indeed (https://secure.indeed.com)",
                    "Naukri (https://www.naukri.com/nlogin/login)",
                    "Google Account (https://accounts.google.com)",
                    "Wellfound / AngelList (https://wellfound.com/login)",
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
        st.subheader("📱 Mobile Sync & App Experience")
        st.write("Use this Co-Pilot on any smartphone (**iPhone 13–18 / Pro / Max**, **Samsung Galaxy**, **Google Pixel**, Android, or iOS) with a tailored touch interface.")
        
        local_ip = get_local_ip()
        mobile_url = f"http://{local_ip}:8501"
        qr_img_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={mobile_url}"
        
        m_col1, m_col2 = st.columns([1.2, 2.8])
        with m_col1:
            st.markdown(f'<div style="text-align: center; background: white; padding: 12px; border-radius: 16px; border: 1px solid #E2E8F0; display: inline-block;"><img src="{qr_img_url}" width="160" height="160" alt="Mobile QR Code" /><div style="font-size: 0.75rem; color: #64748B; margin-top: 6px; font-weight: 600;">Scan with Phone Camera</div></div>', unsafe_allow_html=True)
        with m_col2:
            st.markdown(f"#### 🌐 Mobile Web URL: `{mobile_url}`")
            st.write("1. **Connect:** Ensure your phone is connected to the same Wi-Fi network.")
            st.write("2. **Open:** Scan the QR code with your camera or open in Safari / Chrome.")
            st.write("3. **Install as Full-Screen App (PWA):**")
            st.markdown("""
            - 🍎 **iPhone (Safari)**: Tap the Share button **([↑])** ➡️ scroll down and tap **'Add to Home Screen'** ➡️ tap **Add**.
            - 🤖 **Android (Chrome)**: Tap **(⋮)** ➡️ **'Install app'** (or **'Add to Home screen'**).
            - 🪐 **Samsung Internet**: Tap menu **(☰)** ➡️ **'Add page to'** ➡️ **'App screen'**.
            """)
            st.write("4. **iPhone 13–18 & Mobile Optimizations Active:**")
            st.markdown("""
            - 🏝️ **Dynamic Island & Notch Safe Areas**: Headers and menus automatically inset below the Dynamic Island / Notch and above the bottom Home Bar.
            - 🚫 **No Input Auto-Zoom**: Inputs formatted to prevent iOS Safari from zooming into form fields on tap.
            - ⚡ **120Hz ProMotion & AMOLED Smoothness**: Hardware-accelerated smooth scrolling and fluid touch response.
            - 💫 **iOS Widget Surfaces**: 20px rounded card surfaces, elevation shadows, and hidden tab scrollbars.
            - 📐 **Adaptive iPhone Viewports (375px - 440px)**: Scales from iPhone 13 mini (375px) to standard 13-18 Pro (390-402px) and Pro Max / Plus (428-440px).
            - 📋 **1-Tap Clipboard**: Instantly copy tailored cover letters, quick-apply answers, and outreach notes directly into the iOS LinkedIn or Mail apps.
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
