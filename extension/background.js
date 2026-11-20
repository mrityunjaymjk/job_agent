/**
 * Job Agent AI - Background Service Worker
 * Handles cross-origin Gemini API requests with zero CORS/CSP restrictions.
 */

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "CALL_GEMINI") {
    (async () => {
      const apiKey = request.apiKey?.trim();
      const model = request.model || "gemini-1.5-flash";
      const prompt = request.prompt;

      if (!apiKey) {
        sendResponse({ success: false, error: "No API key provided" });
        return;
      }

      const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8 second timeout

        const resp = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { maxOutputTokens: 600, temperature: 0.2 }
          }),
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!resp.ok) {
          const errText = await resp.text();
          sendResponse({ success: false, error: `Gemini API returned ${resp.status}: ${errText}` });
          return;
        }

        const data = await resp.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || "";
        sendResponse({ success: true, text });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true; // Keep channel open for async response
  }
});
