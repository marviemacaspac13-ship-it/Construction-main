import { useEffect, useRef, useState } from "react";
import { PixelLogo } from "../components/PixelLogo";
import { useLocation, useNavigate } from "react-router";
import { estimateFromImage, readsPrintedDimensions } from "../../lib/estimate";
import {
  createProject,
  getProject,
  markProjectError,
  updateProjectEstimate,
  type ProjectDraft,
} from "../../lib/projects";
import { EstimateSaveError, prepareEstimateSave, type PendingEstimateSave } from "../../lib/revision-save";
import { cleanupPlanFiles, uploadPlan, type PlanAsset } from "../../lib/plan-assets";
import { PlumbingFixtureReview } from '../components/PlumbingFixtureReview';
import { ElectricalDeviceReview } from '../components/ElectricalDeviceReview';
import { proposeElectrical, type ElectricalChoice, type ElectricalConfirmation, type ElectricalProposal } from '../../lib/electrical-proposals';
import { proposePlumbing, type FixtureConfirmation, type FixtureProposal, type FixtureProposalResult } from '../../lib/plumbing-proposals';

/**
 * `projectId` is present only on a retry after a failed scan - the row
 * already exists and is reused, so retrying does not file a second one.
 */
type NavState = { draft?: ProjectDraft; projectId?: string; expectedRevision?: string | null; file?: File };

/** Reading printed dimensions off the drawing. */
const OCR_STEPS = [
  "Preparing your plan...",
  "Reading your plan...",
  "Checking plan details...",
  "Calculating quantities...",
  "Generating cost estimate...",
];

/** Counting uploaded symbol references against the drawing. */
const DETECTION_STEPS = [
  "Preparing your plan...",
  "Reading your plan...",
  "Checking plan details...",
  "Calculating quantities...",
  "Generating cost estimate...",
];

