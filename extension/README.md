# ⚡ Job Agent AI - Chrome Extension Form Filler

> **1-Click AI Job Application Form Filler** powered by Google Gemini and your active Job Agent candidate profile.

Works seamlessly on **Greenhouse, Lever, Workday, LinkedIn, Indeed, SmartRecruiters, Ashby, Jobvite**, and company career pages.

---

## 🌟 Why Use the Chrome Extension?

- **Zero Bot Detection / No Cloudflare Blocks**: Runs inside your authentic, everyday Google Chrome browser with your real browser fingerprint and IP.
- **No Sign-In / 2FA Headaches**: You are already logged into LinkedIn, Indeed, and Workday on your browser.
- **1-Click Form Filling**: Automatically matches and fills personal details, contact info, experience, portfolio links, and diversity questions.
- **AI-Powered Open-Ended Answers**: Uses Gemini AI to craft authentic, tailored 2-3 sentence answers to questions like *"Why do you want to work here?"*, *"Describe your experience with Spring Boot"*, and cover letters.
- **Controlled Input Compatibility**: Dispatches native DOM events with prototype setters to ensure React, Angular, and Vue inputs accept values without resetting.

---

## 🚀 How to Install in Google Chrome (Takes 30 Seconds)

1. Open **Google Chrome** and enter:
   ```text
   chrome://extensions
   ```
2. In the top-right corner, turn **Developer mode** toggle to **ON**.
3. In the top-left corner, click the **Load unpacked** button.
4. Select this directory:
   ```text
   D:\DEAR MJ\job_agent\extension
   ```
5. Click the puzzle icon 🧩 in Chrome's top toolbar and **Pin** **Job Agent AI**.

---

## 🎯 How to Use

1. Navigate to any job application page (e.g. on LinkedIn Easy Apply, Greenhouse, Lever, or Workday).
2. Look for the floating **⚡ Autofill with AI** pill in the bottom-right corner, or click the **Job Agent AI** icon in your toolbar and press **"Autofill Application Now"**.
3. Watch the form fields fill in real-time with a subtle green highlight!
4. Review the inputs and click **Submit**.

---

## 🔄 Syncing with your Job Agent Database

Whenever you update your resume or settings in the Streamlit app:
- Open the Streamlit app `Settings` tab and click **"🔄 Sync Database to Extension"**.
- Or run the sync script from terminal:
  ```bash
  python extension/sync_profile.py
  ```
- In the Chrome extension popup, click **"🔄 Reload Defaults"**.
