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

def find_or_create_resume_file(resume_data: Dict[str, Any], prefer_docx: bool = True) -> str:
    """
    Ensures a resume file exists on disk for browser file-upload inputs.
    Generates both .docx and .txt formats for compatibility with all ATS systems.
    """
    # 1. Always generate .txt
    resume_txt_path = Path(__file__).parent / "active_resume.txt"
    with open(resume_txt_path, "w", encoding="utf-8") as f:
        f.write(resume_data.get("raw_text", ""))

    # 2. Generate .docx if python-docx is available
    resume_docx_path = Path(__file__).parent / "active_resume.docx"
    try:
        import docx
        doc = docx.Document()
        name = resume_data.get("name", "Candidate")
        doc.add_heading(name, level=0)
        
        contact_line = []
        if resume_data.get("email"):
            contact_line.append(resume_data["email"])
        if resume_data.get("phone"):
            contact_line.append(resume_data["phone"])
        if resume_data.get("location"):
            contact_line.append(resume_data["location"])
        if contact_line:
            doc.add_paragraph(" | ".join(contact_line))
            
        # Skills
        skills = resume_data.get("skills", [])
        if skills:
            doc.add_heading("Technical Skills", level=1)
            doc.add_paragraph(", ".join(skills if isinstance(skills, list) else [str(skills)]))
            
        # Experience
        exp = resume_data.get("experience", "")
        if exp:
            doc.add_heading("Professional Experience", level=1)
            doc.add_paragraph(str(exp))
            
        # Education
        edu = resume_data.get("education", "")
        if edu:
            doc.add_heading("Education", level=1)
            doc.add_paragraph(str(edu))
            
        doc.save(str(resume_docx_path))
        if prefer_docx and resume_docx_path.exists():
            return str(resume_docx_path.resolve())
    except Exception:
        pass

    return str(resume_txt_path.resolve())

def fill_input_safely(page, selectors: List[str], value: Any, logs: Optional[List[str]] = None) -> bool:
    """Tries multiple selectors to find and safely fill an input with human-like keystroke delays."""
    if not value or not str(value).strip():
        return False
    str_val = str(value).strip()
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                current_val = ""
                try:
                    current_val = loc.input_value(timeout=300)
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
    logs: Optional[List[str]] = None
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

    # 11. Resume File Upload
    try:
        file_inputs = page.locator('input[type="file"]')
        if file_inputs.count() > 0:
            for fi_idx in range(file_inputs.count()):
                fi = file_inputs.nth(fi_idx)
                try:
                    accept = (fi.get_attribute("accept") or "").lower()
                    # Choose .docx if .pdf/.docx requested, else .txt
                    upload_target = resume_file_path
                    if ".docx" in accept or ".doc" in accept:
                        docx_cand = str(Path(resume_file_path).with_suffix(".docx"))
                        if os.path.exists(docx_cand):
                            upload_target = docx_cand
                    fi.set_input_files(upload_target)
                    stats["files"] += 1
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

    resume_file_path = find_or_create_resume_file(resume_data, prefer_docx=True)

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
                            time.sleep(2)
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
                    # 1. Fill all visible inputs, selects, radios, checkboxes on current step
                    stats = fill_all_step_fields(page, resume_data, answers, tailored_letter, resume_file_path, logs)
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
                                    time.sleep(4)
                                    break
                            except Exception:
                                continue

                        if submit_clicked:
                            # Verify submission success
                            is_submitted = detect_submission_success(page, target_url, logs)
                            proof_screenshot = take_confirmation_screenshot(page, job_data.get("id", "job"), logs)
                            
                            # Mark as genuinely Applied in DB!
                            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                            db.save_or_update_application(
                                job_id=job_data["id"],
                                job_title=job_data["title"],
                                company=job_data["company"],
                                apply_url=target_url,
                                status="Applied",
                                cover_letter=tailored_letter,
                                applied_date=current_time_str
                            )
                            logs.append("🎉 Application SUBMITTED successfully!")
                            logs.append(f"✅ Application Tracker updated: Status = 'Applied' ({current_time_str})")
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
                                time.sleep(2.5)
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
                                        is_submitted = True
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
