import {useEffect,useRef,useState} from 'react';
import type {Project} from '../../lib/projects';
import type {SourceQuantityOverrides} from '../../lib/estimate-input';
import {editorRequest,type EditorPreview,type ManualInputs} from '../../lib/editor';
import {electricalLabels,plumbingLabels} from '../../lib/editor-input';
import {editorButton} from './EstimateEditor';

export function ManualEstimateEditor({project,onSaved,onDirty}:{project:Project;onSaved:()=>Promise<void>;onDirty:(v:boolean)=>void}) {
  const [open,setOpen]=useState(false),[confirmed,setConfirmed]=useState(false);
  const [values,setValues]=useState<Record<string,string>>({});
  const [errors,setErrors]=useState<Record<string,string>>({});
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [preview,setPreview]=useState<EditorPreview|null>(null);
  const pending=useRef<{inputs:ManualInputs;key:string}|null>(null);
  const lock=useRef(false);
  const errorRef=useRef<HTMLParagraphElement>(null);
  useEffect(()=>{if(error) errorRef.current?.focus();},[error,errors]);
  const floor=project.plan_type==='Floor Plan';
  const labels:Record<string,string>=floor?{width_m:'Building width (m)',length_m:'Building length (m)',exterior_wall_m:'Total exterior wall length (m) · 6-inch blocks',interior_wall_m:'Total interior wall length (m) · 4-inch blocks',doors:'Doors · standard 0.90 × 2.10 m',windows:'Windows · standard 1.20 × 1.20 m',wall_height_m:'Wall height (m)',slab_area_m2:'Slab area (m²)',column_count:'Column count'}:project.plan_type==='Electrical Plan'?electricalLabels:plumbingLabels;
  async function calculate() {
    if(lock.current)return;
    const invalid:Record<string,string>={}, numeric:Record<string,number>={};
    for(const key of Object.keys(labels)) {
      const raw=(values[key]??'').trim(),value=Number(raw);
      const integer=!floor||['doors','windows','column_count'].includes(key);
      const positive=['width_m','length_m','wall_height_m'].includes(key);
      const maximum=key==='wall_height_m'?10:10000;
      if(!raw||!Number.isFinite(value)||value<0||(integer&&!Number.isSafeInteger(value))||(positive&&value<=0)||(floor&&!integer&&value>maximum))invalid[key]=positive?`Enter a number greater than zero and at most ${maximum}.`:integer?'Enter a whole count of zero or more.':'Enter a number from 0 to 10000; zero confirms none.';
      else numeric[key]=value;
    }
    setErrors(invalid);
    if(Object.keys(invalid).length||!confirmed){setError('Complete all quantities and confirm your manual review.');return;}
    const quantities:SourceQuantityOverrides=floor?{wall_height_m:numeric.wall_height_m,slab_area_m2:numeric.slab_area_m2,column_count:numeric.column_count}:project.plan_type==='Electrical Plan'?{electrical_counts:numeric}:{plumbing_counts:numeric};
    const inputs:ManualInputs={quantities,confirmed};
    if(floor)Object.assign(inputs,Object.fromEntries(['width_m','length_m','exterior_wall_m','interior_wall_m','doors','windows'].map(k=>[k,numeric[k]])));
    lock.current=true;setBusy(true);setError('');
    try{const result=await editorRequest<EditorPreview>('manual/preview',{project_id:project.id,asset_id:project.plan_asset!.id,inputs});setPreview(result);pending.current={inputs,key:crypto.randomUUID()};}
    catch(e){setError(e instanceof Error?e.message:'Could not calculate. Your entries are retained.');}
    finally{lock.current=false;setBusy(false);}
  }
  async function save() {
    if(!pending.current||!preview||lock.current)return;
    lock.current=true;setBusy(true);setError('');
    try{await editorRequest('manual/revisions',{project_id:project.id,asset_id:project.plan_asset!.id,inputs:pending.current.inputs,prices:preview.effective_input.prices,
      precondition:{expected_active_revision_id:project.active_revision_id??null,idempotency_key:pending.current.key}});await onSaved();onDirty(false);}
    catch(e){setError(e instanceof Error?e.message:'Could not save. Your entries are retained.');}
    finally{lock.current=false;setBusy(false);}
  }
  if(!project.plan_asset?.storage_path)return null;
  if(!open)return <button className={editorButton} onClick={()=>setOpen(true)}>Enter quantities manually</button>;
  return <section className="border border-border rounded-lg bg-card p-5">
    <h2 className="text-xl font-semibold">Manual estimate</h2>
    <p className="text-sm text-muted-foreground my-3">The scan could not read this plan. Enter quantities you have checked; blank fields are unknown, not zero. This creates a separate manual version linked to the original image.</p>
    {floor&&<p className="text-sm text-muted-foreground mb-4">Member sizes and slab thickness use the project guide. Opening deductions use the standard sizes below and apply to exterior walls (interior walls if no exterior length is entered).</p>}
    {error&&<p ref={errorRef} tabIndex={-1} role="alert" className="text-sm text-red-400 mb-3">{error}</p>}
    {Object.entries(labels).map(([key,label])=><div key={key} className="mb-4">
      <label htmlFor={`manual-${key}`} className="block text-sm mb-1">{label}</label>
      <input id={`manual-${key}`} type="number" min={0} step="any" value={values[key]??''} disabled={busy} aria-invalid={!!errors[key]} aria-describedby={errors[key]?`manual-error-${key}`:undefined}
        onChange={e=>{setValues(v=>({...v,[key]:e.target.value}));setPreview(null);pending.current=null;onDirty(true);}}
        className="w-full min-h-11 border border-border rounded-lg bg-background px-3 text-base focus-visible:outline-2 focus-visible:outline-foreground"/>
      {errors[key]&&<p id={`manual-error-${key}`} className="text-sm text-red-400 mt-1">{errors[key]}</p>}
    </div>)}
    <label className="flex items-start gap-3 text-sm py-3"><input type="checkbox" checked={confirmed} disabled={busy} className="mt-1" onChange={e=>{setConfirmed(e.target.checked);setPreview(null);pending.current=null;}}/>I checked these quantities against the original plan and confirm any zeros.</label>
    <button className={editorButton} disabled={busy} onClick={calculate}>{busy?'Working…':'Recalculate manual estimate'}</button>
    {preview&&<div className="mt-4" aria-live="polite"><p className="text-base mb-3">Manual estimate: ₱{preview.estimate.grand_total.toLocaleString('en-PH',{minimumFractionDigits:2})} · {preview.estimate.line_items.length} material types</p>
      <ul className="text-sm mb-4 space-y-1">{preview.estimate.line_items.map(li=><li key={li.item_id}>{li.item_id} · {li.quantity} {li.unit} · ₱{li.line_total.toLocaleString()}</li>)}</ul>
      <button className={`${editorButton} bg-foreground text-background hover:bg-foreground`} disabled={busy} onClick={save}>Save manual estimate</button></div>}
  </section>;
}