export function ScanningScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const { draft, projectId, file, expectedRevision } = (location.state ?? {}) as NavState;

  const [progress, setProgress] = useState(0);
  const [step, setStep]         = useState(0);
  const [error, setError]       = useState("");
  // The failure could not be recorded, so the row is still "processing".
  const [unmarked, setUnmarked] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const [saveConflict, setSaveConflict] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hasPreviousResult, setHasPreviousResult] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);
  const [uploading, setUploading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [proposal, setProposal] = useState<FixtureProposalResult | null>(null);
  const [electricalProposal,setElectricalProposal]=useState<ElectricalProposal|null>(null);
  const electricalWait=useRef<{resolve:(value:ElectricalConfirmation)=>void;reject:(error:Error)=>void}|null>(null);
  const [readerMessage, setReaderMessage] = useState('');
  const reviewWait = useRef<{resolve:(value:FixtureConfirmation|null)=>void; reject:(error:Error)=>void} | null>(null);
  const uploaded = useRef<PlanAsset | null>(null);
  const uploadId = useRef(crypto.randomUUID());
  const scanAttempt = useRef<(() => Promise<void>) | null>(null);
  const pending = useRef<PendingEstimateSave | null>(null);
  const saveInFlight = useRef(false);
  const ran = useRef(false);
  // Survives a failed scan so "Back to Upload" can hand the existing row
  // back instead of orphaning it.
  const created = useRef<string | null>(projectId ?? null);
  // Whether the user is still on this screen. Its own effect, NOT a flag
  // cleared in the scan effect's cleanup: StrictMode runs that cleanup once
  // right after mount, `ran` stops the scan effect from re-running, and the
  // flag would then say "left" for the whole scan - so no scan would ever
  // reach Results. This one sets itself back to true on the remount.
  const onScreen = useRef(true);

  useEffect(() => {
    onScreen.current = true;
    return () => { onScreen.current = false; reviewWait.current?.reject(new Error('Fixture review was left before confirmation.')); reviewWait.current=null; electricalWait.current?.reject(new Error('Electrical review was left before confirmation.'));electricalWait.current=null; };
  }, []);

  const planType = draft?.planType;
  const readsDimensions = readsPrintedDimensions(planType);
  const steps = readsDimensions ? OCR_STEPS : DETECTION_STEPS;

  function confirmFixtures(fixtures:FixtureProposal[]) {
    if (!proposal?.receipt) return;
    reviewWait.current?.resolve({receipt:proposal.receipt,confirmed:true,fixtures});
    reviewWait.current=null; setProposal(null);
  }

  function confirmElectrical(choices:ElectricalChoice[]) {
    if(!electricalProposal)return;
    electricalWait.current?.resolve({receipt:electricalProposal.receipt,confirmed:true,choices,estimate_scope:'reviewed_device_allowances'});
    electricalWait.current=null;setElectricalProposal(null);
  }

  // Leaving the review any other way strands the row at "processing"; rejecting
  // marks it as an error, whose Back to Upload reuses the same project.
  function uploadClearerElectrical() {
    electricalWait.current?.reject(new Error('No devices were found on this drawing. Upload a clearer export of the original plan.'));
    electricalWait.current=null;setElectricalProposal(null);
  }

  async function saveComputedEstimate() {
    if (!pending.current || saveInFlight.current) return;
    saveInFlight.current = true;
    if (onScreen.current) setSaving(true);
    try {
      await updateProjectEstimate(pending.current);
      if (onScreen.current) {
        setProgress(100);
        navigate("/results", { state: { projectId: pending.current.project_id } });
      }
    } finally {
      saveInFlight.current = false;
      if (onScreen.current) setSaving(false);
    }
  }

  async function retrySave() {
    try {
      await saveComputedEstimate();
    } catch (e) {
      if (!onScreen.current) return;
      setError(e instanceof Error ? e.message : "Saving failed. Try again.");
      setSaveConflict(e instanceof EstimateSaveError && e.status === 409);
    }
  }

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
    //
    // Leaving mid-scan does NOT cancel it: the row is still saved as
    // completed or error, and shows up on Projects. What stops is everything
    // that touches this screen - above all the jump to Results, which used
    // to pull the user off whatever page they had moved on to (audit FLOW-01).
    scanAttempt.current = async () => {
      try {
        if (onScreen.current) { setError(""); setReaderMessage(''); setUploadFailed(false); setRetrying(true); }
        if (!created.current) {
          created.current = (await createProject(draft)).id;
        }
        const id = created.current;
        // Capture BEFORE scanning; reading after would conceal a stale tab.
        const existing = await getProject(id);
        if (!existing) throw new Error("Project not found. Return to Projects and try again.");
        if (onScreen.current) setHasPreviousResult(existing.status === "completed");
        const expected = expectedRevision !== undefined ? expectedRevision : existing.active_revision_id ?? null;
        if (!uploaded.current) {
          if (onScreen.current) setUploading(true);
          await cleanupPlanFiles().catch(() => undefined);
          uploaded.current = await uploadPlan(id, uploadId.current, file);
        }
        if (onScreen.current) setUploading(false);
        let fixtureReview:FixtureConfirmation|null=null;
        if (draft.planType === 'Plumbing Plan') {
          const found=await proposePlumbing(file);
          if (found) {
            if (found.source_sha256 !== uploaded.current.source_sha256) throw new Error('The proposal image differs from its saved original. Upload the plan again.');
            if (found.available) {
              clearInterval(tick);
              if (!onScreen.current) throw new Error('Return to the plan to review fixtures before estimating.');
              fixtureReview=await new Promise<FixtureConfirmation|null>((resolve,reject)=>{
                reviewWait.current={resolve,reject};setProposal(found);
              });
            } else if(onScreen.current) setReaderMessage('Reading your plumbing plan…');
          }
        }
        let electricalReview:ElectricalConfirmation|undefined;
        if(draft.planType==='Electrical Plan') {
          const found=await proposeElectrical(file);
          if(found.source_sha256!==uploaded.current.source_sha256)throw new Error('Electrical proposals differ from the saved original. Upload the plan again.');
          clearInterval(tick);
          if(!onScreen.current)throw new Error('Return to the plan to review electrical devices before estimating.');
          electricalReview=await new Promise<ElectricalConfirmation>((resolve,reject)=>{electricalWait.current={resolve,reject};setElectricalProposal(found);});
        }
        const result = await estimateFromImage(file, draft.planType, draft.wallHeightM, fixtureReview ?? undefined, electricalReview);
        if (result.scan.source_sha256 !== uploaded.current.source_sha256) throw new Error("The scanned image differs from its saved original. Upload the plan again.");
        pending.current = prepareEstimateSave(id, expected, result, file, crypto.randomUUID(), uploaded.current.id);
        clearInterval(tick);
        await saveComputedEstimate();
      } catch (e) {
        clearInterval(tick);
        const message = e instanceof Error ? e.message : "Scan failed.";
        if (onScreen.current) {
          setError(message);
          setUploadFailed(!uploaded.current);
          setSaveFailed(!!pending.current);
          setSaveConflict(e instanceof EstimateSaveError && e.status === 409);
        }
        if (created.current) {
          await markProjectError(created.current, message).catch(() => {
            if (onScreen.current) setUnmarked(true);
          });
        }
      } finally {
        if (onScreen.current) setRetrying(false);
      }
    };
    void scanAttempt.current();

    return () => clearInterval(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rings = [200, 168, 136, 108, 82, 60, 42, 28];

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-full py-20 px-6 sm:px-8 animate-page-in motion-reduce:animate-none text-center" aria-busy={saving}>
        <h1 className="text-[20px] font-medium text-foreground mb-3">{uploadFailed ? "Original plan not uploaded" : saveFailed ? "Estimate not saved" : "Scan could not be completed"}</h1>
        <p role="alert" className="text-[16px] leading-relaxed text-muted-foreground max-w-md mb-6 break-words">{error}</p>
        {saveFailed && (
          <p className="text-[16px] leading-relaxed text-muted-foreground max-w-md mb-6">
            Your computed estimate is kept in this tab. Keep it open to retry saving.
            Any previously saved estimate remains available.
          </p>
        )}
        {unmarked && (
          <p className="text-[16px] leading-relaxed text-muted-foreground max-w-md mb-6">
            The status of this attempt could not be saved either. Keep this tab open to retry,
            or return to upload to scan again using the same project.
          </p>
        )}
        <div className="flex flex-wrap justify-center gap-3">
        {uploadFailed && <button type="button" disabled={retrying} onClick={() => void scanAttempt.current?.()}
          className="min-h-11 px-5 rounded-lg bg-foreground text-background text-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-foreground">
          Retry uploading
        </button>}
        {saveFailed && !saveConflict && (
          <button type="button" onClick={retrySave} disabled={saving}
            className="min-h-[44px] px-5 rounded-lg bg-foreground text-background text-[14px] font-medium hover:opacity-90 active:opacity-80 cursor-pointer disabled:opacity-60 disabled:cursor-wait focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-foreground/70">
            {saving ? "Saving estimate…" : "Retry saving"}
          </button>
        )}
        {(uploaded.current || (saveFailed && (hasPreviousResult || saveConflict))) && (
          <button type="button" disabled={saving}
            onClick={() => navigate("/results", { state: { projectId: created.current } })}
            className="min-h-[44px] px-5 rounded-lg border border-border text-[14px] hover:bg-accent active:bg-accent cursor-pointer disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-foreground/70">
            {uploaded.current && !saveFailed && !hasPreviousResult ? "View original plan" : "View saved project"}
          </button>
        )}
        {!saveFailed && !uploadFailed && <button type="button" disabled={retrying} className="min-h-11 px-5 rounded-lg border border-border hover:bg-accent" onClick={()=>void scanAttempt.current?.()}>Retry scan and review</button>}
        <button
          type="button" disabled={saving}
          onClick={() =>
            navigate("/upload", { state: { draft, projectId: created.current, expectedRevision } })
          }
          className="min-h-[44px] px-5 rounded-lg border border-border text-[14px] hover:bg-accent active:bg-accent cursor-pointer disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-foreground/70"
        >
          Back to Upload
        </button>
        </div>
      </div>
    );
  }

  if (proposal && file) return <PlumbingFixtureReview key={proposal.receipt} file={file} proposal={proposal} busy={false} onConfirm={confirmFixtures}/>;
  if(electricalProposal&&file)return <ElectricalDeviceReview key={electricalProposal.receipt} file={file} proposal={electricalProposal} onConfirm={confirmElectrical} onUploadClearer={uploadClearerElectrical}/>;

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

      <p role="status" className="text-sm text-muted-foreground mb-2 text-center">{readerMessage || (uploading ? "Saving original plan…" : planType==='Plumbing Plan' ? 'Finding plumbing fixtures…' : planType==='Electrical Plan' ? 'Finding electrical devices…' : steps[step])}</p>
      <p className="text-[10px] font-mono text-muted-foreground/50 text-center max-w-xs leading-relaxed">
        Sit back and relax while TRACE performs material cost estimation.
      </p>

      <style>{`@keyframes traceSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
