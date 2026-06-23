// Pure navigation helpers — no DOM, unit-testable.
const TOL = 2; // px tolerance for "at edge"

export function atEdge(scrollTop: number, scrollHeight: number, clientHeight: number, dir: 1 | -1): boolean {
  if (dir === 1) return scrollTop + clientHeight >= scrollHeight - TOL;
  return scrollTop <= TOL;
}

export function nextIndex(current: number, dir: 1 | -1, count: number): number {
  return Math.max(0, Math.min(count - 1, current + dir));
}

export function shouldSuppressKeys(active: { tagName: string } | null, modalOpen: boolean): boolean {
  if (modalOpen) return true;
  if (!active) return false;
  return active.tagName === "INPUT" || active.tagName === "TEXTAREA";
}
