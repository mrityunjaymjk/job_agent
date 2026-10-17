import json
from typing import Dict, Any, List, Optional
from datetime import datetime

def generate_offline_cover_letter(resume_data: Dict[str, Any], job_data: Dict[str, Any], tone: str = "Confident & Professional") -> str:
    name = resume_data.get('name', 'Candidate')
    email = resume_data.get('email', '')
    phone = resume_data.get('phone', '')
    skills = resume_data.get('skills', [])
    top_skills = ", ".join(skills[:5]) if skills else "modern software development tools"
    
    company = job_data.get('company', 'Hiring Team')
    title = job_data.get('title', 'Target Role')
    
    current_date = datetime.now().strftime("%B %d, %Y")
    
    letter = f"""{name}
{email} | {phone}
{current_date}

Hiring Manager
{company}

Dear Hiring Team at {company},

I am writing to express my strong interest in the {title} position. With a solid foundation in {top_skills} and a proven track record of delivering scalable, reliable solutions, I am eager to contribute immediately to your team's objectives.

Throughout my experience, I have focused on solving real-world challenges, optimizing performance, and collaborating effectively across teams. What excites me most about {company} is your commitment to high-impact work and engineering excellence. Your requirements for {title} align closely with my hands-on background and strengths.

Specifically, I bring:
• Demonstrated proficiency in {top_skills} to architect and maintain robust applications.
• A disciplined approach to problem-solving, clean code, and automated testing.
• The self-direction and proactive communication vital for high-performing remote teams.

I would welcome the opportunity to discuss how my technical skills and enthusiasm for {company}'s mission will bring immediate value to your engineering team. Thank you for your time and consideration.

Sincerely,

{name}
"""
    return letter.strip()

AVAILABLE_GEMINI_MODELS = [
    'gemini-3.5-flash',
    'gemini-3.6-flash',
    'gemini-flash-lite-latest',
    'gemini-3.5-flash-lite',
    'gemini-3.8-flash',
]

def _call_gemini(client, prompt: str, config: Optional[dict] = None):
    """
    Attempts generation across a resilient multi-model priority cascade.
    If any model encounters 429 quota exhaustion, 503 unavailable, or 404,
    it seamlessly cascades to the next available model.
    """
    last_err = None
    for m in AVAILABLE_GEMINI_MODELS:
        try:
            kwargs = {'model': m, 'contents': prompt}
            if config:
                kwargs['config'] = config
            return client.models.generate_content(**kwargs)
        except Exception as e:
            last_err = e
            err_str = str(e)
            if any(code in err_str for code in ['429', 'RESOURCE_EXHAUSTED', '503', 'UNAVAILABLE', '404', 'NOT_FOUND']):
                continue
            raise e
    raise last_err

def generate_cover_letter(
    resume_data: Dict[str, Any], 
    job_data: Dict[str, Any], 
    api_key: str = "",
    tone: str = "Confident & Professional"
) -> str:
    if not api_key:
        return generate_offline_cover_letter(resume_data, job_data, tone)
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
You are an elite career strategist. Write a highly persuasive, tailored, ATS-friendly cover letter for this candidate applying to this specific job.

TONE: {tone}

CANDIDATE:
Name: {resume_data.get('name')}
Email: {resume_data.get('email')}
Phone: {resume_data.get('phone')}
Skills: {', '.join(resume_data.get('skills', []))}
Experience & Projects summary:
{resume_data.get('experience', '')[:1000]}
{resume_data.get('projects', '')[:600]}

TARGET JOB:
Company: {job_data.get('company')}
Position: {job_data.get('title')}
Tags: {', '.join(job_data.get('tags', []))}
Description:
{job_data.get('description', '')[:2000]}

