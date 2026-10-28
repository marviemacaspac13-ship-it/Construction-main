import { useEffect, useRef, useState } from 'react';
import { Plus, Minus, RotateCcw, Trash2, Pencil } from 'lucide-react';
import { FIXTURE_COLORS, FIXTURE_NAMES, fixtureReviewError, fixtureSummary, moveFixtureBox, placeFixtureBox, resizeFixtureBox, reviewClasses, type FixtureBox, type FixtureClass, type FixtureProposal, type FixtureProposalResult } from '../../lib/plumbing-proposals';

const colorNames: Record<FixtureClass, string> = {WC:'Red', LAV:'Blue', U:'Purple', FD:'Green', CO:'Orange'};
const name = (cls: FixtureClass) => FIXTURE_NAMES[cls][0].replace(/^./, c => c.toUpperCase());
const button = 'min-h-11 px-4 rounded-lg border border-border hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground disabled:opacity-50';

/** Extends scan review using normalized coordinates; zoom never changes stored boxes. */
export function PlumbingFixtureReview({file, proposal, busy, onConfirm}: {
  file: File; proposal: FixtureProposalResult; busy: boolean;
  onConfirm: (fixtures: FixtureProposal[])=>void;
}) {
  const [fixtures,setFixtures]=useState<FixtureProposal[]>(proposal.fixtures);
  const [selected,setSelected]=useState<string|null>(proposal.fixtures[0]?.id ?? null);
  const [confirmed,setConfirmed]=useState(false);
  const [draw,setDraw]=useState(false);
  const classes=reviewClasses(proposal.provider);
  const fromTags=proposal.provider==='tags';
  const [drawClass,setDrawClass]=useState<FixtureClass>('WC');
  const [zoom,setZoom]=useState(1);
  const [url,setUrl]=useState('');
  const [imageError,setImageError]=useState(false);
  const [dragBox,setDragBox]=useState<[number,number,number,number]|null>(null);
  const gesture=useRef<{kind:'add'|'move'|'resize'; start:[number,number]; box?:FixtureBox; id?:string; corner?:number} | null>(null);
  useEffect(()=>{const next=URL.createObjectURL(file);setUrl(next);return ()=>URL.revokeObjectURL(next);},[file]);
  const chosen=fixtures.find(f=>f.id===selected);
  const error=fixtureReviewError(fixtures,classes);
  const classOptions=classes.map(cls=><option value={cls} key={cls}>{name(cls)}</option>);
  const update=(next:FixtureProposal[])=>{setFixtures(next);setConfirmed(false);};
  const add=(box:FixtureProposal['box_2d'])=>{
    const fixture:FixtureProposal={id:`added-${crypto.randomUUID()}`,fixture_class:drawClass,box_2d:box,uncertainty:null};
    update([...fixtures,fixture]);setSelected(fixture.id);setDraw(false);
  };
  const point=(event:React.PointerEvent<SVGSVGElement>):[number,number]=>{
    const rect=event.currentTarget.getBoundingClientRect();
    return [Math.max(0,Math.min(1000,(event.clientY-rect.top)/rect.height*1000)),Math.max(0,Math.min(1000,(event.clientX-rect.left)/rect.width*1000))];
  };
  const replaceBox=(id:string,box:FixtureBox)=>update(fixtures.map(f=>f.id===id?{...f,box_2d:box}:f));
  const removeSelected=()=>{const next=fixtures.filter(f=>f.id!==selected);update(next);setSelected(next[0]?.id??null);};
  const startGesture=(event:React.PointerEvent<SVGSVGElement>)=>{
    if(busy || event.button!==0)return;
    const start=point(event);
    if(draw)gesture.current={kind:'add',start};
    else {
      const target=(event.target as Element).closest('[data-fixture]');
      const fixture=fixtures.find(f=>f.id===target?.getAttribute('data-fixture'));
      if(!fixture){setSelected(null);return;}
      setSelected(fixture.id);
      const corner=(event.target as Element).getAttribute('data-corner');
      gesture.current={kind:corner===null?'move':'resize',start,box:fixture.box_2d,id:fixture.id,corner:corner===null?undefined:Number(corner)};
    }
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const continueGesture=(event:React.PointerEvent<SVGSVGElement>)=>{
    const active=gesture.current;if(!active)return;
    const [y,x]=point(event);const [oy,ox]=active.start;
    if(active.kind==='add')setDragBox([Math.min(y,oy),Math.min(x,ox),Math.max(y,oy),Math.max(x,ox)]);
    else if(active.id && active.box && (Math.abs(y-oy)>.5 || Math.abs(x-ox)>.5))replaceBox(active.id,active.kind==='move'?moveFixtureBox(active.box,y-oy,x-ox):resizeFixtureBox(active.box,active.corner!,y,x));
  };
  const finishGesture=(event:React.PointerEvent<SVGSVGElement>)=>{
    const active=gesture.current;if(!active)return;
    continueGesture(event);gesture.current=null;setDragBox(null);
    if(active.kind!=='add')return;
    const [y,x]=point(event);const [oy,ox]=active.start;
    if(Math.abs(y-oy)>2 && Math.abs(x-ox)>2)add([Math.min(y,oy),Math.min(x,ox),Math.max(y,oy),Math.max(x,ox)]);
    else {
      const example=fixtures.find(f=>f.fixture_class===drawClass)?.box_2d;
      add(placeFixtureBox(y,x,example?Math.max(10,Math.min(100,example[2]-example[0])):40,example?Math.max(10,Math.min(100,example[3]-example[1])):30));
    }
  };
  return <section className="max-w-7xl mx-auto p-4 sm:p-8 text-foreground" aria-busy={busy}>
    <h1 className="text-2xl font-medium">Review plumbing fixtures</h1>
    <p className="text-sm text-muted-foreground mt-2 max-w-2xl">{fromTags?'Boxes mark the fixture labels printed on the drawing, such as WC and FD. Unlabelled fixtures are not marked. ':''}Check every box against the drawing. Remove mistakes, change fixture types, and add missing fixtures before confirming the counts.</p>
    <div className="flex flex-wrap items-center gap-4 my-5 text-sm" role="status">
      {classes.map(cls=><span key={cls}>{FIXTURE_NAMES[cls][1].replace(/^./,c=>c.toUpperCase())}: <strong>{fixtures.filter(f=>f.fixture_class===cls).length}</strong></span>)}
      <span className="text-muted-foreground">Check the whole plan for missing fixtures before confirming.</span>
    </div>
    {proposal.limitations.length>0 && <p className="text-sm text-muted-foreground mb-4">Some fixture locations or types need checking. Review the entire drawing before confirming.</p>}
    <div className="grid lg:grid-cols-[minmax(0,1fr)_320px] gap-6 items-start">
      <div className="border border-border rounded-xl overflow-hidden bg-card min-w-0">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <button className={button} aria-label="Zoom out" disabled={busy || zoom<=1} onClick={()=>setZoom(Math.max(1,zoom/1.5))}><Minus size={16}/></button>
          <output className="text-sm tabular-nums">{Math.round(zoom*100)}%</output>
          <button className={button} aria-label="Zoom in" disabled={busy || zoom>=6} onClick={()=>setZoom(Math.min(6,zoom*1.5))}><Plus size={16}/></button>
          <button className={button} disabled={busy} onClick={()=>setZoom(1)}>Fit</button>
          <button className={`${button} flex gap-2 items-center`} disabled={busy || fixtures.length>=500} aria-pressed={draw} onClick={()=>setDraw(!draw)}><Pencil size={16}/>{draw?'Cancel adding':'Add fixture'}</button>
        </div>
        <div className="overflow-auto max-h-[65vh] bg-background p-2" tabIndex={0} aria-label="Plan image; scroll to pan when zoomed">
          <div className="relative" style={{width:`${zoom*100}%`}}>
            {url && <img src={url} alt="Original plumbing plan with proposed fixture locations" className="block w-full" onLoad={()=>setImageError(false)} onError={()=>setImageError(true)}/>}
            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Fixture boxes" tabIndex={draw?0:-1} style={{touchAction:'none',cursor:draw?'crosshair':'default'}}
              onKeyDown={event=>{if(draw && !busy && event.target===event.currentTarget && (event.key==='Enter' || event.key===' ')){event.preventDefault();add(placeFixtureBox(500,500));}}}
              onPointerDown={startGesture} onPointerMove={continueGesture} onPointerUp={finishGesture}
              onPointerCancel={()=>{const active=gesture.current;if(active?.id && active.box)replaceBox(active.id,active.box);gesture.current=null;setDragBox(null);}}
              onLostPointerCapture={()=>{gesture.current=null;setDragBox(null);}}>
              {fixtures.map((fixture,i)=>{const [y,x,y2,x2]=fixture.box_2d;return <g key={fixture.id} data-fixture={fixture.id} role="button" tabIndex={busy?-1:0} aria-label={`Select fixture ${i+1}: ${name(fixture.fixture_class)}`} aria-pressed={selected===fixture.id}
                onKeyDown={event=>{
                  if(busy)return;
                  if(event.key==='Enter' || event.key===' '){event.preventDefault();setSelected(fixture.id);}
                  const moves:Record<string,[number,number]>={ArrowUp:[-2,0],ArrowDown:[2,0],ArrowLeft:[0,-2],ArrowRight:[0,2]};
                  const shift=moves[event.key];if(shift){event.preventDefault();setSelected(fixture.id);replaceBox(fixture.id,event.shiftKey?resizeFixtureBox(fixture.box_2d,3,y2+shift[0],x2+shift[1]):moveFixtureBox(fixture.box_2d,...shift));}
                  if(event.key==='Delete' || event.key==='Backspace'){event.preventDefault();update(fixtures.filter(f=>f.id!==fixture.id));setSelected(null);}
                }}>
                <rect x={x} y={y} width={Math.max(0,x2-x)} height={Math.max(0,y2-y)} fill={selected===fixture.id?'rgba(255,255,255,.15)':'transparent'} stroke={FIXTURE_COLORS[fixture.fixture_class]} strokeWidth={selected===fixture.id?3:2} vectorEffect="non-scaling-stroke"/>
                <text x={x} y={Math.max(14,y-5)} fill={FIXTURE_COLORS[fixture.fixture_class]} fontSize="14" stroke="white" strokeWidth="2" paintOrder="stroke">{i+1} {fixture.fixture_class}</text>
                {selected===fixture.id && !draw && [[y,x],[y,x2],[y2,x],[y2,x2]].map(([hy,hx],corner)=><rect key={corner} data-corner={corner} x={hx-5} y={hy-5} width="10" height="10" fill="white" stroke={FIXTURE_COLORS[fixture.fixture_class]} strokeWidth="1" vectorEffect="non-scaling-stroke" style={{cursor:corner===0 || corner===3?'nwse-resize':'nesw-resize'}}/>)}
              </g>;})}
              {dragBox && <rect x={dragBox[1]} y={dragBox[0]} width={dragBox[3]-dragBox[1]} height={dragBox[2]-dragBox[0]} fill="transparent" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke"/>}
            </svg>
          </div>
        </div>
        <p className="text-sm text-muted-foreground p-4 border-t border-border">{draw?'Click a fixture to place a box, or drag around its body.':`Click a box to select it. Drag it to move; drag a corner to resize. ${classes.map(cls=>`${colorNames[cls]}: ${FIXTURE_NAMES[cls][1]}`).join('. ')}.`}</p>
      </div>
      <div className="space-y-4 min-w-0">
        <label className="block text-sm">Type for new fixtures<select className="mt-1 w-full min-h-11 border border-border rounded-lg bg-background px-3" value={drawClass} disabled={busy} onChange={e=>setDrawClass(e.target.value as FixtureClass)}>{classOptions}</select></label>
        <label className="block text-sm">Fixture<select className="mt-1 w-full min-h-11 border border-border rounded-lg bg-background px-3" value={selected ?? ''} disabled={busy || !fixtures.length} onChange={e=>setSelected(e.target.value)}>{fixtures.length===0 && <option value="">No fixtures</option>}{fixtures.map((f,i)=><option value={f.id} key={f.id}>{i+1}. {name(f.fixture_class)}</option>)}</select></label>
        {chosen && <>
          <label className="block text-sm">Fixture type<select className="mt-1 w-full min-h-11 border border-border rounded-lg bg-background px-3" disabled={busy} value={chosen.fixture_class} onChange={e=>update(fixtures.map(f=>f.id===chosen.id?{...f,fixture_class:e.target.value as FixtureClass}:f))}>{classOptions}</select></label>
          {chosen.uncertainty && <p className="text-sm text-muted-foreground">Check this fixture carefully against the drawing before confirming its type.</p>}
          <button className={`${button} w-full flex items-center justify-center gap-2`} disabled={busy} onClick={removeSelected}><Trash2 size={16}/>Remove fixture</button>
          <p className="text-sm text-muted-foreground">Keyboard: focus a box and use arrow keys to move it. Shift + arrows resize it. Delete removes it.</p>
        </>}
        <button className={`${button} w-full flex items-center justify-center gap-2`} disabled={busy} onClick={()=>{update(proposal.fixtures);setSelected(proposal.fixtures[0]?.id??null);}}><RotateCcw size={16}/>Restore proposals</button>
      </div>
    </div>
    {(error || imageError) && <p role="alert" className="text-sm text-destructive mt-5">{imageError?'The image could not be displayed. Upload the plan again.':error}</p>}
    <label className="flex items-start gap-3 mt-6 text-sm"><input type="checkbox" className="mt-1 size-5 shrink-0 accent-current" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/><span>I checked the entire drawing, corrected missing or incorrect fixtures, and confirm {fixtureSummary(fixtures,classes)}.</span></label>
    <div className="flex flex-wrap gap-3 mt-5">
      <button className={`${button} bg-foreground text-background hover:opacity-90 hover:bg-foreground`} disabled={busy || !confirmed || !!error || imageError} onClick={()=>onConfirm(fixtures)}>{busy?'Processing…':'Confirm counts and estimate'}</button>
    </div>
  </section>;
}
