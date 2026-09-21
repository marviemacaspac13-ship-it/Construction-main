import { useEffect, useRef, useState } from "react";
import { PixelLogo } from "../components/PixelLogo";
import { useLocation, useNavigate } from "react-router";
import { estimateFromImage, readsPrintedDimensions } from "../../lib/estimate";
import {
  createProject,
  markProjectError,
  updateProjectEstimate,
  type ProjectDraft,
} from "../../lib/projects";

/**
 * `projectId` is present only on a retry after a failed scan - the row
 * already exists and is reused, so retrying does not file a second one.
 */
type NavState = { draft?: ProjectDraft; projectId?: string; file?: File };

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
  const { draft, projectId, file } = (location.state ?? {}) as NavState;

  const [progress, setProgress] = useState(0);
  const [step, setStep]         = useState(0);
  const [error, setError]       = useState("");
  const ran = useRef(false);
  // Survives a failed scan so "Back to Upload" can hand the existing row
  // back instead of orphaning it.
  const created = useRef<string | null>(projectId ?? null);

  const planType = draft?.planType;
  const readsDimensions = readsPrintedDimensions(planType);
  const steps = readsDimensions ? OCR_STEPS : DETECTION_STEPS;

  useEffect(() => {
    if (!draft || !file) {
      navigate("/projects/details");
      return;
    }
    // Guards the StrictMode double-invoke. It matters more than it used to:
    // this effect now CREATES the project, so running twice files two rows.
    if (ran.current) return;
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

    // The project row is written HERE and nowhere earlier. Everything before
    // this point is a draft in router state, so abandoning the flow leaves
    // nothing behind. A scan that fails still leaves a row, marked "error" -
    // that one is a record of something that actually happened.
    //
    // One endpoint for every plan type. Floor plans are read from their
    // printed dimensions; the rest are counted against uploaded symbol
    // references. The backend picks the path and prices both the same way.
    (async () => {
      try {
        if (!created.current) {
          created.current = (await createProject(draft)).id;
        }
        const id = created.current;

        const result = await estimateFromImage(file, draft.planType);
        await updateProjectEstimate(id, result);

        clearInterval(tick);
        setProgress(100);
        setStep(steps.length - 1);
        setTimeout(() => navigate("/results", { state: { projectId: id } }), 500);
      } catch (e) {
        clearInterval(tick);
        const message = e instanceof Error ? e.message : "Scan failed.";
        setError(message);
        if (created.current) {
          await markProjectError(created.current, message).catch(() => {});
        }
      }
    })();

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
          onClick={() =>
            navigate("/upload", { state: { draft, projectId: created.current } })
          }
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