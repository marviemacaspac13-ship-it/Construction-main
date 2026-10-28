import { useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, ImageIcon, Loader2, Maximize, Minus, Plus, RefreshCw } from 'lucide-react';
import { planViewLink, type PlanAsset } from '../../lib/plan-assets';
import { FIXTURE_COLORS, type FixtureReview } from '../../lib/plumbing-proposals';
import { deviceNames, type ElectricalReview } from '../../lib/electrical-proposals';

type Point = {x: number; y: number};

/** An immutable asset, never the project's latest upload or an expiring stored URL. */
export function PlanViewer({projectId, asset, scanRevisionId, fixtureReview, electricalReview}: {
  projectId: string; asset: PlanAsset | null | undefined; scanRevisionId?: string; fixtureReview?: FixtureReview | null;
  electricalReview?: ElectricalReview | null;
}) {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>({x:0,y:0});
  const [size, setSize] = useState({width:1,height:1});
  const [natural, setNatural] = useState({width:asset?.pixel_width ?? 1,height:asset?.pixel_height ?? 1});
  const stage = useRef<HTMLDivElement>(null);
  const drag = useRef<{id:number; start:Point; pan:Point} | null>(null);
  const imageRetry = useRef(false);

  useEffect(() => {
    if (!stage.current) return;
    const observer = new ResizeObserver(([entry]) => setSize({width:entry.contentRect.width,height:entry.contentRect.height}));
    observer.observe(stage.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!asset?.storage_path) { setLoading(false); return; }
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const link = await planViewLink(projectId, asset.id);
        if (!active) return;
        setUrl(link.url); setError('');
        // Renew before expiration; preserve zoom/pan while renewing the capability.
        timer = setTimeout(() => void refresh(), Math.max(10, link.expires_in - 60) * 1000);
      } catch (e) {
        if (active) { setError(e instanceof Error ? e.message : 'Could not open the original plan.'); setLoading(false); }
      }
    };
    setLoading(true); setError('');
    void refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [projectId, asset?.id, asset?.storage_path, retry]);

  const fit = Math.min(size.width / natural.width, size.height / natural.height) * 0.96;
  const scale = fit * zoom;
  const bounded = (point:Point): Point => {
    const maxX = Math.max(0,(natural.width * scale - size.width) / 2);
    const maxY = Math.max(0,(natural.height * scale - size.height) / 2);
    return {x:Math.max(-maxX,Math.min(maxX,point.x)),y:Math.max(-maxY,Math.min(maxY,point.y))};
  };
  const visiblePan = bounded(pan);
  const movePan = (x:number,y:number) => setPan(bounded({x:visiblePan.x+x,y:visiblePan.y+y}));
  const fitPage = () => { setZoom(1); setPan({x:0,y:0}); };
  const changeZoom = (factor:number) => setZoom(current => Math.max(1,Math.min(8,current * factor)));
  const buttonClass = 'min-w-11 min-h-11 flex items-center justify-center rounded-lg border border-border text-foreground hover:bg-accent disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground';
  const unavailable = !asset?.storage_path;

  return <section aria-label="Original plan" className="min-w-0 border border-border rounded-xl overflow-hidden bg-card">
    <div className="p-4 border-b border-border flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-base font-medium text-foreground">Original plan</h2>
        <p className="text-sm text-muted-foreground break-all mt-1">{asset?.original_filename ?? 'No original image saved'}</p>
      </div>
      <div className="flex items-center gap-2" role="group" aria-label="Plan view controls">
        <button type="button" className={buttonClass} aria-label="Zoom out" disabled={unavailable || loading || !!error || zoom <= 1} onClick={() => changeZoom(1/1.5)}><Minus size={16}/></button>
        <output aria-label="Plan zoom" className="text-sm font-mono tabular-nums w-12 text-center">{Math.round(zoom*100)}%</output>
        <button type="button" className={buttonClass} aria-label="Zoom in" disabled={unavailable || loading || !!error || zoom >= 8} onClick={() => changeZoom(1.5)}><Plus size={16}/></button>
        <button type="button" className={buttonClass} aria-label="Fit plan to page" disabled={unavailable || loading || !!error} onClick={fitPage}><Maximize size={16}/></button>
      </div>
    </div>
    <div ref={stage} role="region" aria-label="Plan image. Drag to pan; use plus, minus, arrow keys or Home to fit."
      tabIndex={unavailable ? -1 : 0}
      className="relative h-[420px] sm:h-[540px] overflow-hidden bg-background select-none focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-foreground"
      style={{cursor:zoom > 1 ? 'grab' : 'default',touchAction:zoom > 1 && !unavailable && !loading && !error ? 'none' : 'auto'}}
      onKeyDown={event => {
        if (unavailable || loading || error) return;
        if (event.key === '+' || event.key === '=') { event.preventDefault(); changeZoom(1.5); }
        if (event.key === '-') { event.preventDefault(); changeZoom(1/1.5); }
        if (event.key === 'Home') { event.preventDefault(); fitPage(); }
        const moves:Record<string,Point> = {ArrowLeft:{x:40,y:0},ArrowRight:{x:-40,y:0},ArrowUp:{x:0,y:40},ArrowDown:{x:0,y:-40}};
        const move=moves[event.key];
        if (move) { event.preventDefault(); movePan(move.x,move.y); }
      }}
      onPointerDown={event => {
        if (event.button !== 0 || zoom <= 1 || loading || error) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current={id:event.pointerId,start:{x:event.clientX,y:event.clientY},pan:visiblePan};
      }}
      onPointerMove={event => {
        const origin=drag.current;
        if (origin?.id === event.pointerId) setPan(bounded({x:origin.pan.x+event.clientX-origin.start.x,y:origin.pan.y+event.clientY-origin.start.y}));
      }}
      onPointerUp={() => {drag.current=null;}} onPointerCancel={() => {drag.current=null;}} onLostPointerCapture={() => {drag.current=null;}}>
      {url && !error && <img key={retry} src={url} alt={`Original uploaded plan: ${asset?.original_filename}`} draggable={false}
        onLoad={event => {setNatural({width:event.currentTarget.naturalWidth,height:event.currentTarget.naturalHeight});setLoading(false);imageRetry.current=false;}}
        onError={() => {
          if (!imageRetry.current) {imageRetry.current=true;setRetry(current=>current+1);}
          else {setLoading(false);setError('The image could not be loaded. Retry opening the plan.');}
        }}
        className="absolute max-w-none" style={{width:natural.width,height:natural.height,left:'50%',top:'50%',
          transform:`translate(-50%, -50%) translate(${visiblePan.x}px, ${visiblePan.y}px) scale(${scale})`,transformOrigin:'center'}} />}
      {url && !loading && !error && fixtureReview && fixtureReview.source_sha256===asset?.source_sha256 && <svg aria-label="Confirmed scan fixture locations" viewBox="0 0 1000 1000" preserveAspectRatio="none" className="absolute max-w-none pointer-events-none" style={{width:natural.width,height:natural.height,left:'50%',top:'50%',transform:`translate(-50%, -50%) translate(${visiblePan.x}px, ${visiblePan.y}px) scale(${scale})`,transformOrigin:'center'}}>
        {fixtureReview.accepted.map((fixture,i)=>{const [y,x,y2,x2]=fixture.box_2d;return <g key={fixture.id}><rect x={x} y={y} width={x2-x} height={y2-y} fill="transparent" stroke={FIXTURE_COLORS[fixture.fixture_class]} strokeWidth="2" vectorEffect="non-scaling-stroke"/><text x={x} y={Math.max(14,y-5)} fontSize="14" fill={FIXTURE_COLORS[fixture.fixture_class]} stroke="white" strokeWidth="2" paintOrder="stroke">{i+1} {fixture.fixture_class}</text></g>;})}
      </svg>}
      {url&&!loading&&!error&&electricalReview&&electricalReview.source_sha256===asset?.source_sha256&&<svg aria-label="Reviewed electrical device locations" viewBox="0 0 1000 1000" preserveAspectRatio="none" className="absolute max-w-none pointer-events-none" style={{width:natural.width,height:natural.height,left:'50%',top:'50%',transform:`translate(-50%, -50%) translate(${visiblePan.x}px, ${visiblePan.y}px) scale(${scale})`,transformOrigin:'center'}}>
        {electricalReview.choices.map((c,i)=>{const [y,x,y2,x2]=c.observation.box_2d;return <g key={c.observation.id}><title>{i+1}. {deviceNames[c.observation.device_class]} · {c.disposition==='exclude'?`Excluded: ${c.exclusion_reason}`:c.selected_sku}</title><rect x={x} y={y} width={x2-x} height={y2-y} fill="transparent" stroke={c.disposition==='exclude'?'#475569':'#1d4ed8'} strokeDasharray={c.disposition==='exclude'?'4 3':undefined} strokeWidth="2" vectorEffect="non-scaling-stroke"/><text x={x} y={Math.max(14,y-4)} fontSize="14" fill="#1d4ed8" stroke="white" strokeWidth="2" paintOrder="stroke">{i+1}</text></g>;})}
      </svg>}
      {(unavailable || loading || error) && <div className="absolute inset-0 flex flex-col justify-center items-center gap-3 p-6 text-center bg-card">
        {unavailable ? <><ImageIcon size={24} className="text-muted-foreground"/><p className="text-sm text-muted-foreground max-w-xs">The original image is unavailable for this older scan. Re-upload the plan to save a viewable original.</p></>
          : error ? <><p role="alert" className="text-sm text-muted-foreground max-w-xs">{error}</p><button type="button" className={`${buttonClass} gap-2 px-4`} onClick={() => {imageRetry.current=false;setRetry(current=>current+1);}}><RefreshCw size={15}/>Retry opening</button></>
          : <><Loader2 size={22} className="animate-spin"/><p role="status" className="text-sm text-muted-foreground">Opening original plan…</p></>}
      </div>}
    </div>
    <div className="p-4 border-t border-border text-sm text-muted-foreground space-y-1">
      {fixtureReview && <p>Boxes show fixtures confirmed at scan time. Later quantity corrections are recorded separately.</p>}
      {electricalReview&&<p>Boxes show reviewed electrical assemblies. Dashed boxes were explicitly excluded from this partial estimate.</p>}
      <div role="group" aria-label="Pan plan" className="flex items-center gap-2 mb-3">
        <span className="mr-1">Pan</span>
        {([{label:'Pan left',x:80,y:0,Icon:ArrowLeft},{label:'Pan up',x:0,y:80,Icon:ArrowUp},{label:'Pan down',x:0,y:-80,Icon:ArrowDown},{label:'Pan right',x:-80,y:0,Icon:ArrowRight}]).map(({label,x,y,Icon}) =>
          <button key={label} type="button" className={buttonClass} aria-label={label} disabled={unavailable || loading || !!error || zoom <= 1} onClick={() => movePan(x,y)}><Icon size={16}/></button>)}
      </div>
      <p>Drag to pan after zooming. Fit restores the full sheet.</p>
      {!unavailable && <p className="break-words">{scanRevisionId ? `Image for saved scan ${scanRevisionId.slice(0,8)}` : 'Original retained for this scan attempt'} · {asset.pixel_width} × {asset.pixel_height} px</p>}
    </div>
  </section>;
}
