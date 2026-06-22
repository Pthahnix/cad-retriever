// Search is intentionally cosmetic: any query shows the same fixed results.
const tabs = document.querySelectorAll<HTMLButtonElement>(".tab");
const textInput = document.querySelector<HTMLInputElement>("#text-input")!;
const fileInput = document.querySelector<HTMLInputElement>("#file-input")!;
const searchBtn = document.querySelector<HTMLButtonElement>("#search-btn")!;
const status = document.querySelector<HTMLParagraphElement>("#status")!;
const grid = document.querySelector<HTMLElement>(".results-grid")!;
const examples = document.querySelectorAll<HTMLButtonElement>(".example");

let mode: "text" | "sketch" | "image" = "text";

function setMode(next: "text" | "sketch" | "image") {
  mode = next;
  tabs.forEach((t) => t.classList.toggle("active", t.dataset.mode === next));
  const fileMode = next !== "text";
  textInput.hidden = fileMode;
  fileInput.hidden = !fileMode;
}

function runSearch() {
  // ponytail: hardcoded retrieval — fake latency, then reveal the same grid
  status.hidden = false;
  grid.style.opacity = "0.3";
  setTimeout(() => {
    status.hidden = true;
    grid.style.opacity = "1";
  }, 450);
}

tabs.forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode as typeof mode)));
searchBtn.addEventListener("click", runSearch);
textInput.addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
fileInput.addEventListener("change", runSearch);
examples.forEach((b) =>
  b.addEventListener("click", () => { setMode("text"); textInput.value = b.dataset.q ?? ""; runSearch(); })
);
