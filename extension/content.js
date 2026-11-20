/**
 * Job Agent AI - Content Script Form Filler & Dynamic Resume Tailor
 * Autonomously inspects the active Job Description (JD), tailors the resume via Gemini AI,
 * compiles a bespoke ATS PDF in-browser, and autofills the entire application.
 */

(() => {
  // Global suppression of harmless extension context invalidation errors when extension is reloaded
  window.addEventListener("error", (event) => {
    if (event?.message && event.message.includes("Extension context invalidated")) {
      event.preventDefault?.();
      event.stopImmediatePropagation?.();
    }
  }, true);

  window.addEventListener("unhandledrejection", (event) => {
    const msg = event?.reason?.message || String(event?.reason || "");
    if (msg.includes("Extension context invalidated")) {
      event.preventDefault?.();
      event.stopImmediatePropagation?.();
    }
  }, true);

  let isAutofilling = false;

  // Known ATS vendors that should NEVER be used as genuine company names
  const ATS_VENDORS = [
    "smartrecruiters", "greenhouse", "lever", "myworkdayjobs", "workday",
    "ashbyhq", "ashby", "jobvite", "bamboohr", "taleo", "icims", "workable",
    "jazzhr", "recruitee", "rippling", "phenompeople", "brassring",
    "successfactors", "adp", "bullhorn", "paylocity", "cornerstone",
    "ultipro", "clearcompany", "breezy", "pinpointhq", "hireology", "applicantlist"
  ];

  function isAtsVendor(name) {
    if (!name) return false;
    const clean = name.toLowerCase().replace(/[^a-z0-9]/g, "");
    return ATS_VENDORS.some(ats => clean.includes(ats));
  }

  // Safe check for valid Chrome extension context (avoids 'Extension context invalidated' error on reloaded extensions)
  function isContextValid() {
    try {
      if (typeof chrome === "undefined" || !chrome) return false;
      const runtime = chrome.runtime;
      if (!runtime) return false;
      return Boolean(runtime.id);
    } catch (e) {
      return false;
    }
  }

  // Deep query selector that pierces Shadow DOM boundaries (open shadowRoots) and accessible iframes
  function querySelectorAllDeep(selector, root = document) {
    const results = [];
    const visited = new Set();

    function search(node) {
      if (!node || visited.has(node)) return;
      visited.add(node);

      try {
        if (node.querySelectorAll) {
          const matched = node.querySelectorAll(selector);
          for (let i = 0; i < matched.length; i++) {
            results.push(matched[i]);
          }

          const all = node.querySelectorAll("*");
          for (let i = 0; i < all.length; i++) {
            const el = all[i];
            if (el.shadowRoot) {
              search(el.shadowRoot);
            }
            if (el.tagName === "IFRAME") {
              try {
                const doc = el.contentDocument || el.contentWindow?.document;
                if (doc) search(doc);
              } catch (e) {}
            }
          }
        }
      } catch (e) {}
    }

    search(root);
    return results;
  }

  // Retrieve stored profile from chrome storage
  function getProfile() {
    return new Promise((resolve) => {
      try {
        if (!isContextValid()) {
          return resolve(null);
        }
        chrome.storage.local.get(["jobAgentProfile"], (res) => {
          try {
            if (!isContextValid()) {
              return resolve(null);
            }
            resolve(res?.jobAgentProfile || null);
          } catch (e) {
            resolve(null);
          }
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

  // React/Angular/Vue compatible native value setter with Shadow DOM event composition
  function setNativeValue(element, value) {
    if (!element || value === undefined || value === null) return false;
    const strVal = String(value).trim();
    if (!strVal) return false;

    if (element.value === strVal) return false;

    try {
      const isTextarea = element.tagName.toLowerCase() === "textarea";
      const proto = isTextarea ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;

      // Reset React synthetic event value tracker
      if (element._valueTracker) {
        element._valueTracker.setValue("");
      }

      if (setter) {
        setter.call(element, strVal);
      } else {
        element.value = strVal;
      }

      element.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      element.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      element.dispatchEvent(new Event("blur", { bubbles: true, composed: true }));

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

  // Extract contextual signature from an element across Shadow DOM, wrappers, containers, and siblings
  function getElementSignature(el) {
    const parts = [
      el.getAttribute("name") || "",
      el.getAttribute("id") || "",
      el.getAttribute("placeholder") || "",
      el.getAttribute("autocomplete") || "",
      el.getAttribute("aria-label") || "",
      el.getAttribute("data-automation-id") || "",
      el.getAttribute("data-test") || "",
      el.getAttribute("data-testid") || "",
      el.getAttribute("data-qa") || "",
      el.getAttribute("title") || "",
      el.getAttribute("type") || ""
    ];

    // Check aria-labelledby
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      const rootNode = el.getRootNode?.() || document;
      const lblEl = (rootNode.getElementById ? rootNode.getElementById(labelledBy) : null) || document.getElementById(labelledBy);
      if (lblEl) parts.push(lblEl.innerText || lblEl.textContent || "");
    }

    // Check explicit <label for="id">
    if (el.id) {
      const rootNode = el.getRootNode?.() || document;
      const lbl = rootNode.querySelector ? rootNode.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
      if (lbl) parts.push(lbl.innerText || lbl.textContent || "");
    }

    // Check wrapping <label>
    const parentLabel = el.closest ? el.closest("label") : null;
    if (parentLabel) parts.push(parentLabel.innerText || parentLabel.textContent || "");

    // Check Shadow Host if inside Shadow DOM (e.g. SmartRecruiters <spl-input>)
    const rootNode = el.getRootNode ? el.getRootNode() : null;
    if (rootNode && rootNode.host) {
      const host = rootNode.host;
      parts.push(
        host.getAttribute("label") || "",
        host.getAttribute("name") || "",
        host.getAttribute("data-test") || "",
        host.getAttribute("data-automation-id") || "",
        host.getAttribute("placeholder") || "",
        host.getAttribute("aria-label") || ""
      );
      const hostLabel = host.querySelector ? host.querySelector("label, .label, [class*='label']") : null;
      if (hostLabel) parts.push(hostLabel.innerText || hostLabel.textContent || "");
    }

    // Check preceding siblings (e.g. <label>First name*</label><input>)
    if (el.previousElementSibling) {
      const prevText = (el.previousElementSibling.innerText || el.previousElementSibling.textContent || "").trim();
      if (prevText.length < 100) parts.push(prevText);
    }
    // Only check parent sibling in table cells (e.g. <tr><td>Label</td><td><input></td></tr>)
    if (el.parentElement?.tagName === "TD" && el.parentElement.previousElementSibling?.tagName === "TD") {
      const prevCellText = (el.parentElement.previousElementSibling.innerText || el.parentElement.previousElementSibling.textContent || "").trim();
      if (prevCellText.length < 100) parts.push(prevCellText);
    }

    // Check parent containers (up to 4 levels) for child label and concise text
    let curr = el.parentElement;
    for (let i = 0; i < 4 && curr; i++) {
      const lbl = curr.querySelector ? curr.querySelector("label, .label, [class*='label'], [class*='title'], [class*='header']") : null;
      if (lbl && lbl !== el && !lbl.contains(el)) {
        const lblText = (lbl.innerText || lbl.textContent || "").trim();
        if (lblText.length < 120) parts.push(lblText);
        break;
      }
      const cText = (curr.innerText || curr.textContent || "").trim();
      if (cText && cText.length < 100) {
        parts.push(cText);
      }
      curr = curr.parentElement;
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

    const inputs = querySelectorAllDeep("input:not([type='hidden'])");
    let matches = 0;
    for (const inp of inputs) {
      const sig = getElementSignature(inp);
      if (sig.includes("email") || sig.includes("resume") || sig.includes("phone") || sig.includes("linkedin") || sig.includes("first name")) {
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
      ".ashby-job-posting-heading", "[data-test='job-title']", "h1", "h2[class*='title']", "h2"
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
    // A. Check logo images first (alt / title attribute)
    const logoSelectors = [
      "img[class*='logo']", "header img", ".company-logo img", ".branding-logo img",
      "img[alt*='logo' i]", "img[alt*='company' i]", "[data-test='company-logo']",
      "[data-automation-id='companyLogo'] img", ".app-header img"
    ];
    for (const sel of logoSelectors) {
      const img = document.querySelector(sel);
      if (img) {
        const alt = (img.getAttribute("alt") || img.getAttribute("title") || "").replace(/logo/i, "").trim();
        if (alt && alt.length >= 2 && !isAtsVendor(alt)) {
          company = alt;
          break;
        }
      }
    }

    // B. Check standard company element selectors
    if (!company) {
      const companySelectors = [
        ".company-name", "[data-automation-id='companyName']",
        ".jobsearch-JobInfoHeader-companyName", ".topcard__flavor--black-link",
        "[class*='company']", "[data-test='company-name']",
        ".job-details-jobs-unified-top-card__company-name",
        "a[href*='/company/']", "span[class*='employer']"
      ];

      for (const sel of companySelectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim().length > 1) {
          const txt = el.innerText.trim();
          if (!isAtsVendor(txt) && !txt.toLowerCase().includes("careers") && !txt.toLowerCase().includes("jobs")) {
            company = txt;
            break;
          }
        }
      }
    }

    // C. Extract from URL pathname or subdomain (avoiding ATS vendor names)
    if (!company || isAtsVendor(company)) {
      const host = window.location.hostname.toLowerCase();
      const path = window.location.pathname;

      // SmartRecruiters: jobs.smartrecruiters.com/<company_slug>/... or /company/<slug>
      if (host.includes("smartrecruiters.com")) {
        const m = path.match(/\/(?:company\/)?([a-zA-Z0-9_-]+)/);
        if (m && m[1] && !["apply", "jobs", "careers", "all", "search", "details"].includes(m[1].toLowerCase())) {
          company = m[1].replace(/([A-Z])/g, " $1").replace(/[_-]+/g, " ").trim();
        }
      }
      // Workday: <company>.myworkdayjobs.com
      else if (host.includes("myworkdayjobs.com")) {
        const sub = host.split(".")[0];
        if (sub && sub !== "www") {
          company = sub.replace(/[-_]+/g, " ");
        }
      }
      // Greenhouse: boards.greenhouse.io/<company>
      else if (host.includes("greenhouse.io")) {
        const m = path.match(/\/([a-zA-Z0-9_-]+)/);
        if (m && m[1] && !["embed", "jobs"].includes(m[1].toLowerCase())) {
          company = m[1].replace(/[-_]+/g, " ");
        }
      }
      // Lever: jobs.lever.co/<company>
      else if (host.includes("lever.co")) {
        const m = path.match(/\/([a-zA-Z0-9_-]+)/);
        if (m && m[1]) company = m[1].replace(/[-_]+/g, " ");
      }
      // General hostname domain fallback (only if NOT an ATS vendor)
      else {
        const parts = host.split(".");
        if (parts.length >= 2) {
          let domainBase = parts[parts.length - 2];
          if (["co", "com", "org", "net"].includes(domainBase) && parts.length >= 3) {
            domainBase = parts[parts.length - 3];
          }
          if (!isAtsVendor(domainBase)) {
            company = domainBase.charAt(0).toUpperCase() + domainBase.slice(1);
          }
        }
      }
    }

    if (!company || isAtsVendor(company)) {
      company = "Employer";
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

  // Detect whether the page has a genuine, substantive Job Description or is a direct application form
  function hasGenuineJobDescription(description, title = "") {
    if (!description || typeof description !== "string") return false;
    const cleanDesc = description.trim();
    if (cleanDesc.length < 150) return false;

    const lower = cleanDesc.toLowerCase();

    // Check for application form boilerplate indicators
    const formKeywords = [
      "first name", "last name", "confirm your email", "confirm email",
      "choose an option to autocomplete", "fields marked with * are required",
      "choose a file or drop it here", "upload resume", "drag and drop",
      "phone number", "personal information", "apply with indeed",
      "attach resume", "browse file", "submit application", "easy apply"
    ];

    let formKeywordCount = 0;
    for (const kw of formKeywords) {
      if (lower.includes(kw)) formKeywordCount++;
    }

    // Check for substantive Job Description indicators
    const jdKeywords = [
      "responsibilities", "key responsibilities", "job responsibilities",
      "requirements", "basic requirements", "minimum requirements", "required skills",
      "qualifications", "minimum qualifications", "preferred qualifications",
      "what you will do", "what you'll do", "about the role", "about the job",
      "who you are", "role overview", "job overview", "we are looking for",
      "ideal candidate", "years of experience in", "bachelor's degree",
      "master's degree", "technical requirements", "skills required"
    ];

    let jdKeywordCount = 0;
    for (const kw of jdKeywords) {
      if (lower.includes(kw)) jdKeywordCount++;
    }

    // If it has multiple form field labels and no substantive JD sections, it's an application form!
    if (formKeywordCount >= 3 && jdKeywordCount === 0) {
      return false;
    }

    // If it has at least 1 strong JD section header and sufficient length (> 200 chars), it's a genuine JD
    if (jdKeywordCount >= 1 && cleanDesc.length >= 200) {
      return true;
    }

    // If form field count is significant compared to JD terms
    if (formKeywordCount >= 2 && jdKeywordCount < 2) {
      return false;
    }

    return cleanDesc.length >= 350;
  }

  // ==========================================
  // 2. GEMINI AI RESUME TAILORING ENGINE
  // ==========================================
  async function tailorResumeForJob(jobDetails, profile, hasJd = true) {
    const defaultTitle = profile.current_title || "Backend Developer";
    const candSkills = Array.isArray(profile.skills) && profile.skills.length
      ? profile.skills
      : ["Java", "Spring Boot", "REST APIs", "MySQL", "React", "Python", "SQL", "Git", "Docker"];

    // When on a form without a genuine JD, fall back cleanly to default profile!
    if (!hasJd) {
      console.log("[JobAgent] No genuine JD found on page. Utilizing default profile resume.");
      const cleanCompany = (jobDetails.company && !isAtsVendor(jobDetails.company) && jobDetails.company !== "Employer") ? jobDetails.company : "";
      const headline = `${defaultTitle} - ${candSkills.slice(0, 4).join(", ")}`;
      const summary = `Results-driven ${defaultTitle} with ${profile.years_exp || "1+ years"} of experience engineering high-performance RESTful APIs, database architectures, and scalable microservices with Java, Spring Boot, and MySQL. Proven track record of clean code standards, JPA/MySQL optimization, and reliable system design.`;

      const defaultBullets = [
        "Architected and optimized Java Spring Boot REST APIs using Controller-Service-Repository patterns, JPA, and MySQL.",
        "Built and secured merchant workflows with JWT authentication, asynchronous processing, and third-party integrations.",
        "Engineered database schemas and complex queries to support high-reliability transaction processing with zero downtime."
      ];

      const defaultCoverLetter = `Dear Hiring Team${cleanCompany ? " at " + cleanCompany : ""},\n\nI am writing to express my strong interest in the ${jobDetails.title && !jobDetails.title.toLowerCase().includes("apply") ? jobDetails.title : defaultTitle} position. With hands-on experience in backend development, Java Spring Boot, and database architecture, I am eager to contribute immediately to your team's engineering goals.\n\nSincerely,\n${profile.name}`;

      return {
        is_default: true,
        title: jobDetails.title && !jobDetails.title.toLowerCase().includes("apply") ? cleanText(jobDetails.title) : defaultTitle,
        company: cleanCompany ? cleanText(cleanCompany) : "",
        headline: cleanText(headline),
        summary: cleanText(summary),
        prioritized_skills: candSkills.map(cleanText),
        tailored_bullets: defaultBullets.map(cleanText),
        cover_letter: defaultCoverLetter
      };
    }

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
      title: cleanText(jobDetails.title),
      company: cleanText(jobDetails.company),
      headline: cleanText(headline),
      summary: cleanText(summary),
      prioritized_skills: prioritizedSkills.map(cleanText),
      tailored_bullets: tailoredBullets.map(cleanText),
      cover_letter: coverLetter
    };
  }

  // ==========================================
  // 3. IN-BROWSER ATS PDF COMPILER (PURE JS)
  // ==========================================
  const HELVETICA_CHAR_WIDTHS = {
    ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667, '\'': 222,
    '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
    '0': 556, '1': 556, '2': 556, '3': 556, '4': 556, '5': 556, '6': 556, '7': 556,
    '8': 556, '9': 556, ':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556,
    '@': 1015, 'A': 667, 'B': 667, 'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778,
    'H': 722, 'I': 278, 'J': 500, 'K': 667, 'L': 556, 'M': 833, 'N': 722, 'O': 778,
    'P': 667, 'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722, 'V': 667, 'W': 944,
    'X': 667, 'Y': 667, 'Z': 611, '[': 278, '\\': 278, ']': 278, '^': 469, '_': 556,
    'a': 556, 'b': 556, 'c': 500, 'd': 556, 'e': 556, 'f': 278, 'g': 556, 'h': 556,
    'i': 222, 'j': 222, 'k': 500, 'l': 222, 'm': 833, 'n': 556, 'o': 556, 'p': 556,
    'q': 556, 'r': 333, 's': 500, 't': 278, 'u': 556, 'v': 500, 'w': 722, 'x': 500,
    'y': 500, 'z': 500, '{': 334, '|': 260, '}': 334, '~': 584
  };

  function getTextWidth(text, fontSize) {
    if (!text) return 0;
    let w = 0;
    for (let i = 0; i < text.length; i++) {
      w += HELVETICA_CHAR_WIDTHS[text[i]] || 550;
    }
    return (w * fontSize) / 1000;
  }

  function cleanText(text) {
    if (!text) return "";
    return String(text)
      .replace(/[\u2013\u2014]/g, " - ")
      .replace(/[\u2018\u2019]/g, "'")
      .replace(/[\u201C\u201D]/g, '"')
      .replace(/[\u2022\u2023\u25E6\u2043\u2219]/g, "")
      .replace(/â€[¢â“]/g, " - ")
      .replace(/â¢/g, "")
      .replace(/â/g, " - ")
      .replace(/\s+/g, " ")
      .replace(/[^\x20-\x7E]/g, "")
      .trim();
  }

  function escapePdf(text) {
    if (!text) return "";
    return cleanText(text)
      .replace(/\\/g, "\\\\")
      .replace(/\(/g, "\\(")
      .replace(/\)/g, "\\)");
  }

  function wrapText(text, maxPtWidth, fontSize) {
    const cleaned = cleanText(text);
    if (!cleaned) return [];
    const words = cleaned.split(/\s+/);
    const lines = [];
    let currentLine = [];
    let currentWidth = 0;
    const spaceWidth = getTextWidth(" ", fontSize);

    for (const w of words) {
      const wordWidth = getTextWidth(w, fontSize);
      const addedWidth = currentLine.length ? spaceWidth + wordWidth : wordWidth;
      if (currentWidth + addedWidth <= maxPtWidth) {
        currentLine.push(w);
        currentWidth += addedWidth;
      } else {
        if (currentLine.length) lines.push(currentLine.join(" "));
        currentLine = [w];
        currentWidth = wordWidth;
      }
    }
    if (currentLine.length) lines.push(currentLine.join(" "));
    return lines;
  }

  function buildTailoredPdfBlob(tailored, profile) {
    const leftMargin = 50;
    const rightMargin = 562;
    const contentWidth = rightMargin - leftMargin; // 512 pt
    let y = 745;
    const streamParts = [];

    function addText(text, font, size, posX, posY) {
      const clean = escapePdf(text);
      streamParts.push(`BT /${font} ${size} Tf ${posX.toFixed(1)} ${posY.toFixed(1)} Td (${clean}) Tj ET`);
    }

    function addRightText(text, font, size, posY) {
      const clean = cleanText(text);
      const width = getTextWidth(clean, size);
      const posX = rightMargin - width;
      addText(clean, font, size, posX, posY);
    }

    function addLine(x1, y1, x2, y2, lineWidth = 0.5) {
      streamParts.push(`q ${lineWidth} w 0.82 0.85 0.9 RG ${x1.toFixed(1)} ${y1.toFixed(1)} m ${x2.toFixed(1)} ${y2.toFixed(1)} l S Q`);
    }

    function addSectionHeader(title) {
      y -= 13;
      addText(title, "F2", 9.5, leftMargin, y);
      y -= 3;
      addLine(leftMargin, y, rightMargin, y, 0.6);
      y -= 9;
    }

    function drawBullet(cx, cy, r = 1.35) {
      const k = r * 0.55228475;
      streamParts.push(`q 0.15 0.2 0.3 rg`);
      streamParts.push(`${cx.toFixed(1)} ${(cy + r).toFixed(1)} m ${(cx + k).toFixed(1)} ${(cy + r).toFixed(1)} ${(cx + r).toFixed(1)} ${(cy + k).toFixed(1)} ${(cx + r).toFixed(1)} ${cy.toFixed(1)} c ${(cx + r).toFixed(1)} ${(cy - k).toFixed(1)} ${(cx + k).toFixed(1)} ${(cy - r).toFixed(1)} ${cx.toFixed(1)} ${(cy - r).toFixed(1)} c ${(cx - k).toFixed(1)} ${(cy - r).toFixed(1)} ${(cx - r).toFixed(1)} ${(cy - k).toFixed(1)} ${(cx - r).toFixed(1)} ${cy.toFixed(1)} c ${(cx - r).toFixed(1)} ${(cy + k).toFixed(1)} ${(cx - k).toFixed(1)} ${(cy + r).toFixed(1)} ${cx.toFixed(1)} ${(cy + r).toFixed(1)} c f Q`);
    }

    // 1. Header: Name & Contact Info
    addText(profile.name || "Mrityunjay Kumar", "F2", 18, leftMargin, y);
    y -= 15;

    const contactParts = [
      profile.location || profile.city || "Pune, India",
      profile.phone || "+91-7972379015",
      profile.email || "mrityunjayk456@gmail.com",
      profile.linkedin ? profile.linkedin.replace(/^https?:\/\/(www\.)?/, "") : "linkedin.com/in/mrityunjayk456"
    ].filter(Boolean);

    addText(contactParts.join("  |  "), "F1", 8.5, leftMargin, y);
    y -= 8;
    addLine(leftMargin, y, rightMargin, y, 0.75);
    y -= 13;

    // 2. Targeted Headline
    addText(tailored.headline || `${tailored.title} - ${tailored.company}`, "F2", 10.5, leftMargin, y);
    y -= 4;

    // 3. Professional Summary (Tailored to JD)
    addSectionHeader("PROFESSIONAL SUMMARY");
    const summaryLines = wrapText(tailored.summary, contentWidth, 8.5);
    for (const line of summaryLines) {
      addText(line, "F1", 8.5, leftMargin, y);
      y -= 11.5;
    }

    // 4. Core Technical Skills (Prioritized to JD)
    addSectionHeader("TECHNICAL SKILLS & COMPETENCIES");
    const allSkills = (tailored.prioritized_skills && tailored.prioritized_skills.length)
      ? tailored.prioritized_skills
      : (Array.isArray(profile.skills) ? profile.skills : ["Java", "Spring Boot", "REST APIs", "MySQL", "React", "Python", "SQL", "Git", "Docker"]);
    
    const skillLine1 = "Languages & Frameworks: " + allSkills.slice(0, 8).join(", ");
    const skillLine2 = "Databases, Cloud & Tools: " + allSkills.slice(8, 16).join(", ");
    const skillLinesToPrint = [
      skillLine1,
      allSkills.length > 8 ? skillLine2 : null
    ].filter(Boolean);

    for (const sl of skillLinesToPrint) {
      const wrapped = wrapText(sl, contentWidth, 8.5);
      for (const line of wrapped) {
        addText(line, "F1", 8.5, leftMargin, y);
        y -= 11.5;
      }
    }

    // 5. Professional Experience (With Tailored Bullets & Hanging Indents)
    addSectionHeader("PROFESSIONAL EXPERIENCE");

    // Current Role
    const company = profile.current_company || "Digitalllydrunk Pvt Ltd";
    const roleTitle = profile.current_title || "Backend Developer";
    const dates = `${profile.experience_start || "Nov 2025"} - ${profile.experience_end || "Present"}`;

    addText(`${roleTitle} | ${company}`, "F2", 9, leftMargin, y);
    addRightText(dates, "F1", 8.5, y);
    y -= 12;

    const bulletTextWidth = contentWidth - 14;
    for (const bullet of tailored.tailored_bullets) {
      const bLines = wrapText(bullet, bulletTextWidth, 8.5);
      drawBullet(leftMargin + 5, y + 2.8, 1.35);
      for (const line of bLines) {
        addText(line, "F1", 8.5, leftMargin + 14, y);
        y -= 11.5;
      }
      y -= 3;
    }
    y -= 3;

    // Secondary Role / Internship
    addText("Software Developer (Intern) | Tubhyam IT Solution", "F2", 9, leftMargin, y);
    addRightText("Aug 2025 - Nov 2025", "F1", 8.5, y);
    y -= 12;

    const internBullets = [
      "Developed Java Spring Boot REST APIs for payment workflows handling 1,000+ transactions monthly.",
      "Integrated Stripe Payment Gateway for secure payment classification and asynchronous webhooks."
    ];
    for (const b of internBullets) {
      const bLines = wrapText(b, bulletTextWidth, 8.5);
      drawBullet(leftMargin + 5, y + 2.8, 1.35);
      for (const line of bLines) {
        addText(line, "F1", 8.5, leftMargin + 14, y);
        y -= 11.5;
      }
      y -= 3;
    }
    y -= 2;

    // 6. Education & Certifications
    addSectionHeader("EDUCATION & CERTIFICATIONS");
    addText(profile.degree || "Post Graduate Diploma in Advanced Computing (PG-DAC)", "F2", 8.5, leftMargin, y);
    addRightText("2025", "F1", 8.5, y);
    y -= 11;
    addText(profile.school || "Sunbeam Institute of Information Technology", "F1", 8.5, leftMargin, y);
    y -= 12;
    addText("B.Tech in Mechanical Engineering | MIT Academy of Engineering", "F1", 8.5, leftMargin, y);
    addRightText("2020", "F1", 8.5, y);
    y -= 12;
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

      fileInput.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      fileInput.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      fileInput.classList.add("jobagent-highlight");

      // Visually update nearby filename displays (e.g. SmartRecruiters dropzone, WordPress, custom file uploaders)
      const container = fileInput.closest(".wpcf7-form-control-wrap, .form-group, div, label, [class*='dropzone'], [class*='upload'], spl-dropzone");
      if (container) {
        container.classList.add("jobagent-highlight");
        const nameBadge = container.querySelector(".file-name, .custom-file-label, .file-upload-status, [class*='filename'], [class*='name']");
        if (nameBadge) {
          nameBadge.textContent = fileToAttach.name;
        } else {
          const helper = container.querySelector("p, span, [class*='description'], [class*='text']");
          if (helper && helper.innerText.toLowerCase().includes("drop")) {
            helper.innerHTML = `✅ Attached: <strong>${fileToAttach.name}</strong>`;
          }
        }
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

      const jobDetails = extractJobDetails();
      const hasJd = hasGenuineJobDescription(jobDetails.description, jobDetails.title);

      if (!hasJd) {
        showManualJdModal((pastedJd) => {
          runAutofill(null, pastedJd);
        });
      } else {
        await runAutofill();
      }
    });

    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      container.style.display = "none";
    });
  }

  // On-page modal to paste JD when no JD is detected on form page
  function showManualJdModal(onProceed) {
    let modal = document.getElementById("jobagent-jd-modal");
    if (modal) modal.remove();

    modal = document.createElement("div");
    modal.id = "jobagent-jd-modal";
    modal.innerHTML = `
      <div class="jobagent-jd-modal-header">
        <div class="jobagent-jd-title">
          <span>📝</span>
          <span>No JD on this page</span>
        </div>
        <button class="jobagent-close-btn" id="jobagentCloseJdModalBtn" title="Close">×</button>
      </div>
      <p class="jobagent-jd-desc">Paste the job description below to tailor your resume & form fields:</p>
      <textarea id="jobagent-manual-jd-input" placeholder="Paste Job Description (responsibilities, skills, requirements)..." rows="4"></textarea>
      <div class="jobagent-jd-btn-row">
        <button id="jobagent-tailor-btn" class="jobagent-btn-primary">⚡ Tailor & Autofill</button>
        <button id="jobagent-default-btn" class="jobagent-btn-secondary">📄 Use Default Profile</button>
      </div>
    `;

    document.body.appendChild(modal);

    const input = document.getElementById("jobagent-manual-jd-input");
    const tailorBtn = document.getElementById("jobagent-tailor-btn");
    const defaultBtn = document.getElementById("jobagent-default-btn");
    const closeBtn = document.getElementById("jobagentCloseJdModalBtn");

    try {
      chrome.storage.local.get(["customJdText"], (res) => {
        if (res?.customJdText && input) {
          input.value = res.customJdText;
        }
      });
    } catch (e) {}

    input.focus();

    closeBtn.addEventListener("click", () => modal.remove());

    tailorBtn.addEventListener("click", () => {
      const pastedJd = input.value.trim();
      modal.remove();
      if (pastedJd) {
        try {
          chrome.storage.local.set({ customJdText: pastedJd });
        } catch (e) {}
      }
      onProceed(pastedJd);
    });

    defaultBtn.addEventListener("click", () => {
      modal.remove();
      onProceed("");
    });
  }

  // ==========================================
  // 5. MASTER AUTOFILL & TAILORING EXECUTION
  // ==========================================
  async function runAutofill(passedProfile = null, manualJd = "") {
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

      // 1. Scrape Job Description & Company from Active Page (or use pasted manual JD)
      const jobDetails = extractJobDetails();
      let hasJd = false;

      if (manualJd && manualJd.trim().length > 15) {
        jobDetails.description = manualJd.trim();
        hasJd = true;
      } else {
        hasJd = hasGenuineJobDescription(jobDetails.description, jobDetails.title);
      }

      let tailoredData = null;
      let tailoredFile = null;

      if (profile.enable_tailored_resume !== false) {
        if (hasJd) {
          if (pillText) pillText.textContent = `Tailoring for ${jobDetails.company.slice(0, 10)}...`;
          tailoredData = await tailorResumeForJob(jobDetails, profile, true);
          const pdfBlob = buildTailoredPdfBlob(tailoredData, profile);
          const cleanCompany = (jobDetails.company || "Company").replace(/[^a-zA-Z0-9]/g, "_").slice(0, 20);
          const cleanName = (profile.name || "Candidate").replace(/[^a-zA-Z0-9]/g, "_");
          const filename = `${cleanName}_Resume_${cleanCompany}.pdf`;
          tailoredFile = new File([pdfBlob], filename, { type: "application/pdf", lastModified: Date.now() });
        } else {
          // Direct form without rich JD: fall back cleanly to candidate's default profile!
          tailoredData = await tailorResumeForJob(jobDetails, profile, false);

          if (profile.resume_base64) {
            // Use candidate's pre-loaded default resume PDF directly
            const mime = profile.resume_mime || "application/pdf";
            const filename = profile.resume_filename || "Mrityunjay_Kumar_Resume.pdf";
            const blob = base64ToBlob(profile.resume_base64, mime);
            if (blob) {
              tailoredFile = new File([blob], filename, { type: mime, lastModified: Date.now() });
            }
          } else {
            // Compile default clean ATS PDF without ATS vendor suffix
            const pdfBlob = buildTailoredPdfBlob(tailoredData, profile);
            const cleanName = (profile.name || "Candidate").replace(/[^a-zA-Z0-9]/g, "_");
            const filename = `${cleanName}_Resume.pdf`;
            tailoredFile = new File([pdfBlob], filename, { type: "application/pdf", lastModified: Date.now() });
          }
        }
      }

      if (pillText) pillText.textContent = "Autofilling...";

      let filledCount = 0;
      let filesUploaded = 0;

      // 2. Resume File Inputs (<input type="file">) across light DOM and open Shadow DOM
      const fileInputs = querySelectorAllDeep("input[type='file']");
      for (const fi of fileInputs) {
        const sig = getElementSignature(fi);
        const isResume =
          sig.includes("resume") || sig.includes("cv") || sig.includes("curriculum") ||
          sig.includes("upload") || sig.includes("attachment") || sig.includes("document") ||
          sig.includes("choose a file") || sig.includes("drop it here") || sig.includes("drop file") ||
          sig.includes("file") || fileInputs.length === 1;

        if (isResume) {
          if (attachResumeFile(fi, profile, tailoredFile)) {
            filesUploaded++;
            filledCount++;
          }
        }
      }

      // 3. Text Inputs & Textareas across light DOM and open Shadow DOM
      const textElements = querySelectorAllDeep(
        "input:not([type='hidden']):not([type='radio']):not([type='checkbox']):not([type='file']):not([type='submit']):not([type='button']), textarea"
      );

      for (const el of textElements) {
        const sig = getElementSignature(el);
        const directSig = ((el.name || "") + " " + (el.id || "") + " " + (el.placeholder || "") + " " + (el.getAttribute("aria-label") || "")).toLowerCase();
        const isTextarea = el.tagName.toLowerCase() === "textarea";

        // First Name
        if (
          !isTextarea &&
          (sig.includes("first name") || sig.includes("firstname") || sig.includes("given name") ||
           sig.includes("first_name") || sig.includes("given-name") || sig.includes("first-name") ||
           directSig.includes("firstname") || directSig.includes("first_name")) &&
          !sig.includes("last")
        ) {
          if (setNativeValue(el, profile.first_name || profile.name.split(" ")[0])) filledCount++;
        }
        // Last Name
        else if (
          !isTextarea &&
          (sig.includes("last name") || sig.includes("lastname") || sig.includes("family name") ||
           sig.includes("surname") || sig.includes("last_name") || sig.includes("family-name") ||
           sig.includes("last-name") || directSig.includes("lastname") || directSig.includes("last_name"))
        ) {
          const parts = profile.name.split(" ");
          const lastName = profile.last_name || (parts.length > 1 ? parts.slice(1).join(" ") : "");
          if (setNativeValue(el, lastName)) filledCount++;
        }
        // Full Name (Matches "Name *", "Full Name", "Your Name", etc.)
        else if (
          !isTextarea &&
          (/\b(full\s*name|candidate\s*name|applicant\s*name|your\s*name)\b/i.test(sig) ||
           (/\bname\b/i.test(sig) && !sig.includes("first") && !sig.includes("last") &&
            !sig.includes("company") && !sig.includes("user") && !sig.includes("school") &&
            !sig.includes("file") && !sig.includes("drop")))
        ) {
          if (setNativeValue(el, profile.name)) filledCount++;
        }
        // Confirm Email (check before generic email)
        else if (
          !isTextarea &&
          (sig.includes("confirm your email") || sig.includes("confirm email") ||
           sig.includes("confirm_email") || sig.includes("email confirmation") ||
           sig.includes("re-enter email") || sig.includes("repeat email") || sig.includes("verify email"))
        ) {
          if (setNativeValue(el, profile.email)) filledCount++;
        }
        // Email
        else if (!isTextarea && (el.type === "email" || sig.includes("email") || sig.includes("e-mail"))) {
          if (setNativeValue(el, profile.email)) filledCount++;
        }
        // Phone
        else if (!isTextarea && (el.type === "tel" || sig.includes("phone") || sig.includes("mobile") || sig.includes("cell") || sig.includes("contact number"))) {
          const containerText = el.parentElement?.innerText || el.closest(".form-group, div, [class*='phone'], [class*='input']")?.innerText || "";
          let phoneToFill = profile.phone || "+91-7972379015";
          if (containerText.includes("+91") || containerText.includes("+1") || containerText.includes("flag")) {
            phoneToFill = phoneToFill.replace(/^\+?\d{1,3}[-\s]?/, "");
          }
          if (setNativeValue(el, phoneToFill)) filledCount++;
        }
        // City (check before general location/address)
        else if (!isTextarea && (sig.includes("city") || sig.includes("current city")) && !sig.includes("state") && !sig.includes("country")) {
          const loc = profile.city || (profile.location ? profile.location.split(",")[0].trim() : "Pune");
          if (setNativeValue(el, loc)) filledCount++;
        }
        // Technical Skills / Skill Sets (e.g. "Skill Sets *", "Technical Skills", "Technologies")
        else if (
          directSig.includes("skill") ||
          (isTextarea && sig.includes("skill")) ||
          ((sig.includes("skill") || sig.includes("technical skill") || sig.includes("technolog")) && !sig.includes("years of experience"))
        ) {
          const skillsVal = (tailoredData?.prioritized_skills && tailoredData.prioritized_skills.length)
            ? tailoredData.prioritized_skills.join(", ")
            : (Array.isArray(profile.skills) ? profile.skills.join(", ") : (profile.skills || "Java, Spring Boot, MySQL, REST APIs, React"));
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
        // Location / Address
        else if (sig.includes("location") || sig.includes("current location") || sig.includes("address")) {
          const loc = profile.location || profile.city;
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
            const letter = tailoredData?.cover_letter || `Dear Hiring Team,\n\nI am writing to express my strong interest in this position. With hands-on experience in Java Spring Boot and backend engineering, I am excited about the opportunity to contribute to your engineering goals.\n\nSincerely,\n${profile.name}`;
            if (setNativeValue(el, letter)) filledCount++;
          } else if (profile.enable_ai_answers && profile.gemini_api_key && !el.value && hasJd) {
            const label = el.closest(".form-group, .field, div")?.innerText || sig;
            const prompt = `Answer this job application question for a Java/Backend candidate named ${profile.name} applying for ${jobDetails.title} at ${jobDetails.company}. Question: "${label.slice(0, 200)}". Keep it 2-3 sentences, direct, first person.`;
            const aiAnswer = await callGeminiApi(prompt, profile);
            if (aiAnswer && setNativeValue(el, aiAnswer)) filledCount++;
          }
        }
      }

      // 4. Radio Buttons (Work Auth, Sponsorship, etc.) across light DOM and open Shadow DOM
      const radios = querySelectorAllDeep("input[type='radio']");
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
              r.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
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
              r.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
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
              r.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
              filledCount++;
            }
          }
        }
      }

      // 5. Select Dropdowns (Country, Experience, Gender, etc.) across light DOM and open Shadow DOM
      const selects = querySelectorAllDeep("select");
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
                sel.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
                sel.classList.add("jobagent-highlight");
                filledCount++;
              }
              break;
            }
          }
        }
      }

      // 6. Checkboxes (Terms, consent) across light DOM and open Shadow DOM
      const checkboxes = querySelectorAllDeep("input[type='checkbox']");
      for (const cb of checkboxes) {
        const sig = getElementSignature(cb);
        if (
          sig.includes("agree") || sig.includes("terms") || sig.includes("consent") ||
          sig.includes("privacy policy") || sig.includes("certify")
        ) {
          if (!cb.checked) {
            cb.click();
            cb.checked = true;
            cb.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
            filledCount++;
          }
        }
      }

      let statusMsg = "";
      if (tailoredData?.is_default) {
        statusMsg = " (🎯 Loaded Default Profile Resume)";
      } else if (tailoredFile && jobDetails.company && !isAtsVendor(jobDetails.company) && jobDetails.company !== "Employer") {
        statusMsg = ` (🎯 Resume Tailored for ${jobDetails.company})`;
      } else if (tailoredFile) {
        statusMsg = " (🎯 Resume Tailored for Role)";
      }
      showToast(`Autofilled ${filledCount} fields${statusMsg}!`, true);

      return {
        success: true,
        count: filledCount,
        filesUploaded: filesUploaded,
        tailoredFor: tailoredData?.is_default ? "Default Profile" : (jobDetails.company !== "Employer" ? jobDetails.company : ""),
        isDefault: Boolean(tailoredData?.is_default),
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
          runAutofill(request.profile, request.manualJd || "").then((res) => {
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
            const hasJd = hasGenuineJobDescription(jd.description, jd.title);
            sendResponse({
              ...jd,
              hasJd: hasJd
            });
          } catch (err) {
            sendResponse({ title: "Software Engineer", company: "Company", hasJd: false });
          }
          return false;
        }

        if (request.action === "GENERATE_TAILORED_PREVIEW") {
          (async () => {
            try {
              const jd = extractJobDetails();
              const profile = request.profile || (await getProfile());

              if (request.manualJd && request.manualJd.trim().length > 15) {
                jd.description = request.manualJd.trim();
              }

              const hasJd = Boolean(request.manualJd && request.manualJd.trim().length > 15) || hasGenuineJobDescription(jd.description, jd.title);
              const tailored = await tailorResumeForJob(jd, profile, hasJd);
              const blob = buildTailoredPdfBlob(tailored, profile);

              const reader = new FileReader();
              reader.onloadend = () => {
                const cleanName = (profile.name || "Candidate").replace(/[^a-zA-Z0-9]/g, "_");
                const filename = tailored.is_default
                  ? `${cleanName}_Resume.pdf`
                  : `${cleanName}_Resume_${(jd.company || "Company").replace(/[^a-zA-Z0-9]/g, "_")}.pdf`;

                if (isContextValid()) {
                  try {
                    sendResponse({
                      success: true,
                      jobTitle: tailored.is_default ? (profile.current_title || "Backend Developer") : (tailored.title || jd.title),
                      company: tailored.is_default ? "Default Profile" : (tailored.company || jd.company),
                      isDefault: Boolean(tailored.is_default),
                      filename: filename,
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
