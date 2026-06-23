import { atEdge, nextIndex, shouldSuppressKeys } from "./nav-core";

const track = document.querySelector<HTMLElement>("#deck-track")!;
const sections = Array.from(document.querySelectorAll<HTMLElement>(".deck-section"));
const indicator = document.querySelector<HTMLElement>("#deck-progress")!;
const count = sections.length;
let current = 0;
let animating = false;

// modalOpen is read from a data attribute the demo viewer toggles.
const isModalOpen = () => document.body.dataset.modalOpen === "1";

function go(dir: 1 | -1) {
  const target = nextIndex(current, dir, count);
  if (target === current) return;
  current = target;
  animating = true;
  track.style.transform = `translateY(-${current * 100}vh)`;
  indicator.textContent = `${current + 1} / ${count}`;
  // re-enable input after the CSS transition (matches .deck-track transition: 600ms)
  window.setTimeout(() => { animating = false; }, 650);
}

// Keyboard: explicit flip keys always flip (when not suppressed).
window.addEventListener("keydown", (e) => {
  if (shouldSuppressKeys(document.activeElement, isModalOpen())) return;
  if (e.key === "ArrowDown" || e.key === "PageDown" || e.key === " ") { e.preventDefault(); go(1); }
  else if (e.key === "ArrowUp" || e.key === "PageUp") { e.preventDefault(); go(-1); }
  else if (e.key === "Home") { e.preventDefault(); while (current > 0) go(-1); }
  else if (e.key === "End") { e.preventDefault(); while (current < count - 1) go(1); }
});

// Wheel: scroll within section; flip only when at boundary and pushing past it.
let wheelLock = 0;
window.addEventListener("wheel", (e) => {
  if (isModalOpen() || animating) return;
  const sec = sections[current];
  const dir: 1 | -1 = e.deltaY > 0 ? 1 : -1;
  if (atEdge(sec.scrollTop, sec.scrollHeight, sec.clientHeight, dir)) {
    const now = e.timeStamp;
    if (now - wheelLock < 700) return;     // throttle: one flip per gesture
    wheelLock = now;
    e.preventDefault();
    go(dir);
  }
  // else: let the section scroll natively (do not preventDefault)
}, { passive: false });

// Touch: flip on swipe when at boundary.
let touchStartY = 0;
window.addEventListener("touchstart", (e) => { touchStartY = e.touches[0].clientY; }, { passive: true });
window.addEventListener("touchend", (e) => {
  if (isModalOpen() || animating) return;
  const dy = touchStartY - e.changedTouches[0].clientY;
  if (Math.abs(dy) < 40) return;
  const dir: 1 | -1 = dy > 0 ? 1 : -1;
  const sec = sections[current];
  if (atEdge(sec.scrollTop, sec.scrollHeight, sec.clientHeight, dir)) go(dir);
});

indicator.textContent = `1 / ${count}`;
