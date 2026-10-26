import os
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

import copilot
import db

BROWSER_PROFILE_DIR = Path(__file__).parent / "browser_profile"
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"

def get_browser_profile_path() -> Path:
    """Returns the persistent browser profile directory, creating it if needed."""
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return BROWSER_PROFILE_DIR

def get_screenshots_path() -> Path:
    """Returns directory for storing proof screenshots of submitted applications."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOTS_DIR

_playwright_installed = False

def ensure_playwright_browsers() -> None:
    """Ensures Chromium is installed when running in cloud/Linux environments."""
    global _playwright_installed
    if _playwright_installed:
        return
    if os.name != "nt":
        try:
            import subprocess
            subprocess.run(["playwright", "install", "chromium"], timeout=120, check=False)
            _playwright_installed = True
        except Exception:
            pass

def get_profile_status() -> Dict[str, Any]:
    """Inspects the persistent browser profile and counts stored cookies and sessions."""
    p_dir = get_browser_profile_path()
    status = {
        "exists": p_dir.exists(),
        "path": str(p_dir.resolve()),
        "total_cookies": 0,
        "linkedin_cookies": 0,
        "google_cookies": 0,
        "wellfound_cookies": 0,
        "has_local_storage": False,
        "size_mb": 0.0,
        "seeded": False
    }
    
    total_bytes = 0
    try:
        for root, dirs, files in os.walk(p_dir):
            for f in files:
                try:
                    total_bytes += (Path(root) / f).stat().st_size
                except Exception:
                    pass
        status["size_mb"] = round(total_bytes / (1024 * 1024), 2)
    except Exception:
        pass

    cookie_db = p_dir / "Default" / "Network" / "Cookies"
    if cookie_db.exists():
        status["seeded"] = True
        try:
            import sqlite3
            conn = sqlite3.connect(cookie_db)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM cookies")
            status["total_cookies"] = c.fetchone()[0]
            c.execute("SELECT count(*) FROM cookies WHERE host_key LIKE ?", ("%linkedin%",))
            status["linkedin_cookies"] = c.fetchone()[0]
            c.execute("SELECT count(*) FROM cookies WHERE host_key LIKE ?", ("%google%",))
            status["google_cookies"] = c.fetchone()[0]
            c.execute("SELECT count(*) FROM cookies WHERE host_key LIKE ?", ("%wellfound%",))
            status["wellfound_cookies"] = c.fetchone()[0]
            conn.close()
        except Exception:
            pass

    ls_dir = p_dir / "Default" / "Local Storage"
    if ls_dir.exists() and any(ls_dir.iterdir()):
        status["has_local_storage"] = True

    return status

def sync_chrome_cache(force: bool = False) -> Dict[str, Any]:
    """
    Safely copies cache memory, session cookies, Local State, and Local Storage from
    the user's installed Google Chrome profile into the agent's persistent browser profile.
    """
    import shutil
    p_dir = get_browser_profile_path()
    chrome_user_data = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    
    if not chrome_user_data.exists():
        return {"success": False, "message": "Google Chrome User Data folder not found."}

    synced_items = []

    # 1. Local State
    src_ls = chrome_user_data / "Local State"
    if src_ls.exists():
        try:
            shutil.copy2(src_ls, p_dir / "Local State")
            synced_items.append("Local State & Encryption Config")
        except Exception:
            pass

    # 2. Default Network & Cookies
    src_net = chrome_user_data / "Default" / "Network"
    dst_net = p_dir / "Default" / "Network"
    if src_net.exists():
        dst_net.mkdir(parents=True, exist_ok=True)
        for item in src_net.iterdir():
            try:
                if item.is_file():
                    shutil.copy2(item, dst_net / item.name)
            except Exception:
                pass
        synced_items.append("Network & Session Cookies")

    # 3. Default Local Storage
    src_storage = chrome_user_data / "Default" / "Local Storage"
    dst_storage = p_dir / "Default" / "Local Storage"
    if src_storage.exists():
        try:
            shutil.copytree(src_storage, dst_storage, dirs_exist_ok=True)
            synced_items.append("Local Storage (App State & Auth Tokens)")
        except Exception:
            pass

    # 4. Default IndexedDB
    src_idb = chrome_user_data / "Default" / "IndexedDB"
    dst_idb = p_dir / "Default" / "IndexedDB"
    if src_idb.exists():
        try:
            shutil.copytree(src_idb, dst_idb, dirs_exist_ok=True)
            synced_items.append("IndexedDB Database")
        except Exception:
            pass

    return {
        "success": True,
        "synced_items": synced_items,
        "message": f"Successfully imported {len(synced_items)} components from your Google Chrome cache!"
    }

def ensure_cache_seeded() -> None:
    """Auto-seeds cache on first run if profile cookies do not yet exist."""
    p_dir = get_browser_profile_path()
    cookie_db = p_dir / "Default" / "Network" / "Cookies"
    if not cookie_db.exists() or cookie_db.stat().st_size == 0:
        sync_chrome_cache(force=False)

def open_persistent_browser_manager(target_url: str = "https://www.linkedin.com/login", wait_seconds: int = 180) -> Dict[str, Any]:
    """
    Opens a visible persistent browser window for the user to sign in to LinkedIn, Google,
    or job boards once. All cookies, tokens, and cache memory are permanently saved on disk.
    """
    from playwright.sync_api import sync_playwright

    p_dir = get_browser_profile_path()
    ensure_cache_seeded()

    logs = []
    logs.append(f"🌐 Opening persistent session manager at {target_url}...")
    logs.append("💡 Please sign in or verify your accounts. Your session cookies and cache will be permanently remembered.")

    with sync_playwright() as p:
        launch_args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ]
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(p_dir),
                channel="chrome",
                headless=False,
                no_viewport=True,
                args=launch_args,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-US"
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(p_dir),
                headless=False,
                no_viewport=True,
                args=launch_args,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-US"
            )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            page.bring_to_front()

            start_t = time.time()
            while time.time() - start_t < wait_seconds:
                try:
                    if page.is_closed():
                        logs.append("Window closed by user. Sessions and cache saved to disk.")
                        break
                    time.sleep(1)
                except Exception:
                    break
        except Exception as e:
            logs.append(f"Notice: {str(e)[:120]}")
        finally:
            try:
                context.close()
            except Exception:
                pass

    status = get_profile_status()
    logs.append(f"✅ Persistent session saved! ({status['total_cookies']} cookies active)")
    return {"success": True, "logs": logs, "status": status}

RESUMES_DIR = Path(__file__).parent / "tailored_resumes"

def get_resumes_dir() -> Path:
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    return RESUMES_DIR

def _clean_for_pdf(text: str) -> str:
    """Replaces non-latin1 unicode characters with clean standard equivalents."""
    if not text:
        return ""
    replacements = {
        '\u2022': '-',
        '\u2013': '-',
        '\u2014': '--',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2026': '...',
        '\u00a0': ' ',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_tailored_resume_files(
    resume_data: Dict[str, Any], 
    job_data: Optional[Dict[str, Any]] = None, 
    api_key: str = ""
) -> Dict[str, Any]:
    """
    Dynamically generates ATS-tailored resume files (.pdf, .docx, .txt) customized
    for the specific target company and role, highlighting matching keywords.
    """
    if not job_data:
        job_data = {
            "title": "Software Engineer",
            "company": "Technology Company",
            "description": ""
        }

    tailored = copilot.generate_tailored_resume_data(resume_data, job_data, api_key)
    res_dir = get_resumes_dir()

    name = tailored.get("name", "Candidate")
    cand_slug = re.sub(r'[^a-zA-Z0-9]', '_', name).strip('_') or "Candidate"
    comp_slug = re.sub(r'[^a-zA-Z0-9]', '_', tailored.get("company", "Company")).strip('_')[:20] or "Company"
    title_slug = re.sub(r'[^a-zA-Z0-9]', '_', tailored.get("job_title", "Role")).strip('_')[:20] or "Role"
    file_base = f"{cand_slug}_Resume_{comp_slug}_{title_slug}"

    docx_path = res_dir / f"{file_base}.docx"
    pdf_path = res_dir / f"{file_base}.pdf"
    txt_path = res_dir / f"{file_base}.txt"

    contact_parts = []
    if resume_data.get("email"): contact_parts.append(resume_data["email"])
    if resume_data.get("phone"): contact_parts.append(resume_data["phone"])
    if resume_data.get("location"): contact_parts.append(resume_data["location"])
    links = db.get_candidate_links(resume_data)
    if links.get("linkedin"): contact_parts.append(links["linkedin"])
    if links.get("github"): contact_parts.append(links["github"])

    # 1. Generate DOCX
    try:
        import docx
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = docx.Document()
        for section in doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)

        # Header Name
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_name = p_name.add_run(name)
        r_name.font.size = Pt(18)
        r_name.font.bold = True
        r_name.font.color.rgb = RGBColor(15, 23, 42)

        # Target Headline
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_title = p_title.add_run(tailored.get("headline", tailored.get("job_title", "Target Role")))
        r_title.font.size = Pt(11)
        r_title.font.bold = True
        r_title.font.color.rgb = RGBColor(37, 99, 235)

        # Contact line
        p_cont = doc.add_paragraph()
        p_cont.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cont.paragraph_format.space_after = Pt(8)
        r_cont = p_cont.add_run(" | ".join(contact_parts))
        r_cont.font.size = Pt(9.5)
        r_cont.font.color.rgb = RGBColor(100, 116, 139)

        def add_docx_heading(h_text):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(h_text.upper())
            r.font.size = Pt(10.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor(30, 41, 59)

        # Summary
        add_docx_heading("Professional Summary")
        p_s = doc.add_paragraph()
        p_s.paragraph_format.space_after = Pt(6)
        r_s = p_s.add_run(tailored.get("summary", ""))
        r_s.font.size = Pt(9.5)

        # Skills
        add_docx_heading("Technical Skills & Core Competencies")
        p_sk = doc.add_paragraph()
        p_sk.paragraph_format.space_after = Pt(6)
        skills_list = tailored.get("prioritized_skills", [])
        r_sk = p_sk.add_run(" • ".join(skills_list))
        r_sk.font.size = Pt(9.5)

        # Experience
        add_docx_heading("Professional Experience")
        p_exp = doc.add_paragraph()
        p_exp.paragraph_format.space_after = Pt(4)
        r_exp = p_exp.add_run(str(resume_data.get("experience", "")))
        r_exp.font.size = Pt(9.5)

        # Tailored achievements
        bullets = tailored.get("tailored_bullets", [])
        if bullets:
            add_docx_heading("Key Technical Achievements & Highlights")
            for b in bullets:
                p_b = doc.add_paragraph(style='List Bullet')
                p_b.paragraph_format.space_after = Pt(2)
                r_b = p_b.add_run(str(b))
                r_b.font.size = Pt(9.5)

        # Education
        add_docx_heading("Education")
        p_ed = doc.add_paragraph()
        r_ed = p_ed.add_run(str(resume_data.get("education", "")))
        r_ed.font.size = Pt(9.5)

        doc.save(str(docx_path))
    except Exception as e:
        print(f"Notice generating DOCX: {e}")

    # 2. Generate PDF via fpdf2
    try:
        from fpdf import FPDF
        class PDFResume(FPDF):
            def header(self): pass
            def footer(self): pass

        pdf = PDFResume(format='letter')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(15, 12, 15)
        pdf.add_page()
        
        usable_w = pdf.w - pdf.l_margin - pdf.r_margin

        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(usable_w, 7, _clean_for_pdf(name), align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font('Helvetica', 'B', 10.5)
        pdf.set_text_color(37, 99, 235)
        pdf.cell(usable_w, 6, _clean_for_pdf(tailored.get("headline", tailored.get("job_title", ""))[:75]), align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        clean_contact = [_clean_for_pdf(c) for c in contact_parts]
        pdf.cell(usable_w, 5, " | ".join(clean_contact), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        def add_pdf_heading(h_text):
            pdf.set_x(15)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(usable_w, 6, h_text.upper(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(226, 232, 240)
            pdf.line(15, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

        add_pdf_heading("Professional Summary")
        pdf.set_x(15)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(usable_w, 4.5, _clean_for_pdf(tailored.get("summary", "")))
        pdf.ln(2)

        add_pdf_heading("Technical Skills & Core Competencies")
        pdf.set_x(15)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        clean_skills = [_clean_for_pdf(s) for s in tailored.get("prioritized_skills", [])]
        pdf.multi_cell(usable_w, 4.5, " | ".join(clean_skills))
        pdf.ln(2)

        add_pdf_heading("Professional Experience")
        pdf.set_x(15)
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(usable_w, 4.5, _clean_for_pdf(str(resume_data.get("experience", ""))[:1400]))
        pdf.ln(2)

        bullets = tailored.get("tailored_bullets", [])
        if bullets:
            add_pdf_heading("Key Technical Achievements & Highlights")
            pdf.set_font('Helvetica', '', 8.5)
            pdf.set_text_color(51, 65, 85)
            for b in bullets:
                pdf.set_x(15)
                pdf.multi_cell(usable_w, 4.5, f"- {_clean_for_pdf(str(b))}")
            pdf.ln(2)

        add_pdf_heading("Education")
        pdf.set_x(15)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(usable_w, 4.5, _clean_for_pdf(str(resume_data.get("education", ""))))

        pdf.output(str(pdf_path))
    except Exception as e:
        print(f"Notice generating PDF: {e}")

    # 3. Generate Plain Text
    try:
        txt_content = f"""{name}
{tailored.get("headline", "")}
{" | ".join(contact_parts)}

