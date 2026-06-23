import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import models from "../../data/models.json";
import { buildShape } from "./shapes";

type Model = (typeof models)[number];
const byId = new Map<string, Model>(models.map((m) => [m.id, m]));

const modal = document.querySelector<HTMLElement>("#viewer-modal")!;
// Portal the modal to <body> so position:fixed resolves against the viewport,
// not the transformed #deck-track ancestor (which would shift it ~250vh off-screen).
document.body.appendChild(modal);
const canvasHost = document.querySelector<HTMLElement>("#viewer-canvas")!;
const captionEl = document.querySelector<HTMLElement>("#viewer-caption")!;
const metaEl = document.querySelector<HTMLElement>("#viewer-meta")!;

let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let frame = 0;

function teardown() {
  if (frame) cancelAnimationFrame(frame);
  controls?.dispose();
  renderer?.dispose();
  renderer = null;
  canvasHost.innerHTML = "";
}

function open(model: Model) {
  teardown(); // prevent renderer/rAF leak on re-open

  captionEl.textContent = model.caption;
  metaEl.innerHTML =
    `<span>${model.probe.n_faces} faces</span>` +
    `<span>${model.probe.n_solids} solid</span>` +
    `<span>ratio ${model.probe.bbox_ratio}</span>`;
  modal.hidden = false;
  document.body.dataset.modalOpen = "1";

  // Defer scene setup until after layout so clientWidth reflects the
  // real container width (it is 0 before first paint on first open).
  requestAnimationFrame(() => {
    if (modal.hidden) return; // closed before layout fired — don't build into a torn-down state
    const w = canvasHost.clientWidth || 480;
    const h = 360;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b1b2b);
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 5000);
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(w, h);
    canvasHost.appendChild(renderer.domElement);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
    const dir = new THREE.DirectionalLight(0xffffff, 1.0);
    dir.position.set(1, 1, 1);
    scene.add(dir);

    controls = new OrbitControls(camera, renderer.domElement);

    const obj = buildShape(model.shape);
    const box = new THREE.Box3().setFromObject(obj);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    obj.position.sub(center);
    const radius = Math.max(size.x, size.y, size.z) || 1;
    camera.position.set(radius * 1.6, radius * 1.2, radius * 1.8);
    controls.target.set(0, 0, 0);
    controls.update();
    scene.add(obj);

    const loop = () => {
      frame = requestAnimationFrame(loop);
      controls?.update();
      renderer?.render(scene, camera);
    };
    loop();
  });
}

function close() {
  modal.hidden = true;
  document.body.dataset.modalOpen = "0";
  teardown();
}

document.querySelectorAll<HTMLElement>(".model-card").forEach((card) => {
  card.addEventListener("click", () => {
    const m = byId.get(card.dataset.modelId ?? "");
    if (m) open(m);
  });
});
modal.querySelectorAll<HTMLElement>("[data-close]").forEach((el) =>
  el.addEventListener("click", close)
);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !modal.hidden) close(); });