GUIDELINES:
1. Highlight specific candidate skills that match the job description.
2. Maintain a natural, authentic voice (avoid robotic clichés like "I am writing with fervent passion").
3. Include standard professional header with candidate contact info and date.
4. Keep it under 350 words, punchy and compelling.
"""
        response = _call_gemini(client, prompt)
        return response.text.strip()
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            print("ℹ️ Gemini daily quota limit reached across all models. Generating tailored offline cover letter.")
        else:
            print(f"Notice: Gemini unavailable ({err_str[:80]}), generating tailored offline cover letter.")
        return generate_offline_cover_letter(resume_data, job_data, tone)

def generate_tailored_bullets(
    resume_data: Dict[str, Any], 
    job_data: Dict[str, Any], 
    api_key: str = ""
) -> List[str]:
    if not api_key:
        skills = resume_data.get('skills', [])
        top3 = skills[:3] if skills else ['Python', 'System Architecture', 'Cloud']
        return [
            f"Designed and deployed scalable services leveraging {top3[0] if len(top3) > 0 else 'core technologies'}, improving system throughput by 30%.",
            f"Collaborated cross-functionally to integrate {top3[1] if len(top3) > 1 else 'RESTful APIs'} with automated CI/CD deployment pipelines.",
            f"Mentored engineering peers on best practices in {top3[2] if len(top3) > 2 else 'code quality'}, reducing post-release defects by 25%."
        ]
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
Given this candidate's background and this target job, rewrite 3 high-impact resume achievement bullet points (following the Action Verb + Context + Quantified Metric format) that directly target the employer's tech stack and requirements.

Candidate Skills: {', '.join(resume_data.get('skills', []))}
Job Title: {job_data.get('title')}
Job Description: {job_data.get('description', '')[:1200]}

Return JSON array of 3 strings:
["Bullet 1", "Bullet 2", "Bullet 3"]
"""
        response = _call_gemini(
            client, 
            prompt, 
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception:
        return [
            "Architected and deployed high-availability microservices reducing latency by 35%.",
            "Implemented end-to-end automated testing pipelines, accelerating release cycles.",
            "Collaborated directly with product stakeholders to deliver high-priority user-facing features on schedule."
        ]

def get_recruiter_targets(company: str, job_title: str = "") -> List[Dict[str, Any]]:
    """
    Generates targeted LinkedIn Search & Google X-Ray URLs for key hiring personas at the company.
    """
    import urllib.parse
    
    clean_company = company.replace('"', '').strip()
    quoted_comp = f'"{clean_company}"'
    
    # 1. Technical Recruiter / Talent Acquisition
    li_recruiter = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(clean_company + ' recruiter')}"
    xray_recruiter = f"https://www.google.com/search?q={urllib.parse.quote(f'site:linkedin.com/in/ {quoted_comp} (recruiter OR \"talent acquisition\" OR sourcer)')}"
    
    # 2. Engineering Manager / Tech Lead
    li_em = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(clean_company + ' engineering manager')}"
    xray_em = f"https://www.google.com/search?q={urllib.parse.quote(f'site:linkedin.com/in/ {quoted_comp} (\"engineering manager\" OR \"tech lead\" OR \"head of engineering\")')}"
    
    # 3. CTO / VP of Engineering / Founder
    li_cto = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(clean_company + ' CTO')}"
    xray_cto = f"https://www.google.com/search?q={urllib.parse.quote(f'site:linkedin.com/in/ {quoted_comp} (CTO OR \"VP of Engineering\" OR Founder OR Co-Founder)')}"
    
    # 4. Peer Software Engineer (For Referral)
    li_peer = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(clean_company + ' software engineer')}"
    xray_peer = f"https://www.google.com/search?q={urllib.parse.quote(f'site:linkedin.com/in/ {quoted_comp} (\"software engineer\" OR \"full stack developer\" OR \"backend developer\")')}"
    
    return [
        {
            "id": "recruiter",
            "persona": "🎯 Technical Recruiter / Talent Acquisition",
            "description": "Reviews applications, manages candidate pipelines, and schedules technical interviews.",
            "linkedin_url": li_recruiter,
            "xray_url": xray_recruiter,
            "tip": "Ask if the role is actively reviewing candidates and highlight your top 2 matching skills."
        },
        {
            "id": "hiring_manager",
            "persona": "💻 Engineering Manager / Tech Lead",
            "description": "The decision-maker leading the team. Highest interview conversion rate when messaged directly!",
            "linkedin_url": li_em,
            "xray_url": xray_em,
            "tip": "Keep it technical. Mention direct experience solving problems similar to what their team builds."
        },
        {
            "id": "executive",
            "persona": "🚀 CTO / VP of Engineering / Founder",
            "description": "Key leader for startups and growth companies. Receptive to proactive builders who understand the product.",
            "linkedin_url": li_cto,
            "xray_url": xray_cto,
            "tip": "Focus on high-level impact, business value, speed of delivery, and passion for the product mission."
        },
        {
            "id": "peer",
            "persona": "🤝 Peer Software Engineer (Referral)",
            "description": "A developer on the team who can answer engineering questions and submit an internal referral.",
            "linkedin_url": li_peer,
            "xray_url": xray_peer,
            "tip": "Ask for a 10-minute chat about engineering culture and their tech stack before asking for a referral."
        }
    ]

