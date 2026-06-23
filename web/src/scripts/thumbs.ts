import * as THREE from "three";
import { buildShape } from "./shapes";

// Render each demo shape to a PNG once on load, reusing the viewer's
// lighting/framing so thumbnails match the 3D popup. One shared offscreen
// renderer; context disposed when done.
// ponytail: client-side one-shot for 5 demo shapes. Real systems serve
// backend-generated thumbnail URLs — swap img.src for those then.
const SIZE = 96; // 2x of the 48px cell for retina

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setSize(SIZE, SIZE);

const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
const dir = new THREE.DirectionalLight(0xffffff, 1.0);
dir.position.set(1, 1, 1);
scene.add(dir);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);

const cache = new Map<string, string>();

function renderThumb(shape: string): string {
  const hit = cache.get(shape);
  if (hit) return hit;

  const obj = buildShape(shape);
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  obj.position.sub(center);
  const radius = Math.max(size.x, size.y, size.z) || 1;
  camera.position.set(radius * 1.6, radius * 1.2, radius * 1.8);
  camera.lookAt(0, 0, 0);

  scene.add(obj);
  renderer.render(scene, camera);
  const url = renderer.domElement.toDataURL("image/png");
  scene.remove(obj);

  cache.set(shape, url);
  return url;
}

document.querySelectorAll<HTMLImageElement>("img.thumb[data-shape]").forEach((img) => {
  img.src = renderThumb(img.dataset.shape!);
});

renderer.dispose();
