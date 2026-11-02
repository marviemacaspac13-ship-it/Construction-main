import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * PlanScene — a wireframe building built from lines and dots.
 *
 * Three layers, matching the three plan types ARCE reads:
 *   floor      white walls, rooms and furniture
 *   electrical teal conduit, lights, outlets and switches
 *   plumbing   blue supply pipes running through the doorways
 *
 * Behaviour
 *  - Intro: walls rise from the floor, then plumbing and electrical light up.
 *  - Light pulses travel along every pipe and conduit.
 *  - Drag to rotate (left/right) and tilt (up/down). It resumes turning on its own.
 *  - Layers fade in and out when toggled; `focus` dims the other layers.
 *  - prefers-reduced-motion: no intro, no auto-rotation, no pulses.
 */

export type LayerKey = "floor" | "electrical" | "plumbing";
export type LayerState = Record<LayerKey, boolean>;

type Props = {
  layers: LayerState;
  focus: LayerKey | null;
};

type P3 = [number, number, number];

// ─── Palette ──────────────────────────────────────────────────────────────────
const COLOR_FLOOR = 0xdfe8f5;
const COLOR_PLUMBING = 0x2f7bff;
const COLOR_ELECTRICAL = 0x2fe3c0;

// ─── Plan data (units are metres; x runs east, z runs south) ──────────────────
const WALL_H = 3;
const PLAN_CX = 12;
const PLAN_CZ = 8;

// Wall segments as [x1, z1, x2, z2]. Gaps are doorways and openings.
const WALLS: [number, number, number, number][] = [
  // outer shell
  [0, 0, 24, 0],
  [24, 0, 24, 10],
  [24, 10, 15, 10],
  [18, 10, 18, 16],
  [18, 16, 12, 16],
  [10, 16, 0, 16],
  [0, 16, 0, 0],
  // interior
  [9, 0, 9, 6],
  [9, 8.5, 9, 16],
  [16, 0, 16, 4],
  [16, 9, 16, 10],
  [0, 7, 3, 7],
  [8, 7, 9, 7],
  [9, 10, 12, 10],
];

// Furniture boxes as [centreX, centreZ, width, depth, height].
const FURNITURE: [number, number, number, number, number][] = [
  [4, 3, 3, 4, 0.7], // bed
  [4.5, 12.2, 4, 1.4, 0.8], // sofa
  [6.8, 9, 2, 1.4, 0.9], // table
  [14, 15.3, 6, 1.2, 0.9], // kitchen counter
  [12.5, 1.6, 3, 1.2, 0.8], // desk
  [21.8, 1.8, 3.4, 1.4, 0.6], // tub
  [22.7, 8.2, 1, 1, 0.7], // toilet
];

// Plumbing runs: the trunk passes through the doorways at z=6.5 and x=12.5.
const PIPES_PLUMBING: P3[][] = [
  [[-1.8, 0.4, 11], [7, 0.4, 11], [7, 0.4, 6.5], [12.5, 0.4, 6.5], [12.5, 0.4, 13.5], [16.4, 0.4, 13.5], [16.4, 1.7, 13.5]],
  [[12.5, 0.4, 6.5], [12.5, 0.4, 5], [21.5, 0.4, 5], [21.5, 1.6, 5]],
  [[7, 0.4, 11], [7, 0.4, 14.5], [2.5, 0.4, 14.5], [2.5, 1.6, 14.5]],
];
const PLUMBING_FIXTURES: P3[] = [[16.4, 1.7, 13.5], [21.5, 1.6, 5], [2.5, 1.6, 14.5]];