def generate_persona_outreach(
    resume_data: Dict[str, Any], 
    job_data: Dict[str, Any], 
    persona_id: str = "recruiter",
    contact_name: str = "",
    msg_type: str = "linkedin_note"
) -> str:
    cand_name = resume_data.get('name', 'Candidate')
    company = job_data.get('company', 'the team')
    title = job_data.get('title', 'the role')
    skills = resume_data.get('skills', [])
    top_skill = skills[0] if skills else "software engineering"
    top_skills_str = ", ".join(skills[:3]) if skills else "modern web architectures"
    
    salutation = f"Hi {contact_name.strip()}!" if contact_name.strip() else "Hi!"
    
    if msg_type == "linkedin_note":
        # Strictly under 300 characters for LinkedIn connection note limit
        if persona_id == "hiring_manager":
            note = f"{salutation} I saw your team is hiring a {title} at {company}. With deep background in {top_skill} and building high-scale systems, I'd love to connect and share how my experience aligns with your roadmap. Best, {cand_name}"
        elif persona_id == "executive":
            note = f"{salutation} Really impressed by what {company} is building. I noticed the {title} opening—with proven experience in {top_skill} delivering scalable features fast, I'd value connecting. Best, {cand_name}"
        elif persona_id == "peer":
            note = f"{salutation} I came across your profile while researching {company} and the {title} opening. I'm a developer working with {top_skill} and would love to connect to learn a bit about your experience on the team! Best, {cand_name}"
        else: # recruiter
            note = f"{salutation} I noticed the {title} opening at {company}. With strong experience in {top_skill} and scalable architectures, I've applied and would love to connect. Best, {cand_name}"
            
        if len(note) > 298:
            note = note[:295] + "..."
        return note

    elif msg_type == "linkedin_inmail":
        if persona_id == "hiring_manager":
            return f"""{salutation}

I noticed you're leading the engineering efforts for the {title} opening at {company}.

My background is centered around {top_skills_str}, where I've led development on high-throughput services and full-stack applications. Looking at your requirements, I've tackled similar scalability and performance challenges in my recent projects.

I'd welcome the chance to briefly connect and share a few architectural takeaways that could benefit your team's upcoming milestones.

Would you be open to a quick 10-minute introductory chat this week?

Best regards,
{cand_name}
{resume_data.get('email', '')}"""
        elif persona_id == "executive":
            return f"""{salutation}

I've been following {company}'s trajectory and love the engineering mission you're executing.

I saw your team is expanding with the {title} position. With a strong track record in {top_skills_str}, I specialize in translating high-level product goals into resilient, production-ready systems without bloated overhead.

I'd love to connect to support your engineering growth and share how I can make an immediate contribution to your team.

Warm regards,
{cand_name}
{resume_data.get('email', '')}"""
        elif persona_id == "peer":
            return f"""{salutation}

Hope you're having a great week! I came across your profile while exploring {company}'s tech stack and the {title} opening.

I'm a fellow engineer specializing in {top_skills_str}. Your work on the platform looks fascinating, and I'd really appreciate hearing your honest perspective on the engineering culture and daily workflow.

If you have 10 minutes for a quick virtual coffee, I'd love to connect!

Best,
{cand_name}"""
        else: # recruiter
            return f"""{salutation}

I hope you're having a productive week! I recently submitted my application for the {title} role at {company} and wanted to introduce myself directly.

Over my career, I've developed deep hands-on expertise in {top_skills_str}. My experience directly maps to the core responsibilities outlined in your job posting.

I'd love to connect to confirm you received my materials and answer any initial screening questions you might have.

Thank you for your time,
{cand_name}
{resume_data.get('email', '')}"""

    else: # Recruiter Cold Email
        return f"""Subject: {cand_name} - {title} Candidate Introduction ({top_skill})

{salutation}

I hope this note finds you well. I recently applied for the {title} role at {company} and wanted to reach out directly to express my strong enthusiasm for the position.

Key highlights of my background:
• Technical Proficiencies: {top_skills_str}
• Focus: Building scalable, low-latency applications with clean architectural patterns and automated testing.
• Track Record: Proven ability to collaborate effectively across distributed engineering teams.

I have attached my resume and would welcome the opportunity to discuss how my technical skill set and work ethic align with {company}'s roadmap.

Best regards,

{cand_name}
{resume_data.get('email', '')} | {resume_data.get('phone', '')}
Portfolio: {resume_data.get('links', {}).get('github', 'https://github.com/')}
"""

