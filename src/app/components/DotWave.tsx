import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * DotWave — 3D particle wave grid / dot-matrix terrain.
 *
 * A flat grid of glowing points extends into the horizon. Each point's
 * height oscillates over time via layered sine waves (a cheap stand-in for
 * Perlin noise) to read as flowing terrain. Fog fades far-away dots into
 * the dark background for atmospheric depth. Mouse movement gives a subtle
 * camera parallax tilt.
 *
 * Drop-in replacement for the old SVG version — same `<DotWave />` usage,
 * no props required.
 */
export function DotWave() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // ────────────────────────────────────────────────────────────────────
    // TWEAKABLE PARAMETERS
    // ────────────────────────────────────────────────────────────────────

    // Dot spacing, size & density
    const GRID_COLS = 150;      // number of dots across (density)
    const GRID_ROWS = 220;      // number of dots into the distance (density)
    const SEPARATION = 26;      // spacing between dots, in world units
    const DOT_SIZE = 7.5;       // base rendered size of each dot (px, before perspective attenuation)

    // Wave motion: speed & frequency
    const WAVE_SPEED = 0.045;   // how fast the waves scroll/animate (higher = faster)
    const WAVE_FREQ_X = 0.22;   // spatial frequency across the grid (columns) — higher = tighter ripples
    const WAVE_FREQ_Z = 0.32;   // spatial frequency into the distance (rows)

    // Wave amplitude: height of the "hills"
    const WAVE_AMPLITUDE_X = 52; // hill height driven by the column-wise wave
    const WAVE_AMPLITUDE_Z = 28; // hill height driven by the row-wise wave

    // Dot color & glow
    const DOT_COLOR = 0xffffff;   // glowing dot color
    const DOT_OPACITY = 0.9;      // overall opacity of dots (peak, before fog)

    // Atmospheric depth / fog fade (far dots shrink & fade into background)
    const FOG_COLOR = 0x000000;   // must match the page's dark background
    const FOG_NEAR = 350;         // distance where fog starts
    const FOG_FAR = 2600;         // distance where dots are fully faded out

    // Camera framing (perspective depth feel)
    const CAMERA_FOV = 70;
    const CAMERA_HEIGHT = 300;    // how high above the grid the camera sits
    const CAMERA_DISTANCE = 300;  // how far back the camera sits (behind the grid's near edge)

    // Interactive mouse parallax (set MOUSE_PARALLAX_STRENGTH to 0 to disable)
    const MOUSE_PARALLAX_STRENGTH = 40; // max camera x/y offset in world units
    const MOUSE_LERP = 0.04;            // smoothing factor for the parallax follow

    // ────────────────────────────────────────────────────────────────────

    const width = mount.clientWidth;
    const height = mount.clientHeight;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(FOG_COLOR, FOG_NEAR, FOG_FAR);

    const camera = new THREE.PerspectiveCamera(CAMERA_FOV, width / height, 1, 4000);
    camera.position.set(0, CAMERA_HEIGHT, CAMERA_DISTANCE);
    camera.lookAt(0, 0, -GRID_ROWS * SEPARATION * 0.5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    mount.appendChild(renderer.domElement);

    // Build the dot grid, centered on X, extending away from camera on Z
    const numDots = GRID_COLS * GRID_ROWS;
    const positions = new Float32Array(numDots * 3);
    const basePositions = new Float32Array(numDots * 3); // resting x/z, so wave math has a stable reference

    let i = 0;
    for (let row = 0; row < GRID_ROWS; row++) {
      for (let col = 0; col < GRID_COLS; col++) {
        const x = (col - GRID_COLS / 2) * SEPARATION;
        const z = -row * SEPARATION;
        positions[i * 3] = x;
        positions[i * 3 + 1] = 0;
        positions[i * 3 + 2] = z;
        basePositions[i * 3] = x;
        basePositions[i * 3 + 2] = z;
        i++;
      }
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    // Soft circular glow sprite for each point (instead of a hard square dot)
    const spriteCanvas = document.createElement("canvas");
    spriteCanvas.width = 64;
    spriteCanvas.height = 64;
    const ctx = spriteCanvas.getContext("2d")!;
    const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, "rgba(255,255,255,1)");
    grad.addColorStop(0.4, "rgba(255,255,255,0.6)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 64);
    const dotTexture = new THREE.CanvasTexture(spriteCanvas);

    const material = new THREE.PointsMaterial({
      color: DOT_COLOR,
      size: DOT_SIZE,
      map: dotTexture,
      transparent: true,
      opacity: DOT_OPACITY,
      sizeAttenuation: true,   // dots shrink with distance (perspective depth)
      depthWrite: false,
      blending: THREE.AdditiveBlending, // gives the dots a soft glow where they overlap
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    // ── Mouse parallax state ──────────────────────────────────────────
    let targetX = 0;
    let targetY = 0;
    const handlePointerMove = (e: PointerEvent) => {
      const rect = mount.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;   // -1..1
      const ny = ((e.clientY - rect.top) / rect.height) * 2 - 1;   // -1..1
      targetX = nx * MOUSE_PARALLAX_STRENGTH;
      targetY = -ny * MOUSE_PARALLAX_STRENGTH * 0.4;
    };
    if (MOUSE_PARALLAX_STRENGTH > 0) {
      mount.addEventListener("pointermove", handlePointerMove);
    }

    // ── Resize handling (auto-fit to the container, not just window) ──
    const resizeObserver = new ResizeObserver(() => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    resizeObserver.observe(mount);

    // ── Animation loop ─────────────────────────────────────────────────
    let animationFrameId: number;
    let count = 0;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      const posAttr = geometry.attributes.position as THREE.BufferAttribute;
      let idx = 0;
      for (let row = 0; row < GRID_ROWS; row++) {
        for (let col = 0; col < GRID_COLS; col++) {
          const bx = basePositions[idx * 3];
          const bz = basePositions[idx * 3 + 2];
          // Layered sine waves standing in for Perlin/simplex noise —
          // swap this line for a real noise(x, z, t) call for a less regular look.
          const y =
            Math.sin(col * WAVE_FREQ_X + count) * WAVE_AMPLITUDE_X +
            Math.sin(row * WAVE_FREQ_Z - count * 1.3) * WAVE_AMPLITUDE_Z;
          posAttr.array[idx * 3] = bx;
          posAttr.array[idx * 3 + 1] = y;
          posAttr.array[idx * 3 + 2] = bz;
          idx++;
        }
      }
      posAttr.needsUpdate = true;

      count += WAVE_SPEED;

      // Smoothly ease the camera toward the mouse-driven target (parallax)
      camera.position.x += (targetX - camera.position.x) * MOUSE_LERP;
      camera.position.y += (CAMERA_HEIGHT + targetY - camera.position.y) * MOUSE_LERP;
      camera.lookAt(0, 0, -GRID_ROWS * SEPARATION * 0.5);

      renderer.render(scene, camera);
    };
    animate();

    // ── Cleanup: cancel RAF, remove listeners, dispose GPU resources ──
    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      if (MOUSE_PARALLAX_STRENGTH > 0) {
        mount.removeEventListener("pointermove", handlePointerMove);
      }
      geometry.dispose();
      material.dispose();
      dotTexture.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, []);

  return <div ref={mountRef} style={{ width: "100%", height: "100%", display: "block", overflow: "hidden" }} />;
}