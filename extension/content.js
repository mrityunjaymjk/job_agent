/**
 * Job Agent AI - Content Script Form Filler
 * Autonomously inspects and autofills job applications across ATS portals (Greenhouse, Lever, Workday, LinkedIn, Indeed, etc.)
 */

(() => {
  let activeProfile = null;
  let isAutofilling = false;

  // Retrieve stored profile
  function getProfile() {
    return new Promise((resolve) => {
      chrome.storage.local.get(["jobAgentProfile"], (res) => {
        resolve(res.jobAgentProfile || null);
      });
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

  // React/Angular/Vue compatible value setter
  function setNativeValue(element, value) {
    if (!element || value === undefined || value === null) return false;
    const strVal = String(value);

    // Skip if already has correct value
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

  // Attach resume file directly to <input type="file"> via DataTransfer API
  function attachResumeFile(fileInput, profile) {
    if (!profile.resume_base64) return false;
    try {
      const mime = profile.resume_mime || "application/pdf";
      const filename = profile.resume_filename || "Resume.pdf";
      const blob = base64ToBlob(profile.resume_base64, mime);
      if (!blob) return false;

      const file = new File([blob], filename, { type: mime, lastModified: Date.now() });
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      fileInput.files = dataTransfer.files;

      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
      fileInput.dispatchEvent(new Event("input", { bubbles: true }));
      fileInput.classList.add("jobagent-highlight");

      // Highlight parent upload dropzone if available
      const parentDrop = fileInput.closest(".dropzone, .file-upload, [class*='upload'], [class*='drop'], label");
      if (parentDrop) parentDrop.classList.add("jobagent-highlight");

      return true;
    } catch (e) {
      console.warn("[JobAgent] Error attaching resume file:", e);
      return false;
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

    // Check associated labels
    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label) parts.push(label.innerText);
    }

    const parentLabel = el.closest("label");
    if (parentLabel) parts.push(parentLabel.innerText);

    // Closest form group or container text
    const container = el.closest(".form-group, .field, [class*='formRow'], [class*='field'], tr, div");
    if (container) {
      const text = container.innerText || "";
      if (text.length < 200) parts.push(text);
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

    // Detect if multiple standard job inputs are present
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

  // Inject floating action pill
  function injectFloatingPill() {
    if (document.getElementById("jobagent-floating-container")) return;

    const container = document.createElement("div");
    container.id = "jobagent-floating-container";
    container.innerHTML = `
      <div class="jobagent-pill" id="jobagentPillBtn" title="Job Agent AI - 1-Click Autofill">
        <div class="jobagent-icon">⚡</div>
        <span class="jobagent-text">Autofill with AI</span>
        <button class="jobagent-close-btn" id="jobagentClosePillBtn" title="Dismiss">×</button>
      </div>
    `;

    document.body.appendChild(container);

    const pillBtn = document.getElementById("jobagentPillBtn");
    const closeBtn = document.getElementById("jobagentClosePillBtn");

    pillBtn.addEventListener("click", async (e) => {
      if (e.target === closeBtn) return;
      await runAutofill();
    });

    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      container.style.display = "none";
    });
  }

  // Display Toast Banner
  function showToast(message, isSuccess = true) {
    let toast = document.getElementById("jobagent-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "jobagent-toast";
      document.body.appendChild(toast);
    }

    toast.innerHTML = `<span>${isSuccess ? "🎉" : "⚠️"}</span> <span>${message}</span>`;
    toast.style.borderColor = isSuccess ? "#10b981" : "#f59e0b";
    toast.classList.add("show");

    setTimeout(() => {
      toast.classList.remove("show");
    }, 4500);
  }

  // Direct Gemini REST API caller for open-ended questions
  async function answerWithGemini(question, profile) {
    if (!profile.gemini_api_key || !profile.enable_ai_answers) return null;

    const apiKey = profile.gemini_api_key.trim();
    const model = profile.gemini_model || "gemini-1.5-flash";
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

    const prompt = `You are an AI assistant answering a job application question for a software candidate.
Candidate Details:
- Name: ${profile.name}
- Current/Target Role: Backend / Fullstack Software Engineer
- Core Skills: ${Array.isArray(profile.skills) ? profile.skills.join(", ") : "Java, Spring Boot, REST APIs, MySQL, React, JavaScript"}
- Experience Summary: ${profile.experience || "1+ years experience developing Java Spring Boot microservices, REST APIs, and database solutions."}

Job Application Question: "${question}"
Page Title: "${document.title}"

Instructions:
Write a direct, professional, concise answer in first person ("I have...", "My background..."). Keep it between 2 to 4 sentences. Do NOT include placeholders, greetings, or formatting asterisks.`;

    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { maxOutputTokens: 250, temperature: 0.3 }
        })
      });

      if (!resp.ok) {
        console.warn("[JobAgent] Gemini API error:", resp.status, await resp.text());
        return null;
      }

      const data = await resp.json();
      const answer = data.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
      return answer || null;
    } catch (e) {
      console.warn("[JobAgent] Gemini fetch failed:", e);
      return null;
    }
  }

  // Core Autofill Logic
  async function runAutofill(passedProfile = null) {
    if (isAutofilling) return;
    isAutofilling = true;

    const pillText = document.querySelector(".jobagent-text");
    if (pillText) pillText.textContent = "Filling...";

    const profile = passedProfile || (await getProfile());
    if (!profile) {
      showToast("Please configure your profile in the Job Agent popup first!", false);
      if (pillText) pillText.textContent = "Autofill with AI";
      isAutofilling = false;
      return { success: false, message: "Profile not found" };
    }

    let filledCount = 0;
    let filesUploaded = 0;

    // 0. Resume File Inputs (<input type="file">)
    const fileInputs = document.querySelectorAll("input[type='file']");
    for (const fi of fileInputs) {
      const sig = getElementSignature(fi);
      if (
        sig.includes("resume") || sig.includes("cv") || sig.includes("curriculum") ||
        sig.includes("attachment") || sig.includes("document") || fileInputs.length === 1
      ) {
        if (attachResumeFile(fi, profile)) {
          filesUploaded++;
          filledCount++;
        }
      }
    }

    // 1. Text Inputs & Textareas
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
      // Full Name (only if not specific first/last)
      else if (
        (sig.includes("full name") || sig.includes("your name") || sig.includes("legal name") || sig === "name" || sig.startsWith("name ")) &&
        !sig.includes("first") && !sig.includes("last") && !sig.includes("company") && !sig.includes("school")
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
      // Experience years
      else if (sig.includes("years of experience") || sig.includes("total experience") || sig.includes("experience in years")) {
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
        if (setNativeValue(el, profile.resume_raw_text || profile.experience)) filledCount++;
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
      // Textarea / Open-Ended Question Answering with Gemini AI
      else if (isTextarea || el.clientHeight > 50) {
        if (sig.includes("cover letter")) {
          const letter = `Dear Hiring Team,\n\nI am writing to express my strong interest in this position. With over a year of hands-on experience developing robust backend services, RESTful APIs, and Spring Boot applications, I am eager to contribute to your engineering team.\n\nBest regards,\n${profile.name}`;
          if (setNativeValue(el, letter)) filledCount++;
        } else if (profile.enable_ai_answers && profile.gemini_api_key && !el.value) {
          // Send to Gemini for contextual answer
          const label = el.closest(".form-group, .field, div")?.innerText || sig;
          const aiAnswer = await answerWithGemini(label.slice(0, 300), profile);
          if (aiAnswer && setNativeValue(el, aiAnswer)) filledCount++;
        }
      }
    }

    // 2. Radio Buttons (Work Auth, Sponsorship, etc.)
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

    // 3. Select Dropdowns
    const selects = document.querySelectorAll("select");
    for (const sel of selects) {
      const sig = getElementSignature(sel);
      let targetText = null;

      if (sig.includes("country")) {
        targetText = profile.country || "India";
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
          if (opt.text.toLowerCase().includes(targetText.toLowerCase())) {
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

    // 4. Checkboxes (Terms, consent)
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

    if (pillText) pillText.textContent = "Autofill with AI";
    isAutofilling = false;

    const fileNotice = filesUploaded > 0 ? ` (+${filesUploaded} resume attached)` : "";
    showToast(`Autofilled ${filledCount} field${filledCount === 1 ? "" : "s"}${fileNotice} successfully!`, true);
    return { success: true, count: filledCount, filesUploaded: filesUploaded };
  }

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "AUTOFILL_FORM") {
      runAutofill(request.profile).then((res) => sendResponse(res));
      return true; // Keep message channel open for async response
    }
  });

  // Initialization
  (async () => {
    const profile = await getProfile();
    const showPill = profile?.show_floating_pill !== false;

    if (showPill && isJobApplicationPage()) {
      injectFloatingPill();
    }
  })();
})();