// Electrical runs at ceiling height, plus switch drops.
const CEIL = 2.6;
const PIPES_ELECTRICAL: P3[][] = [
  [[-1.8, CEIL, 8], [22, CEIL, 8]], // spine
  [[4, CEIL, 8], [4, CEIL, 12.5]],
  [[4, CEIL, 8], [4, CEIL, 3]],
  [[12.5, CEIL, 8], [12.5, CEIL, 5], [11, CEIL, 5], [11, CEIL, 2.5]],
  [[19, CEIL, 8], [19, CEIL, 2.5]],
  [[14, CEIL, 8], [14, CEIL, 13]],
  [[8.7, CEIL, 8], [8.7, 1.2, 8]], // switch drops
  [[15.3, CEIL, 8], [15.3, 1.2, 8]],
  [[20.5, CEIL, 8], [20.5, 1.2, 8]],
];
const ELECTRICAL_LIGHTS: P3[] = [[4, CEIL, 12.5], [4, CEIL, 3], [11, CEIL, 2.5], [19, CEIL, 2.5], [14, CEIL, 13], [22, CEIL, 8]];
const ELECTRICAL_SWITCHES: P3[] = [[8.7, 1.2, 8], [15.3, 1.2, 8], [20.5, 1.2, 8]];
const ELECTRICAL_OUTLETS: P3[] = [
  [0.2, 0.45, 3], [0.2, 0.45, 12], [23.8, 0.45, 3], [23.8, 0.45, 7],
  [9.2, 0.45, 13], [17.8, 0.45, 13], [11, 0.45, 0.2], [8.8, 0.45, 4],
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const smooth = (v: number) => {
  const t = clamp01(v);
  return t * t * (3 - 2 * t);
};
const easeOutCubic = (v: number) => 1 - Math.pow(1 - clamp01(v), 3);

/** A polyline with rounded corners, as a curve a tube can follow. */
export function roundedPath(pts: P3[], radius: number): THREE.CurvePath<THREE.Vector3> {
  const v = pts.map((p) => new THREE.Vector3(p[0], p[1], p[2]));
  const path = new THREE.CurvePath<THREE.Vector3>();
  let cur = v[0].clone();
  for (let i = 1; i < v.length - 1; i++) {
    const b = v[i];
    const d1 = new THREE.Vector3().subVectors(v[i - 1], b);
    const d2 = new THREE.Vector3().subVectors(v[i + 1], b);
    const l1 = d1.length();
    const l2 = d2.length();
    d1.normalize();
    d2.normalize();
    if (Math.abs(d1.dot(d2)) > 0.999) continue; // straight through
    const rr = Math.min(radius, l1 / 2, l2 / 2);
    const p1 = b.clone().addScaledVector(d1, rr);
    const p2 = b.clone().addScaledVector(d2, rr);
    path.add(new THREE.LineCurve3(cur.clone(), p1));
    path.add(new THREE.QuadraticBezierCurve3(p1, b.clone(), p2));
    cur = p2;
  }
  path.add(new THREE.LineCurve3(cur.clone(), v[v.length - 1].clone()));
  return path;
}

function makeDotTexture(ring: boolean): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 64;
  c.height = 64;
  const g = c.getContext("2d")!;
  if (ring) {
    g.strokeStyle = "rgba(255,255,255,1)";
    g.lineWidth = 5;
    g.beginPath();
    g.arc(32, 32, 20, 0, Math.PI * 2);
    g.stroke();
    const grad = g.createRadialGradient(32, 32, 0, 32, 32, 9);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 64, 64);
  } else {
    const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.45, "rgba(255,255,255,0.7)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 64, 64);
  }
  return new THREE.CanvasTexture(c);
}

// ─── Shaders ──────────────────────────────────────────────────────────────────
const PIPE_VERT = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vN;
  varying vec3 vV;
  void main() {
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal);
    vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

const PIPE_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uOpacity;
  uniform float uPhase;
  uniform float uDensity;
  uniform float uFlow;
  varying vec2 vUv;
  varying vec3 vN;
  varying vec3 vV;
  void main() {
    float facing = abs(dot(normalize(vN), normalize(vV)));
    float core = pow(facing, 1.6);
    float t = fract(vUv.x * uDensity - uTime * uFlow + uPhase);
    float pulse = pow(1.0 - t, 7.0);
    vec3 col = uColor * (0.30 + 0.55 * core) + uColor * pulse * 1.5 + vec3(pulse * pulse * 0.3);
    float a = (0.55 + 0.40 * core) * uOpacity;
    gl_FragColor = vec4(col, a);
  }
`;

const GROUND_VERT = /* glsl */ `
  attribute float aBright;
  uniform float uTime;
  uniform float uScale;
  uniform float uSize;
  uniform float uOpacity;
  varying float vB;
  void main() {
    vec3 p = position;
    float d = length(p.xz);
    float wave = sin(d * 0.8 - uTime * 1.1);
    p.y += wave * 0.10 * exp(-d * 0.05);
    vB = aBright * (0.75 + 0.25 * wave) * uOpacity;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = uSize * uScale / -mv.z;
  }
`;

const GROUND_FRAG = /* glsl */ `
  uniform vec3 uColor;
  varying float vB;
  void main() {
    float r = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.0, r);
    gl_FragColor = vec4(uColor, a * vB);
  }
