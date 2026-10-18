import requests
import json
import re
import hashlib
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html, application/xml, text/xml, */*'
}

def make_job_id(source: str, identifier: str) -> str:
    """Generates a 100% deterministic unique ID for a job to prevent duplicate records."""
    clean_id = identifier.strip().lower()
    h = hashlib.md5(clean_id.encode('utf-8')).hexdigest()[:12]
    return f"{source.lower()}_{h}"

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        # Fallback regex strip
        return re.sub(r'<[^>]+>', ' ', raw_html).strip()

def clean_tags(raw_tags: Any) -> List[str]:
    """Sanitizes raw tags from scrapers into a flat list of non-empty strings."""
    if not raw_tags:
        return []
    if isinstance(raw_tags, str):
        try:
            parsed = json.loads(raw_tags)
            if isinstance(parsed, (list, tuple)):
                raw_tags = parsed
            else:
                return [t.strip() for t in raw_tags.split(',') if t.strip()]
        except Exception:
            return [t.strip() for t in raw_tags.split(',') if t.strip()]
    result = []
    if isinstance(raw_tags, (list, tuple, set)):
        for item in raw_tags:
            if not item:
                continue
            if isinstance(item, str):
                s = item.strip()
                if s:
                    result.append(s)
            elif isinstance(item, (list, tuple, set)):
                for sub in item:
                    if sub and str(sub).strip():
                        result.append(str(sub).strip())
            elif isinstance(item, dict):
                for k in ["name", "label", "tag", "value"]:
                    val = item.get(k)
                    if val and str(val).strip():
                        result.append(str(val).strip())
            else:
                s = str(item).strip()
                if s:
                    result.append(s)
    return result

def fetch_remoteok_jobs(tag: Optional[str] = None, limit: int = 60) -> List[Dict[str, Any]]:
    jobs = []
    url = "https://remoteok.com/api"
    if tag:
        url += f"?tag={tag.lower().strip()}"
        
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            data = res.json()
            # RemoteOK's first element is usually metadata legal notice
            items = data[1:] if len(data) > 1 and isinstance(data[0], dict) and 'legal' in data[0] else data
            
            for item in items[:limit]:
                if not isinstance(item, dict):
                    continue
                job_id = f"remoteok_{item.get('id', item.get('slug', ''))}"
                title = item.get('position', '').strip()
                company = item.get('company', '').strip()
                if not title or not company:
                    continue
                    
                tags = clean_tags(item.get('tags', []))
                    
                desc = clean_html(item.get('description', ''))
                
                # Format salary if available
                salary_min = item.get('salary_min')
                salary_max = item.get('salary_max')
                salary_str = ""
                if salary_min and salary_max:
                    salary_str = f"${salary_min:,.0f} - ${salary_max:,.0f}/yr"
                elif salary_min:
                    salary_str = f"From ${salary_min:,.0f}/yr"
                elif salary_max:
                    salary_str = f"Up to ${salary_max:,.0f}/yr"
                    
                apply_url = item.get('apply_url') or item.get('url') or f"https://remoteok.com/remote-jobs/{item.get('slug', '')}"
                
                jobs.append({
                    "id": job_id,
                    "source": "RemoteOK",
                    "title": title,
                    "company": company,
                    "tags": tags,
                    "location": item.get('location', 'Remote (Worldwide)'),
                    "salary": salary_str,
                    "url": item.get('url', apply_url),
                    "apply_url": apply_url,
                    "description": desc,
                    "published_date": item.get('date', '')
                })
    except Exception as e:
        print(f"Error fetching RemoteOK jobs: {e}")
        
    return jobs

def fetch_weworkremotely_jobs(category: str = "remote-programming-jobs", limit: int = 35) -> List[Dict[str, Any]]:
    jobs = []
    feed_url = f"https://weworkremotely.com/categories/{category}.rss"
    
    try:
        res = requests.get(feed_url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "xml")
            items = soup.find_all("item")
            
            for item in items[:limit]:
                raw_title = item.find("title").text if item.find("title") else ""
                link = item.find("link").text if item.find("link") else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") else ""
                raw_desc = item.find("description").text if item.find("description") else ""
                desc = clean_html(raw_desc)
                
                # Split company and title: WWR formats as "Company Name: Job Title"
                company = "Remote Company"
                title = raw_title
                if ":" in raw_title:
                    parts = raw_title.split(":", 1)
                    company = parts[0].strip()
                    title = parts[1].strip()
                    
                # Extract tags or region from description/title
                tags = []
                for kw in ["python", "react", "javascript", "golang", "devops", "aws", "backend", "frontend", "fullstack", "ruby", "data"]:
                    if kw in title.lower() or kw in desc.lower()[:500]:
                        tags.append(kw.capitalize())
                        
                # Create deterministic ID
                job_id = make_job_id("wwr", link or f"{title}_{company}")
                
                jobs.append({
                    "id": job_id,
                    "source": "WeWorkRemotely",
                    "title": title,
                    "company": company,
                    "tags": tags,
                    "location": "Remote",
                    "salary": "",
                    "url": link,
                    "apply_url": link,
                    "description": desc,
                    "published_date": pub_date
                })
    except Exception as e:
        print(f"Error fetching WeWorkRemotely jobs: {e}")
        
    return jobs

def fetch_arbeitnow_jobs(search_query: str = "", limit: int = 40) -> List[Dict[str, Any]]:
    jobs = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            data = res.json().get('data', [])
            for item in data[:limit]:
                title = item.get('title', '').strip()
                company = item.get('company_name', '').strip()
                if not title or not company:
                    continue
                job_id = make_job_id("arbeitnow", str(item.get('slug') or item.get('url') or f"{title}_{company}"))
                desc = clean_html(item.get('description', ''))
                tags = clean_tags(item.get('tags', []))
                url_link = item.get('url', '')
                jobs.append({
                    "id": job_id,
                    "source": "Arbeitnow",
                    "title": title,
                    "company": company,
                    "tags": tags,
                    "location": item.get('location', 'Remote'),
                    "salary": "",
                    "url": url_link,
                    "apply_url": url_link,
                    "description": desc,
                    "published_date": str(item.get('created_at', ''))[:10]
                })
    except Exception as e:
        print(f"Error fetching Arbeitnow jobs: {e}")
    return jobs

def fetch_jobicy_jobs(search_query: str = "", limit: int = 30) -> List[Dict[str, Any]]:
    jobs = []
    url = f"https://jobicy.com/api/v2/remote-jobs?count={limit}"
    if search_query:
        url += f"&tag={search_query.lower()}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            data = res.json().get('jobs', [])
            for item in data[:limit]:
                title = item.get('jobTitle', '').strip()
                company = item.get('companyName', '').strip()
                if not title or not company:
                    continue
                job_id = make_job_id("jobicy", str(item.get('id') or item.get('url') or f"{title}_{company}"))
                desc = clean_html(item.get('jobDescription', ''))
                tags = clean_tags(item.get('jobIndustry'))
                url_link = item.get('url', '')
                salary_str = ""
                s_min = item.get('salaryMin')
                s_max = item.get('salaryMax')
                if s_min and s_max:
                    salary_str = f"${s_min:,.0f} - ${s_max:,.0f}/yr"
                jobs.append({
                    "id": job_id,
                    "source": "Jobicy",
                    "title": title,
                    "company": company,
                    "tags": tags,
                    "location": item.get('jobGeo', 'Remote'),
                    "salary": salary_str,
                    "url": url_link,
                    "apply_url": url_link,
                    "description": desc,
                    "published_date": str(item.get('pubDate', ''))[:16]
                })
    except Exception as e:
        print(f"Error fetching Jobicy jobs: {e}")
    return jobs

def fetch_remotive_jobs(search_query: str = "", limit: int = 35) -> List[Dict[str, Any]]:
    jobs = []
    url = "https://remotive.com/api/remote-jobs?category=software-dev"
    if search_query:
        url += f"&search={search_query.lower()}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            data = res.json().get('jobs', [])
            for item in data[:limit]:
                title = item.get('title', '').strip()
                company = item.get('company_name', '').strip()
                if not title or not company:
                    continue
                job_id = make_job_id("remotive", str(item.get('id') or item.get('url') or f"{title}_{company}"))
                desc = clean_html(item.get('description', ''))
                tags = clean_tags(item.get('tags', []))
                url_link = item.get('url', '')
                salary_str = item.get('salary', '')
                jobs.append({
                    "id": job_id,
                    "source": "Remotive",
                    "title": title,
                    "company": company,
                    "tags": tags,
                    "location": item.get('candidate_required_location', 'Remote (Worldwide)'),
                    "salary": salary_str,
                    "url": url_link,
                    "apply_url": url_link,
                    "description": desc,
                    "published_date": str(item.get('publication_date', ''))[:10]
                })
    except Exception as e:
        print(f"Error fetching Remotive jobs: {e}")
    return jobs

def fetch_linkedin_jobs(search_query: str = "Software Engineer", location: str = "Remote", limit: int = 30) -> List[Dict[str, Any]]:
    jobs = []
    # Query across multiple page offsets
    for start in [0, 10, 20]:
        if len(jobs) >= limit:
            break
        q = requests.utils.quote(search_query if search_query else "Software Engineer")
        loc = requests.utils.quote(location if location else "Remote")
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={q}&location={loc}&f_WT=2&start={start}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                cards = soup.find_all("li")
                if not cards:
                    break
                for card in cards:
                    t_el = card.find("h3", class_="base-search-card__title")
                    c_el = card.find("h4", class_="base-search-card__subtitle")
                    l_el = card.find("span", class_="job-search-card__location")
                    link_el = card.find("a", class_="base-card__full-link")
                    date_el = card.find("time")
                    
                    if not t_el or not link_el:
                        continue
                        
                    title = t_el.text.strip()
                    company = c_el.text.strip() if c_el else "Company on LinkedIn"
                    raw_link = link_el.get("href", "")
                    job_url = raw_link.split("?")[0] if "?" in raw_link else raw_link
                    location_text = l_el.text.strip() if l_el else "Remote"
                    pub_date = date_el.text.strip() if date_el else ""
                    
                    job_id = make_job_id("linkedin", job_url or f"{title}_{company}")
                    
                    jobs.append({
                        "id": job_id,
                        "source": "LinkedIn",
                        "title": title,
                        "company": company,
                        "tags": ["LinkedIn", "Tech"],
                        "location": location_text,
                        "salary": "",
                        "url": job_url,
                        "apply_url": job_url,
                        "description": f"{title} opening at {company} on LinkedIn. Location: {location_text}",
                        "published_date": pub_date
                    })
                    if len(jobs) >= limit:
                        break
        except Exception as e:
            print(f"Error fetching LinkedIn jobs: {e}")
            break
    return jobs

def fetch_wellfound_jobs(search_query: str = "", limit: int = 35) -> List[Dict[str, Any]]:
    jobs = []
    url = "https://wellfound.com/jobs"
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if script and script.string:
                data = json.loads(script.string)
                apollo = data.get("props", {}).get("pageProps", {}).get("apolloState", {}).get("data", {})
                for k, v in apollo.items():
                    if isinstance(v, dict) and v.get("__typename") == "JobListing":
                        title = v.get("title", "").strip()
                        if not title:
                            continue
                        comp_ref = v.get("startup", {}).get("__ref", "")
                        startup_obj = apollo.get(comp_ref, {})
                        comp_name = startup_obj.get("name", "Tech Startup").strip()
                        comp_slug = startup_obj.get("slug", "")
                        job_slug = v.get("slug", "")
                        job_id_num = v.get("id", "")
                        comp_str = v.get("compensation", "")
                        if "" in comp_str:
                            comp_str = comp_str.replace("", "-")
                            
                        link = f"https://wellfound.com/company/{comp_slug}/jobs/{job_id_num}-{job_slug}" if comp_slug else f"https://wellfound.com/jobs/{job_id_num}"
                        
                        loc_names = v.get("locationNames", [])
                        loc_str = ", ".join(loc_names) if loc_names else "Remote"
                        
                        job_id = make_job_id("wellfound", link or f"{title}_{comp_name}")
                        
                        jobs.append({
                            "id": job_id,
                            "source": "Wellfound",
                            "title": title,
                            "company": comp_name,
                            "tags": ["Startup", "Wellfound"],
                            "location": loc_str,
                            "salary": comp_str,
                            "url": link,
                            "apply_url": link,
                            "description": f"{title} at {comp_name}. Compensation: {comp_str}. Location: {loc_str}",
                            "published_date": ""
                        })
                        if len(jobs) >= limit:
                            break
    except Exception as e:
        print(f"Error fetching Wellfound jobs: {e}")
    return jobs

WWR_CATEGORIES = [
    ("Programming", "remote-programming-jobs"),
    ("DevOps & Sysadmin", "remote-devops-sysadmin-jobs"),
    ("Design", "remote-design-jobs"),
    ("Product", "remote-product-jobs"),
    ("Management & Finance", "remote-management-and-finance-jobs"),
    ("Customer Support", "remote-customer-support-jobs")
]

def fetch_all_jobs(
    sources: Optional[List[str]] = None, 
    search_query: str = "", 
    location: str = "Remote",
    category: str = "remote-programming-jobs",
    limit_per_source: int = 35
) -> List[Dict[str, Any]]:
    if sources is None:
        sources = ["LinkedIn", "Wellfound", "RemoteOK", "Arbeitnow", "Jobicy", "Remotive"]
        
    all_jobs = []

    if "LinkedIn" in sources:
        li_jobs = fetch_linkedin_jobs(search_query=search_query, location=location or "Remote", limit=limit_per_source)
        if li_jobs:
            all_jobs.extend(li_jobs)

    if "Wellfound" in sources:
        wf_jobs = fetch_wellfound_jobs(search_query=search_query, limit=limit_per_source)
        if wf_jobs:
            all_jobs.extend(wf_jobs)
    
    if "RemoteOK" in sources:
        tag = search_query if search_query else None
        rok_jobs = fetch_remoteok_jobs(tag=tag, limit=limit_per_source)
        if rok_jobs:
            all_jobs.extend(rok_jobs)

    if "Arbeitnow" in sources:
        arbeit_jobs = fetch_arbeitnow_jobs(search_query=search_query, limit=limit_per_source)
        if arbeit_jobs:
            all_jobs.extend(arbeit_jobs)

    if "Jobicy" in sources:
        jobicy_jobs = fetch_jobicy_jobs(search_query=search_query, limit=limit_per_source)
        if jobicy_jobs:
            all_jobs.extend(jobicy_jobs)

    if "Remotive" in sources:
        remotive_jobs = fetch_remotive_jobs(search_query=search_query, limit=limit_per_source)
        if remotive_jobs:
            all_jobs.extend(remotive_jobs)
        
    if "WeWorkRemotely" in sources:
        wwr_jobs = fetch_weworkremotely_jobs(category=category, limit=limit_per_source)
        if wwr_jobs:
            all_jobs.extend(wwr_jobs)
        
    # Deduplicate by title & company
    seen = set()
    deduped = []
    for j in all_jobs:
        key = (j['title'].lower().strip(), j['company'].lower().strip())
        if key not in seen:
            seen.add(key)
            j_tags = clean_tags(j.get('tags', []))
            j['tags'] = j_tags
            # Filter by search_query if specified and not already filtered
            if search_query:
                q = search_query.lower()
                text = f"{j['title']} {j['company']} {' '.join(j_tags)} {j['description']}".lower()
                if q not in text:
                    continue
            deduped.append(j)
            
    return deduped
