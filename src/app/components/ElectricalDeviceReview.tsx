import { useEffect, useRef, useState } from 'react';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { deviceNames, electricalChoiceError, emptyProposalHint, initialElectricalChoice, productOptions,
  type ElectricalChoice, type ElectricalObservation, type ElectricalProposal } from '../../lib/electrical-proposals';
import { fixtureReviewError, moveFixtureBox, placeFixtureBox, resizeFixtureBox, type FixtureBox } from '../../lib/plumbing-proposals';
import { ElectricalReviewGroups } from './ElectricalReviewGroups';

const button='min-h-11 px-4 rounded-lg border border-border hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foreground disabled:opacity-50';
const field='mt-1 w-full min-h-11 border border-border rounded-lg bg-background px-3 text-base';
const productLabels:Record<string,string>={OT01:'1-gang outlet · OT01',OT02:'2-gang outlet · OT02',OT03:'3-gang outlet · OT03',
  SW01:'1-gang, one-way · SW01',SW02:'2-gang, one-way · SW02',SW03:'3-gang, one-way · SW03',
  CLR01:'Ceiling receptacle, 3 1/2 · CLR01',CLR02:'Ceiling receptacle, 4 1/2 · CLR02',CLR03:'Ceiling receptacle, 2 1/4 · CLR03',ACO01:'Generic 1-gang AC outlet · ACO01'};

