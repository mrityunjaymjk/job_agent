import threading
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import db
import job_scraper
import matcher
import auto_applicant

logger = logging.getLogger("auto_hunter")

DEFAULT_SOURCES = ["Naukri", "Indeed", "LinkedIn", "Wellfound", "Jobicy", "RemoteOK", "Remotive", "Arbeitnow"]
DEFAULT_MIN_SCORE = 80.0
DEFAULT_SCHEDULE_TIME = "09:00"

def get_hunter_settings() -> Dict[str, Any]:
    """Retrieves all Auto-Hunter configurations and defaults from SQLite settings."""
    active_resume = db.get_active_resume()
    default_loc = "Pune, India"
    default_query = "Java Developer"
    
    if active_resume:
        if active_resume.get("location"):
            default_loc = active_resume["location"]
        skills = active_resume.get("skills", [])
        if skills and isinstance(skills, list):
            top_tech = [s for s in skills if str(s).lower() in ["java", "spring boot", "react", "python", "node", "backend", "full stack"]][:2]
            if top_tech:
                default_query = ", ".join(top_tech)
            elif skills:
                default_query = str(skills[0])

    enabled = db.get_setting("hunter_enabled", "0") == "1"
    sched_time = db.get_setting("hunter_schedule_time", DEFAULT_SCHEDULE_TIME)
    keywords = db.get_setting("hunter_keywords", default_query)
    location = db.get_setting("hunter_location", default_loc)
    work_mode = db.get_setting("hunter_work_mode", "All")
    
    try:
        min_score = float(db.get_setting("hunter_min_score", str(DEFAULT_MIN_SCORE)))
    except Exception:
        min_score = DEFAULT_MIN_SCORE
        
    sources_raw = db.get_setting("hunter_sources", "")
    if sources_raw:
        try:
            sources = json.loads(sources_raw)
        except Exception:
            sources = [s.strip() for s in sources_raw.split(",") if s.strip()]
    else:
        sources = list(DEFAULT_SOURCES)

    auto_apply = db.get_setting("hunter_auto_apply", "0") == "1"
    last_run_date = db.get_setting("hunter_last_run_date", "")
    last_status = db.get_setting("hunter_last_status", "Never run")

    return {
        "enabled": enabled,
        "schedule_time": sched_time,
        "keywords": keywords,
        "location": location,
        "work_mode": work_mode,
        "min_score": min_score,
        "sources": sources,
        "auto_apply": auto_apply,
        "last_run_date": last_run_date,
        "last_status": last_status
    }

def save_hunter_settings(settings: Dict[str, Any]):
    """Persists Auto-Hunter user preferences."""
    db.set_setting("hunter_enabled", "1" if settings.get("enabled") else "0")
    db.set_setting("hunter_schedule_time", str(settings.get("schedule_time", DEFAULT_SCHEDULE_TIME)))
    db.set_setting("hunter_keywords", str(settings.get("keywords", "")))
    db.set_setting("hunter_location", str(settings.get("location", "")))
    db.set_setting("hunter_work_mode", str(settings.get("work_mode", "All")))
    db.set_setting("hunter_min_score", str(settings.get("min_score", DEFAULT_MIN_SCORE)))
    
    sources = settings.get("sources", DEFAULT_SOURCES)
    db.set_setting("hunter_sources", json.dumps(sources))
    db.set_setting("hunter_auto_apply", "1" if settings.get("auto_apply") else "0")

