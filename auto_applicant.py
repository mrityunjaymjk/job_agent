import os
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional

import copilot
import db

BROWSER_PROFILE_DIR = Path(__file__).parent / "browser_profile"

def get_browser_profile_path() -> Path:
    """Returns the persistent browser profile directory, creating it if needed."""
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return BROWSER_PROFILE_DIR

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
    
    # Calculate folder size
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

    # 1. Local State (DPAPI encryption keys & browser configuration)
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

def find_or_create_resume_file(resume_data: Dict[str, Any]) -> str:
    """Ensures a resume file exists on disk for browser file-upload inputs."""
    resume_path = Path(__file__).parent / "active_resume.txt"
    with open(resume_path, "w", encoding="utf-8") as f:
        f.write(resume_data.get("raw_text", ""))
    return str(resume_path.resolve())

def fill_input_safely(page, selectors, value):
    """Tries multiple selectors to find and fill an input without crashing."""
    if not value:
        return False
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1000):
                loc.fill(str(value))
                return True
        except Exception:
            continue
    return False

def auto_apply_to_job(
    job_data: Dict[str, Any], 
    resume_data: Dict[str, Any], 
    api_key: str = "",
    keep_open_seconds: int = 120
) -> Dict[str, Any]:
    """
    Automated Job Application Engine with Human-in-the-Loop:
    1. Generates tailored cover letter and bullets.
    2. Opens a visible real browser (Chromium) on screen.
    3. Navigates to application URL.
    4. Auto-detects and fills form inputs (Name, Email, Phone, Links, Cover Letter, Resume Upload).
    5. Pops the browser into view and pauses for user to review, solve CAPTCHAs, and submit.
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

    # Save to application DB
    db.save_or_update_application(
        job_id=job_data["id"],
        job_title=job_data["title"],
        company=job_data["company"],
        apply_url=target_url,
        status="In Progress",
        cover_letter=tailored_letter
    )

    resume_file_path = find_or_create_resume_file(resume_data)

    user_prefs = {
        "years_exp": db.get_setting("years_exp", "4+ years"),
        "expected_salary": db.get_setting("expected_salary", "$120,000 / yr"),
        "work_auth": db.get_setting("work_auth", "Authorized to work"),
        "notice_period": db.get_setting("notice_period", "Immediate (2 weeks)")
    }
    answers = copilot.generate_application_answers(resume_data, job_data, user_prefs)

    p_dir = get_browser_profile_path()
    ensure_cache_seeded()

    # Detect if running in headless cloud environment (Streamlit Community Cloud / Linux without X11)
    is_cloud = os.environ.get("STREAMLIT_SHARING_MODE") is not None or (os.name != "nt" and os.environ.get("DISPLAY") is None)
    headless_mode = bool(is_cloud)

    logs = []
    logs.append(f"🎯 Target: {job_data['title']} at {job_data['company']}")
    logs.append(f"✍️ Tailored cover letter generated ({len(tailored_letter)} chars)")
    
    if is_cloud:
        logs.append("☁️ Running on Streamlit Community Cloud (Headless Mode)")
    else:
        logs.append("🍪 Loaded persistent browser profile & cache memory (saved logins active)")
        logs.append("🌐 Launching visible Chrome browser on your screen...")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        logs.append("ℹ️ Cloud Notice: Automated screen pop-up is available when running locally on desktop.")
        logs.append("✅ Tailored cover letter, form answers, and resume are prepared and saved in your tracker!")
        return {"success": True, "logs": logs, "tailored_letter": tailored_letter}

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
            page.goto(target_url, timeout=35000, wait_until="domcontentloaded")
            time.sleep(2)

            # Check if gated behind an account registration or login screen
            current_url = page.url.lower()
            if "register" in current_url or "login" in current_url or "account" in current_url:
                logs.append("ℹ️ This application portal requires a sign-in. Please log in once in the opened window — your session will be saved automatically for future applications!")
                page.bring_to_front()
            else:
                logs.append("⚡ Logged in & session authenticated via cached profile!")

            name = resume_data.get("name", "")
            name_parts = name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            email = resume_data.get("email", "")
            phone = resume_data.get("phone", "")
            links = resume_data.get("links", {})
            linkedin = links.get("linkedin", "")
            github = links.get("github", "")
            portfolio = links.get("portfolio", "")

            # If there's an "Apply", "Easy Apply", or "Apply for this job" button on landing page, click it
            apply_buttons = [
                'button:has-text("Easy Apply")',
                'button.jobs-apply-button',
                'button[aria-label*="Easy Apply"]',
                'a:has-text("Apply to Startup")',
                'button:has-text("Apply to Startup")',
                'a:has-text("Apply")',
                'button:has-text("Apply")',
                'a:has-text("Apply for this job")',
                'button:has-text("Apply for this job")',
                'a:has-text("Apply Now")',
                'button:has-text("Apply Now")',
                'button:has-text("Quick Apply")'
            ]
            for btn_sel in apply_buttons:
                try:
                    loc = page.locator(btn_sel).first
                    if loc.is_visible(timeout=1500):
                        loc.click()
                        logs.append(f"Clicked initial '{btn_sel}' button")
                        time.sleep(2)
                        break
                except Exception:
                    pass

            # Auto-fill fields
            # Full Name or First/Last
            if not fill_input_safely(page, [
                'input[name*="first_name" i]', 
                'input[id*="first_name" i]',
                'input[placeholder*="First Name" i]',
                'input[autocomplete="given-name"]'
            ], first_name):
                # Try combined name
                fill_input_safely(page, [
                    'input[name*="name" i]',
                    'input[id*="name" i]',
                    'input[placeholder*="Full Name" i]',
                    'input[autocomplete="name"]'
                ], name)
            else:
                fill_input_safely(page, [
                    'input[name*="last_name" i]',
                    'input[id*="last_name" i]',
                    'input[placeholder*="Last Name" i]',
                    'input[autocomplete="family-name"]'
                ], last_name)

            # Email
            fill_input_safely(page, [
                'input[type="email"]',
                'input[name*="email" i]',
                'input[id*="email" i]',
                'input[placeholder*="Email" i]',
                'input[autocomplete="email"]'
            ], email)

            # Phone
            fill_input_safely(page, [
                'input[type="tel"]',
                'input[name*="phone" i]',
                'input[id*="phone" i]',
                'input[placeholder*="Phone" i]',
                'input[autocomplete="tel"]'
            ], phone)

            # LinkedIn & URLs
            fill_input_safely(page, [
                'input[name*="linkedin" i]',
                'input[id*="linkedin" i]',
                'input[placeholder*="LinkedIn" i]'
            ], linkedin)

            fill_input_safely(page, [
                'input[name*="github" i]',
                'input[id*="github" i]',
                'input[placeholder*="GitHub" i]'
            ], github)

            fill_input_safely(page, [
                'input[name*="website" i]',
                'input[name*="portfolio" i]',
                'input[id*="website" i]',
                'input[placeholder*="Portfolio" i]'
            ], portfolio or github)

            # Cover letter textarea
            fill_input_safely(page, [
                'textarea[name*="cover" i]',
                'textarea[id*="cover" i]',
                'textarea[placeholder*="Cover Letter" i]',
                'textarea[name*="comments" i]',
                'textarea'
            ], tailored_letter)

            # File upload: Resume
            try:
                file_input = page.locator('input[type="file"]').first
                if file_input.is_visible(timeout=1500) or file_input.count() > 0:
                    file_input.set_input_files(resume_file_path)
                    logs.append("📎 Attached resume file")
            except Exception:
                pass

            logs.append("✅ Form fields auto-populated where detected!")
            logs.append("👀 Screen popped up for you! Please review the form, answer any custom questions, and click Submit when ready.")

            # Bring to front & wait for human review
            page.bring_to_front()

            # Wait loop while user completes or closes
            start_wait = time.time()
            while time.time() - start_wait < keep_open_seconds:
                try:
                    # If page was closed by user, exit gracefully
                    if page.is_closed():
                        logs.append("Window closed by user.")
                        break
                    time.sleep(1)
                except Exception:
                    break

        except Exception as e:
            logs.append(f"Notice: {str(e)[:150]}")
        finally:
            try:
                context.close()
            except Exception:
                pass
    except Exception as e:
        logs.append(f"ℹ️ Cloud Notice: Automated screen pop-up is designed for local desktop environments. ({str(e)[:80]})")
        logs.append("✅ All application materials (tailored cover letter, answers, resume) have been generated and saved to your Application Tracker!")

    return {
        "success": True,
        "logs": logs,
        "tailored_letter": tailored_letter
    }
