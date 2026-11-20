document.addEventListener("DOMContentLoaded", () => {
  const viewerFrame = document.getElementById("viewerFrame");
  const docTitle = document.getElementById("docTitle");
  const docMeta = document.getElementById("docMeta");
  const downloadPdfBtn = document.getElementById("downloadPdfBtn");

  chrome.storage.local.get(["previewPdfData", "previewPdfTitle", "previewPdfCompany", "previewPdfFilename", "previewPdfIsDefault"], (res) => {
    if (!res.previewPdfData) {
      docTitle.textContent = "No Preview Data Found";
      docMeta.textContent = "Please generate a preview from the Job Agent extension popup on a job posting.";
      return;
    }

    const title = res.previewPdfTitle || "Software Engineer";
    const company = res.previewPdfCompany || "Company";
    const filename = res.previewPdfFilename || "Resume.pdf";
    const isDefault = Boolean(res.previewPdfIsDefault);

    if (isDefault) {
      docTitle.textContent = `📄 Standard ATS Resume (Default Profile)`;
      docMeta.textContent = `File: ${filename} | Primary profile skills, authentic summary & credentials`;
      document.title = `Standard ATS Resume - ${title}`;
    } else {
      docTitle.textContent = `🎯 Tailored for: ${title} at ${company}`;
      docMeta.textContent = `File: ${filename} | Targeted headline, skills & ATS summary compiled on the fly`;
      document.title = `Tailored Resume - ${company}`;
    }

    viewerFrame.src = res.previewPdfData;

    downloadPdfBtn.addEventListener("click", () => {
      const a = document.createElement("a");
      a.href = res.previewPdfData;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  });
});
