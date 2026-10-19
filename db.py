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

    conn.commit()
    
    # Safe migration: add location column to resumes if missing
    try:
        cursor.execute("ALTER TABLE resumes ADD COLUMN location TEXT")
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

# Initialize DB on load
init_db()
