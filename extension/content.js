/**
 * Job Agent AI - Content Script Form Filler & Dynamic Resume Tailor
 * Autonomously inspects the active Job Description (JD), tailors the resume via Gemini AI,
 * compiles a bespoke ATS PDF in-browser, and autofills the entire application.
 */

(() => {
  let isAutofilling = false;

  // Safe check for valid Chrome extension context (avoids 'Extension context invalidated' error on reloaded extensions)
  function isContextValid() {
    try {
      return typeof chrome !== "undefined" && Boolean(chrome?.runtime?.id);
    } catch (e) {
      return false;
    }
  }

  // Retrieve stored profile from chrome storage
  function getProfile() {
    return new Promise((resolve) => {
      if (!isContextValid()) {
        return resolve(null);
      }
      try {
        chrome.storage.local.get(["jobAgentProfile"], (res) => {
          if (!isContextValid() || chrome.runtime.lastError) {
            return resolve(null);
          }
          resolve(res?.jobAgentProfile || null);
        });
      } catch (err) {
        resolve(null);
      }
    });
  }

  // Convert Base64 data to Blob
  function base64ToBlob(base64, mimeType) {
    try {
      const byteCharacters = atob(base64);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      return new Blob([byteArray], { type: mimeType });
    } catch (e) {
      console.warn("[JobAgent] Failed to convert base64 to blob:", e);
      return null;
    }
  }

  // Route Gemini API calls to Background Service Worker (Bypasses all page CORS and CSP restrictions)
  function callGeminiApi(prompt, profile) {
    return new Promise((resolve) => {
      if (!profile?.gemini_api_key || !profile?.enable_ai_answers) {
        return resolve(null);
      }
      if (!isContextValid()) {
        console.warn("[JobAgent] Extension context invalidated during Gemini API call.");
        return resolve(null);
      }
      try {
        chrome.runtime.sendMessage(
          {
            action: "CALL_GEMINI",
            apiKey: profile.gemini_api_key,
            model: profile.gemini_model || "gemini-1.5-flash",
            prompt: prompt
          },
          (resp) => {
            if (!isContextValid()) {
              return resolve(null);
            }
            try {
              if (chrome.runtime?.lastError || !resp || !resp.success) {
                console.warn("[JobAgent] Background Gemini call failed or timed out:", chrome?.runtime?.lastError?.message || resp?.error);
                return resolve(null);
              }
              resolve(resp.text);
            } catch (err) {
              resolve(null);
            }
          }
        );
      } catch (err) {
        console.warn("[JobAgent] Failed to send message to background:", err);
        resolve(null);
      }
    });
  }

  // React/Angular/Vue compatible native value setter
  function setNativeValue(element, value) {
    if (!element || value === undefined || value === null) return false;
    const strVal = String(value);

    if (element.value === strVal && strVal !== "") return false;

    try {
      const isTextarea = element.tagName.toLowerCase() === "textarea";
      const proto = isTextarea ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;

      if (setter) {
        setter.call(element, strVal);
      } else {
        element.value = strVal;
      }

      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
      element.dispatchEvent(new Event("blur", { bubbles: true }));

      element.classList.add("jobagent-highlight");
      return true;
    } catch (e) {
      console.warn("[JobAgent] Error setting native value:", e);
      try {
        element.value = strVal;
        element.classList.add("jobagent-highlight");
        return true;
      } catch (err) {
        return false;
      }
    }
  }

  // Extract contextual signature from an element
  function getElementSignature(el) {
    const parts = [
      el.getAttribute("name") || "",
      el.getAttribute("id") || "",
      el.getAttribute("placeholder") || "",
      el.getAttribute("autocomplete") || "",
      el.getAttribute("aria-label") || "",
      el.getAttribute("data-automation-id") || "",
      el.getAttribute("data-test") || ""
    ];

    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label) parts.push(label.innerText);
    }

    const parentLabel = el.closest("label");
    if (parentLabel) parts.push(parentLabel.innerText);

    // Immediate parent text (limit to 120 chars so we don't leak global form container labels)
    const container = el.closest(".form-group, .field, [class*='formRow'], [class*='field'], tr, p");
    if (container) {
      const text = container.innerText || "";
      if (text.length < 120) parts.push(text);
    }

    return parts.join(" ").toLowerCase();
  }

  // Check if current page looks like a job application
  function isJobApplicationPage() {
    const url = window.location.href.toLowerCase();
    const commonATS = [
      "greenhouse.io", "lever.co", "myworkdayjobs.com", "workday.com",
      "smartrecruiters.com", "ashbyhq.com", "linkedin.com/jobs", "indeed.com",
      "jobvite.com", "bamboohr.com", "apply", "careers", "jobs"
    ];

    if (commonATS.some(ats => url.includes(ats))) return true;

    const inputs = document.querySelectorAll("input:not([type='hidden'])");
    let matches = 0;
    for (const inp of inputs) {
      const sig = getElementSignature(inp);
      if (sig.includes("email") || sig.includes("resume") || sig.includes("phone") || sig.includes("linkedin")) {
        matches++;
      }
    }
    return matches >= 2;
  }

  // ==========================================
  // 1. LIVE JOB DESCRIPTION (JD) SCRAPER
  // ==========================================
  function extractJobDetails() {
    let title = "";
    let company = "";
    let description = "";

    // 1. Job Title
    const titleSelectors = [
      "h1.app-title", "#header h1", ".posting-headline h2", ".main-header h2",
      "[data-automation-id='jobPostingHeader']", ".job-details-jobs-unified-top-card__job-title",
      ".jobs-unified-top-card__job-title", "h1.jobsearch-JobInfoHeader-title",
      ".ashby-job-posting-heading", "h1", "h2[class*='title']", "h2"
    ];

    for (const sel of titleSelectors) {
      const el = document.querySelector(sel);
      if (el && el.innerText.trim().length > 3) {
        const text = el.innerText.trim();
        if (!text.toLowerCase().includes("apply") && !text.toLowerCase().includes("careers")) {
          title = text;
          break;
        } else if (!title) {
          title = text;
        }
      }
    }

    if (!title || title.toLowerCase().includes("apply")) {
      const dt = document.title.split(/[-–|·]/)[0].trim();
      title = dt || "Software Engineer";
    }

    // 2. Company Name
    const companySelectors = [
      ".company-name", "[data-automation-id='companyName']",
      ".jobsearch-JobInfoHeader-companyName", ".topcard__flavor--black-link",
      "[class*='company']", "[data-test='company-name']"
    ];

    for (const sel of companySelectors) {
      const el = document.querySelector(sel);
      if (el && el.innerText.trim().length > 1) {
        company = el.innerText.trim();
        break;
      }
    }

    if (!company) {
      const host = window.location.hostname;
      const parts = host.split(".");
      if (parts.length >= 2) {
        // e.g. automationedge.com -> AutomationEdge
        let domainBase = parts[parts.length - 2];
        if (["co", "com", "org", "net"].includes(domainBase) && parts.length >= 3) {
          domainBase = parts[parts.length - 3];
        }
        company = domainBase.charAt(0).toUpperCase() + domainBase.slice(1);
      } else {
        company = "Target Company";
      }
    }

    // 3. Job Description Text
    const descSelectors = [
      "#jobDescriptionText", "[data-automation-id='jobPostingDescription']",
      ".job-description", ".jobs-description__content", ".section-wrapper",
      ".entry-content", ".awsm_job_openings", "#content", "article", "[class*='job-description']", "[class*='description']", "main"
    ];

    for (const sel of descSelectors) {
      const el = document.querySelector(sel);
      if (el && el.innerText.trim().length > 80) {
        description = el.innerText.trim();
        break;
      }
    }

    if (!description) {
      description = document.body.innerText.slice(0, 3000);
    }

    return {
      title: title.replace(/[\n\r]+/g, " ").trim(),
      company: company.replace(/[\n\r]+/g, " ").trim(),
      description: description.slice(0, 3500)
    };
  }

  // ==========================================
  // 2. GEMINI AI RESUME TAILORING ENGINE
  // ==========================================
  async function tailorResumeForJob(jobDetails, profile) {
    const candSkills = Array.isArray(profile.skills) && profile.skills.length
      ? profile.skills
      : ["Java", "Spring Boot", "REST APIs", "MySQL", "React", "Python", "SQL", "Git", "Docker"];
    const jobText = (jobDetails.title + " " + jobDetails.description).toLowerCase();

    // Match candidate skills with JD keywords
    const matching = [];
    const others = [];
    for (const s of candSkills) {
      if (jobText.includes(s.toLowerCase())) {
        matching.push(s);
      } else {
        others.push(s);
      }
    }
    const prioritizedSkills = matching.concat(others);
    const topMatches = matching.slice(0, 4);

    let headline = `${jobDetails.title}${topMatches.length ? " (" + topMatches.join(", ") + ")" : ""}`;
    let summary = `Results-driven ${jobDetails.title} with ${profile.years_exp || "1+ years"} of experience developing enterprise backend systems and RESTful APIs with ${topMatches.length ? topMatches.join(", ") : "Java, Spring Boot, and MySQL"}. Proven track record of engineering scalable architectures and clean code standards. Excited to contribute hands-on technical excellence and high-velocity problem solving to ${jobDetails.company}.`;
    let tailoredBullets = [
      `Architected and optimized RESTful APIs and backend services using ${topMatches[0] || "Java Spring Boot"}, improving system response times by 30%.`,
      `Engineered database schemas, complex JPA/SQL queries, and secure API workflows to support high-reliability transaction processing.`,
      `Integrated third-party APIs and automated testing pipelines to ensure high test coverage and zero-downtime deployments.`
    ];
    let coverLetter = `Dear Hiring Team at ${jobDetails.company},\n\nI am writing to express my strong interest in the ${jobDetails.title} role. With hands-on experience in ${topMatches.length ? topMatches.join(", ") : "backend development, Java Spring Boot, and database architecture"}, I am eager to contribute immediately to ${jobDetails.company}'s engineering goals.\n\nIn my previous work, I focused on building high-performance REST APIs and scalable backend architectures. I would welcome the opportunity to discuss how my skill set aligns with your team's needs.\n\nSincerely,\n${profile.name}`;

    // Qualitative Tailoring with Background Gemini Worker
    if (profile.gemini_api_key && profile.enable_ai_answers !== false) {
      const prompt = `You are an expert ATS resume strategist. Tailor this candidate's resume specifically for this job posting.

CANDIDATE:
Name: ${profile.name}
Core Skills: ${candSkills.join(", ")}
Experience Summary: ${profile.experience || ""}
Education: ${profile.education || ""}

TARGET JOB:
Title: ${jobDetails.title}
Company: ${jobDetails.company}
Job Description:
${jobDetails.description.slice(0, 1800)}

Instructions:
Return ONLY a valid JSON object (no markdown formatting, no backticks) with this exact schema:
{
  "headline": "${jobDetails.title} - ${topMatches.slice(0, 3).join(", ") || "Java / Backend"}",
  "summary": "3-sentence ATS summary under 75 words highlighting alignment with ${jobDetails.company} and required tech stack",
  "tailored_bullets": [
    "Achievement bullet 1 with metrics highlighting candidate's relevance to this role",
    "Achievement bullet 2 emphasizing skills required in the job description",
    "Achievement bullet 3 focused on scalable architecture and reliability"
  ],
  "cover_letter": "Concise 3-paragraph tailored cover letter for ${jobDetails.company}"
}`;

      const aiText = await callGeminiApi(prompt, profile);
      if (aiText) {
        try {
          let cleanJson = aiText.replace(/^```json/i, "").replace(/^```/i, "").replace(/```$/i, "").trim();
          const parsed = JSON.parse(cleanJson);
          if (parsed.headline) headline = parsed.headline;
          if (parsed.summary) summary = parsed.summary;
          if (Array.isArray(parsed.tailored_bullets) && parsed.tailored_bullets.length) {
            tailoredBullets = parsed.tailored_bullets;
          }
          if (parsed.cover_letter) coverLetter = parsed.cover_letter;
        } catch (e) {
          console.warn("[JobAgent] Could not parse Gemini response JSON, using fallback:", e);
        }
      }
    }

    return {
      title: jobDetails.title,
      company: jobDetails.company,
      headline,
      summary,
      prioritized_skills: prioritizedSkills,
      tailored_bullets: tailoredBullets,
      cover_letter: coverLetter
    };
  }

  // ==========================================
  // 3. IN-BROWSER ATS PDF COMPILER (PURE JS)
  // ==========================================
  function escapePdf(text) {
    if (!text) return "";
    return String(text)
      .replace(/\\/g, "\\\\")
      .replace(/\(/g, "\\(")
      .replace(/\)/g, "\\)")
      .replace(/[\r\n]+/g, " ");
  }

  function wrapText(text, maxChars = 84) {
    if (!text) return [];
    const words = text.split(/\s+/);
    const lines = [];
    let currentLine = [];
    let currentLen = 0;

    for (const w of words) {
      if (currentLen + w.length + 1 <= maxChars) {
        currentLine.push(w);
        currentLen += w.length + 1;
      } else {
        if (currentLine.length) lines.push(currentLine.join(" "));
        currentLine = [w];
        currentLen = w.length;
      }
    }
    if (currentLine.length) lines.push(currentLine.join(" "));
    return lines;
  }

  function buildTailoredPdfBlob(tailored, profile) {
    const leftMargin = 50;
    let y = 745;
    const streamParts = [];

    function addText(text, font, size, posX, posY) {
      const clean = escapePdf(text);
      streamParts.push(`BT /${font} ${size} Tf ${posX} ${posY} Td (${clean}) Tj ET`);
    }

    function addLine(x1, y1, x2, y2) {
      streamParts.push(`${x1} ${y1} m ${x2} ${y2} l S`);
    }

    // 1. Header: Name & Contact Info
    addText(profile.name || "Mrityunjay Kumar", "F2", 17, leftMargin, y);
    y -= 16;

    const contactParts = [
      profile.location || profile.city || "Pune, India",
      profile.phone || "+91-7972379015",
      profile.email || "mrityunjayk456@gmail.com",
      profile.linkedin ? profile.linkedin.replace(/^https?:\/\/(www\.)?/, "") : "linkedin.com/in/mrityunjayk456"
    ].filter(Boolean);

    addText(contactParts.join(" | "), "F1", 8.5, leftMargin, y);
    y -= 10;
    addLine(leftMargin, y, 562, y);
    y -= 16;

    // 2. Targeted Headline
    addText(tailored.headline || `${tailored.title} – ${tailored.company}`, "F2", 11, leftMargin, y);
    y -= 16;

    // 3. Professional Summary (Tailored)
    addText("PROFESSIONAL SUMMARY", "F2", 9.5, leftMargin, y);
    y -= 12;
    const summaryLines = wrapText(tailored.summary, 88);
    for (const line of summaryLines) {
      addText(line, "F1", 8.5, leftMargin, y);
      y -= 11;
    }
    y -= 6;

    // 4. Core Technical Skills (Prioritized to JD)
    addText("TECHNICAL SKILLS & COMPETENCIES", "F2", 9.5, leftMargin, y);
    y -= 12;
    const topSkills = tailored.prioritized_skills.slice(0, 16).join(", ");
    const skillLines = wrapText(topSkills, 88);
    for (const line of skillLines) {
      addText(line, "F1", 8.5, leftMargin, y);
      y -= 11;
    }
    y -= 6;

    // 5. Professional Experience (With Tailored Bullets)
    addText("PROFESSIONAL EXPERIENCE", "F2", 9.5, leftMargin, y);
    y -= 13;

    // Current Role
    const company = profile.current_company || "Digitalllydrunk Pvt Ltd";
    const roleTitle = profile.current_title || "Backend Developer";
    const dates = `${profile.experience_start || "Nov 2025"} – ${profile.experience_end || "Present"}`;

    addText(`${roleTitle} | ${company}`, "F2", 9, leftMargin, y);
    addText(dates, "F1", 8.5, 460, y);
    y -= 12;

    for (const bullet of tailored.tailored_bullets) {
      const bLines = wrapText(`• ${bullet}`, 86);
      for (const line of bLines) {
        addText(line, "F1", 8.5, leftMargin + 4, y);
        y -= 11;
      }
    }
    y -= 4;

    // Secondary Role / Internship
    addText("Software Developer (Intern) | Tubhyam IT Solution", "F2", 9, leftMargin, y);
    addText("Aug 2025 – Nov 2025", "F1", 8.5, 460, y);
    y -= 12;
    const internBullets = [
      "• Developed Java Spring Boot REST APIs for payment workflows handling 1,000+ transactions monthly.",
      "• Integrated Stripe Payment Gateway for secure payment classification and asynchronous webhooks."
    ];
    for (const b of internBullets) {
      const bLines = wrapText(b, 86);
      for (const line of bLines) {
        addText(line, "F1", 8.5, leftMargin + 4, y);
        y -= 11;
      }
    }
    y -= 6;

    // 6. Education & Certifications
    addText("EDUCATION & CERTIFICATIONS", "F2", 9.5, leftMargin, y);
    y -= 12;
    addText(profile.degree || "Post Graduate Diploma in Advanced Computing (PG-DAC)", "F2", 8.5, leftMargin, y);
    addText("2025", "F1", 8.5, 520, y);
    y -= 10;
    addText(profile.school || "Sunbeam Institute of Information Technology", "F1", 8.5, leftMargin, y);
    y -= 12;
    addText("B.Tech in Mechanical Engineering | MIT Academy of Engineering (2020)", "F1", 8.5, leftMargin, y);
    y -= 11;
    addText("Certifications: HackerRank 3-Star MySQL | 3-Star Problem Solving (Java / JavaScript)", "F1", 8.5, leftMargin, y);

    // Compile into PDF 1.4 Binary
    const streamContent = streamParts.join("\n");
    const streamBytes = new TextEncoder().encode(streamContent);

    const objCatalog = new TextEncoder().encode("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n");
    const objPages = new TextEncoder().encode("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n");
    const objPage = new TextEncoder().encode("3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>\nendobj\n");
    const objFont1 = new TextEncoder().encode("4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n");
    const objFont2 = new TextEncoder().encode("5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n");
    const objStreamHeader = new TextEncoder().encode(`6 0 obj\n<< /Length ${streamBytes.length} >>\nstream\n`);
    const objStreamFooter = new TextEncoder().encode("\nendstream\nendobj\n");

    const header = new TextEncoder().encode("%PDF-1.4\n");
    const chunks = [header];
    const offsets = [0];

    const objs = [
      objCatalog,
      objPages,
      objPage,
      objFont1,
      objFont2,
      new Uint8Array([...objStreamHeader, ...streamBytes, ...objStreamFooter])
    ];

    let currentLength = header.length;
    for (const o of objs) {
      offsets.push(currentLength);
      chunks.push(o);
      currentLength += o.length;
    }

    const xrefOffset = currentLength;
    let xref = `xref\n0 ${offsets.length}\n0000000000 65535 f \n`;
    for (let i = 1; i < offsets.length; i++) {
      xref += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
    }
    xref += `trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
    chunks.push(new TextEncoder().encode(xref));

    return new Blob(chunks, { type: "application/pdf" });
  }

  // ==========================================
  // 4. FILE ATTACHMENT VIA DATATRANSFER
  // ==========================================
  function attachResumeFile(fileInput, profile, tailoredFile = null) {
    try {
      let fileToAttach = tailoredFile;

      if (!fileToAttach && profile.resume_base64) {
        const mime = profile.resume_mime || "application/pdf";
        const filename = profile.resume_filename || "Resume.pdf";
        const blob = base64ToBlob(profile.resume_base64, mime);
        if (blob) {
          fileToAttach = new File([blob], filename, { type: mime, lastModified: Date.now() });
        }
      }

      if (!fileToAttach) return false;

      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(fileToAttach);
      fileInput.files = dataTransfer.files;

      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
      fileInput.dispatchEvent(new Event("input", { bubbles: true }));
      fileInput.classList.add("jobagent-highlight");

      // Visually update nearby filename displays (e.g. WordPress Contact Form 7, custom dropzones)
      const container = fileInput.closest(".wpcf7-form-control-wrap, .form-group, div, label");
      if (container) {
        container.classList.add("jobagent-highlight");
        const nameBadge = container.querySelector(".file-name, .custom-file-label, .file-upload-status");
        if (nameBadge) nameBadge.textContent = fileToAttach.name;
      }

      return true;
    } catch (e) {
      console.warn("[JobAgent] Error attaching resume file:", e);
      return false;
    }
  }

  // UI Toast Banner
  function showToast(message, isSuccess = true) {
    let toast = document.getElementById("jobagent-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "jobagent-toast";
      document.body.appendChild(toast);
    }

    toast.innerHTML = `<span>${isSuccess ? "🎯" : "⚠️"}</span> <span>${message}</span>`;
    toast.style.borderColor = isSuccess ? "#10b981" : "#f59e0b";
    toast.classList.add("show");

    setTimeout(() => {
      toast.classList.remove("show");
    }, 5500);
  }

  // Floating Pill UI
  function injectFloatingPill() {
    if (document.getElementById("jobagent-floating-container")) return;

    const container = document.createElement("div");
    container.id = "jobagent-floating-container";
    container.innerHTML = `
      <div class="jobagent-pill" id="jobagentPillBtn" title="Job Agent AI - 1-Click Tailor & Autofill">
        <div class="jobagent-icon">⚡</div>
        <span class="jobagent-text">Tailor & Autofill</span>
        <button class="jobagent-close-btn" id="jobagentClosePillBtn" title="Dismiss">×</button>
      </div>
    `;

    document.body.appendChild(container);

    const pillBtn = document.getElementById("jobagentPillBtn");
    const closeBtn = document.getElementById("jobagentClosePillBtn");

    pillBtn.addEventListener("click", async (e) => {
      if (e.target === closeBtn) return;
      if (!isContextValid()) {
        showToast("Extension updated! Please refresh (F5) this webpage once.", false);
        container.remove();
        return;
      }
      await runAutofill();
    });

    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      container.style.display = "none";
    });
  }

  // ==========================================
  // 5. MASTER AUTOFILL & TAILORING EXECUTION
  // ==========================================
  async function runAutofill(passedProfile = null) {
    if (isAutofilling) return;
    isAutofilling = true;

    const pillText = document.querySelector(".jobagent-text");
    if (pillText) pillText.textContent = "Scanning JD...";

    try {
      const profile = passedProfile || (await getProfile());
      if (!profile) {
        showToast("Please configure your profile in the Job Agent popup first!", false);
        return { success: false, message: "Profile not found" };
      }

      // 1. Scrape Job Description from Active Page
      const jobDetails = extractJobDetails();
      let tailoredData = null;
      let tailoredFile = null;

      if (jobDetails.title && profile.enable_tailored_resume !== false) {
        if (pillText) pillText.textContent = `Tailoring for ${jobDetails.company.slice(0, 10)}...`;
        tailoredData = await tailorResumeForJob(jobDetails, profile);
        const pdfBlob = buildTailoredPdfBlob(tailoredData, profile);
        const cleanCompany = (jobDetails.company || "Employer").replace(/[^a-zA-Z0-9]/g, "_").slice(0, 20);
        const cleanName = (profile.name || "Candidate").replace(/[^a-zA-Z0-9]/g, "_");
        const filename = `${cleanName}_Resume_${cleanCompany}.pdf`;
        tailoredFile = new File([pdfBlob], filename, { type: "application/pdf", lastModified: Date.now() });
      }

      if (pillText) pillText.textContent = "Autofilling...";

      let filledCount = 0;
      let filesUploaded = 0;

      // 2. Resume File Inputs (<input type="file">)
      const fileInputs = document.querySelectorAll("input[type='file']");
      for (const fi of fileInputs) {
        const sig = getElementSignature(fi);
        if (
          sig.includes("resume") || sig.includes("cv") || sig.includes("curriculum") ||
          sig.includes("upload") || sig.includes("attachment") || sig.includes("document") || fileInputs.length === 1
        ) {
          if (attachResumeFile(fi, profile, tailoredFile)) {
            filesUploaded++;
            filledCount++;
          }
        }
      }

      // 3. Text Inputs & Textareas
      const textElements = document.querySelectorAll(
        "input:not([type='hidden']):not([type='radio']):not([type='checkbox']):not([type='file']):not([type='submit']):not([type='button']), textarea"
      );

      for (const el of textElements) {
        const sig = getElementSignature(el);
        const isTextarea = el.tagName.toLowerCase() === "textarea";

        // First Name
        if (
          (sig.includes("first name") || sig.includes("firstname") || sig.includes("given name") || sig.includes("first_name")) &&
          !sig.includes("last")
        ) {
          if (setNativeValue(el, profile.first_name || profile.name.split(" ")[0])) filledCount++;
        }
        // Last Name
        else if (sig.includes("last name") || sig.includes("lastname") || sig.includes("family name") || sig.includes("surname") || sig.includes("last_name")) {
          const parts = profile.name.split(" ");
          const lastName = profile.last_name || (parts.length > 1 ? parts.slice(1).join(" ") : "");
          if (setNativeValue(el, lastName)) filledCount++;
        }
        // Full Name (Matches "Name *", "Full Name", "Your Name", etc.)
        else if (
          /\b(name|full\s*name|your\s*name|candidate\s*name|applicant\s*name)\b/i.test(sig) &&
          !sig.includes("first") && !sig.includes("last") && !sig.includes("company") &&
          !sig.includes("school") && !sig.includes("user")
        ) {
          if (setNativeValue(el, profile.name)) filledCount++;
        }
        // Email
        else if (el.type === "email" || sig.includes("email") || sig.includes("e-mail")) {
          if (setNativeValue(el, profile.email)) filledCount++;
        }
        // Phone
        else if (el.type === "tel" || sig.includes("phone") || sig.includes("mobile") || sig.includes("cell")) {
          if (setNativeValue(el, profile.phone)) filledCount++;
        }
        // Technical Skills / Skill Sets
        else if (
          (sig.includes("skill") || sig.includes("technical skill") || sig.includes("technolog")) &&
          !sig.includes("years")
        ) {
          const skillsVal = Array.isArray(profile.skills) ? profile.skills.join(", ") : (profile.skills || "Java, Spring Boot, MySQL, REST APIs, React");
          if (setNativeValue(el, skillsVal)) filledCount++;
        }
        // Current Profile / Short Description / Summary
        else if (
          sig.includes("current profile") || sig.includes("short description") ||
          sig.includes("about your") || sig.includes("about yourself") ||
          sig.includes("profile description") || sig.includes("bio")
        ) {
          const summaryVal = tailoredData?.summary || profile.experience || profile.resume_raw_text;
          if (setNativeValue(el, summaryVal)) filledCount++;
        }
        // Location / City / Address
        else if (sig.includes("city") || sig.includes("location") || sig.includes("current city") || sig.includes("address")) {
          const loc = sig.includes("city") ? profile.city : (profile.location || profile.city);
          if (setNativeValue(el, loc)) filledCount++;
        }
        // Country
        else if (sig.includes("country") && !sig.includes("code")) {
          if (setNativeValue(el, profile.country || "India")) filledCount++;
        }
        // LinkedIn
        else if (sig.includes("linkedin")) {
          if (setNativeValue(el, profile.linkedin)) filledCount++;
        }
        // GitHub
        else if (sig.includes("github")) {
          if (setNativeValue(el, profile.github)) filledCount++;
        }
        // Portfolio / Website
        else if (sig.includes("portfolio") || sig.includes("website") || sig.includes("personal site") || sig.includes("url")) {
          if (setNativeValue(el, profile.portfolio || profile.github)) filledCount++;
        }
        // Experience years (inputs only, NOT textareas!)
        else if (
          !isTextarea &&
          (sig.includes("years of experience") || sig.includes("total experience") || sig.includes("experience in years"))
        ) {
          const cleanYears = profile.years_exp.match(/\d+/) ? profile.years_exp.match(/\d+/)[0] : "1";
          if (setNativeValue(el, cleanYears)) filledCount++;
        }
        // Notice Period
        else if (sig.includes("notice period") || sig.includes("notice")) {
          if (setNativeValue(el, profile.notice_period || "Immediate (2 weeks)")) filledCount++;
        }
        // Salary / Compensation
        else if (sig.includes("desired salary") || sig.includes("expected salary") || sig.includes("compensation")) {
          const cleanSalary = profile.expected_salary.replace(/[^\d]/g, "") || "10000";
          if (setNativeValue(el, cleanSalary)) filledCount++;
        }
        // Plain text resume paste
        else if (
          sig.includes("paste resume") || sig.includes("resume text") ||
          sig.includes("plain text resume") || sig.includes("copy and paste your resume") ||
          sig.includes("resume content")
        ) {
          const textToFill = tailoredData
            ? `${profile.name}\n${tailoredData.headline}\n${profile.email} | ${profile.phone}\n\nSUMMARY\n${tailoredData.summary}\n\nSKILLS\n${tailoredData.prioritized_skills.join(", ")}\n\nEXPERIENCE\n${profile.experience}`
            : (profile.resume_raw_text || profile.experience);
          if (setNativeValue(el, textToFill)) filledCount++;
        }
        // Current Employer / Company
        else if (
          (sig.includes("current company") || sig.includes("most recent company") || sig.includes("current employer") || sig.includes("employer") || sig.includes("organization")) &&
          !sig.includes("school")
        ) {
          if (setNativeValue(el, profile.current_company || "Digitalllydrunk Pvt Ltd")) filledCount++;
        }
        // Current Job Title
        else if (
          sig.includes("job title") || sig.includes("current title") || sig.includes("designation") ||
          sig.includes("position title") || sig.includes("current role")
        ) {
          if (setNativeValue(el, profile.current_title || "Backend Developer")) filledCount++;
        }
        // Employment Start Date
        else if (sig.includes("start date") || sig.includes("from date") || sig.includes("start month") || sig.includes("start year")) {
          if (setNativeValue(el, profile.experience_start || "Nov 2025")) filledCount++;
        }
        // Employment End Date
        else if (sig.includes("end date") || sig.includes("to date") || sig.includes("end month") || sig.includes("end year")) {
          if (setNativeValue(el, profile.experience_end || "Present")) filledCount++;
        }
        // Degree / Qualification
        else if (sig.includes("degree") || sig.includes("qualification") || sig.includes("highest education") || sig.includes("education level")) {
          if (setNativeValue(el, profile.degree || "Post Graduate Diploma in Advanced Computing (PG-DAC)")) filledCount++;
        }
        // Major / Field of Study
        else if (sig.includes("major") || sig.includes("field of study") || sig.includes("discipline")) {
          if (setNativeValue(el, profile.major || "Advanced Computing / Computer Science")) filledCount++;
        }
        // College / School / University
        else if (sig.includes("school") || sig.includes("university") || sig.includes("college") || sig.includes("institution")) {
          if (setNativeValue(el, profile.school || "Sunbeam Institute of Information Technology")) filledCount++;
        }
        // Graduation Year
        else if (sig.includes("grad year") || sig.includes("graduation year") || sig.includes("completion year") || sig.includes("year graduated")) {
          if (setNativeValue(el, profile.grad_year || "2025")) filledCount++;
        }
        // Cover Letter & Open-Ended Textarea
        else if (isTextarea || el.clientHeight > 50) {
          if (sig.includes("cover letter")) {
            const letter = tailoredData?.cover_letter || `Dear Hiring Team at ${jobDetails.company},\n\nI am writing to express my strong interest in the ${jobDetails.title} role. With hands-on experience in Java Spring Boot and backend engineering, I am excited about the opportunity to contribute to your engineering goals.\n\nSincerely,\n${profile.name}`;
            if (setNativeValue(el, letter)) filledCount++;
          } else if (profile.enable_ai_answers && profile.gemini_api_key && !el.value) {
            const label = el.closest(".form-group, .field, div")?.innerText || sig;
            const prompt = `Answer this job application question for a Java/Backend candidate named ${profile.name} applying for ${jobDetails.title} at ${jobDetails.company}. Question: "${label.slice(0, 200)}". Keep it 2-3 sentences, direct, first person.`;
            const aiAnswer = await callGeminiApi(prompt, profile);
            if (aiAnswer && setNativeValue(el, aiAnswer)) filledCount++;
          }
        }
      }

      // 4. Radio Buttons (Work Auth, Sponsorship, etc.)
      const radios = document.querySelectorAll("input[type='radio']");
      for (const r of radios) {
        const sig = getElementSignature(r);
        const val = (r.value || "").toLowerCase();

        // Authorized to work -> YES
        if (
          sig.includes("authorized to work") || sig.includes("legally authorized") ||
          sig.includes("eligible to work") || sig.includes("legal right")
        ) {
          if (val === "yes" || val === "true" || sig.includes("yes") || sig.includes("authorized")) {
            if (!r.checked) {
              r.click();
              r.checked = true;
              r.dispatchEvent(new Event("change", { bubbles: true }));
              filledCount++;
            }
          }
        }

        // Sponsorship -> NO
        if (
          sig.includes("require sponsorship") || sig.includes("visa sponsorship") ||
          sig.includes("future sponsorship") || sig.includes("sponsorship in the future")
        ) {
          if (val === "no" || val === "false" || sig.includes("no") || sig.includes("not require")) {
            if (!r.checked) {
              r.click();
              r.checked = true;
              r.dispatchEvent(new Event("change", { bubbles: true }));
              filledCount++;
            }
          }
        }

        // 18+ years of age -> YES
        if (sig.includes("18 years of age") || sig.includes("legal age") || sig.includes("are you 18")) {
          if (val === "yes" || val === "true" || sig.includes("yes")) {
            if (!r.checked) {
              r.click();
              r.checked = true;
              r.dispatchEvent(new Event("change", { bubbles: true }));
              filledCount++;
            }
          }
        }
      }

      // 5. Select Dropdowns (Country, Experience, Gender, etc.)
      const selects = document.querySelectorAll("select");
      for (const sel of selects) {
        const sig = getElementSignature(sel);
        let targetText = null;

        if (sig.includes("country")) {
          targetText = profile.country || "India";
        } else if (sig.includes("experience") || sig.includes("years")) {
          targetText = "1"; // Matches "1 Years" or "1 Years +" or "Fresher"
        } else if (sig.includes("gender")) {
          targetText = profile.eeo_gender || "Prefer not to disclose";
        } else if (sig.includes("disability")) {
          targetText = profile.eeo_disability || "No";
        } else if (sig.includes("veteran")) {
          targetText = profile.eeo_veteran || "I am not a protected veteran";
        } else if (sig.includes("how did you hear") || sig.includes("source")) {
          targetText = "LinkedIn";
        }

        if (targetText) {
          for (let i = 0; i < sel.options.length; i++) {
            const opt = sel.options[i];
            if (opt.text.toLowerCase().includes(targetText.toLowerCase()) || opt.value.toLowerCase().includes(targetText.toLowerCase())) {
              if (sel.selectedIndex !== i) {
                sel.selectedIndex = i;
                sel.dispatchEvent(new Event("change", { bubbles: true }));
                sel.classList.add("jobagent-highlight");
                filledCount++;
              }
              break;
            }
          }
        }
      }

      // 6. Checkboxes (Terms, consent)
      const checkboxes = document.querySelectorAll("input[type='checkbox']");
      for (const cb of checkboxes) {
        const sig = getElementSignature(cb);
        if (
          sig.includes("agree") || sig.includes("terms") || sig.includes("consent") ||
          sig.includes("privacy policy") || sig.includes("certify")
        ) {
          if (!cb.checked) {
            cb.click();
            cb.checked = true;
            cb.dispatchEvent(new Event("change", { bubbles: true }));
            filledCount++;
          }
        }
      }

      const tailNote = tailoredFile ? ` (🎯 Resume Tailored for ${jobDetails.company})` : "";
      showToast(`Autofilled ${filledCount} fields${tailNote}!`, true);

      return {
        success: true,
        count: filledCount,
        filesUploaded: filesUploaded,
        tailoredFor: jobDetails.company,
        jobTitle: jobDetails.title
      };
    } catch (err) {
      console.error("[JobAgent] Autofill runtime error:", err);
      showToast("Error during autofill: " + err.message, false);
      return { success: false, error: err.message };
    } finally {
      if (pillText) pillText.textContent = "Tailor & Autofill";
      isAutofilling = false;
    }
  }

  // ==========================================
  // 6. COMMUNICATION & PREVIEW MESSAGES
  // ==========================================
  if (isContextValid()) {
    try {
      chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (!isContextValid()) return false;

        if (request.action === "AUTOFILL_FORM") {
          runAutofill(request.profile).then((res) => {
            if (isContextValid()) {
              try {
                sendResponse(res);
              } catch (e) {}
            }
          });
          return true;
        }

        if (request.action === "GET_ACTIVE_JD") {
          try {
            const jd = extractJobDetails();
            sendResponse(jd);
          } catch (err) {
            sendResponse({ title: "Software Engineer", company: "Company" });
          }
          return false;
        }

        if (request.action === "GENERATE_TAILORED_PREVIEW") {
          (async () => {
            try {
              const jd = extractJobDetails();
              const profile = request.profile || (await getProfile());
              const tailored = await tailorResumeForJob(jd, profile);
              const blob = buildTailoredPdfBlob(tailored, profile);

              const reader = new FileReader();
              reader.onloadend = () => {
                const cleanCompany = (jd.company || "Company").replace(/[^a-zA-Z0-9]/g, "_");
                const cleanName = (profile.name || "Candidate").replace(/[^a-zA-Z0-9]/g, "_");
                if (isContextValid()) {
                  try {
                    sendResponse({
                      success: true,
                      jobTitle: jd.title,
                      company: jd.company,
                      filename: `${cleanName}_Resume_${cleanCompany}.pdf`,
                      dataUrl: reader.result
                    });
                  } catch (e) {}
                }
              };
              reader.readAsDataURL(blob);
            } catch (err) {
              console.error("[JobAgent] Preview generation error:", err);
              if (isContextValid()) {
                try {
                  sendResponse({ success: false, error: err.message });
                } catch (e) {}
              }
            }
          })();
          return true;
        }
      });
    } catch (e) {
      // Ignored if extension context is invalidated
    }
  }

  // Initialization
  (async () => {
    if (!isContextValid()) return;
    const profile = await getProfile();
    const showPill = profile?.show_floating_pill !== false;

    if (showPill && isJobApplicationPage()) {
      injectFloatingPill();
    }
  })();
})();
