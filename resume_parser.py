import re
from pathlib import Path
from typing import Dict, Any, List
import pypdf
import docx

# Comprehensive Tech & Professional Skill Dictionary
COMMON_SKILLS = [
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "PHP", 
    "Ruby", "Swift", "Kotlin", "Scala", "R", "SQL", "HTML", "CSS", "Bash", "Shell",
    
    # Frontend & Fullstack
    "React", "React Native", "Vue.js", "Vue", "Angular", "Next.js", "Nuxt.js", 
    "Svelte", "Redux", "Tailwind CSS", "Bootstrap", "Webpack", "Vite", "GraphQL", 
    "REST API", "Node.js", "Express.js", "Django", "Flask", "FastAPI", "Spring Boot",
    "Ruby on Rails", "ASP.NET", "Laravel",
    
    # Data & AI / ML
    "Machine Learning", "Deep Learning", "Artificial Intelligence", "LLM", "NLP",
    "Computer Vision", "TensorFlow", "PyTorch", "Keras", "Scikit-Learn", "Pandas",
    "NumPy", "OpenCV", "Hugging Face", "LangChain", "LlamaIndex", "Generative AI",
    "Prompt Engineering", "Data Engineering", "Apache Spark", "Airflow", "Kafka",
    "Snowflake", "Databricks", "BigQuery", "Tableau", "Power BI",
    
    # Cloud & DevOps
    "AWS", "Amazon Web Services", "Azure", "Google Cloud", "GCP", "Docker", 
    "Kubernetes", "Terraform", "CI/CD", "GitHub Actions", "GitLab CI", "Jenkins", 
    "Ansible", "Linux", "Prometheus", "Grafana", "Nginx", "Microservices",
    
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "DynamoDB", 
    "SQLite", "Cassandra", "Supabase", "Firebase",
    
    # Tools & Practices
    "Git", "GitHub", "GitLab", "Jira", "Agile", "Scrum", "TDD", "Unit Testing",
    "System Design", "OOP", "Software Architecture", "Cybersecurity", "Penetration Testing"
]

def extract_text_from_pdf(file_bytes_or_path) -> str:
    reader = pypdf.PdfReader(file_bytes_or_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def extract_text_from_docx(file_bytes_or_path) -> str:
    doc = docx.Document(file_bytes_or_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return "\n".join(full_text)

def extract_email(text: str) -> str:
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else ""

def extract_phone(text: str) -> str:
    match = re.search(r'(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}', text)
    return match.group(0).strip() if match else ""

def extract_links(text: str) -> Dict[str, str]:
    links = {}
    linkedin = re.search(r'(https?://(?:www\.)?linkedin\.com/in/[\w-]+)', text, re.I)
    if linkedin:
        links['linkedin'] = linkedin.group(0)
    github = re.search(r'(https?://(?:www\.)?github\.com/[\w-]+)', text, re.I)
    if github:
        links['github'] = github.group(0)
    portfolio = re.search(r'(https?://(?:www\.)?[\w-]+\.(?:com|dev|io|me|org)[\w/-]*)', text, re.I)
    if portfolio and 'linkedin' not in portfolio.group(0) and 'github' not in portfolio.group(0):
        links['portfolio'] = portfolio.group(0)
    return links

def extract_skills(text: str) -> List[str]:
    found_skills = set()
    text_lower = text.lower()
    
    for skill in COMMON_SKILLS:
        # Exact word boundary matching for short names like Go, R, C, C++
        escaped = re.escape(skill)
        pattern = rf'\b{escaped}\b'
        if re.search(pattern, text, re.IGNORECASE):
            found_skills.add(skill)
            
    # Also sort alphabetically
    return sorted(list(found_skills))

def extract_sections(text: str) -> Dict[str, str]:
    sections = {
        "experience": "",
        "education": "",
        "projects": ""
    }
    
    lines = text.split("\n")
    current_sec = None
    exp_lines, edu_lines, proj_lines = [], [], []
    
    for line in lines:
        clean = line.strip().lower()
        if re.match(r'^(experience|work experience|employment history|work history)\b', clean):
            current_sec = "experience"
            continue
        elif re.match(r'^(education|academic background|academics)\b', clean):
            current_sec = "education"
            continue
        elif re.match(r'^(projects|personal projects|technical projects)\b', clean):
            current_sec = "projects"
            continue
        elif re.match(r'^(skills|certifications|awards|summary|profile|interests)\b', clean):
            current_sec = None
            continue
            
        if current_sec == "experience":
            exp_lines.append(line)
        elif current_sec == "education":
            edu_lines.append(line)
        elif current_sec == "projects":
            proj_lines.append(line)
            
    sections["experience"] = "\n".join(exp_lines[:50]).strip()
    sections["education"] = "\n".join(edu_lines[:25]).strip()
    sections["projects"] = "\n".join(proj_lines[:40]).strip()
    return sections

def parse_resume(file_obj_or_path, filename: str) -> Dict[str, Any]:
    raw_text = ""
    lower_fn = filename.lower()
    
    if lower_fn.endswith('.pdf'):
        raw_text = extract_text_from_pdf(file_obj_or_path)
    elif lower_fn.endswith('.docx'):
        raw_text = extract_text_from_docx(file_obj_or_path)
    elif lower_fn.endswith('.txt'):
        if hasattr(file_obj_or_path, 'read'):
            raw = file_obj_or_path.read()
            raw_text = raw.decode('utf-8', errors='ignore') if isinstance(raw, bytes) else str(raw)
        else:
            with open(file_obj_or_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_text = f.read()
    else:
        # Fallback treat as text
        if hasattr(file_obj_or_path, 'read'):
            raw = file_obj_or_path.read()
            raw_text = raw.decode('utf-8', errors='ignore') if isinstance(raw, bytes) else str(raw)
            
    # Try guessing candidate name from the top non-empty lines
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    guessed_name = lines[0] if lines else "Candidate"
    # Filter out common headers like Resume / Curriculum Vitae
    if len(lines) > 1 and any(kw in guessed_name.lower() for kw in ["resume", "curriculum vitae", "cv", "portfolio"]):
        guessed_name = lines[1]
        
    email = extract_email(raw_text)
    phone = extract_phone(raw_text)
    links = extract_links(raw_text)
    skills = extract_skills(raw_text)
    sections = extract_sections(raw_text)
    
    return {
        "name": guessed_name[:60],
        "email": email,
        "phone": phone,
        "links": links,
        "skills": skills,
        "experience": sections.get("experience", ""),
        "education": sections.get("education", ""),
        "projects": sections.get("projects", ""),
        "raw_text": raw_text
    }