export function ElectricalDeviceReview({file,proposal,onConfirm,onUploadClearer}:{file:File;proposal:ElectricalProposal;onConfirm:(choices:ElectricalChoice[])=>void;onUploadClearer:()=>void}) {
  const [choices,setChoices]=useState(()=>proposal.proposed.map(initialElectricalChoice));
  const [selected,setSelected]=useState(proposal.proposed[0]?.id??'');
  const [group,setGroup]=useState<ElectricalObservation['device_class']>(proposal.proposed[0]?.device_class??'unknown');
  const [groupIds,setGroupIds]=useState(()=>proposal.proposed.filter(o=>o.device_class===proposal.proposed[0]?.device_class && o.device_class!=='unknown').map(o=>o.id));
  const [editing,setEditing]=useState(false);
  const [undoChoices,setUndoChoices]=useState<ElectricalChoice[]|null>(null);
  const [confirmed,setConfirmed]=useState(false);
  const [adding,setAdding]=useState(false);
  const [zoom,setZoom]=useState(1);
  const [url,setUrl]=useState('');
  const [imageReady,setImageReady]=useState(false);
  const [imageError,setImageError]=useState(false);
  const gesture=useRef<{id:string;box:FixtureBox;start:[number,number]}|null>(null);
  useEffect(()=>{const next=URL.createObjectURL(file);setUrl(next);return()=>URL.revokeObjectURL(next);},[file]);
  const chosen=choices.find(c=>c.observation.id===selected);
  const included=choices.filter(c=>c.disposition==='include');
  const unresolved=choices.filter(c=>!!electricalChoiceError(c));
  const purchaseCounts=new Map<string,number>();
  const exclusions=new Map<string,number>();
  for(const c of choices){
    if(c.disposition==='exclude'){const reason=`Device: ${c.exclusion_reason||'reason needed'}`;exclusions.set(reason,(exclusions.get(reason)??0)+1);continue;}
    for(const sku of [c.selected_sku,c.box_item_id])if(sku)purchaseCounts.set(sku,(purchaseCounts.get(sku)??0)+1);
    if(!c.box_item_id){const reason=`Box: ${c.box_exclusion_reason||'decision needed'}`;exclusions.set(reason,(exclusions.get(reason)??0)+1);}
  }
  const geometryError=fixtureReviewError(included.map(c=>({id:c.observation.id,fixture_class:'WC',box_2d:c.observation.box_2d,uncertainty:null})));
  function update(next:ElectricalChoice[]){setChoices(next);setConfirmed(false);setUndoChoices(null);}
  function applyGroup(next:ElectricalChoice[]){update(next);setUndoChoices(choices);}
  function patch(change:Partial<ElectricalChoice>){update(choices.map(c=>c.observation.id===selected?{...c,...change}:c));if(change.observation){setGroup(change.observation.device_class);setGroupIds([selected]);}}
  function selectDevice(id:string){setSelected(id);setEditing(true);const c=choices.find(c=>c.observation.id===id);if(c){setGroup(c.observation.device_class);setGroupIds([id]);}}
  function selectGroup(family:ElectricalObservation['device_class']){setGroup(family);setGroupIds(choices.filter(c=>c.observation.device_class===family&&c.disposition==='include'&&family!=='unknown').map(c=>c.observation.id));setEditing(false);}
  function patchObservation(change:Partial<ElectricalObservation>){if(chosen)patch({observation:{...chosen.observation,...change},...('gang_count' in change||'switching_function' in change?{box_compatibility_confirmed:false}:{})});}
  function changeBox(id:string,box:FixtureBox){update(choices.map(c=>c.observation.id===id?{...c,observation:{...c.observation,box_2d:box}}:c));}
  function point(event:React.PointerEvent<SVGSVGElement>):[number,number]{const r=event.currentTarget.getBoundingClientRect();return [Math.max(0,Math.min(1000,(event.clientY-r.top)/r.height*1000)),Math.max(0,Math.min(1000,(event.clientX-r.left)/r.width*1000))];}
  function add(box:FixtureBox){if(choices.length>=500)return;const id=`added-${crypto.randomUUID()}`;
    update([...choices,initialElectricalChoice({id,assembly_id:id,box_2d:box,device_class:'unknown',raw_mark:null,adjacent_text:null,socket_configuration:null,gang_count:null,switching_function:null,uncertainty:null})]);setSelected(id);setGroup('unknown');setGroupIds([]);setEditing(true);setAdding(false);}
  return <section className="max-w-7xl mx-auto p-4 sm:p-8 text-foreground">
    <h1 className="text-2xl font-medium">Review electrical devices</h1>
    {emptyProposalHint(proposal)&&<div className="mt-3 max-w-2xl"><p role="alert" className="text-base">{emptyProposalHint(proposal)}</p><button type="button" className={`${button} mt-3`} onClick={onUploadClearer}>Upload a clearer plan</button></div>}
    <p className="mt-2 text-sm" role="status">Check the drawing, then choose products and boxes for selected devices in each group. Edit exceptions individually.</p>
    <p className="text-base mt-2 max-w-2xl">Includes reviewed devices, compatible boxes, and wire and conduit allowances for supported lights and convenience outlets.</p>
    <p className="text-sm text-muted-foreground mt-2 max-w-2xl">Wire and conduit quantities are estimating allowances, not measured routes. Switch and AC wiring, breakers, panels and circuit design are excluded.</p>
    <p className="text-sm text-muted-foreground my-4">Review the entire drawing. Resolve unclear device types or explicitly exclude them with a reason.</p>
    <p role="status" className="text-sm my-4">{included.length} included · {choices.length-included.length} excluded · {unresolved.length} need a decision</p>
    <div className="grid lg:grid-cols-[minmax(0,1fr)_380px] gap-6 items-start">
      <div className="border border-border rounded-xl overflow-hidden min-w-0 lg:sticky lg:top-4">
        <div className="flex flex-wrap gap-2 p-3 border-b border-border">
          <button className={button} aria-label="Zoom out" disabled={zoom<=1} onClick={()=>setZoom(Math.max(1,zoom/1.5))}><Minus size={16}/></button>
          <output className="self-center tabular-nums text-sm">{Math.round(zoom*100)}%</output>
          <button className={button} aria-label="Zoom in" disabled={zoom>=6} onClick={()=>setZoom(Math.min(6,zoom*1.5))}><Plus size={16}/></button>
          <button className={button} disabled={choices.length>=500||!imageReady} aria-pressed={adding} onClick={()=>setAdding(!adding)}>{adding?'Cancel adding':'Add device on plan'}</button>
        </div>
        <div className="overflow-auto max-h-[70vh] bg-background p-2" tabIndex={0} aria-label="Plan image; scroll to pan">
          <div className="relative" style={{width:`${zoom*100}%`}}>
            <img src={url||undefined} alt="Original electrical plan" className="block w-full" onLoad={()=>{setImageReady(true);setImageError(false);}} onError={()=>{setImageReady(false);setImageError(true);}}/>
            <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Electrical device boxes" tabIndex={adding?0:-1} style={{touchAction:'none',cursor:adding?'crosshair':'default'}}
              onKeyDown={e=>{if(adding&&e.target===e.currentTarget&&(e.key==='Enter'||e.key===' ')){e.preventDefault();add(placeFixtureBox(500,500));}}}
              onPointerDown={e=>{if(e.button!==0)return;const start=point(e);if(adding){add(placeFixtureBox(...start));return;}const id=(e.target as Element).closest('[data-device]')?.getAttribute('data-device');const c=choices.find(c=>c.observation.id===id);if(c){selectDevice(c.observation.id);gesture.current={id:c.observation.id,box:c.observation.box_2d,start};e.currentTarget.setPointerCapture(e.pointerId);}}}
              onPointerMove={e=>{const g=gesture.current;if(g){const [y,x]=point(e);changeBox(g.id,moveFixtureBox(g.box,y-g.start[0],x-g.start[1]));}}}
              onPointerUp={()=>{gesture.current=null;}} onLostPointerCapture={()=>{gesture.current=null;}}
              onPointerCancel={()=>{const g=gesture.current;if(g)changeBox(g.id,g.box);gesture.current=null;}}>
              {choices.map((c,i)=>{const o=c.observation;const [y,x,y2,x2]=o.box_2d;return <g key={o.id} data-device={o.id} role="button" tabIndex={0} aria-label={`Select device ${i+1}: ${deviceNames[o.device_class]}`} aria-pressed={groupIds.includes(o.id)&&c.disposition==='include'}
                onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectDevice(o.id);}const moves:Record<string,[number,number]>={ArrowUp:[-2,0],ArrowDown:[2,0],ArrowLeft:[0,-2],ArrowRight:[0,2]};const d=moves[e.key];if(d){e.preventDefault();selectDevice(o.id);changeBox(o.id,e.shiftKey?resizeFixtureBox(o.box_2d,3,y2+d[0],x2+d[1]):moveFixtureBox(o.box_2d,...d));}}}>
                <rect x={x} y={y} width={x2-x} height={y2-y} fill={groupIds.includes(o.id)&&c.disposition==='include'?'rgba(37,99,235,.2)':'transparent'} stroke={c.disposition==='exclude'?'#475569':'#1d4ed8'} strokeWidth={groupIds.includes(o.id)?3:1} strokeDasharray={c.disposition==='exclude'?'4 3':undefined} vectorEffect="non-scaling-stroke"/>
                <text x={x} y={Math.max(14,y-4)} fontSize="14" fill="#1d4ed8" stroke="white" strokeWidth="2" paintOrder="stroke">{i+1}</text>
              </g>;})}
            </svg>
          </div>
        </div>
        <p className="text-sm text-muted-foreground p-4 border-t border-border">{adding?'Click a device to place its box. Keyboard: Enter places a box at the centre.':'Select and drag boxes to move them. Focus a box: arrows move it; Shift + arrows resize it.'}</p>
      </div>
      <div className="space-y-4 min-w-0">
        <ElectricalReviewGroups key={group} choices={choices} family={group} selectedIds={groupIds} productLabels={productLabels} onGroup={selectGroup} onSelection={setGroupIds} onEdit={selectDevice} onChange={applyGroup}/>
        <button type="button" className={button} disabled={!undoChoices} onClick={()=>{if(undoChoices)update(undoChoices);}}>Undo shared decision</button>
        {chosen&&editing&&<div className="space-y-4 border-t border-border pt-5">
          <div className="flex items-center justify-between gap-2"><h2 className="font-medium">Edit device {choices.findIndex(c=>c.observation.id===selected)+1}</h2><button type="button" className={button} onClick={()=>setEditing(false)}>Close details</button></div>
          <label className="block text-sm">Decision<select className={field} value={chosen.disposition} onChange={e=>patch({disposition:e.target.value as 'include'|'exclude',selected_sku:null,exclusion_reason:null,box_item_id:null,box_compatibility_confirmed:false,box_exclusion_reason:null})}><option value="include">Include in partial estimate</option><option value="exclude">Exclude with a reason</option></select></label>
          {chosen.disposition==='exclude'?<label className="block text-sm">Reason for excluding device<textarea className={`${field} py-2`} maxLength={1000} value={chosen.exclusion_reason??''} onChange={e=>patch({exclusion_reason:e.target.value})}/></label>:<>
            <label className="block text-sm">Device type<select className={field} value={chosen.observation.device_class} onChange={e=>{patch({selected_sku:null,box_item_id:null,box_compatibility_confirmed:false,box_exclusion_reason:null,observation:{...chosen.observation,device_class:e.target.value as ElectricalObservation['device_class'],gang_count:null,switching_function:null,socket_configuration:null}});}}>{Object.entries(deviceNames).map(([v,n])=><option value={v} key={v}>{n}</option>)}</select></label>
            <label className="block text-sm">Printed mark (optional)<input className={field} maxLength={120} value={chosen.observation.raw_mark??''} onChange={e=>patchObservation({raw_mark:e.target.value||null})}/></label>
            {chosen.observation.adjacent_text&&<p className="text-sm text-muted-foreground break-words">Nearby text: {chosen.observation.adjacent_text}</p>}
            {chosen.observation.uncertainty&&<p className="text-sm text-muted-foreground">Check this device carefully against the drawing before choosing a product.</p>}
            {chosen.observation.device_class==='switch'&&<>
              <label className="block text-sm">Switching function<select className={field} value={chosen.observation.switching_function??''} onChange={e=>patchObservation({switching_function:e.target.value as ElectricalObservation['switching_function']||null})}><option value="">Not confirmed</option><option value="one_way">One-way</option><option value="three_way">Three-way (unsupported)</option><option value="four_way">Four-way (unsupported)</option></select></label>
              <label className="block text-sm">Confirmed gang count<select className={field} value={chosen.observation.gang_count??''} onChange={e=>patchObservation({gang_count:e.target.value?Number(e.target.value):null})}><option value="">Not confirmed</option>{[1,2,3].map(n=><option key={n} value={n}>{n}</option>)}</select></label>
            </>}
            <label className="block text-sm">Catalog product<select className={field} value={chosen.selected_sku??''} onChange={e=>patch({selected_sku:e.target.value as ElectricalChoice['selected_sku']||null,box_compatibility_confirmed:false})}><option value="">Choose product</option>{productOptions[chosen.observation.device_class].map(v=><option key={v} value={v}>{productLabels[v]}</option>)}</select></label>
            <p className="text-sm text-muted-foreground">Product choice is your confirmation. Socket strokes do not determine gang count. AC pricing covers only the generic device.</p>
            <label className="block text-sm">Box for this assembly<select className={field} value={chosen.box_item_id??''} onChange={e=>patch({box_item_id:e.target.value as ElectricalChoice['box_item_id']||null,box_compatibility_confirmed:false,box_exclusion_reason:null})}><option value="">Exclude box from scope</option><option value="UTB01">Utility box · UTB01</option><option value="JCB01">Junction box with cover · JCB01</option></select></label>
            {chosen.box_item_id?<label className="flex gap-3 text-sm"><input type="checkbox" className="size-5 shrink-0" checked={chosen.box_compatibility_confirmed} onChange={e=>patch({box_compatibility_confirmed:e.target.checked})}/>I verified that this catalog box fits the assembly.</label>:<label className="block text-sm">Reason for excluding box<textarea className={`${field} py-2`} maxLength={1000} value={chosen.box_exclusion_reason??''} onChange={e=>patch({box_exclusion_reason:e.target.value})}/></label>}
          </>}
          {electricalChoiceError(chosen)&&<p role="status" className="text-sm text-muted-foreground">{electricalChoiceError(chosen)}</p>}
        </div>}
        <button className={`${button} flex gap-2 items-center`} onClick={()=>{update(proposal.proposed.map(initialElectricalChoice));setSelected(proposal.proposed[0]?.id??'');setGroup(proposal.proposed[0]?.device_class??'unknown');setGroupIds([]);setEditing(false);}}><RotateCcw size={16}/>Restore proposals</button>
      </div>
    </div>
    {(geometryError||imageError)&&<p role="alert" className="text-sm text-destructive mt-5">{imageError?'The original image could not be displayed. Upload it again.':geometryError}</p>}
    <div className="mt-6 border-t border-border pt-5 space-y-3"><h2 className="font-medium">Review summary</h2>
      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm">{(Object.keys(deviceNames) as ElectricalObservation['device_class'][]).filter(f=>choices.some(c=>c.observation.device_class===f)).map(f=><li key={f}>{deviceNames[f]}: {included.filter(c=>c.observation.device_class===f).length} included, {choices.filter(c=>c.observation.device_class===f&&c.disposition==='exclude').length} excluded</li>)}</ul>
      {!!purchaseCounts.size&&<ul className="text-sm space-y-1" aria-label="Selected products and boxes">{[...purchaseCounts].map(([sku,count])=><li key={sku}>{count} × {productLabels[sku]??(sku==='UTB01'?'Utility box · UTB01':'Junction box with cover · JCB01')}</li>)}</ul>}
      {!!exclusions.size&&<div className="text-sm"><p className="font-medium">Exclusions and outstanding box decisions</p><ul className="mt-1 space-y-1">{[...exclusions].map(([reason,count])=><li className="break-words" key={reason}>{count} × {reason}</li>)}</ul></div>}
    </div>
    <label className="flex items-start gap-3 text-sm mt-6"><input type="checkbox" className="size-5 shrink-0" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>I checked the entire drawing, including missed devices, and accept the stated partial scope and exclusions.</span></label>
    <button className={`${button} mt-5 bg-foreground text-background hover:bg-foreground hover:opacity-90`} disabled={!confirmed||!!geometryError||unresolved.length>0||included.length===0||!imageReady} onClick={()=>onConfirm(choices)}>Confirm partial estimate</button>
  </section>;
}