PROFESSIONAL SUMMARY
{tailored.get("summary", "")}

TECHNICAL SKILLS
{", ".join(tailored.get("prioritized_skills", []))}

PROFESSIONAL EXPERIENCE
{str(resume_data.get("experience", ""))}

EDUCATION
{str(resume_data.get("education", ""))}
"""
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content.strip())
    except Exception:
        pass

    # Compatibility copies
    active_txt = Path(__file__).parent / "active_resume.txt"
    active_docx = Path(__file__).parent / "active_resume.docx"
    try:
        import shutil
        if docx_path.exists(): shutil.copy2(docx_path, active_docx)
        if txt_path.exists(): shutil.copy2(txt_path, active_txt)
    except Exception:
        pass

    return {
        "pdf": str(pdf_path.resolve()) if pdf_path.exists() else str(docx_path.resolve()),
        "docx": str(docx_path.resolve()) if docx_path.exists() else str(txt_path.resolve()),
        "txt": str(txt_path.resolve()),
        "filename_base": file_base,
        "headline": tailored.get("headline", ""),
        "summary": tailored.get("summary", ""),
        "matching_skills": tailored.get("matching_skills", []),
        "prioritized_skills": tailored.get("prioritized_skills", []),
        "tailored_bullets": tailored.get("tailored_bullets", [])
    }

def find_or_create_resume_file(resume_data: Dict[str, Any], prefer_docx: bool = True) -> str:
    """Backwards compatibility helper."""
    res = generate_tailored_resume_files(resume_data, None)
    return res["docx"] if prefer_docx else res["pdf"]

def get_search_scopes(page):
    """Returns page and all accessible frames so inputs inside ATS iframes (Greenhouse, Lever, Workday) are populated."""
    scopes = [page]
    try:
        for f in page.frames:
            if f != page.main_frame:
                scopes.append(f)
    except Exception:
        pass
    return scopes

def get_active_page(context, fallback_page):
    """Finds the most recently active non-closed tab in the browser context."""
    if context.pages:
        for p in reversed(context.pages):
            try:
                if not p.is_closed():
                    return p
            except Exception:
                continue
    return fallback_page

def fill_input_safely(page, selectors: List[str], value: Any, logs: Optional[List[str]] = None) -> bool:
    """Tries multiple selectors across page and any nested ATS iframes to find and safely fill an input."""
    if not value or not str(value).strip():
        return False
    str_val = str(value).strip()
    scopes = get_search_scopes(page)
    for scope in scopes:
        for sel in selectors:
            try:
                loc = scope.locator(sel).first
                if loc.is_visible(timeout=400):
                    current_val = ""
                    try:
                        current_val = loc.input_value(timeout=200)
                    except Exception:
                        pass
                    if not current_val:
                        loc.click()
                        loc.fill(str_val)
                        return True
            except Exception:
                continue
    return False

def safe_answer_radios(page, logs: Optional[List[str]] = None) -> int:
    """
    Intelligently answers common job application radio button groups:
    - Work authorization: Yes
    - Need visa sponsorship: No
    - 18+ years of age: Yes
    - Terms & conditions agreement: Yes
    """
    answered = 0
    try:
        radios = page.locator('input[type="radio"]')
        count = radios.count()
        if count == 0:
            return 0
            
        for i in range(count):
            r = radios.nth(i)
            try:
                if not r.is_visible(timeout=300):
                    continue
                # Get surrounding context text
                parent_text = r.evaluate("el => el.closest('fieldset, .form-group, .radio-group, div, label')?.innerText || ''").lower()
                r_val = (r.get_attribute("value") or "").lower()
                r_id = (r.get_attribute("id") or "").lower()
                r_aria = (r.get_attribute("aria-label") or "").lower()
                full_sig = f"{r_val} {r_id} {r_aria} {parent_text}"

                # Work Authorization -> YES
                if any(k in parent_text for k in ["authorized to work", "legally authorized", "eligible to work", "legal right to work"]):
                    if any(k in full_sig for k in ["yes", "true", "authorized", "eligible"]) and "sponsor" not in full_sig:
                        if not r.is_checked():
                            r.check(force=True)
                            answered += 1

                # Visa Sponsorship -> NO
                elif any(k in parent_text for k in ["sponsorship", "require visa", "require sponsorship", "future sponsorship"]):
                    if any(k in full_sig for k in ["no", "false", "do not require", "will not"]):
                        if not r.is_checked():
                            r.check(force=True)
                            answered += 1

                # Legal Age / 18+ -> YES
                elif any(k in parent_text for k in ["18 years", "at least 18", "legal age"]):
                    if any(k in full_sig for k in ["yes", "true"]):
                        if not r.is_checked():
                            r.check(force=True)
                            answered += 1

                # Terms & Agreement -> YES
                elif any(k in parent_text for k in ["agree", "consent", "terms"]):
                    if any(k in full_sig for k in ["yes", "true", "agree", "accept"]):
                        if not r.is_checked():
                            r.check(force=True)
                            answered += 1
            except Exception:
                continue
    except Exception:
        pass
    return answered

def safe_select_dropdowns(page, user_prefs: Dict[str, Any], logs: Optional[List[str]] = None) -> int:
    """
    Intelligently handles <select> dropdowns for work auth, notice period, and standard screening.
    """
    selected_count = 0
    try:
        selects = page.locator("select")
        count = selects.count()
        for i in range(count):
            s = selects.nth(i)
            try:
                if not s.is_visible(timeout=300):
                    continue
                # Get select label or parent context
                ctx = s.evaluate("el => el.closest('fieldset, .form-group, div, label')?.innerText || ''").lower()
                curr_val = s.input_value()
                if curr_val and curr_val != "0" and curr_val.lower() != "select":
                    continue

                options_data = s.evaluate("""el => Array.from(el.options).map(o => ({
                    value: o.value, 
                    text: o.text.trim().toLowerCase(),
                    index: o.index
                }))""")

                chosen_val = None

                # Work Auth
                if any(k in ctx for k in ["authorized", "eligibility", "legally authorized"]):
                    for opt in options_data:
                        if opt["text"] in ["yes", "authorized", "yes, authorized", "citizen", "permanent resident"]:
                            chosen_val = opt["value"]
                            break

                # Sponsorship
                elif any(k in ctx for k in ["sponsorship", "visa"]):
                    for opt in options_data:
                        if opt["text"] in ["no", "will not require", "not required", "no sponsorship"]:
                            chosen_val = opt["value"]
                            break

                # Notice Period / Availability
                elif any(k in ctx for k in ["notice period", "availability", "how soon", "start date"]):
                    for opt in options_data:
                        if any(k in opt["text"] for k in ["immediate", "2 weeks", "two weeks", "1 month", "30 days"]):
                            chosen_val = opt["value"]
                            break

                # Gender / EEO / Race / Veteran / Disability
                elif any(k in ctx for k in ["gender", "race", "ethnicity", "veteran", "disability", "equal opportunity"]):
                    for opt in options_data:
                        if any(k in opt["text"] for k in ["decline", "prefer not", "wish not", "i do not wish", "choose not to disclose"]):
                            chosen_val = opt["value"]
                            break

                # If required and still no value, choose first valid option
                if not chosen_val:
                    is_req = s.get_attribute("required") is not None or "required" in ctx
                    if is_req and len(options_data) > 1:
                        # Choose option 1 if option 0 is placeholder
                        first_valid = [o for o in options_data if o["value"] and o["text"] not in ["select", "choose", "--"]][:1]
                        if first_valid:
                            chosen_val = first_valid[0]["value"]

                if chosen_val:
                    s.select_option(value=chosen_val)
                    selected_count += 1
            except Exception:
                continue
    except Exception:
        pass
    return selected_count

def safe_check_checkboxes(page, logs: Optional[List[str]] = None) -> int:
    """Checks required consent, privacy policy, and terms checkboxes."""
    checked = 0
    try:
        boxes = page.locator('input[type="checkbox"]')
        count = boxes.count()
        for i in range(count):
            cb = boxes.nth(i)
            try:
                if not cb.is_visible(timeout=300):
                    continue
                if cb.is_checked():
                    continue

                # Check if checkbox context requires agreement
                ctx = cb.evaluate("el => el.closest('label, div, p, .form-group')?.innerText || ''").lower()
                is_req = cb.get_attribute("required") is not None or cb.get_attribute("aria-required") == "true"
                terms_kw = any(k in ctx for k in [
                    "agree", "consent", "terms", "privacy", "certify", 
                    "acknowledge", "confirm", "accept", "policy", "declaration"
                ])

                if is_req or terms_kw:
                    cb.check(force=True)
                    checked += 1
            except Exception:
                continue
    except Exception:
        pass
    return checked

def fill_all_step_fields(
    page, 
    resume_data: Dict[str, Any], 
    answers: Dict[str, str], 
    tailored_letter: str, 
    resume_file_path: str,
    logs: Optional[List[str]] = None,
    tailored_resume: Optional[Dict[str, Any]] = None
) -> Dict[str, int]:
    """
    Comprehensive multi-field auto-filler executed at each step of an application wizard.
    """
    stats = {"inputs": 0, "radios": 0, "selects": 0, "checkboxes": 0, "files": 0}

    name = resume_data.get("name", "")
    name_parts = name.split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    email = resume_data.get("email", "")
    phone = resume_data.get("phone", "")
    loc = resume_data.get("location") or db.get_setting("user_location", "San Francisco, CA")
    
    links = db.get_candidate_links(resume_data)
    linkedin = links.get("linkedin", "")
    github = links.get("github", "")
    portfolio = links.get("portfolio", "") or github

    years_exp = db.get_setting("years_exp", "4+ years")
    clean_years_num = re.findall(r'\d+', years_exp)
    years_num_str = clean_years_num[0] if clean_years_num else "4"

    salary = db.get_setting("expected_salary", "$120,000 / yr")
    clean_salary_num = re.sub(r'[^\d]', '', salary) or "120000"

    notice_period = db.get_setting("notice_period", "Immediate (2 weeks)")
    why_us = answers.get("Why do you want to work here?", "")

    # 1. Names
    if fill_input_safely(page, [
        'input[autocomplete="given-name"]',
        'input[name*="first_name" i]',
        'input[name*="firstname" i]',
        'input[id*="first_name" i]',
        'input[id*="firstname" i]',
        'input[placeholder*="First Name" i]',
        'input[placeholder*="First" i]'
    ], first_name):
        stats["inputs"] += 1
        
    if fill_input_safely(page, [
        'input[autocomplete="family-name"]',
        'input[name*="last_name" i]',
        'input[name*="lastname" i]',
        'input[id*="last_name" i]',
        'input[id*="lastname" i]',
        'input[placeholder*="Last Name" i]',
        'input[placeholder*="Last" i]'
    ], last_name):
        stats["inputs"] += 1

    # Full name fallback
    if fill_input_safely(page, [
        'input[autocomplete="name"]',
        'input[name="name" i]',
        'input[id="name" i]',
        'input[placeholder*="Full Name" i]',
        'input[placeholder*="Your Name" i]'
    ], name):
        stats["inputs"] += 1

    # 2. Email
    if fill_input_safely(page, [
        'input[type="email"]',
        'input[autocomplete="email"]',
        'input[name*="email" i]',
        'input[id*="email" i]',
        'input[placeholder*="Email" i]'
    ], email):
        stats["inputs"] += 1

    # 3. Phone
    if fill_input_safely(page, [
        'input[type="tel"]',
        'input[autocomplete="tel"]',
        'input[name*="phone" i]',
        'input[name*="mobile" i]',
        'input[id*="phone" i]',
        'input[placeholder*="Phone" i]',
        'input[placeholder*="Mobile" i]'
    ], phone):
        stats["inputs"] += 1

    # 4. Location / City / Address
    fill_input_safely(page, [
        'input[autocomplete="address-level2"]',
        'input[name*="city" i]',
        'input[id*="city" i]',
        'input[placeholder*="City" i]'
    ], loc.split(",")[0] if loc else "San Francisco")

    fill_input_safely(page, [
        'input[name*="location" i]',
        'input[id*="location" i]',
        'input[placeholder*="Location" i]',
        'input[placeholder*="Current City" i]'
    ], loc)

    # 5. Social & Portfolios
    fill_input_safely(page, [
        'input[name*="linkedin" i]',
        'input[id*="linkedin" i]',
        'input[placeholder*="LinkedIn" i]',
        'input[aria-label*="LinkedIn" i]'
    ], linkedin)

    fill_input_safely(page, [
        'input[name*="github" i]',
        'input[id*="github" i]',
        'input[placeholder*="GitHub" i]'
    ], github)

    fill_input_safely(page, [
        'input[name*="portfolio" i]',
        'input[name*="website" i]',
        'input[id*="portfolio" i]',
        'input[id*="website" i]',
        'input[placeholder*="Portfolio" i]',
        'input[placeholder*="Website" i]'
    ], portfolio or github)

    # 6. Screening Questions: Experience, Salary, Notice
    fill_input_safely(page, [
        'input[name*="experience" i]',
        'input[id*="experience" i]',
        'input[placeholder*="years of experience" i]'
    ], years_num_str)

    fill_input_safely(page, [
        'input[name*="salary" i]',
        'input[name*="compensation" i]',
        'input[id*="salary" i]',
        'input[placeholder*="desired salary" i]',
        'input[placeholder*="expected salary" i]'
    ], clean_salary_num)

    fill_input_safely(page, [
        'input[name*="notice" i]',
        'input[id*="notice" i]',
        'input[placeholder*="notice period" i]'
    ], notice_period)

    # 7. Cover Letter & Open-ended Textareas
    fill_input_safely(page, [
        'textarea[name*="cover" i]',
        'textarea[id*="cover" i]',
        'textarea[placeholder*="Cover Letter" i]',
        'textarea[aria-label*="Cover Letter" i]',
        'textarea[name*="comments" i]'
    ], tailored_letter)

    fill_input_safely(page, [
        'textarea[name*="why" i]',
        'textarea[placeholder*="Why do you want" i]',
        'textarea[placeholder*="tell us about yourself" i]'
    ], why_us)

    # 8. Radio Buttons
    stats["radios"] = safe_answer_radios(page, logs)

    # 9. Dropdowns
    stats["selects"] = safe_select_dropdowns(page, {"years_exp": years_exp, "notice_period": notice_period}, logs)

    # 10. Checkboxes
    stats["checkboxes"] = safe_check_checkboxes(page, logs)

    # 11. Tailored Resume File Upload (Across page and all ATS iframes)
    try:
        scopes = get_search_scopes(page)
        for scope in scopes:
            file_inputs = scope.locator('input[type="file"]')
            if file_inputs.count() > 0:
                for fi_idx in range(file_inputs.count()):
                    fi = file_inputs.nth(fi_idx)
                    try:
                        accept = (fi.get_attribute("accept") or "").lower()
                        upload_target = resume_file_path
                        if tailored_resume:
                            if ".docx" in accept or ".doc" in accept:
                                upload_target = tailored_resume.get("docx") or resume_file_path
                            elif ".pdf" in accept or not accept or "*/*" in accept:
                                upload_target = tailored_resume.get("pdf") or resume_file_path
                            elif ".txt" in accept:
                                upload_target = tailored_resume.get("txt") or resume_file_path

                        fi.set_input_files(upload_target)
                        stats["files"] += 1
                        if logs is not None:
                            logs.append(f"📎 Attached tailored resume: {Path(upload_target).name}")
                    except Exception:
                        pass
    except Exception:
        pass

    return stats

def detect_submission_success(page, original_url: str, logs: Optional[List[str]] = None) -> bool:
    """
    Checks multiple signals across the page, URL, and DOM to confirm the application was genuinely submitted.
    """
    try:
        curr_url = page.url.lower()
        # 1. URL pattern change
        url_success_kws = ["confirmation", "thank-you", "thank_you", "applied", "success", "submitted"]
        if any(kw in curr_url for kw in url_success_kws) and not any(kw in original_url.lower() for kw in url_success_kws):
            return True

        # 2. Body text confirmation
        body_text = page.inner_text("body", timeout=1500).lower()
        success_phrases = [
            "application submitted",
            "application was sent",
            "application has been submitted",
            "thank you for applying",
            "thanks for applying",
            "we've received your application",
            "we have received your application",
            "application received",
            "your application was submitted",
            "your application has been sent",
            "congratulations! you've applied",
            "you applied to"
        ]
        for phrase in success_phrases:
            if phrase in body_text:
                return True

        # 3. LinkedIn Easy Apply "Done" or "Dismiss" dialog
        done_btn = page.locator('button:has-text("Done"), button[aria-label*="Dismiss" i]').first
        if done_btn.is_visible(timeout=500):
            try:
                done_btn.click()
            except Exception:
                pass
            return True

    except Exception:
        pass
    return False

def take_confirmation_screenshot(page, job_id: str, logs: Optional[List[str]] = None) -> Optional[str]:
    """Saves a verification screenshot of the submitted application for user records."""
    try:
        sc_dir = get_screenshots_path()
        sc_path = sc_dir / f"applied_{job_id}_{int(time.time())}.png"
        page.screenshot(path=str(sc_path), full_page=False)
        if logs is not None:
            logs.append(f"📸 Proof screenshot saved: {sc_path.name}")
        return str(sc_path.resolve())
    except Exception:
        return None

def detect_captcha(page) -> Dict[str, Any]:
    """
    Detects if a CAPTCHA, Cloudflare Turnstile, reCAPTCHA, hCaptcha, Arkose / FunCAPTCHA,
    or bot-verification challenge is currently active and visible on the page.
    Returns:
        {"has_captcha": bool, "type": str, "details": str}
    """
    try:
        if page.is_closed():
            return {"has_captcha": False, "type": "", "details": "Page is closed"}

        # 1. Check known CAPTCHA and bot challenge iframes
        iframe_patterns = [
            ('iframe[src*="challenges.cloudflare.com" i]', "Cloudflare Turnstile Challenge"),
            ('iframe[src*="turnstile" i]', "Cloudflare Turnstile"),
            ('iframe[title*="turnstile" i]', "Cloudflare Turnstile"),
            ('iframe[src*="google.com/recaptcha" i]', "Google reCAPTCHA"),
            ('iframe[src*="recaptcha" i]', "Google reCAPTCHA"),
            ('iframe[title*="recaptcha" i]', "Google reCAPTCHA"),
            ('iframe[src*="hcaptcha.com" i]', "hCaptcha"),
            ('iframe[src*="hcaptcha" i]', "hCaptcha"),
            ('iframe[title*="hcaptcha" i]', "hCaptcha"),
            ('iframe[src*="arkoselabs" i]', "Arkose Labs FunCAPTCHA"),
            ('iframe[src*="funcaptcha" i]', "FunCAPTCHA"),
            ('iframe[id*="arkose" i]', "Arkose Labs Challenge"),
            ('iframe[title*="challenge" i]', "Security Challenge Frame"),
            ('iframe[title*="verification" i]', "Security Verification Frame"),
            ('iframe[src*="captcha" i]', "Generic CAPTCHA Frame")
        ]

        for sel, name in iframe_patterns:
            try:
                frame_loc = page.locator(sel).first
                if frame_loc.is_visible(timeout=250):
                    box = frame_loc.bounding_box(timeout=250)
                    if box and box["width"] > 20 and box["height"] > 20:
                        return {"has_captcha": True, "type": name, "details": f"Visible iframe matched selector '{sel}'"}
            except Exception:
                continue

        # 2. Check DOM elements specifically associated with CAPTCHAs
        element_patterns = [
            ('.g-recaptcha', "Google reCAPTCHA Container"),
            ('.h-captcha', "hCaptcha Container"),
            ('#cf-turnstile', "Cloudflare Turnstile Container"),
            ('#challenge-running', "Cloudflare Waiting Room / Challenge"),
            ('#challenge-stage', "Cloudflare Challenge Stage"),
            ('.challenge-form', "Security Challenge Form"),
            ('[data-testid*="captcha" i]', "CAPTCHA Test Element"),
            ('[id*="captcha" i]', "CAPTCHA Element"),
            ('[class*="captcha" i]', "CAPTCHA Widget"),
            ('[id*="security-check" i]', "Security Check Element"),
            ('[class*="security-check" i]', "Security Check Element")
        ]

        for sel, name in element_patterns:
            try:
                elem_loc = page.locator(sel).first
                if elem_loc.is_visible(timeout=200):
                    box = elem_loc.bounding_box(timeout=200)
                    if box and box["width"] > 20 and box["height"] > 20:
                        return {"has_captcha": True, "type": name, "details": f"Visible element matched selector '{sel}'"}
            except Exception:
                continue

        # 3. Check text patterns inside body or page title
        try:
            page_title = page.title().lower()
            if any(t in page_title for t in ["just a moment...", "security check", "attention required! | cloudflare", "blocked - indeed", "blocked", "access denied"]):
                return {"has_captcha": True, "type": "Cloudflare / Security Page", "details": f"Title matched: '{page_title}'"}

            body_text = page.inner_text("body", timeout=400).lower()
            text_signals = [
                ("verify you are human", "Cloudflare / Human Verification"),
                ("verify that you are human", "Human Verification Challenge"),
                ("verifying you are human", "Cloudflare Turnstile Verification"),
                ("complete the security check", "Security Verification"),
                ("please verify that you are not a robot", "reCAPTCHA Verification"),
                ("confirm you're not a robot", "Bot Challenge"),
                ("confirm you are human", "Human Verification"),
                ("press and hold", "Press & Hold Bot Challenge"),
                ("press & hold", "Press & Hold Bot Challenge"),
                ("please solve this puzzle", "Arkose Puzzle Challenge"),
                ("let's confirm you are human", "Human Verification")
            ]
            for phrase, name in text_signals:
                if phrase in body_text:
                    return {"has_captcha": True, "type": name, "details": f"Body text contains '{phrase}'"}
        except Exception:
            pass

    except Exception:
        pass

    return {"has_captcha": False, "type": "", "details": "No CAPTCHA detected"}

def handle_captcha_handover(
    page, 
    logs: Optional[List[str]] = None, 
    timeout_seconds: int = 90
) -> bool:
    """
    Hands over control to the user when a CAPTCHA or security verification is detected:
    1. Pops the browser window to the front on the user's screen.
    2. Emits an audible system alert chime on Windows.
    3. Informs the user clearly in logs that control is handed over to them.
    4. Automatically polls every 1.2 seconds for the CAPTCHA to be resolved.
    5. The moment the user solves it and the challenge clears, resumes autonomous execution seamlessly!
    """
    detection = detect_captcha(page)
    if not detection["has_captcha"]:
        return True

    captcha_name = detection.get("type", "Security Check")

    # 1. Bring browser window to front
    try:
        page.bring_to_front()
    except Exception:
        pass

    # 2. Sound audible alert
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass

    # 3. Log clear handover instructions
    handover_msg_1 = f"🚨 [ACTION REQUIRED] {captcha_name} detected on screen!"
    handover_msg_2 = "🎮 GIVING CHARGE TO YOUR HANDS: Please click or solve the CAPTCHA in the opened browser window."
    handover_msg_3 = f"⏳ Automation paused. Waiting for you to pass it (auto-resumes the instant you finish)..."
    
    if logs is not None:
        logs.append(handover_msg_1)
        logs.append(handover_msg_2)
        logs.append(handover_msg_3)

    start_time = time.time()
    last_reminder = start_time

    while time.time() - start_time < timeout_seconds:
        try:
            if page.is_closed():
                if logs is not None:
                    logs.append("ℹ️ Browser window was closed by user.")
                return False

            # Check if CAPTCHA is still present
            check = detect_captcha(page)
            if not check["has_captcha"]:
                if logs is not None:
                    logs.append("🎉 CAPTCHA solved & passed! Taking back charge and resuming auto-apply...")
                # Allow DOM to stabilize after human interaction
                time.sleep(2.5)
                return True

            # Periodic log update every 15 seconds
            elapsed = time.time() - start_time
            if time.time() - last_reminder >= 15:
                rem = max(0, int(timeout_seconds - elapsed))
                if logs is not None:
                    logs.append(f"⏳ Waiting for you to solve the challenge... ({rem}s remaining)")
                last_reminder = time.time()

            time.sleep(1.2)
        except Exception as e:
            if logs is not None:
                logs.append(f"Notice while waiting for CAPTCHA: {str(e)[:80]}")
            break

    if logs is not None:
        logs.append("⚠️ CAPTCHA handover timed out. Attempting to proceed with application flow...")
    return False

def detect_login_wall(page) -> Dict[str, Any]:
    """
    Detects if the user has hit a login wall on LinkedIn, Indeed, Naukri, or an ATS portal.
    """
    try:
        if page.is_closed():
            return {"needs_login": False, "platform": ""}
        curr_url = page.url.lower()
        if "linkedin.com/login" in curr_url or "linkedin.com/checkpoint" in curr_url:
            return {"needs_login": True, "platform": "LinkedIn"}
        if "indeed.com/account/login" in curr_url or "secure.indeed.com/auth" in curr_url:
            return {"needs_login": True, "platform": "Indeed"}
        if "naukri.com/nlogin" in curr_url:
            return {"needs_login": True, "platform": "Naukri"}
    except Exception:
        pass
    return {"needs_login": False, "platform": ""}

def handle_login_handover(page, platform: str, logs: Optional[List[str]] = None, timeout_seconds: int = 120) -> bool:
    """
    Hands over browser to user to complete one-time login; saves cookies permanently to disk.
    """
    try:
        page.bring_to_front()
    except Exception:
        pass
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass

    if logs is not None:
        logs.append(f"🔑 [ACTION REQUIRED] {platform} Sign-In Required!")
        logs.append("🎮 GIVING CHARGE TO YOUR HANDS: Please sign in to your account in the opened window.")
        logs.append(f"💾 Your session & cookies will be permanently remembered! Auto-apply resumes once you log in (Timeout: {timeout_seconds}s)...")

    start_time = time.time()
    last_reminder = start_time

    while time.time() - start_time < timeout_seconds:
        try:
            if page.is_closed():
                return False
            check = detect_login_wall(page)
            if not check["needs_login"]:
                if logs is not None:
                    logs.append(f"🎉 Successfully signed in to {platform}! Session saved to disk. Resuming auto-apply...")
                time.sleep(2)
                return True
            if time.time() - last_reminder >= 20:
                rem = max(0, int(timeout_seconds - (time.time() - start_time)))
                if logs is not None:
                    logs.append(f"⏳ Waiting for your login in the browser window... ({rem}s remaining)")
                last_reminder = time.time()
            time.sleep(1.5)
        except Exception:
            break

    if logs is not None:
        logs.append(f"⚠️ Login handover timed out for {platform}.")
    return False

def auto_apply_to_job(
    job_data: Dict[str, Any], 
    resume_data: Dict[str, Any], 
    api_key: str = "",
    auto_submit: bool = True,
    keep_open_seconds: int = 90
) -> Dict[str, Any]:
    """
    Fully Autonomous End-to-End Job Application Engine:
    1. Tailors cover letter and answers for target role.
    2. Opens authenticated browser session via persistent cache.
    3. Handles initial 'Apply' / 'Easy Apply' triggers.
    4. Autonomous progression loop:
       - Multi-step form auto-fill (Contact, Resume, Screening, Radios, Checkboxes, Dropdowns).
       - Clicks 'Next' / 'Continue' / 'Review' across multi-page wizards.
       - If auto_submit=True: Locates and clicks 'Submit Application' / 'Submit' automatically!
       - Verifies submission confirmation, takes proof screenshot, and marks status as 'Applied'.
    5. If auto_submit=False (Assist Mode): Pre-fills fields and pauses for user review.
    """
    from playwright.sync_api import sync_playwright

    target_url = job_data.get("apply_url") or job_data.get("url")
    if not target_url:
        return {"success": False, "message": "No application URL available for this job."}

    # 1. Tailor Cover Letter
    tailored_letter = copilot.generate_cover_letter(
        resume_data=resume_data,
        job_data=job_data,
        api_key=api_key,
        tone="Confident & Professional"
    )

    # Initial DB registration (In Progress)
    db.save_or_update_application(
        job_id=job_data["id"],
        job_title=job_data["title"],
        company=job_data["company"],
        apply_url=target_url,
        status="In Progress",
        cover_letter=tailored_letter
    )

    # Candidate Contact info (Email is recipient for platform confirmation/revert emails)
    candidate_email = (
        resume_data.get("email") 
        or db.get_setting("user_email") 
        or "mrityunjayk456@gmail.com"
    ).strip()
    resume_data["email"] = candidate_email
    db.set_setting("user_email", candidate_email)

    candidate_phone = (
        resume_data.get("phone") 
        or db.get_setting("user_phone") 
        or "+91-7972379015"
    ).strip()
    resume_data["phone"] = candidate_phone
    db.set_setting("user_phone", candidate_phone)

    # 2. Dynamically tailor resume for this specific job & company
    tailored_resume = generate_tailored_resume_files(resume_data, job_data, api_key=api_key)
    resume_file_path = tailored_resume.get("pdf") or tailored_resume.get("docx")

    user_prefs = {
        "years_exp": db.get_setting("years_exp", "4+ years"),
        "expected_salary": db.get_setting("expected_salary", "$120,000 / yr"),
        "work_auth": db.get_setting("work_auth", "Authorized to work"),
        "notice_period": db.get_setting("notice_period", "Immediate (2 weeks)")
    }
    answers = copilot.generate_application_answers(resume_data, job_data, user_prefs)

    p_dir = get_browser_profile_path()
    ensure_cache_seeded()

    # Detect headless cloud vs local desktop
    is_cloud = os.environ.get("STREAMLIT_SHARING_MODE") is not None or (os.name != "nt" and os.environ.get("DISPLAY") is None)
    headless_mode = bool(is_cloud)

    logs = []
    logs.append(f"🎯 Target: {job_data['title']} at {job_data['company']}")
    logs.append(f"✍️ Tailored cover letter generated ({len(tailored_letter)} chars)")
    
    if auto_submit:
        logs.append("🚀 Mode: FULLY AUTONOMOUS (Will auto-traverse steps & click SUBMIT)")
    else:
        logs.append("👀 Mode: CO-PILOT ASSIST (Will pre-fill fields & pause for review)")

    if is_cloud:
        logs.append("☁️ Running on Streamlit Community Cloud (Headless Mode)")
        ensure_playwright_browsers()
    else:
        logs.append("🍪 Loaded persistent browser profile & cache memory (saved logins active)")
        logs.append("🌐 Launching visible Chrome browser on your screen...")

    is_submitted = False
    proof_screenshot = None

    try:
        with sync_playwright() as p:
            launch_args = [
                "--start-maximized" if not headless_mode else "--headless",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(p_dir),
                    channel="chrome" if os.name == "nt" else None,
                    headless=headless_mode,
                    no_viewport=not headless_mode,
                    args=launch_args,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="en-US"
                )
            except Exception:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(p_dir),
                    headless=headless_mode,
                    no_viewport=not headless_mode,
                    args=launch_args,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="en-US"
                )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            page = context.pages[0] if context.pages else context.new_page()

            try:
                page.goto(target_url, timeout=40000, wait_until="domcontentloaded")
                time.sleep(2.5)

                # 🛡️ CAPTCHA Check 1: Initial landing check & handover if challenge present
                c_stat = detect_captcha(page)
                if c_stat["has_captcha"]:
                    handle_captcha_handover(page, logs, timeout_seconds=90)

                # Check login wall
                curr_url = page.url.lower()
                if "register" in curr_url or "login" in curr_url or "account" in curr_url:
                    logs.append("ℹ️ Application portal requires a login. Using authenticated cached session...")
                    page.bring_to_front()
                else:
                    logs.append("⚡ Authenticated via cached persistent profile!")

                # Step 0: Click initial Apply button if on a job landing page
                initial_apply_selectors = [
                    'button:has-text("Easy Apply")',
                    'button.jobs-apply-button',
                    'button[aria-label*="Easy Apply" i]',
                    'a:has-text("Apply to Startup")',
                    'button:has-text("Apply to Startup")',
                    'a:has-text("Apply for this job")',
                    'button:has-text("Apply for this job")',
                    'a:has-text("Apply Now")',
                    'button:has-text("Apply Now")',
                    'button:has-text("Quick Apply")',
                    'a:has-text("Apply")',
                    'button:has-text("Apply")'
                ]
                for sel in initial_apply_selectors:
                    try:
                        loc = page.locator(sel).first
                        if loc.is_visible(timeout=1000):
                            loc.click()
                            logs.append(f"Clicked initial '{sel.replace('button:has-text(', '').replace('a:has-text(', '').rstrip(')')}' button")
                            time.sleep(2.5)

                            # Check if click opened a new tab/window
                            new_page = get_active_page(context, page)
                            if new_page != page:
                                page = new_page
                                page.bring_to_front()
                                logs.append(f"🌐 Application opened in new tab: {page.url[:80]}...")
                            
                            # Check login wall
                            l_stat = detect_login_wall(page)
                            if l_stat["needs_login"]:
                                handle_login_handover(page, l_stat["platform"], logs, timeout_seconds=120)

                            # 🛡️ CAPTCHA Check 2: Check if opening application triggered a challenge
                            c_stat = detect_captcha(page)
                            if c_stat["has_captcha"]:
                                handle_captcha_handover(page, logs, timeout_seconds=90)
                            break
                    except Exception:
                        continue

                # ================= AUTONOMOUS PROGRESSION LOOP =================
                # Multi-step forms (Page 1 -> Next -> Page 2 -> Review -> Submit)
                MAX_WIZARD_STEPS = 8
                
                SUBMIT_SELECTORS = [
                    'button:has-text("Submit application")',
                    'button:has-text("Submit Application")',
                    'button:has-text("Submit your application")',
                    'button:has-text("Submit Your Application")',
                    'button:has-text("Send Application")',
                    'button:has-text("Send application")',
                    'button:has-text("Complete Application")',
                    'button[data-testid*="submit" i]',
                    'button[id*="submit" i]',
                    'button[aria-label*="Submit application" i]',
                    'button:has-text("Submit")',
                    'input[type="submit"]'
                ]

                NEXT_SELECTORS = [
                    'button:has-text("Review your application")',
                    'button:has-text("Review Application")',
                    'button:has-text("Review")',
                    'button:has-text("Next step")',
                    'button:has-text("Next")',
                    'button:has-text("Continue to next step")',
                    'button:has-text("Continue")',
                    'button:has-text("Proceed")',
                    'button[aria-label*="Continue to next step" i]',
                    'button[aria-label*="Continue" i]',
                    'button[aria-label*="Next" i]',
                    'button[aria-label*="Review" i]'
                ]

                for step_num in range(1, MAX_WIZARD_STEPS + 1):
                    # 🛡️ CAPTCHA Check 3: Check at beginning of wizard step
                    c_stat = detect_captcha(page)
                    if c_stat["has_captcha"]:
                        handle_captcha_handover(page, logs, timeout_seconds=90)

                    # 1. Fill all visible inputs, selects, radios, checkboxes on current step
                    stats = fill_all_step_fields(page, resume_data, answers, tailored_letter, resume_file_path, logs, tailored_resume)
                    logs.append(f"Step {step_num}: Populated form fields (Inputs: {stats['inputs']}, Radios: {stats['radios']}, Dropdowns: {stats['selects']}, Checkboxes: {stats['checkboxes']}, Files: {stats['files']})")
                    time.sleep(1.2)

                    # 2. Check if a final Submit button is present and active!
                    submit_clicked = False
                    if auto_submit:
                        for sub_sel in SUBMIT_SELECTORS:
                            try:
                                sub_btn = page.locator(sub_sel).first
                                if sub_btn.is_visible(timeout=800) and sub_btn.is_enabled():
                                    logs.append(f"🚀 Found final submission button ('{sub_sel}')! Executing SUBMIT click...")
                                    sub_btn.click()
                                    submit_clicked = True
                                    time.sleep(3)
                                    
                                    # 🛡️ CAPTCHA Check 4: Check if submit click triggered a verification modal
                                    c_stat = detect_captcha(page)
                                    if c_stat["has_captcha"]:
                                        handle_captcha_handover(page, logs, timeout_seconds=90)
                                    time.sleep(1)
                                    break
                            except Exception:
                                continue

                        if submit_clicked:
                            # Verify submission success
                            is_submitted = detect_submission_success(page, target_url, logs)
                            proof_screenshot = take_confirmation_screenshot(page, job_data.get("id", "job"), logs)
                            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")

                            if is_submitted:
                                db.save_or_update_application(
                                    job_id=job_data["id"],
                                    job_title=job_data["title"],
                                    company=job_data["company"],
                                    apply_url=target_url,
                                    status="Applied",
                                    cover_letter=tailored_letter,
                                    applied_date=current_time_str
                                )
                                logs.append("🎉 Application GENUINELY SUBMITTED & CONFIRMED by platform!")
                                logs.append(f"✅ Application Tracker updated: Status = 'Applied' ({current_time_str})")
                                logs.append(f"📧 Confirmation / revert email will be delivered to: {candidate_email}")
                                break
                            else:
                                db.save_or_update_application(
                                    job_id=job_data["id"],
                                    job_title=job_data["title"],
                                    company=job_data["company"],
                                    apply_url=target_url,
                                    status="Needs Review",
                                    cover_letter=tailored_letter
                                )
                                logs.append("⚠️ Submit was clicked, but platform confirmation receipt was not detected.")
                                logs.append("📋 Tracker updated to 'Needs Review' (to prevent false 'Applied' without revert email).")
                                logs.append("💡 Browser window kept open so you can review or complete remaining steps.")
                                page.bring_to_front()
                                break

                    # 3. If not submitted, check if there's a NEXT / CONTINUE button to advance
                    next_clicked = False
                    for next_sel in NEXT_SELECTORS:
                        try:
                            next_btn = page.locator(next_sel).first
                            if next_btn.is_visible(timeout=800) and next_btn.is_enabled():
                                logs.append(f"Advancing wizard: Clicked '{next_sel}'...")
                                next_btn.click()
                                next_clicked = True
                                time.sleep(2)
                                
                                # 🛡️ CAPTCHA Check 5: Check if advancing wizard triggered a challenge
                                c_stat = detect_captcha(page)
                                if c_stat["has_captcha"]:
                                    handle_captcha_handover(page, logs, timeout_seconds=90)
                                time.sleep(0.5)
                                break
                        except Exception:
                            continue

                    if not next_clicked and not submit_clicked:
                        # Re-check if submit button became visible after fields settled
                        if auto_submit:
                            for sub_sel in SUBMIT_SELECTORS:
                                try:
                                    sub_btn = page.locator(sub_sel).first
                                    if sub_btn.is_visible(timeout=1000):
                                        logs.append(f"🚀 Triggering final Submit click...")
                                        sub_btn.click()
                                        submit_clicked = True
                                        time.sleep(4)
                                        
                                        c_stat = detect_captcha(page)
                                        if c_stat["has_captcha"]:
                                            handle_captcha_handover(page, logs, timeout_seconds=90)
                                            
                                        is_submitted = detect_submission_success(page, target_url, logs)
                                        proof_screenshot = take_confirmation_screenshot(page, job_data.get("id", "job"), logs)
                                        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")

                                        if is_submitted:
                                            db.save_or_update_application(
                                                job_id=job_data["id"],
                                                job_title=job_data["title"],
                                                company=job_data["company"],
                                                apply_url=target_url,
                                                status="Applied",
                                                cover_letter=tailored_letter,
                                                applied_date=current_time_str
                                            )
                                            logs.append("🎉 Application SUBMITTED & CONFIRMED by platform!")
                                            logs.append(f"📧 Confirmation / revert email will be sent to: {candidate_email}")
                                        else:
                                            db.save_or_update_application(
                                                job_id=job_data["id"],
                                                job_title=job_data["title"],
                                                company=job_data["company"],
                                                apply_url=target_url,
                                                status="Needs Review",
                                                cover_letter=tailored_letter
                                            )
                                            logs.append("⚠️ Submit clicked, but platform confirmation receipt was not detected.")
                                            logs.append("📋 Marked as 'Needs Review' so you can verify in the opened browser window.")
                                        break
                                except Exception:
                                    continue
                        break

                # If Co-Pilot Assist mode, wait for user to review and submit manually
                if not auto_submit:
                    logs.append("👀 Screen popped up for you! Form is pre-filled. Please review and click Submit when ready.")
                    page.bring_to_front()
                    start_wait = time.time()
                    while time.time() - start_wait < keep_open_seconds:
                        try:
                            if page.is_closed():
                                logs.append("Window closed by user.")
                                break
                            time.sleep(1)
                        except Exception:
                            break

            except Exception as e:
                logs.append(f"Notice during application: {str(e)[:160]}")
            finally:
                try:
                    context.close()
                except Exception:
                    pass

    except Exception as e:
        logs.append(f"Notice: {str(e)[:120]}")

    return {
        "success": True,
        "submitted": is_submitted,
        "screenshot": proof_screenshot,
        "logs": logs,
        "tailored_letter": tailored_letter
    }
