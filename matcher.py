import json
import re
from typing import Dict, Any, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from resume_parser import COMMON_SKILLS, extract_skills

NON_TECH_TAGS = {
    "dev", "developer", "engineer", "remote", "full time", "full-time", "part time", 
    "senior", "junior", "lead", "tech", "worldwide", "contract", "front end", "back end", 
    "full stack", "frontend", "backend", "fullstack", "usa", "manager", "director"
}

def compute_local_match(resume_data: Dict[str, Any], job_data: Dict[str, Any]) -> Dict[str, Any]:
    resume_skills = set([s.lower() for s in resume_data.get('skills', [])])
    resume_text = resume_data.get('raw_text', '')
    
    # Extract skills from job description and tags
    raw_job_tags = set([t.lower().strip() for t in job_data.get('tags', [])])
    job_tags = set([t for t in raw_job_tags if t not in NON_TECH_TAGS])
    
    job_desc = job_data.get('description', '')
    job_title = job_data.get('title', '')
    job_full_text = f"{job_title} {job_desc}"
    
    # Extract known skills from job text
    job_extracted_skills = set([s.lower() for s in extract_skills(job_full_text)])
    all_job_skills = job_tags.union(job_extracted_skills)
    
    # Filter out non-tech words
    clean_job_skills = set([s for s in all_job_skills if s not in NON_TECH_TAGS])
    
    # Calculate skill overlaps
    if clean_job_skills:
        matched_skills = sorted(list(resume_skills.intersection(clean_job_skills)))
        missing_skills = sorted(list(clean_job_skills - resume_skills))
        
        # Effective saturation formula: 6-8 matching tech skills represent high qualification
        effective_denom = max(3, min(len(clean_job_skills), 8))
        skill_score = min(100.0, (len(matched_skills) / effective_denom) * 100)
    else:
        matched_skills = []
        missing_skills = []
        skill_score = 50.0
        
    # Calculate TF-IDF Cosine Similarity
    tfidf_score = 0.0
    if resume_text.strip() and job_full_text.strip():
        try:
            vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            tfidf_matrix = vectorizer.fit_transform([resume_text, job_full_text])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            tfidf_score = min(100.0, float(similarity * 250))
        except Exception:
            tfidf_score = 40.0
            
    # Weighted Final Score: 70% skill match, 30% text semantic similarity
    if clean_job_skills:
        final_score = (0.70 * skill_score) + (0.30 * tfidf_score)
    else:
        final_score = tfidf_score

    # Bonus: Does the candidate's skill appear directly in the Job Title? (e.g. React Developer)
    title_lower = job_title.lower()
    title_matches = [s for s in matched_skills if s in title_lower]
    if title_matches:
        final_score += 12.0
        
    final_score = round(max(5.0, min(98.0, final_score)), 1)
    
    # Capitalize matched and missing skills nicely
    title_case_matched = [s.title() for s in matched_skills]
    title_case_missing = [s.title() for s in missing_skills[:12]] # Limit display to top 12
    
    return {
        "score": final_score,
        "skill_score": round(skill_score, 1),
        "tfidf_score": round(tfidf_score, 1),
        "matched_skills": title_case_matched,
        "missing_skills": title_case_missing,
        "analysis_mode": "local_heuristic"
    }

def analyze_match_with_gemini(
    resume_data: Dict[str, Any], 
    job_data: Dict[str, Any], 
    api_key: str
) -> Dict[str, Any]:
    """Deep AI match analysis with Google Gemini"""
    local_result = compute_local_match(resume_data, job_data)
    
    if not api_key:
        return local_result
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
You are an expert technical recruiter and ATS specialist.
Analyze this candidate's resume against the target job posting.

CANDIDATE INFO:
Name: {resume_data.get('name')}
Skills: {', '.join(resume_data.get('skills', []))}
Experience summary: {resume_data.get('experience', '')[:1200]}

JOB POSTING:
Title: {job_data.get('title')}
Company: {job_data.get('company')}
Tags: {', '.join(job_data.get('tags', []))}
Description: {job_data.get('description', '')[:2000]}

Provide your evaluation in valid JSON strictly conforming to this structure:
{{
  "match_score": 85,
  "summary": "Brief 2-sentence summary of candidate fit",
  "strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "gaps": ["Missing skill or experience 1", "Missing skill 2"],
  "ats_recommendations": ["Actionable tweak 1", "Actionable tweak 2"]
}}
"""
        models_to_try = [
            'gemini-3.5-flash',
            'gemini-3.6-flash',
            'gemini-flash-lite-latest',
            'gemini-3.5-flash-lite',
            'gemini-3.8-flash'
        ]
        response = None
        for m in models_to_try:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                break
            except Exception as e:
                err_str = str(e)
                # If 429 quota, 503 unavailable, or 404 not found, seamlessly try next model
                if any(code in err_str for code in ['429', 'RESOURCE_EXHAUSTED', '503', 'UNAVAILABLE', '404', 'NOT_FOUND']):
                    continue
                break
                
        if not response:
            local_result["quota_exhausted"] = True
            return local_result
            
        ai_data = json.loads(response.text)
        
        # Merge local skill lists with AI deep insights
        return {
            "score": float(ai_data.get("match_score", local_result["score"])),
            "summary": ai_data.get("summary", ""),
            "strengths": ai_data.get("strengths", []),
            "gaps": ai_data.get("gaps", local_result["missing_skills"]),
            "ats_recommendations": ai_data.get("ats_recommendations", []),
            "matched_skills": local_result["matched_skills"],
            "missing_skills": local_result["missing_skills"],
            "analysis_mode": "gemini_ai"
        }
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            local_result["quota_exhausted"] = True
        local_result["error"] = err_str
        return local_result
