import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).parent / "job_agent.db"

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        skills TEXT, -- JSON list
        experience TEXT,
        education TEXT,
        raw_text TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        source TEXT,
        title TEXT,
        company TEXT,
        tags TEXT, -- JSON list
        location TEXT,
        salary TEXT,
        url TEXT,
        apply_url TEXT,
        description TEXT,
        published_date TEXT,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT,
        job_title TEXT,
        company TEXT,
        apply_url TEXT,
        match_score REAL DEFAULT 0.0,
        status TEXT DEFAULT 'Saved', -- 'Saved', 'Applied', 'Interviewing', 'Offer', 'Rejected'
        cover_letter TEXT,
        notes TEXT,
        applied_date TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_hunter_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        query TEXT,
        location TEXT,
        sources TEXT,
        total_scanned INTEGER DEFAULT 0,
        new_found INTEGER DEFAULT 0,
        high_matches_found INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Completed',
        summary_notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_hunter_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        job_id TEXT UNIQUE,
        job_title TEXT,
        company TEXT,
        location TEXT,
        source TEXT,
        url TEXT,
        apply_url TEXT,
        match_score REAL DEFAULT 0.0,
        matched_skills TEXT,
        missing_skills TEXT,
        status TEXT DEFAULT 'Queued', -- 'Queued', 'Applied', 'Dismissed'
        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        applied_at TIMESTAMP
    )
    """)

    conn.commit()
    
    # Safe migration: add location column to resumes if missing
    try:
        cursor.execute("ALTER TABLE resumes ADD COLUMN location TEXT")
        conn.commit()
    except Exception:
        pass

    # Safe migration: sync github_url if portfolio_url contains github and github_url is empty
    try:
        cursor.execute("SELECT value FROM settings WHERE key = 'github_url'")
        gh_row = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key = 'portfolio_url'")
        pf_row = cursor.fetchone()
        
        gh_val = gh_row[0].strip() if gh_row and gh_row[0] else ""
        pf_val = pf_row[0].strip() if pf_row and pf_row[0] else ""
        
        if (not gh_val or gh_val.rstrip("/") in ["https://github.com", "http://github.com"]) and "github.com/" in pf_val.lower():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('github_url', ?)", (pf_val,))
            conn.commit()
    except Exception:
        pass

    # Auto-seed default candidate profile (Alex Morgan) if no active resume exists
    try:
        cursor.execute("SELECT id FROM resumes WHERE is_active = 1 LIMIT 1")
        active = cursor.fetchone()
        if not active:
            cursor.execute("SELECT id FROM resumes WHERE name LIKE '%Alex Morgan%' ORDER BY id DESC LIMIT 1")
            alex = cursor.fetchone()
            if alex:
                cursor.execute("UPDATE resumes SET is_active = 0")
                cursor.execute("UPDATE resumes SET is_active = 1 WHERE id = ?", (alex[0],))
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('user_location', 'San Francisco, CA')")
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('linkedin_url', 'https://linkedin.com/in/alexmorgan-dev')")
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('github_url', 'https://github.com/alexmorgan-dev')")
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('portfolio_url', 'https://github.com/alexmorgan-dev')")
                conn.commit()
            else:
                sample_path = Path(__file__).parent / "sample_resume.txt"
                if sample_path.exists():
                    import resume_parser
                    with open(sample_path, "r", encoding="utf-8") as f:
                        sample_raw = f.read()
                    parsed = resume_parser.parse_resume_text(sample_raw, "sample_resume.txt")
                    cursor.execute("UPDATE resumes SET is_active = 0")
                    cursor.execute("""
                        INSERT INTO resumes (name, email, phone, skills, experience, education, raw_text, location, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        parsed["name"],
                        parsed["email"],
                        parsed["phone"],
                        json.dumps(parsed["skills"]),
                        parsed["experience"],
                        parsed["education"],
                        parsed["raw_text"],
                        parsed.get("location", "San Francisco, CA")
                    ))
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('user_location', ?)", (parsed.get("location", "San Francisco, CA"),))
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('linkedin_url', ?)", (parsed.get("links", {}).get("linkedin", "https://linkedin.com/in/alexmorgan-dev"),))
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('github_url', ?)", (parsed.get("links", {}).get("github", "https://github.com/alexmorgan-dev"),))
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('portfolio_url', ?)", (parsed.get("links", {}).get("github", "https://github.com/alexmorgan-dev"),))
                    conn.commit()
    except Exception:
        pass

    conn.close()

