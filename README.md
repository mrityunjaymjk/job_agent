# 💼 AI Job Application Co-Pilot & Matcher

An AI-powered Job Application Assistant designed to parse your resume, fetch real-time tech jobs from top remote boards (RemoteOK, We Work Remotely), calculate ATS match scores and skill gaps, generate tailored cover letters and resume bullets, and track your application pipeline.

---

## 🌟 Key Features

1. **📄 Automated Resume Hub**:
   - Parses `.pdf`, `.docx`, and `.txt` resumes.
   - Extracts contact details, links (LinkedIn, GitHub), and detects over 300+ technical skills.
   - Allows fine-tuning of profile details, target compensation, and notice periods.
   - Includes a 1-click **Sample Developer Profile** for testing.

2. **🔍 Live Remote Job Discovery**:
   - Real-time aggregation from **RemoteOK** and **We Work Remotely** feeds.
   - Search by role keywords (e.g., `Python`, `Full Stack`, `React`, `AI`, `DevOps`).
   - Category filtering (Programming, DevOps & Sysadmin, Design, Product, etc.).
   - Live Resume Match Scoring on every listing with instant color-coded badges.

3. **🎯 Application Co-Pilot & ATS Matcher**:
   - **Match Diagnostics**: Overall percentage score, matched skills vs. missing skill gaps.
   - **Tailored Cover Letters**: 1-click generation tailored to the exact company and position.
   - **Optimized Resume Bullets**: Rephrases your past achievements using the job's targeted keywords.
   - **Recruiter Outreach Notes**: Pre-drafted LinkedIn connection notes (<300 chars) and cold emails.
   - **Pre-filled Application Answers**: Instant answers for standard ATS portal questions (e.g. years of experience, why this company, work authorization).

4. **🤖 Autonomous Auto-Pilot Apply (Human-in-the-Loop)**:
   - **1-Click Auto-Apply**: Automatically generates a tailored cover letter and bullets for the selected job.
   - **Visible Screen Pop**: Launches a real, visible Chromium browser directly on your screen.
   - **Smart Form Auto-Filling**: Automatically identifies and inputs your name, email, phone, LinkedIn, GitHub, portfolio, cover letter, and attaches your resume.
   - **Human-in-the-Loop Pausing**: Whenever custom essay questions, CAPTCHAs, or the final submit button appear, it brings the screen to focus for you to review and click Submit!
   - **Pipeline Tracking**: Automatically marks applied jobs in your tracking database.

5. **📊 Application Pipeline Tracker**:
   - Visual Kanban/Table tracking stages: `Saved` ➔ `Applied` ➔ `Interviewing` ➔ `Offer` ➔ `Rejected`.
   - Stores cover letters and direct application URLs.

5. **⚙️ Dual AI / Local Engine**:
   - **Local Heuristic Mode**: Uses TF-IDF cosine similarity and skill taxonomy for fast, private, 100% free matching.
   - **Google Gemini Mode**: Optional integration with Gemini 2.5 Flash for deep qualitative recruiter feedback, ATS keyword tips, and persuasive writing.

---

## 🚀 Quick Start

### 1. Launch with One Click
Double-click `run_job_agent.bat` in `D:\DEAR MJ` or `job_agent\run.bat`.

### 2. Manual Command Line
Open PowerShell or Command Prompt in `D:\DEAR MJ\job_agent`:
```powershell
.\.venv\Scripts\activate
streamlit run app.py
```
The dashboard will open automatically in your browser at `http://localhost:8501`.

---

## 📁 Project Structure

```
d:\DEAR MJ\
│
├── run_job_agent.bat         # 1-Click launcher
└── job_agent\
    ├── .venv\                # Python virtual environment
    ├── app.py                # Streamlit Web Dashboard
    ├── db.py                 # SQLite storage (resumes, jobs, applications)
    ├── resume_parser.py      # PDF / DOCX / TXT parser & skill extractor
    ├── job_scraper.py        # RemoteOK & We Work Remotely scrapers
    ├── matcher.py            # Local TF-IDF & Gemini match scoring
    ├── copilot.py            # Cover letters, bullets & form pre-fill
    ├── sample_resume.txt     # Demo resume for quick test
    ├── requirements.txt      # Python dependencies
    └── run.bat               # Directory launcher
```

---

## 🔑 Adding a Gemini API Key (Optional)

1. Obtain a free API key at [Google AI Studio](https://aistudio.google.com/).
2. Navigate to **⚙️ Settings** in the Co-Pilot sidebar.
3. Paste your key and click **Save API Key**.
4. Even without a key, the Co-Pilot functions completely offline with TF-IDF keyword matching!