`;

// ─── Component ────────────────────────────────────────────────────────────────
export function PlanScene({ layers, focus }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  // The animation loop reads these every frame, so toggles never rebuild the scene.
  const layersRef = useRef(layers);
  const focusRef = useRef(focus);
  layersRef.current = layers;
  focusRef.current = focus;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      return; // no WebGL: the page still works, the panel just stays black
    }
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(pixelRatio);
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);
    renderer.domElement.style.display = "block";

    const scene = new THREE.Scene();
    const FOV = 34;
    const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 400);

    const spin = new THREE.Group();
    scene.add(spin);
    const plan = new THREE.Group();
    plan.position.set(-PLAN_CX, -WALL_H * 0.42, -PLAN_CZ);
    spin.add(plan);

    const disposables: { dispose: () => void }[] = [];
    const track = <T extends { dispose: () => void }>(o: T): T => {
      disposables.push(o);
      return o;
    };

    const dotTex = track(makeDotTexture(false));
    const ringTex = track(makeDotTexture(true));

    // ── Floor layer: walls, glass, furniture, corner dots ───────────────────
    const shell = new THREE.Group(); // scaled in Y for the intro
    plan.add(shell);

    const wallPos: number[] = [];
    const glassPos: number[] = [];
    const cornerKeys = new Set<string>();
    const cornerPts: number[] = [];
    const addCorner = (x: number, y: number, z: number) => {
      const k = `${x},${y},${z}`;
      if (cornerKeys.has(k)) return;
      cornerKeys.add(k);
      cornerPts.push(x, y, z);
    };
    for (const [x1, z1, x2, z2] of WALLS) {
      wallPos.push(x1, 0, z1, x2, 0, z2); // base
      wallPos.push(x1, WALL_H, z1, x2, WALL_H, z2); // top
      wallPos.push(x1, 0, z1, x1, WALL_H, z1); // posts
      wallPos.push(x2, 0, z2, x2, WALL_H, z2);
      glassPos.push(
        x1, 0, z1, x2, 0, z2, x2, WALL_H, z2,
        x1, 0, z1, x2, WALL_H, z2, x1, WALL_H, z1
      );
      addCorner(x1, 0, z1); addCorner(x2, 0, z2);
      addCorner(x1, WALL_H, z1); addCorner(x2, WALL_H, z2);
    }

    const wallGeo = track(new THREE.BufferGeometry());
    wallGeo.setAttribute("position", new THREE.Float32BufferAttribute(wallPos, 3));
    const wallMat = track(new THREE.LineBasicMaterial({ color: COLOR_FLOOR, transparent: true, opacity: 0.85 }));
    shell.add(new THREE.LineSegments(wallGeo, wallMat));

    const glassGeo = track(new THREE.BufferGeometry());
    glassGeo.setAttribute("position", new THREE.Float32BufferAttribute(glassPos, 3));
    const glassMat = track(
      new THREE.MeshBasicMaterial({
        color: COLOR_FLOOR, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false,
      })
    );
    shell.add(new THREE.Mesh(glassGeo, glassMat));

    const furnPos: number[] = [];
    for (const [cx, cz, w, d, h] of FURNITURE) {
      const box = new THREE.BoxGeometry(w, h, d);
      const edges = new THREE.EdgesGeometry(box);
      const arr = edges.getAttribute("position");
      for (let i = 0; i < arr.count; i++) {
        furnPos.push(arr.getX(i) + cx, arr.getY(i) + h / 2, arr.getZ(i) + cz);
      }
      box.dispose();
      edges.dispose();
    }
    const furnGeo = track(new THREE.BufferGeometry());
    furnGeo.setAttribute("position", new THREE.Float32BufferAttribute(furnPos, 3));
    const furnMat = track(new THREE.LineBasicMaterial({ color: COLOR_FLOOR, transparent: true, opacity: 0.3 }));
    shell.add(new THREE.LineSegments(furnGeo, furnMat));

    const cornerGeo = track(new THREE.BufferGeometry());
    cornerGeo.setAttribute("position", new THREE.Float32BufferAttribute(cornerPts, 3));
    const cornerMat = track(
      new THREE.PointsMaterial({
        color: 0xffffff, size: 0.55, map: dotTex, transparent: true, opacity: 0.95,
        depthWrite: false, blending: THREE.AdditiveBlending,
      })
    );
    shell.add(new THREE.Points(cornerGeo, cornerMat));

    // ── Ground: a dot grid that ripples out from the centre ─────────────────
    const groundPos: number[] = [];
    const groundBright: number[] = [];
    const insideL = (x: number, z: number) =>
      (x >= 0 && x <= 24 && z >= 0 && z <= 10) || (x >= 0 && x <= 18 && z >= 0 && z <= 16);
    for (let gx = -6; gx <= 30; gx += 1) {
      for (let gz = -5; gz <= 21; gz += 1) {
        const dx = gx - PLAN_CX;
        const dz = gz - PLAN_CZ;
        const dist2 = dx * dx + dz * dz;
        const bright = insideL(gx, gz) ? 0.7 : 0.08 + 0.42 * Math.exp(-dist2 / 90);
        // same plane as the plan floor, centred on the scene origin
        groundPos.push(dx, -WALL_H * 0.42, dz);
        groundBright.push(bright);
      }
    }
    const groundGeo = track(new THREE.BufferGeometry());
    groundGeo.setAttribute("position", new THREE.Float32BufferAttribute(groundPos, 3));
    groundGeo.setAttribute("aBright", new THREE.Float32BufferAttribute(groundBright, 1));
    const groundMat = track(
      new THREE.ShaderMaterial({
        vertexShader: GROUND_VERT,
        fragmentShader: GROUND_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uTime: { value: 0 },
          uScale: { value: 500 },
          uSize: { value: 0.2 },
          uOpacity: { value: 0 },
          uColor: { value: new THREE.Color(0x9db4d8) },
        },
      })
    );
    spin.add(new THREE.Points(groundGeo, groundMat));

    // ── Pipe layers ─────────────────────────────────────────────────────────
    const pipeMats: Record<"plumbing" | "electrical", THREE.ShaderMaterial[]> = { plumbing: [], electrical: [] };
    const pipeGroups: Record<"plumbing" | "electrical", THREE.Group> = {
      plumbing: new THREE.Group(),
      electrical: new THREE.Group(),
    };
    plan.add(pipeGroups.plumbing, pipeGroups.electrical);

    const buildPipes = (
      key: "plumbing" | "electrical",
      runs: P3[][],
      color: number,
      bend: number,
      radii: (i: number) => number
    ) => {
      runs.forEach((pts, i) => {
        const path = roundedPath(pts, bend);
        const len = path.getLength();
        const geo = track(new THREE.TubeGeometry(path, Math.max(8, Math.ceil(len * 5)), radii(i), 10, false));
        const mat = track(
          new THREE.ShaderMaterial({
            vertexShader: PIPE_VERT,
            fragmentShader: PIPE_FRAG,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            uniforms: {
              uColor: { value: new THREE.Color(color) },
              uTime: { value: 0 },
              uOpacity: { value: 0 },
              uPhase: { value: (i * 0.37) % 1 },
              uDensity: { value: Math.max(1, len / 9) },
              uFlow: { value: 0.16 },
            },
          })
        );
        pipeMats[key].push(mat);
        pipeGroups[key].add(new THREE.Mesh(geo, mat));
      });
    };
    buildPipes("plumbing", PIPES_PLUMBING, COLOR_PLUMBING, 0.9, (i) => (i === 0 ? 0.14 : 0.1));
    buildPipes("electrical", PIPES_ELECTRICAL, COLOR_ELECTRICAL, 0.5, (i) => (i === 0 ? 0.09 : i >= 6 ? 0.05 : 0.07));

    const makePoints = (pts: P3[], color: number, size: number, tex: THREE.Texture) => {
      const geo = track(new THREE.BufferGeometry());
      geo.setAttribute("position", new THREE.Float32BufferAttribute(pts.flat(), 3));
      const mat = track(
        new THREE.PointsMaterial({
          color, size, map: tex, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending,
        })
      );
      return { points: new THREE.Points(geo, mat), mat };
    };
    const fixturePts = {
      plumbing: makePoints(PLUMBING_FIXTURES, COLOR_PLUMBING, 0.95, ringTex),
      lights: makePoints(ELECTRICAL_LIGHTS, COLOR_ELECTRICAL, 1.0, ringTex),
      switches: makePoints(ELECTRICAL_SWITCHES, COLOR_ELECTRICAL, 0.5, dotTex),
      outlets: makePoints(ELECTRICAL_OUTLETS, COLOR_ELECTRICAL, 0.4, dotTex),
    };
    pipeGroups.plumbing.add(fixturePts.plumbing.points);
    pipeGroups.electrical.add(fixturePts.lights.points, fixturePts.switches.points, fixturePts.outlets.points);

    // ── Camera, fit and sizing ──────────────────────────────────────────────
    let camDist = 40;
    let elevation = 0.6;
    const placeCamera = () => {
      camera.position.set(0, Math.sin(elevation) * camDist, Math.cos(elevation) * camDist);
      camera.lookAt(0, 0, 0);
    };
    const resize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (w === 0 || h === 0) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      const vHalf = Math.tan((FOV * Math.PI) / 360);
      const hHalf = vHalf * camera.aspect;
      const R = 17.5; // radius of the building's footprint, with margin
      camDist = Math.max(R / hHalf, (R * 0.72) / vHalf) + 4;
      groundMat.uniforms.uScale.value = (h * pixelRatio) / (2 * vHalf);
      placeCamera();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(mount);
    resize();

    // ── Pointer: drag to rotate and tilt ────────────────────────────────────
    let az = 0.62;
    let azVel = 0;
    const autoSpeed = reduceMotion ? 0 : 0.11;
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    let lastMove = 0;
    const onDown = (e: PointerEvent) => {
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      lastMove = performance.now();
      mount.setPointerCapture(e.pointerId);
      mount.style.cursor = "grabbing";
    };
    const onMove = (e: PointerEvent) => {
      if (!dragging) return;
      const now = performance.now();
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      const dAz = dx * 0.006;
      az += dAz;
      elevation = Math.min(1.15, Math.max(0.3, elevation + dy * 0.004));
      const dtMove = Math.max(0.008, (now - lastMove) / 1000);
      lastMove = now;
      azVel = Math.max(-3, Math.min(3, dAz / dtMove));
      placeCamera();
    };
    const onUp = (e: PointerEvent) => {
      if (!dragging) return;
      dragging = false;
      if (mount.hasPointerCapture(e.pointerId)) mount.releasePointerCapture(e.pointerId);
      mount.style.cursor = "grab";
    };
    mount.style.cursor = "grab";
    mount.addEventListener("pointerdown", onDown);
    mount.addEventListener("pointermove", onMove);
    mount.addEventListener("pointerup", onUp);
    mount.addEventListener("pointercancel", onUp);

    // ── Animation loop ──────────────────────────────────────────────────────
    const t0 = performance.now();
    let prev = t0;
    let raf = 0;
    const level: Record<LayerKey, number> = { floor: 0, electrical: 0, plumbing: 0 };

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - prev) / 1000);
      prev = now;
      const elapsed = reduceMotion ? 99 : (now - t0) / 1000;
      const time = reduceMotion ? 3 : elapsed;

      // rotation: free-wheel after a drag, then settle into the slow turn
      if (!dragging) {
        azVel += (autoSpeed - azVel) * (1 - Math.exp(-dt * 1.4));
        az += azVel * dt;
      }
      spin.rotation.y = az;

      // intro: walls rise, then plumbing, then electrical
      const rise = easeOutCubic(elapsed / 1.7);
      shell.scale.y = Math.max(0.001, rise);
      const intro: Record<LayerKey, number> = {
        floor: smooth(elapsed / 0.9),
        plumbing: smooth((elapsed - 1.3) / 1.0),
        electrical: smooth((elapsed - 2.0) / 1.0),
      };

      // layer visibility and focus: ease each layer's level toward its target
      const on = layersRef.current;
      const f = focusRef.current;
      (Object.keys(level) as LayerKey[]).forEach((k) => {
        const target = !on[k] ? 0 : f && f !== k ? 0.22 : 1;
        level[k] += (target - level[k]) * (1 - Math.exp(-dt * 7));
      });

      const fl = level.floor * intro.floor;
      wallMat.opacity = 0.85 * fl;
      glassMat.opacity = 0.05 * fl;
      furnMat.opacity = 0.3 * fl;
      cornerMat.opacity = 0.95 * fl;
      shell.visible = fl > 0.003;

      const pl = level.plumbing * intro.plumbing;
      pipeMats.plumbing.forEach((m) => {
        m.uniforms.uOpacity.value = pl;
        m.uniforms.uTime.value = time;
      });
      fixturePts.plumbing.mat.opacity = pl;
      pipeGroups.plumbing.visible = pl > 0.003;

      const el = level.electrical * intro.electrical;
      pipeMats.electrical.forEach((m) => {
        m.uniforms.uOpacity.value = el;
        m.uniforms.uTime.value = time;
      });
      fixturePts.lights.mat.opacity = el;
      fixturePts.switches.mat.opacity = el * 0.9;
      fixturePts.outlets.mat.opacity = el * 0.7;
      pipeGroups.electrical.visible = el > 0.003;

      groundMat.uniforms.uTime.value = time;
      groundMat.uniforms.uOpacity.value = smooth(elapsed / 1.2) * (0.6 + 0.4 * level.floor);

      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      mount.removeEventListener("pointerdown", onDown);
      mount.removeEventListener("pointermove", onMove);
      mount.removeEventListener("pointerup", onUp);
      mount.removeEventListener("pointercancel", onUp);
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={mountRef}
      aria-hidden="true"
      style={{ position: "absolute", inset: 0, touchAction: "pan-y", userSelect: "none" }}
    />
  );
}
