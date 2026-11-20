document.addEventListener("DOMContentLoaded", async () => {
  // Elements
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  const autofillBtn = document.getElementById("autofillCurrentTabBtn");
  const saveBtn = document.getElementById("saveProfileBtn");
  const resetBtn = document.getElementById("resetDefaultsBtn");
  const feedbackEl = document.getElementById("pageFeedback");
  const aiBadge = document.getElementById("aiStatusBadge");

  // Resume elements
  const resumeFileNameEl = document.getElementById("resumeFileName");
  const resumeFileMetaEl = document.getElementById("resumeFileMeta");
  const downloadResumeBtn = document.getElementById("downloadResumeBtn");
  const copyResumeTextBtn = document.getElementById("copyResumeTextBtn");
  const resumeFileInput = document.getElementById("resumeFileInput");

  // JD Tailor elements
  const detectedJobTitleEl = document.getElementById("detectedJobTitle");
  const detectedCompanyEl = document.getElementById("detectedCompany");
  const previewTailoredBtn = document.getElementById("previewTailoredBtn");
  const enableTailoredResumeEl = document.getElementById("enableTailoredResume");

  // Custom JD elements
  const customJdCard = document.getElementById("customJdCard");
  const customJdInput = document.getElementById("customJdInput");
  const clearCustomJdBtn = document.getElementById("clearCustomJdBtn");
  const toggleCustomJdBtn = document.getElementById("toggleCustomJdBtn");

  // Load any previously saved manual JD
  chrome.storage.local.get(["customJdText"], (res) => {
    if (res.customJdText && customJdInput) {
      customJdInput.value = res.customJdText;
      if (customJdCard && res.customJdText.trim()) {
        customJdCard.style.display = "flex";
      }
    }
  });

  if (customJdInput) {
    customJdInput.addEventListener("input", () => {
      chrome.storage.local.set({ customJdText: customJdInput.value });
    });
  }

  if (clearCustomJdBtn) {
    clearCustomJdBtn.addEventListener("click", () => {
      if (customJdInput) {
        customJdInput.value = "";
        chrome.storage.local.remove(["customJdText"]);
      }
    });
  }

  if (toggleCustomJdBtn) {
    toggleCustomJdBtn.addEventListener("click", () => {
      if (customJdCard) {
        const isHidden = customJdCard.style.display === "none";
        customJdCard.style.display = isHidden ? "flex" : "none";
        if (isHidden && customJdInput) customJdInput.focus();
      }
    });
  }

  let currentProfile = {};

  // Tab switching
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const targetTab = document.getElementById(btn.getAttribute("data-tab"));
      if (targetTab) targetTab.classList.add("active");
    });
  });

  // Reliable messaging to active tab with auto-injection on un-refreshed tabs
  async function sendMessageToActiveTab(msg, callback) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      return callback({ success: false, error: "No active tab found" });
    }

    chrome.tabs.sendMessage(tab.id, msg, (response) => {
      if (chrome.runtime.lastError) {
        // Tab was opened before extension was reloaded; inject content script dynamically across all frames
        chrome.scripting.executeScript(
          { target: { tabId: tab.id, allFrames: true }, files: ["content.js"] },
          () => {
            if (chrome.runtime.lastError) {
              return callback({ success: false, error: "Please refresh this webpage (F5) once so the extension can connect!" });
            }
            setTimeout(() => {
              chrome.tabs.sendMessage(tab.id, msg, (retryResp) => {
                if (chrome.runtime.lastError) {
                  return callback({ success: false, error: "Please refresh this webpage (F5) once so the extension can connect!" });
                }
                callback(retryResp);
              });
            }, 100);
          }
        );
      } else {
        callback(response);
      }
    });
  }

  // Query Active Tab for Live Job Description
  function refreshActiveTabJD() {
    sendMessageToActiveTab({ action: "GET_ACTIVE_JD" }, (res) => {
      if (!res || !res.title) {
        if (detectedJobTitleEl) detectedJobTitleEl.textContent = "General Application";
        if (detectedCompanyEl) detectedCompanyEl.textContent = "Ready to tailor on any career page";
        if (customJdCard) customJdCard.style.display = "flex";
        return;
      }
      if (detectedJobTitleEl && res.title) {
        detectedJobTitleEl.textContent = res.title;
      }
      if (detectedCompanyEl) {
        if (!res.hasJd) {
          detectedCompanyEl.textContent = (res.company && res.company !== "Employer")
            ? `${res.company} (No JD on page - Paste JD below or use default)`
            : "Form Page (No JD on page - Paste JD below or use default)";
          // Automatically display the custom JD card when no JD is detected on active tab!
          if (customJdCard) customJdCard.style.display = "flex";
        } else {
          detectedCompanyEl.textContent = res.company || "Target Job Description";
          // If active page already has a genuine JD, hide manual card unless user typed something in it
          if (customJdCard && !customJdInput?.value.trim()) {
            customJdCard.style.display = "none";
          }
        }
      }
    });
  }

  // Load Profile from chrome.storage or fallback to bundled profile_data.json / example
  async function loadProfile() {
    return new Promise((resolve) => {
      chrome.storage.local.get(["jobAgentProfile"], async (result) => {
        let profile = result.jobAgentProfile;
        if (!profile || Object.keys(profile).length === 0) {
          try {
            let resp = await fetch(chrome.runtime.getURL("profile_data.json")).catch(() => null);
            if (!resp || !resp.ok) {
              resp = await fetch(chrome.runtime.getURL("profile_data.example.json")).catch(() => null);
            }
            if (resp && resp.ok) {
              profile = await resp.json();
              chrome.storage.local.set({ jobAgentProfile: profile });
            } else {
              profile = {};
            }
          } catch (e) {
            console.warn("Could not load profile defaults", e);
            profile = {};
          }
        }
        currentProfile = profile || {};
        populateUI(currentProfile);
        resolve(currentProfile);
      });
    });
  }

  function populateUI(p) {
    if (!p) return;
    // Personal
    document.getElementById("firstName").value = p.first_name || "";
    document.getElementById("lastName").value = p.last_name || "";
    document.getElementById("fullName").value = p.name || "";
    document.getElementById("email").value = p.email || "";
    document.getElementById("phone").value = p.phone || "";
    document.getElementById("location").value = p.location || p.city || "";
    document.getElementById("country").value = p.country || "India";
    document.getElementById("linkedin").value = p.linkedin || "";
    document.getElementById("github").value = p.github || "";
    document.getElementById("portfolio").value = p.portfolio || "";

    // Resume & ATS Experience
    document.getElementById("currentCompany").value = p.current_company || "";
    document.getElementById("currentTitle").value = p.current_title || "";
    document.getElementById("expStart").value = p.experience_start || "";
    document.getElementById("expEnd").value = p.experience_end || "";
    document.getElementById("degree").value = p.degree || "";
    document.getElementById("major").value = p.major || "";
    document.getElementById("school").value = p.school || "";
    document.getElementById("gradYear").value = p.grad_year || "";
    document.getElementById("resumeRawText").value = p.resume_raw_text || p.experience || "";

    if (enableTailoredResumeEl) {
      enableTailoredResumeEl.checked = p.enable_tailored_resume !== false;
    }

    // Resume File Card
    if (p.resume_filename) {
      resumeFileNameEl.textContent = p.resume_filename;
      const sizeKb = p.resume_base64 ? Math.round(p.resume_base64.length * 0.75 / 1024) : 0;
      resumeFileMetaEl.textContent = `✅ Ready for 1-Click Auto Upload (${sizeKb > 0 ? sizeKb + " KB" : "Synced"})`;
      resumeFileMetaEl.style.color = "#34d399";
    } else {
      resumeFileNameEl.textContent = "No Resume File Loaded";
      resumeFileMetaEl.textContent = "Attach a PDF or click 'Reload Defaults'";
      resumeFileMetaEl.style.color = "#94a3b8";
    }

    // Preferences
    document.getElementById("yearsExp").value = p.years_exp || "";
    document.getElementById("expectedSalary").value = p.expected_salary || "";
    document.getElementById("noticePeriod").value = p.notice_period || "";
    document.getElementById("workAuth").value = p.work_auth || "Yes";
    document.getElementById("sponsorship").value = p.sponsorship || "No";
    document.getElementById("eeoGender").value = p.eeo_gender || "Prefer not to disclose";
    document.getElementById("eeoDisability").value = p.eeo_disability || "No, I do not have a disability";

    // AI
    document.getElementById("geminiApiKey").value = p.gemini_api_key || "";
    document.getElementById("geminiModel").value = p.gemini_model || "gemini-1.5-flash";
    document.getElementById("enableAiAnswers").checked = p.enable_ai_answers !== false;
    document.getElementById("showFloatingPill").checked = p.show_floating_pill !== false;

    const expText = p.experience || (Array.isArray(p.skills) ? "Skills: " + p.skills.join(", ") : "");
    document.getElementById("experienceContext").value = expText;

    if (p.gemini_api_key && p.gemini_api_key.trim().length > 5) {
      aiBadge.textContent = "⚡ Gemini Active";
      aiBadge.style.color = "#34d399";
    } else {
      aiBadge.textContent = "⚠️ No API Key";
      aiBadge.style.color = "#f59e0b";
    }
  }

  function collectUI() {
    return {
      ...currentProfile,
      first_name: document.getElementById("firstName").value.trim(),
      last_name: document.getElementById("lastName").value.trim(),
      name: document.getElementById("fullName").value.trim(),
      email: document.getElementById("email").value.trim(),
      phone: document.getElementById("phone").value.trim(),
      location: document.getElementById("location").value.trim(),
      city: document.getElementById("location").value.split(",")[0].trim(),
      country: document.getElementById("country").value.trim(),
      linkedin: document.getElementById("linkedin").value.trim(),
      github: document.getElementById("github").value.trim(),
      portfolio: document.getElementById("portfolio").value.trim(),

      // Resume & Work History
      current_company: document.getElementById("currentCompany").value.trim(),
      current_title: document.getElementById("currentTitle").value.trim(),
      experience_start: document.getElementById("expStart").value.trim(),
      experience_end: document.getElementById("expEnd").value.trim(),
      degree: document.getElementById("degree").value.trim(),
      major: document.getElementById("major").value.trim(),
      school: document.getElementById("school").value.trim(),
      grad_year: document.getElementById("gradYear").value.trim(),
      resume_raw_text: document.getElementById("resumeRawText").value.trim(),
      enable_tailored_resume: enableTailoredResumeEl ? enableTailoredResumeEl.checked : true,

      // File attributes preserved
      resume_filename: currentProfile.resume_filename || "Resume.pdf",
      resume_mime: currentProfile.resume_mime || "application/pdf",
      resume_base64: currentProfile.resume_base64 || "",

      // Preferences
      years_exp: document.getElementById("yearsExp").value.trim(),
      expected_salary: document.getElementById("expectedSalary").value.trim(),
      notice_period: document.getElementById("noticePeriod").value.trim(),
      work_auth: document.getElementById("workAuth").value,
      sponsorship: document.getElementById("sponsorship").value,
      eeo_gender: document.getElementById("eeoGender").value,
      eeo_disability: document.getElementById("eeoDisability").value,

      // AI Settings
      gemini_api_key: document.getElementById("geminiApiKey").value.trim(),
      gemini_model: document.getElementById("geminiModel").value,
      enable_ai_answers: document.getElementById("enableAiAnswers").checked,
      show_floating_pill: document.getElementById("showFloatingPill").checked,
      experience: document.getElementById("experienceContext").value.trim()
    };
  }

  // Handle Resume File Upload directly from popup
  if (resumeFileInput) {
    resumeFileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (event) => {
        const dataUrl = event.target.result;
        const b64 = dataUrl.split(",")[1];

        currentProfile.resume_filename = file.name;
        currentProfile.resume_mime = file.type || "application/pdf";
        currentProfile.resume_base64 = b64;

        chrome.storage.local.set({ jobAgentProfile: currentProfile }, () => {
          populateUI(currentProfile);
          feedbackEl.textContent = `📄 Loaded "${file.name}" for auto-upload!`;
          feedbackEl.style.color = "#34d399";
        });
      };
      reader.readAsDataURL(file);
    });
  }

  // Download Resume File
  if (downloadResumeBtn) {
    downloadResumeBtn.addEventListener("click", () => {
      if (!currentProfile.resume_base64) {
        alert("No resume file data available. Please click 'Reload Defaults' or upload a file first.");
        return;
      }
      const byteCharacters = atob(currentProfile.resume_base64);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: currentProfile.resume_mime || "application/pdf" });
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = currentProfile.resume_filename || "Resume.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // Copy Plain Text Resume
  if (copyResumeTextBtn) {
    copyResumeTextBtn.addEventListener("click", () => {
      const text = document.getElementById("resumeRawText").value;
      if (!text) {
        alert("No resume text available.");
        return;
      }
      navigator.clipboard.writeText(text).then(() => {
        const origText = copyResumeTextBtn.textContent;
        copyResumeTextBtn.textContent = "✅ Copied!";
        setTimeout(() => { copyResumeTextBtn.textContent = origText; }, 2000);
      });
    });
  }

  // Preview Tailored PDF for Active Page JD
  if (previewTailoredBtn) {
    previewTailoredBtn.addEventListener("click", async () => {
      previewTailoredBtn.textContent = "⏳ Generating...";
      currentProfile = collectUI();
      const manualJd = customJdInput ? customJdInput.value.trim() : "";

      sendMessageToActiveTab(
        { action: "GENERATE_TAILORED_PREVIEW", profile: currentProfile, manualJd: manualJd },
        (res) => {
          previewTailoredBtn.textContent = "👁️ Preview Tailored PDF";
          if (!res || !res.success || !res.dataUrl) {
            alert(res?.error || "Please refresh this webpage (F5) once so the extension can read the job description!");
            return;
          }

          // Save to chrome storage and open the built-in preview viewer
          chrome.storage.local.set(
            {
              previewPdfData: res.dataUrl,
              previewPdfTitle: res.jobTitle || "Job Title",
              previewPdfCompany: res.company || "Company",
              previewPdfFilename: res.filename || "Tailored_Resume.pdf",
              previewPdfIsDefault: Boolean(res.isDefault)
            },
            () => {
              chrome.tabs.create({ url: chrome.runtime.getURL("preview.html") });
            }
          );
        }
      );
    });
  }

  // Save Button
  saveBtn.addEventListener("click", () => {
    currentProfile = collectUI();
    chrome.storage.local.set({ jobAgentProfile: currentProfile }, () => {
      feedbackEl.textContent = "✅ Profile & Resume saved!";
      feedbackEl.style.color = "#34d399";
      populateUI(currentProfile);
      setTimeout(() => {
        feedbackEl.textContent = "Ready to autofill on active tab";
        feedbackEl.style.color = "#94a3b8";
      }, 3000);
    });
  });

  // Reload Defaults Button
  resetBtn.addEventListener("click", async () => {
    try {
      let resp = await fetch(chrome.runtime.getURL("profile_data.json")).catch(() => null);
      if (!resp || !resp.ok) {
        resp = await fetch(chrome.runtime.getURL("profile_data.example.json")).catch(() => null);
      }
      if (resp && resp.ok) {
        const profile = await resp.json();
        currentProfile = profile;
        chrome.storage.local.set({ jobAgentProfile: currentProfile }, () => {
          populateUI(currentProfile);
          feedbackEl.textContent = "🔄 Profile & Resume reloaded from Job Agent!";
          feedbackEl.style.color = "#818cf8";
          setTimeout(() => {
            feedbackEl.textContent = "Ready to autofill on active tab";
            feedbackEl.style.color = "#94a3b8";
          }, 3000);
        });
      }
    } catch (e) {
      alert("Error reloading defaults: " + e.message);
    }
  });

  // Autofill Button
  autofillBtn.addEventListener("click", async () => {
    feedbackEl.textContent = "🎯 Preparing autofill...";
    feedbackEl.style.color = "#818cf8";

    currentProfile = collectUI();
    chrome.storage.local.set({ jobAgentProfile: currentProfile });
    const manualJd = customJdInput ? customJdInput.value.trim() : "";

    sendMessageToActiveTab(
      { action: "AUTOFILL_FORM", profile: currentProfile, manualJd: manualJd },
      (response) => {
        if (!response || !response.success) {
          feedbackEl.textContent = response?.error || "Please refresh this webpage (F5) once and retry!";
          feedbackEl.style.color = "#f59e0b";
          return;
        }

        let tailMsg = "";
        if (response.isDefault || response.tailoredFor === "Default Profile") {
          tailMsg = " (🎯 Default Profile Resume)";
        } else if (response.tailoredFor && response.tailoredFor !== "Employer") {
          tailMsg = ` (🎯 Tailored for ${response.tailoredFor})`;
        }
        feedbackEl.textContent = `🎉 Filled ${response.count} fields${tailMsg}!`;
        feedbackEl.style.color = "#34d399";
      }
    );
  });

  // Initialize
  await loadProfile();
  refreshActiveTabJD();
});
