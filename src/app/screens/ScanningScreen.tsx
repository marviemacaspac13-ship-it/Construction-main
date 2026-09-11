import { useEffect, useRef, useState } from "react";
import { PixelLogo } from "../components/PixelLogo";
import { useLocation, useNavigate } from "react-router";
import { estimateFromImage, readsPrintedDimensions } from "../../lib/estimate";
import { markProjectError, updateProjectEstimate } from "../../lib/projects";

type NavState = { projectId?: string; planType?: string; file?: File };

/** Reading printed dimensions off the drawing. */
const OCR_STEPS = [
  "Initializing analysis engine...",
  "Reading dimension text...",
  "Checking dimension chains...",
  "Deriving wall quantities...",
  "Generating cost estimate...",
];

/** Counting uploaded symbol references against the drawing. */
const DETECTION_STEPS = [
  "Initializing analysis engine...",
  "Detecting structural elements...",
  "Mapping material regions...",
  "Calculating quantities...",
  "Generating cost estimate...",
];

export function ScanningScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId, planType, file } = (location.state ?? {}) as NavState;

  const [progress, setProgress] = useState(0);
  const [step, setStep]         = useState(0);
  const [error, setError]       = useState("");
  const ran = useRef(false);

  const readsDimensions = readsPrintedDimensions(planType);
  const steps = readsDimensions ? OCR_STEPS : DETECTION_STEPS;

  useEffect(() => {
    if (!projectId || !file) {
      navigate("/projects/details");
      return;
    }
    if (ran.current) return; // guard against React StrictMode double-invoke in dev
    ran.current = true;

    // Animate progress up to 90% while the real request is in flight - we
    // don't know how long it'll actually take, so this is a visual
    // approximation, not tied to real backend progress.
    const tick = setInterval(() => {
      setProgress((p) => {
        const next = Math.min(p + 1, 90);
        setStep(Math.min(Math.floor((next / 100) * steps.length), steps.length - 1));
        return next;
      });
    }, 90);

    // One endpoint for every plan type. Floor plans are read from their
    // printed dimensions; the rest are counted against uploaded symbol
    // references. The backend picks the path and prices both the same way.
    estimateFromImage(file, planType ?? "Floor Plan")
      .then((result) => updateProjectEstimate(projectId, result))
      .then(() => {
        clearInterval(tick);
        setProgress(100);
        setStep(steps.length - 1);
        setTimeout(() => navigate("/results", { state: { projectId } }), 500);
      })
      .catch(async (e) => {
        clearInterval(tick);
        const message = e instanceof Error ? e.message : "Scan failed.";
        setError(message);
        await markProjectError(projectId, message).catch(() => {});
      });

    return () => clearInterval(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rings = [200, 168, 136, 108, 82, 60, 42, 28];

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-20 px-8 animate-page-in text-center">
        <p className="text-[13px] font-mono text-red-400 mb-2">Scan failed</p>
        <p className="text-[11px] font-mono text-muted-foreground max-w-sm mb-6">{error}</p>
        <p className="text-[10px] font-mono text-muted-foreground/60 max-w-sm mb-6">
          Check that the backend server is running at the address configured in VITE_SCAN_API_URL.
        </p>
        <button
          onClick={() => navigate("/upload", { state: { projectId, planType } })}
          className="h-9 px-4 rounded-lg border border-border text-[11px] font-mono tracking-[0.14em] uppercase press-scale hover:bg-accent"
        >
          Back to Upload
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full py-20 px-8 animate-page-in">
      <div className="relative flex items-center justify-center mb-14" style={{ width: 240, height: 240 }}>
        {rings.map((size, i) => (
          <div
            key={i}
            className="absolute rounded-full border"
            style={{
              width: size, height: size,
              borderColor: `rgba(255,255,255,${0.03 + (rings.length - i) * 0.02})`,
              borderTopColor: i % 2 === 0 ? `rgba(255,255,255,${0.25 + (rings.length - i) * 0.04})` : "transparent",
              borderRightColor: i % 3 === 0 ? `rgba(255,255,255,0.12)` : "transparent",
              animation: `traceSpin ${1.6 + i * 0.32}s linear infinite ${i % 2 === 0 ? "" : "reverse"}`,
            }}
          />
        ))}
        <div className="relative z-10 flex flex-col items-center gap-2">
          <PixelLogo dotSize={4} gap={2.5} letterGap={9} />
          <span className="text-[10px] font-mono text-muted-foreground tracking-widest mt-1">{progress}%</span>
        </div>
      </div>

      <div className="w-56 mb-5">
        <div className="h-px bg-border rounded-full overflow-hidden">
          <div className="h-full bg-foreground rounded-full transition-all duration-75" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <p className="text-[11px] font-mono text-muted-foreground mb-2 text-center h-4">{steps[step]}</p>
      <p className="text-[10px] font-mono text-muted-foreground/50 text-center max-w-xs leading-relaxed">
        Sit back and relax while TRACE performs material cost estimation.
      </p>

      <style>{`@keyframes traceSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}