// Search is intentionally cosmetic: any query shows the same fixed results.
const textInput = document.querySelector<HTMLInputElement>("#text-input")!;
const searchBtn = document.querySelector<HTMLButtonElement>("#search-btn")!;
const status = document.querySelector<HTMLParagraphElement>("#status")!;
const results = document.querySelector<HTMLElement>(".results")!;

const modeTag = document.querySelector<HTMLElement>("#mode-tag")!;
const attach = document.querySelector<HTMLElement>("#attach")!;
const attachThumb = document.querySelector<HTMLImageElement>("#attach-thumb")!;
const attachLabel = document.querySelector<HTMLElement>("#attach-label")!;

function runSearch() {
  // ponytail: hardcoded retrieval — fake latency, then reveal the same results
  status.hidden = false;
  results.style.opacity = "0.3";
  setTimeout(() => {
    status.hidden = true;
    results.style.opacity = "1";
  }, 450);
}

function wireUpload(btnId: string, fileId: string, label: string, tag: string) {
  const file = document.querySelector<HTMLInputElement>(fileId)!;
  document.querySelector<HTMLButtonElement>(btnId)!.addEventListener("click", () => file.click());
  file.addEventListener("change", () => {
    const f = file.files?.[0];
    if (!f) return;
    attachThumb.src = URL.createObjectURL(f);
    attachLabel.textContent = `${label}：${f.name}`;
    modeTag.textContent = tag;
    attach.classList.add("show");
    runSearch();
  });
}
wireUpload("#sketch-btn", "#sketch-file", "草图", "Sketch");
wireUpload("#image-btn", "#image-file", "图片", "Image");

document.querySelector<HTMLButtonElement>("#attach-x")!.addEventListener("click", () => {
  attach.classList.remove("show");
  modeTag.textContent = "Text";
  document.querySelector<HTMLInputElement>("#sketch-file")!.value = "";
  document.querySelector<HTMLInputElement>("#image-file")!.value = "";
});

searchBtn.addEventListener("click", runSearch);
textInput.addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
