import * as THREE from "three";

// Build an approximate THREE.Group from primitives for each demo shape.
// ponytail: stand-in geometry, not real CAD — swap for GLB loading when real models exist.
const MAT = new THREE.MeshStandardMaterial({ color: 0x7c9cb5, metalness: 0.2, roughness: 0.6 });

function disc(): THREE.Group {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(40, 40, 8, 48), MAT);
  g.add(body);
  // visual nod to the bolt holes: 6 thin cylinders around the rim
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const hole = new THREE.Mesh(new THREE.CylinderGeometry(4, 4, 9, 16),
      new THREE.MeshStandardMaterial({ color: 0x33485a }));
    hole.position.set(Math.cos(a) * 28, 0, Math.sin(a) * 28);
    g.add(hole);
  }
  return g;
}

function bracket(): THREE.Group {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(50, 8, 40), MAT);
  base.position.set(25, 4, 0);
  const wall = new THREE.Mesh(new THREE.BoxGeometry(8, 50, 40), MAT);
  wall.position.set(4, 25, 0);
  g.add(base, wall);
  return g;
}

function nut(): THREE.Group {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(15, 15, 10, 6), MAT);
  const bore = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, 11, 32),
    new THREE.MeshStandardMaterial({ color: 0x33485a }));
  g.add(body, bore);
  return g;
}

function shaft(): THREE.Group {
  const g = new THREE.Group();
  const lo = new THREE.Mesh(new THREE.CylinderGeometry(15, 15, 40, 32), MAT);
  lo.position.y = 20;
  const hi = new THREE.Mesh(new THREE.CylinderGeometry(9, 9, 30, 32), MAT);
  hi.position.y = 55;
  g.add(lo, hi);
  return g;
}

function plate(): THREE.Group {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(80, 6, 50), MAT);
  g.add(base);
  for (let i = -1; i <= 1; i++) {
    const rib = new THREE.Mesh(new THREE.BoxGeometry(4, 10, 40), MAT);
    rib.position.set(i * 20, 8, 0);
    g.add(rib);
  }
  return g;
}

const BUILDERS: Record<string, () => THREE.Group> = { disc, bracket, nut, shaft, plate };

export function buildShape(shape: string): THREE.Group {
  return (BUILDERS[shape] ?? disc)();
}