def find_company_decision_makers_ai(company: str, job_title: str, api_key: str = "") -> str:
    """Uses Gemini 3.8 Flash to analyze company structure, recommended leadership personas, and search strategies."""
    if not api_key:
        return ""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = f"""
You are an expert executive tech recruiter. 
Analyze the company '{company}' and the job position '{job_title}'.

Provide a concise, practical Recruiter Outreach Strategy:
1. Target Job Titles: The exact LinkedIn job titles of the people who make hiring decisions for this role at {company}.
2. Key Pitch Angle: What specific technical or business hook should the candidate emphasize when messaging leaders at {company}?
3. Boolean Search Operator: Provide 1 exact Boolean search string the candidate can paste into LinkedIn Search or Google.

Keep it under 150 words with clean formatting.
"""
        response = _call_gemini(client, prompt)
        return response.text.strip()
    except Exception as e:
        print("Gemini decision maker error:", e)
        return ""

def generate_outreach_message(
    resume_data: Dict[str, Any], 
    job_data: Dict[str, Any], 
    platform: str = "LinkedIn"
) -> str:
    cand_name = resume_data.get('name', 'Candidate')
    company = job_data.get('company', 'the team')
    title = job_data.get('title', 'the role')
    skills = resume_data.get('skills', [])
    top_skill = skills[0] if skills else "engineering"
    
    if platform.lower() == "linkedin":
        return f"Hi! I noticed the {title} opening at {company}. With my background in {top_skill} and building scalable systems, I'd love to connect and see how I could add value to your team. Best, {cand_name}"
    else:
        return f"""Subject: {cand_name} - Application / Inquiry for {title} at {company}

Hi Hiring Team,

I recently came across the {title} opening at {company} and wanted to reach out directly. With a strong background in {', '.join(skills[:3])}, I have delivered solutions that improve reliability and speed of delivery.

I would love to learn more about the team's upcoming roadmap and share how my technical experience aligns with your goals.

Best regards,
{cand_name}
{resume_data.get('email', '')}
"""

def generate_application_answers(
    resume_data: Dict[str, Any], 
    job_data: Dict[str, Any],
    custom_prefs: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    if not custom_prefs:
        custom_prefs = {}
        
    company = job_data.get('company', 'your company')
    title = job_data.get('title', 'this role')
    
    why_us = f"I am deeply inspired by {company}'s focus on innovation and product quality. The {title} position offers an ideal intersection where my experience solving complex technical challenges can directly drive your engineering goals forward."
    
    return {
        "Why do you want to work here?": why_us,
        "Years of relevant experience": custom_prefs.get('years_exp', '3-5+ years'),
        "Expected Salary / Compensation": custom_prefs.get('expected_salary', 'Competitive / Market Rate (Negotiable)'),
        "Work Authorization / Visa Status": custom_prefs.get('work_auth', 'Authorized to work without sponsorship'),
        "Availability / Notice Period": custom_prefs.get('notice_period', 'Immediate / 2 weeks'),
        "Portfolio / GitHub": resume_data.get('links', {}).get('github', 'https://github.com/'),
        "LinkedIn Profile": resume_data.get('links', {}).get('linkedin', 'https://linkedin.com/in/')
    }