# Resume operations
def save_resume(name: str, email: str, phone: str, skills: List[str], experience: str, education: str, raw_text: str, location: str = "") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    # Mark old resumes as inactive
    cursor.execute("UPDATE resumes SET is_active = 0")
    try:
        cursor.execute("""
            INSERT INTO resumes (name, email, phone, skills, experience, education, raw_text, location, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (name, email, phone, json.dumps(skills), experience, education, raw_text, location))
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE resumes ADD COLUMN location TEXT")
        except Exception:
            pass
        cursor.execute("""
            INSERT INTO resumes (name, email, phone, skills, experience, education, raw_text, location, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (name, email, phone, json.dumps(skills), experience, education, raw_text, location))
        
    resume_id = cursor.lastrowid
    conn.commit()
    conn.close()
    if location:
        set_setting("user_location", location)
    return resume_id

def get_active_resume() -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resumes WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        try:
            data['skills'] = json.loads(data['skills']) if data['skills'] else []
        except Exception:
            data['skills'] = []
        return data
    return None

def update_resume_profile(resume_id: int, name: str, email: str, phone: str, skills: List[str], location: str = ""):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE resumes 
            SET name = ?, email = ?, phone = ?, skills = ?, location = ?
            WHERE id = ?
        """, (name, email, phone, json.dumps(skills), location, resume_id))
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE resumes ADD COLUMN location TEXT")
        except Exception:
            pass
        cursor.execute("""
            UPDATE resumes 
            SET name = ?, email = ?, phone = ?, skills = ?, location = ?
            WHERE id = ?
        """, (name, email, phone, json.dumps(skills), location, resume_id))
    conn.commit()
    conn.close()
    if location:
        set_setting("user_location", location)

# Job operations
def save_jobs(jobs_list: List[Dict[str, Any]]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    count = 0
    for j in jobs_list:
        try:
            cursor.execute("""
                INSERT INTO jobs (id, source, title, company, tags, location, salary, url, apply_url, description, published_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    company = excluded.company,
                    tags = excluded.tags,
                    location = excluded.location,
                    salary = excluded.salary,
                    url = excluded.url,
                    apply_url = excluded.apply_url,
                    description = excluded.description,
                    published_date = excluded.published_date,
                    fetched_at = CURRENT_TIMESTAMP
            """, (
                j['id'],
                j.get('source', 'RemoteOK'),
                j.get('title', ''),
                j.get('company', ''),
                json.dumps(j.get('tags', [])),
                j.get('location', 'Remote'),
                j.get('salary', ''),
                j.get('url', ''),
                j.get('apply_url', ''),
                j.get('description', ''),
                j.get('published_date', '')
            ))
            count += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return count

def _clean_db_tags(raw: Any) -> List[str]:
    if not raw:
        return []
    flat = []
    if isinstance(raw, (list, tuple, set)):
        for x in raw:
            if isinstance(x, (list, tuple, set)):
                for sub in x:
                    if sub and str(sub).strip():
                        flat.append(str(sub).strip())
            elif x and str(x).strip():
                flat.append(str(x).strip())
    elif isinstance(raw, str):
        flat = [s.strip() for s in raw.split(',') if s.strip()]
    return flat

def get_all_jobs() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY fetched_at DESC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    seen = set()
    for r in rows:
        d = dict(r)
        key = (d.get('title', '').strip().lower(), d.get('company', '').strip().lower())
        if key in seen:
            continue
        seen.add(key)
        try:
            raw_tags = json.loads(d['tags']) if d['tags'] else []
            d['tags'] = _clean_db_tags(raw_tags)
        except Exception:
            d['tags'] = []
        result.append(d)
    return result

def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            raw_tags = json.loads(d['tags']) if d['tags'] else []
            d['tags'] = _clean_db_tags(raw_tags)
        except Exception:
            d['tags'] = []
        return d
    return None

# Application tracking operations
def save_or_update_application(
    job_id: str, 
    job_title: str, 
    company: str, 
    apply_url: str, 
    match_score: float = 0.0, 
    status: str = 'Saved',
    cover_letter: str = '',
    notes: str = '',
    applied_date: str = ''
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE applications 
            SET job_title = ?, company = ?, apply_url = ?, match_score = ?, status = ?, 
                cover_letter = CASE WHEN ? != '' THEN ? ELSE cover_letter END,
                notes = CASE WHEN ? != '' THEN ? ELSE notes END,
                applied_date = CASE WHEN ? != '' THEN ? ELSE applied_date END,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
        """, (job_title, company, apply_url, match_score, status, cover_letter, cover_letter, notes, notes, applied_date, applied_date, job_id))
        app_id = existing[0]
    else:
        cursor.execute("""
            INSERT INTO applications (job_id, job_title, company, apply_url, match_score, status, cover_letter, notes, applied_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, job_title, company, apply_url, match_score, status, cover_letter, notes, applied_date))
        app_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return app_id

def get_applications(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute("SELECT * FROM applications WHERE status = ? ORDER BY updated_at DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM applications ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_application_by_job_id(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_application(app_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()

def get_tracked_job_identifiers():
    """Returns (set of job_ids, set of (title.lower(), company.lower()) tuples) currently tracked in applications."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT job_id, job_title, company FROM applications")
    rows = cursor.fetchall()
    conn.close()
    
    ids = set()
    keys = set()
    for r in rows:
        if r["job_id"]:
            ids.add(str(r["job_id"]))
        if r["job_title"] and r["company"]:
            keys.add((str(r["job_title"]).strip().lower(), str(r["company"]).strip().lower()))
    return ids, keys


# Settings operations
def set_setting(key: str, value: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def get_candidate_links(resume_data: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Intelligently resolves and synchronizes LinkedIn, GitHub, and Portfolio URLs
    across database settings and parsed candidate resumes.
    """
    gh = get_setting("github_url", "").strip()
    li = get_setting("linkedin_url", "").strip()
    pf = get_setting("portfolio_url", "").strip()

    # Fallback to resume_data if available
    if resume_data and isinstance(resume_data, dict):
        raw = resume_data.get("raw_text", "")
        if raw:
            try:
                import resume_parser
                extracted = resume_parser.extract_links(raw)
                if not gh and extracted.get("github"):
                    gh = extracted["github"]
                if not li and extracted.get("linkedin"):
                    li = extracted["linkedin"]
                if not pf and extracted.get("portfolio"):
                    pf = extracted["portfolio"]
            except Exception:
                pass

    # If pf contains a valid github.com URL and gh is empty or bare placeholder
    if pf and "github.com/" in pf.lower() and (not gh or gh.rstrip("/") in ["https://github.com", "http://github.com"]):
        gh = pf
        set_setting("github_url", gh)

    # Clean bare placeholder github URLs
    if gh and gh.rstrip("/") in ["https://github.com", "http://github.com"]:
        if pf and "github.com/" in pf.lower():
            gh = pf
        else:
            gh = ""

    return {
        "github": gh,
        "linkedin": li,
        "portfolio": pf
    }

# ================= AUTO-HUNTER OPERATIONS =================

def record_hunter_run(
    query: str,
    location: str,
    sources: List[str],
    total_scanned: int,
    new_found: int,
    high_matches_found: int,
    status: str = 'Completed',
    summary_notes: str = ''
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    sources_str = ", ".join(sources) if isinstance(sources, list) else str(sources)
    cursor.execute("""
        INSERT INTO auto_hunter_runs (query, location, sources, total_scanned, new_found, high_matches_found, status, summary_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (query, location, sources_str, total_scanned, new_found, high_matches_found, status, summary_notes))
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id

def get_hunter_runs(limit: int = 10) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM auto_hunter_runs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_to_hunter_queue(
    job: Dict[str, Any],
    match_score: float,
    matched_skills: List[str],
    missing_skills: List[str],
    run_id: Optional[int] = None
) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    m_skills_json = json.dumps(matched_skills or [])
    miss_skills_json = json.dumps(missing_skills or [])
    
    job_id = str(job.get("id", ""))
    job_title = str(job.get("title", "Role"))
    company = str(job.get("company", "Company"))
    location = str(job.get("location", "Remote / On-site"))
    source = str(job.get("source", "Web"))
    url = str(job.get("url", ""))
    apply_url = str(job.get("apply_url") or job.get("url", ""))

    cursor.execute("""
        INSERT INTO auto_hunter_queue (
            run_id, job_id, job_title, company, location, source, url, apply_url,
            match_score, matched_skills, missing_skills, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Queued')
        ON CONFLICT(job_id) DO UPDATE SET
            run_id = excluded.run_id,
            match_score = excluded.match_score,
            matched_skills = excluded.matched_skills,
            missing_skills = excluded.missing_skills
    """, (run_id, job_id, job_title, company, location, source, url, apply_url, match_score, m_skills_json, miss_skills_json))
    
    conn.commit()
    conn.close()
    return True

def get_hunter_queue(status: Optional[str] = 'Queued', min_score: float = 0.0) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("""
            SELECT * FROM auto_hunter_queue 
            WHERE status = ? AND match_score >= ? 
            ORDER BY match_score DESC, discovered_at DESC
        """, (status, min_score))
    else:
        cursor.execute("""
            SELECT * FROM auto_hunter_queue 
            WHERE match_score >= ? 
            ORDER BY match_score DESC, discovered_at DESC
        """, (min_score,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["matched_skills"] = json.loads(d["matched_skills"]) if d.get("matched_skills") else []
        except Exception:
            d["matched_skills"] = []
        try:
            d["missing_skills"] = json.loads(d["missing_skills"]) if d.get("missing_skills") else []
        except Exception:
            d["missing_skills"] = []
        results.append(d)
    return results

def update_hunter_queue_status(job_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status == 'Applied':
        cursor.execute("UPDATE auto_hunter_queue SET status = ?, applied_at = CURRENT_TIMESTAMP WHERE job_id = ?", (status, job_id))
    else:
        cursor.execute("UPDATE auto_hunter_queue SET status = ? WHERE job_id = ?", (status, job_id))
    conn.commit()
    conn.close()

def dismiss_hunter_queue_item(job_id: str):
    update_hunter_queue_status(job_id, 'Dismissed')

def clear_hunter_queue(status: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("DELETE FROM auto_hunter_queue WHERE status = ?", (status,))
    else:
        cursor.execute("DELETE FROM auto_hunter_queue")
    conn.commit()
    conn.close()

def get_hunter_stats() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM auto_hunter_queue WHERE status = 'Queued'")
    queued_cnt = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM auto_hunter_queue WHERE status = 'Applied'")
    applied_cnt = cursor.fetchone()[0]
    cursor.execute("SELECT MAX(match_score) FROM auto_hunter_queue WHERE status = 'Queued'")
    top_score_row = cursor.fetchone()
    top_score = top_score_row[0] if top_score_row and top_score_row[0] is not None else 0.0
    cursor.execute("SELECT * FROM auto_hunter_runs ORDER BY id DESC LIMIT 1")
    last_run_row = cursor.fetchone()
    last_run = dict(last_run_row) if last_run_row else None
    conn.close()
    return {
        "queued_count": queued_cnt,
        "applied_count": applied_cnt,
        "top_score": top_score,
        "last_run": last_run
    }

# Initialize DB on load
init_db()
