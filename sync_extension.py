"""
Job Agent - Extension Profile & Resume Synchronizer
Exports current profile & resume data from local SQLite database and files to extension/profile_data.json
"""

import os
import sys
import json
import base64
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import db

def sync_profile() -> dict:
    r = db.get_active_resume() or {}
    name = r.get("name") or db.get_setting("user_name", "Mrityunjay Kumar")
    parts = name.split()
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    links = db.get_candidate_links(r)

    # Clean name for filename
    safe_name = name.replace(" ", "_")

    # Locate resume files
    pdf_path = PROJECT_ROOT / "active_resume.pdf"
    docx_path = PROJECT_ROOT / "active_resume.docx"
    txt_path = PROJECT_ROOT / "active_resume.txt"

    resume_b64 = ""
    resume_fn = f"{safe_name}_Resume.pdf"
    resume_mime = "application/pdf"

    if pdf_path.exists():
        with open(pdf_path, "rb") as f:
            resume_b64 = base64.b64encode(f.read()).decode("utf-8")
        resume_fn = f"{safe_name}_Resume.pdf"
        resume_mime = "application/pdf"
    elif docx_path.exists():
        with open(docx_path, "rb") as f:
            resume_b64 = base64.b64encode(f.read()).decode("utf-8")
        resume_fn = f"{safe_name}_Resume.docx"
        resume_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    raw_text = ""
    if txt_path.exists():
        with open(txt_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    elif r.get("experience"):
        raw_text = f"{name}\n{r.get('email', '')}\n\nSUMMARY\n{r.get('experience', '')}\n\nEDUCATION\n{r.get('education', '')}"

    profile = {
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "email": r.get("email") or db.get_setting("user_email", "mrityunjayk456@gmail.com"),
        "phone": r.get("phone") or db.get_setting("user_phone", "+91-7972379015"),
        "location": r.get("location") or db.get_setting("user_location", "Pune, India"),
        "city": (r.get("location") or db.get_setting("user_location", "Pune, India")).split(",")[0].strip(),
        "country": "India",
        "linkedin": links.get("linkedin", ""),
        "github": links.get("github", ""),
        "portfolio": links.get("portfolio", "") or links.get("github", ""),
        "years_exp": db.get_setting("years_exp", "1+ years"),
        "expected_salary": db.get_setting("expected_salary", "$8,400 - $12,000 / yr"),
        "notice_period": db.get_setting("notice_period", "Immediate (2 weeks)"),
        "work_auth": "Yes",
        "sponsorship": "No",
        "skills": r.get("skills", []),
        "experience": r.get("experience", ""),
        "education": r.get("education", ""),

        # Work & Education structured fields for ATS
        "current_company": "Digitalllydrunk Pvt Ltd",
        "current_title": "Backend Developer",
        "experience_start": "Nov 2025",
        "experience_end": "Present",
        "degree": "Post Graduate Diploma in Advanced Computing (PG-DAC)",
        "major": "Advanced Computing / Computer Science",
        "school": "Sunbeam Institute of Information Technology",
        "grad_year": "2025",

        # Resume file payload (for 1-click file upload and download)
        "resume_filename": resume_fn,
        "resume_mime": resume_mime,
        "resume_base64": resume_b64,
        "resume_raw_text": raw_text,

        "gemini_api_key": "",  # Blank for security - users enter this securely in extension popup
        "gemini_model": "gemini-1.5-flash",
        "enable_ai_answers": True,
        "show_floating_pill": True,
        "eeo_gender": "Prefer not to disclose",
        "eeo_race": "Prefer not to disclose",
        "eeo_veteran": "I am not a protected veteran",
        "eeo_disability": "No, I do not have a disability"
    }

    out_file = PROJECT_ROOT / "extension" / "profile_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    print(f"✅ Successfully synced profile & resume ({resume_fn}) to {out_file}")
    return profile

if __name__ == "__main__":
    sync_profile()