def run_auto_hunt(
    search_query: str = "",
    location: str = "",
    sources: Optional[List[str]] = None,
    work_mode: str = "All",
    min_match_score: float = 80.0,
    limit_per_source: int = 25,
    auto_apply_top: bool = False,
    api_key: str = "",
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Executes a comprehensive Auto-Hunter run:
    1. Fetches candidate's active resume.
    2. Scrapes fresh openings across selected platforms (Naukri, Indeed, LinkedIn, Wellfound, etc.).
    3. Saves fresh jobs into SQLite.
    4. Evaluates ATS compatibility and skill gaps against active resume.
    5. Filters for scores >= min_match_score (excluding already tracked jobs).
    6. Adds top opportunities to the Auto-Hunter Morning Digest Queue.
    7. Optionally triggers autonomous auto-apply for top matches.
    """
    def log(msg: str):
        logger.info(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    active_resume = db.get_active_resume()
    if not active_resume:
        return {
            "success": False,
            "error": "No active resume found. Please upload or load a profile in 'Resume Profile' first.",
            "total_scanned": 0,
            "new_found": 0,
            "high_matches": 0,
            "queued_jobs": []
        }

    # Resolve keywords and location
    settings = get_hunter_settings()
    query = search_query.strip() or settings.get("keywords", "").strip() or "Java Developer"
    loc = location.strip() or settings.get("location", "").strip() or "Pune, India"
    active_sources = sources or settings.get("sources") or DEFAULT_SOURCES

    log(f"🔍 Starting Auto-Hunt for '{query}' in '{loc}' across {len(active_sources)} platforms...")

    # Step 1: Scrape platforms
    fetched_jobs = job_scraper.fetch_all_jobs(
        sources=active_sources,
        search_query=query,
        location=loc,
        work_mode=work_mode,
        limit_per_source=limit_per_source
    )
    
    total_scanned = len(fetched_jobs)
    log(f"📥 Scraped {total_scanned} candidate positions. Storing in local database...")

    # Step 2: Save to DB
    new_found = db.save_jobs(fetched_jobs)
    log(f"💾 {new_found} brand-new positions added to your local database.")

    # Step 3: Match against candidate resume
    tracked_ids, tracked_keys = db.get_tracked_job_identifiers()
    all_current_jobs = db.get_all_jobs()
    
    log(f"🎯 Evaluating ATS keyword alignment and match scores (Threshold: {min_match_score}%)...")

    high_matches = []
    for job in all_current_jobs:
        j_id = str(job.get("id", ""))
        j_key = (str(job.get("title", "")).strip().lower(), str(job.get("company", "")).strip().lower())

        # Exclude jobs already in Application Tracker
        if (j_id in tracked_ids) or (j_key in tracked_keys):
            continue

        match_info = matcher.compute_local_match(active_resume, job)
        score = match_info.get("score", 0.0)

        if score >= min_match_score:
            matched_skills = match_info.get("matched_skills", [])
            missing_skills = match_info.get("missing_skills", [])

            # Add to Auto-Hunter Queue
            db.add_to_hunter_queue(
                job=job,
                match_score=score,
                matched_skills=matched_skills,
                missing_skills=missing_skills
            )
            high_matches.append({
                "job": job,
                "score": score,
                "matched_skills": matched_skills,
                "missing_skills": missing_skills
            })

    # Sort high matches by score descending
    high_matches.sort(key=lambda x: x["score"], reverse=True)
    high_match_count = len(high_matches)
    
    log(f"✨ Found {high_match_count} high-matching positions (>= {min_match_score}%) ready in queue!")

    # Step 4: Record Hunter Run
    summary_msg = f"Scanned {total_scanned} positions, added {new_found} new, identified {high_match_count} high matches."
    run_id = db.record_hunter_run(
        query=query,
        location=loc,
        sources=active_sources,
        total_scanned=total_scanned,
        new_found=new_found,
        high_matches_found=high_match_count,
        status="Completed",
        summary_notes=summary_msg
    )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    db.set_setting("hunter_last_run_date", datetime.now().strftime("%Y-%m-%d"))
    db.set_setting("hunter_last_status", f"Completed on {now_str}: {high_match_count} high-match positions queued.")

    # Step 5: Optional Autonomous Auto-Apply for Top Matches
    applied_count = 0
    if auto_apply_top and high_matches:
        log("🚀 Autonomous Mode Active: Running batch application for top 3 positions...")
        top_to_apply = high_matches[:3]
        for item in top_to_apply:
            j = item["job"]
            try:
                log(f"🤖 Submitting application to {j.get('company')} for {j.get('title')}...")
                res = auto_applicant.auto_apply_to_job(
                    job_data=j,
                    resume_data=active_resume,
                    api_key=api_key,
                    auto_submit=True,
                    keep_open_seconds=45
                )
                if res.get("submitted"):
                    applied_count += 1
                    db.update_hunter_queue_status(j["id"], "Applied")
            except Exception as e:
                log(f"⚠️ Auto-apply error on {j.get('company')}: {e}")

    log(f"🎉 Auto-Hunt Completed successfully! Run ID: #{run_id}")

    return {
        "success": True,
        "run_id": run_id,
        "total_scanned": total_scanned,
        "new_found": new_found,
        "high_matches": high_match_count,
        "auto_applied": applied_count,
        "top_matches": high_matches[:10]
    }

def batch_auto_apply_queue(
    limit: int = 5,
    api_key: str = "",
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Iterates through the top queued jobs in the Morning Digest and submits applications autonomously.
    """
    queue_items = db.get_hunter_queue(status="Queued")
    if not queue_items:
        return []

    active_resume = db.get_active_resume()
    if not active_resume:
        return []

    results = []
    to_process = queue_items[:limit]
    total = len(to_process)

    for idx, item in enumerate(to_process):
        job_id = item.get("job_id")
        job = db.get_job_by_id(job_id)
        if not job:
            job = {
                "id": job_id,
                "title": item.get("job_title", "Role"),
                "company": item.get("company", "Company"),
                "location": item.get("location", "Remote"),
                "source": item.get("source", "Web"),
                "url": item.get("url", ""),
                "apply_url": item.get("apply_url") or item.get("url", ""),
                "description": f"{item.get('job_title')} at {item.get('company')}"
            }

        company = job.get("company", "Company")
        title = job.get("title", "Role")
        
        if progress_callback:
            progress_callback(idx + 1, total, f"Applying ({idx+1}/{total}): {title} @ {company}...")

        try:
            res = auto_applicant.auto_apply_to_job(
                job_data=job,
                resume_data=active_resume,
                api_key=api_key,
                auto_submit=True,
                keep_open_seconds=60
            )
            submitted = res.get("submitted", False)
            if submitted:
                db.update_hunter_queue_status(job_id, "Applied")
            else:
                db.update_hunter_queue_status(job_id, "Needs Review")

            results.append({
                "job_id": job_id,
                "company": company,
                "title": title,
                "submitted": submitted,
                "logs": res.get("logs", [])
            })
        except Exception as e:
            results.append({
                "job_id": job_id,
                "company": company,
                "title": title,
                "submitted": False,
                "logs": [f"Error during application: {str(e)}"]
            })

    return results

def save_queue_jobs_to_tracker(job_ids: Optional[List[str]] = None) -> int:
    """Saves all or selected queued jobs into the Application Tracker under 'Saved' status."""
    queue_items = db.get_hunter_queue(status="Queued")
    if job_ids:
        queue_items = [q for q in queue_items if q.get("job_id") in job_ids]
        
    saved_count = 0
    for q in queue_items:
        jid = q.get("job_id")
        db.save_or_update_application(
            job_id=jid,
            job_title=q.get("job_title", ""),
            company=q.get("company", ""),
            apply_url=q.get("apply_url") or q.get("url", ""),
            match_score=q.get("match_score", 0.0),
            status="Saved"
        )
        saved_count += 1
    return saved_count


# ================= BACKGROUND SCHEDULER DAEMON =================

class AutoHunterDaemon(threading.Thread):
    """
    Background daemon thread that monitors scheduled morning execution time
    and runs the Auto-Hunter scout automatically without requiring user clicks.
    """
    def __init__(self):
        super().__init__(daemon=True, name="AutoHunterDaemon")
        self._stop_event = threading.Event()
        self._running = False

    def stop(self):
        self._stop_event.set()

    def run(self):
        self._running = True
        logger.info("AutoHunter background daemon started.")
        while not self._stop_event.is_set():
            try:
                settings = get_hunter_settings()
                if settings.get("enabled"):
                    sched_time = settings.get("schedule_time", DEFAULT_SCHEDULE_TIME)
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    now_hm = datetime.now().strftime("%H:%M")

                    # Check if schedule matches and hasn't run today
                    if now_hm >= sched_time and settings.get("last_run_date") != today_str:
                        logger.info(f"AutoHunter scheduled time {sched_time} reached. Launching Morning Hunt...")
                        run_auto_hunt(
                            search_query=settings.get("keywords", ""),
                            location=settings.get("location", ""),
                            sources=settings.get("sources"),
                            work_mode=settings.get("work_mode", "All"),
                            min_match_score=settings.get("min_score", DEFAULT_MIN_SCORE),
                            auto_apply_top=settings.get("auto_apply", False)
                        )
            except Exception as e:
                logger.error(f"Error in AutoHunter daemon loop: {e}")

            # Sleep 30 seconds between checks
            self._stop_event.wait(30)

def ensure_hunter_daemon_running():
    """Starts the background hunter daemon if enabled in settings and not already running."""
    global _DAEMON_INSTANCE
    settings = get_hunter_settings()
    if settings.get("enabled", False):
        if _DAEMON_INSTANCE is None or not _DAEMON_INSTANCE.is_alive():
            _DAEMON_INSTANCE = AutoHunterDaemon()
            _DAEMON_INSTANCE.start()
            logger.info("AutoHunter background daemon activated.")
    else:
        if _DAEMON_INSTANCE is not None and _DAEMON_INSTANCE.is_alive():
            _DAEMON_INSTANCE.stop()
            _DAEMON_INSTANCE = None
            logger.info("AutoHunter background daemon deactivated.")

def get_daemon_status() -> Dict[str, Any]:
    """Returns the operational status of the background scheduler daemon."""
    global _DAEMON_INSTANCE
    is_alive = _DAEMON_INSTANCE is not None and _DAEMON_INSTANCE.is_alive()
    settings = get_hunter_settings()
    return {
        "daemon_alive": is_alive,
        "scheduler_enabled": settings.get("enabled", False),
        "scheduled_time": settings.get("schedule_time", DEFAULT_SCHEDULE_TIME),
        "last_run_date": settings.get("last_run_date", ""),
        "last_status": settings.get("last_status", "")
    }
