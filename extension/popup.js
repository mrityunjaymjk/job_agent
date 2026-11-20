document.addEventListener("DOMContentLoaded", async () => {
  // Elements
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  const autofillBtn = document.getElementById("autofillCurrentTabBtn");
  const saveBtn = document.getElementById("saveProfileBtn");
  const resetBtn = document.getElementById("resetDefaultsBtn");
  const feedbackEl = document.getElementById("pageFeedback");
  const aiBadge = document.getElementById("aiStatusBadge");

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

  // Load Profile from chrome.storage or fallback to bundled profile_data.json
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
        populateUI(profile);
        resolve(profile);
      });
    });
  }

  function populateUI(p) {
    if (!p) return;
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

    document.getElementById("yearsExp").value = p.years_exp || "";
    document.getElementById("expectedSalary").value = p.expected_salary || "";
    document.getElementById("noticePeriod").value = p.notice_period || "";
    document.getElementById("workAuth").value = p.work_auth || "Yes";
    document.getElementById("sponsorship").value = p.sponsorship || "No";
    document.getElementById("eeoGender").value = p.eeo_gender || "Prefer not to disclose";
    document.getElementById("eeoDisability").value = p.eeo_disability || "No, I do not have a disability";

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
      years_exp: document.getElementById("yearsExp").value.trim(),
      expected_salary: document.getElementById("expectedSalary").value.trim(),
      notice_period: document.getElementById("noticePeriod").value.trim(),
      work_auth: document.getElementById("workAuth").value,
      sponsorship: document.getElementById("sponsorship").value,
      eeo_gender: document.getElementById("eeoGender").value,
      eeo_disability: document.getElementById("eeoDisability").value,
      gemini_api_key: document.getElementById("geminiApiKey").value.trim(),
      gemini_model: document.getElementById("geminiModel").value,
      enable_ai_answers: document.getElementById("enableAiAnswers").checked,
      show_floating_pill: document.getElementById("showFloatingPill").checked,
      experience: document.getElementById("experienceContext").value.trim()
    };
  }

  // Save Button
  saveBtn.addEventListener("click", () => {
    const profile = collectUI();
    chrome.storage.local.set({ jobAgentProfile: profile }, () => {
      feedbackEl.textContent = "✅ Profile saved successfully!";
      feedbackEl.style.color = "#34d399";
      populateUI(profile);
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
        chrome.storage.local.set({ jobAgentProfile: profile }, () => {
          populateUI(profile);
          feedbackEl.textContent = "🔄 Defaults reloaded from Job Agent!";
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
    feedbackEl.textContent = "🔍 Scanning and autofilling active page...";
    feedbackEl.style.color = "#818cf8";

    const profile = collectUI();
    // Save latest in case user edited fields
    chrome.storage.local.set({ jobAgentProfile: profile });

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        feedbackEl.textContent = "❌ No active tab found.";
        feedbackEl.style.color = "#ef4444";
        return;
      }

      chrome.tabs.sendMessage(
        tab.id,
        { action: "AUTOFILL_FORM", profile: profile },
        (response) => {
          if (chrome.runtime.lastError) {
            feedbackEl.textContent = "⚠️ Please open a job application or refresh page!";
            feedbackEl.style.color = "#f59e0b";
            return;
          }
          if (response && response.success) {
            feedbackEl.textContent = `🎉 Success! Autofilled ${response.count} fields!`;
            feedbackEl.style.color = "#34d399";
          } else {
            feedbackEl.textContent = response?.message || "No matching application fields found.";
            feedbackEl.style.color = "#94a3b8";
          }
        }
      );
    } catch (err) {
      feedbackEl.textContent = "Error: " + err.message;
      feedbackEl.style.color = "#ef4444";
    }
  });

  // Initialize
  await loadProfile();
});
